"""xframe command line: explain | verify | convert | frames."""
from __future__ import annotations
import argparse, json, sys
from .catalog import Catalog
from .tifxyz import Source


def _common(ap):
    ap.add_argument("--catalog", help="local metadata.json (gz or plain); default: fetch from the open-data bucket")
    ap.add_argument("--bucket-root", help="local directory laid out like the bucket (offline); default: anonymous HTTPS")
    ap.add_argument("--cache-dir", help="persist downloaded files here (default: stream, write nothing)")


def _ctx(a):
    src = Source(root=a.bucket_root, cache_dir=a.cache_dir)
    return Catalog.load(a.catalog, src), src


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xframe", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("frames", help="list a sample's volumes, voxel sizes and catalog transforms"); _common(p)
    p.add_argument("sample"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("explain", help="describe every mesh of a segment"); _common(p)
    p.add_argument("sample"); p.add_argument("segment"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("verify", help="reproduce published derived meshes from source + catalog and report residuals"); _common(p)
    p.add_argument("sample"); p.add_argument("segment"); p.add_argument("--json", action="store_true")
    p.add_argument("--block-rows", type=int, default=256); p.add_argument("--no-copies", action="store_true")
    p = sub.add_parser("convert", help="convert a points CSV (x,y,z) or a tifxyz between frames"); _common(p)
    p.add_argument("--sample", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--from", dest="from_vol", help="source volume id")
    g.add_argument("--from-normalized-of", help="segment id: input is in that segment's tifxyz_normalized frame (applies its downscale)")
    p.add_argument("--to", dest="to_vol", required=True, help="target volume id")
    p.add_argument("--prescale", type=float, help="uniform scale before the affine (default 1, or the segment downscale)")
    p.add_argument("input", help="points .csv, local tifxyz dir, or bucket key of a tifxyz dir")
    p.add_argument("output", help="output .csv or tifxyz directory")
    a = ap.parse_args(argv)
    cat, src = _ctx(a)

    if a.cmd == "frames":
        s = cat.samples[a.sample]
        vols = {v: dict(um=cat.voxel_um(a.sample, v), long_id=d.get("long_id")) for v, d in sorted(s["volumes"].items())}
        tr = sorted(f"{k[0]} -> {k[1]}" for k in cat._sample_transforms(a.sample))
        if a.json: print(json.dumps(dict(volumes=vols, transforms=tr), indent=1))
        else:
            for v, d in vols.items(): print(f"{v}  {d['um']} um  {d['long_id']}")
            for t in tr: print(f"  transform {t}")
        return 0

    if a.cmd == "explain":
        from .explain import explain_segment, format_explain
        d = explain_segment(cat, cat.segment(a.sample, a.segment), src)
        print(json.dumps(d, indent=1) if a.json else format_explain(d)); return 0

    if a.cmd == "verify":
        from .verify import verify_segment
        rows = verify_segment(cat, cat.segment(a.sample, a.segment), src, a.block_rows, not a.no_copies)
        if a.json: print(json.dumps(rows, indent=1))
        else:
            for r in rows:
                name = r["mesh"].rstrip("/").split("/")[-1]
                if r["class"] in ("ERROR", "NOT_COMPARABLE"):
                    print(f"{r['class']:<15} {name}  {r.get('error') or ('shape published %s vs predicted %s' % (r.get('published_shape'), r.get('predicted_shape')))}")
                else:
                    um = f"  max {r['max_um']:.4g} um" if r.get("max_um") is not None else ""
                    print(f"{r['class']:<15} {name}  median {r['median_vox']:.3g} vox  p99 {r['p99_vox']:.3g} vox  max {r['max_vox']:.3g} vox{um}  (n={r['n_compared']})")
        if not rows: print("no derived meshes to verify", file=sys.stderr); return 0
        if any(r["class"] == "ERROR" for r in rows): return 2
        return 0 if all(r["class"] == "CONSISTENT" for r in rows) else 1

    if a.cmd == "convert":
        from .convert import resolve, convert_csv, convert_tifxyz
        M, prov = resolve(cat, a.sample, a.from_vol, a.to_vol, a.from_normalized_of, a.prescale)
        if a.input.lower().endswith(".csv"):
            n = convert_csv(a.input, a.output, M, prov)
            print(f"converted {n} points {prov['from_volume']} -> {prov['to_volume']} ({prov['how']}, prescale {prov['prescale']:g}) -> {a.output}")
        else:
            info = convert_tifxyz(src, a.input, a.output, M, prov)
            print(f"wrote tifxyz {a.output}: shape {info['shape']}, regrid {info['regrid_factors']}, valid {info['n_valid']} ({prov['how']}, prescale {prov['prescale']:g})")
        print("note: catalog matrix correctness is not checked by xframe (see villa #1835 / PR #1994).", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
