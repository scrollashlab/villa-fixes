"""Measure the coordinate offset a user gets if they ignore `original_volume_downscale` when using a
segment's `tifxyz_normalized` mesh (meta.json does not carry the factor).
For every segment with downscale != 1, stream the normalized mesh (anonymous HTTPS, nothing cached) and, over
all valid points p, compute:
  (a) own-volume offset: |(s-1)·p| in original-volume voxels (and µm) -- using normalized coords directly
      against the original volume;
  (b) per derived mesh: |A·(s-1)·p| in target voxels (and µm), A = linear part of the catalog matrix
      original->target -- applying the catalog matrix without the prescale.
Both follow from the publishing rule verified 902/902 (derived = regrid(T·(s·normalized))).
Output: metadata-only JSON. Usage: python downscale_offsets.py CATALOG OUT_JSON [WORKERS]"""
import json, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
from xframe import __version__
from xframe.catalog import Catalog
from xframe.tifxyz import Source, read_tifxyz
from xframe.geom import valid_mask

CAT, OUT = sys.argv[1], sys.argv[2]
WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 4


def stats(d):
    return {"min": float(d.min()), "median": float(np.median(d)), "p99": float(np.quantile(d, 0.99)), "max": float(d.max())}


def work(args):
    sample, seg_id = args
    cat = Catalog.load(CAT); src = Source()
    seg = cat.segment(sample, seg_id); s = seg.downscale
    P, meta = read_tifxyz(src, seg.normalized.key)
    p = P[valid_mask(P)].astype(np.float64); del P
    ou = cat.voxel_um(sample, seg.original_volume)
    d0 = np.linalg.norm((s - 1.0) * p, axis=1)
    row = {"sample": sample, "segment": seg_id, "downscale": s, "original_volume": seg.original_volume,
           "original_um": ou, "n_valid_points": int(len(p)), "normalized_meta_keys": sorted(meta.keys()),
           "meta_has_downscale": any("downscale" in k for k in meta),
           "own_volume_offset_vox": stats(d0), "derived": []}
    if ou: row["own_volume_offset_um"] = {k: v * ou for k, v in row["own_volume_offset_vox"].items()}
    for m in seg.meshes:
        if m.kind != "derived": continue
        M, prov = cat.matrix(sample, seg.original_volume, m.target_volume)
        A = M[:, :3]
        d = np.linalg.norm(((s - 1.0) * p) @ A.T, axis=1)
        tu = cat.voxel_um(sample, m.target_volume)
        st = stats(d)
        row["derived"].append({"mesh": m.key, "target_volume": m.target_volume, "target_um": tu, "matrix": prov,
                               "offset_target_vox": st, "offset_um": {k: v * tu for k, v in st.items()} if tu else None})
    return row


def main():
    cat = Catalog.load(CAT)
    todo = [(g.sample, g.id) for g in cat.segments() if g.downscale != 1 and g.normalized is not None]
    print(f"downscale segments: {len(todo)}", flush=True)
    rows = []; t0 = time.time()
    with ProcessPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(work, t): t for t in todo}
        for i, fu in enumerate(as_completed(futs), 1):
            try:
                rows.append(fu.result())
            except Exception as e:
                rows.append({"sample": futs[fu][0], "segment": futs[fu][1], "error": repr(e)})
            print(f"[{i}/{len(todo)} {time.time()-t0:.0f}s] {futs[fu]}", flush=True)
    rows.sort(key=lambda r: (r["sample"], r["segment"]))
    per = {}
    for r in rows:
        if "error" in r: continue
        q = per.setdefault(r["sample"], {"downscale": r["downscale"], "segments": 0, "derived_meshes": 0,
                                         "meta_has_downscale_any": False, "own_median_vox": [], "own_max_vox": [],
                                         "derived_median_vox": [], "derived_median_um": [], "derived_max_um": []})
        q["segments"] += 1; q["meta_has_downscale_any"] |= r["meta_has_downscale"]
        q["own_median_vox"].append(r["own_volume_offset_vox"]["median"]); q["own_max_vox"].append(r["own_volume_offset_vox"]["max"])
        for d in r["derived"]:
            q["derived_meshes"] += 1
            q["derived_median_vox"].append(d["offset_target_vox"]["median"])
            if d["offset_um"]:
                q["derived_median_um"].append(d["offset_um"]["median"]); q["derived_max_um"].append(d["offset_um"]["max"])
    summ = {}
    for k, q in per.items():
        rng = lambda a: [min(a), max(a)] if a else None
        summ[k] = {"downscale": q["downscale"], "segments": q["segments"], "derived_meshes": q["derived_meshes"],
                   "meta_has_downscale_any": q["meta_has_downscale_any"],
                   "own_volume_median_offset_vox_range": rng(q["own_median_vox"]),
                   "own_volume_max_offset_vox_range": rng(q["own_max_vox"]),
                   "derived_median_offset_target_vox_range": rng(q["derived_median_vox"]),
                   "derived_median_offset_um_range": rng(q["derived_median_um"]),
                   "derived_max_offset_um_range": rng(q["derived_max_um"])}
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "xframe_version": __version__, "catalog": CAT,
           "n_segments": len(rows), "n_errors": sum("error" in r for r in rows), "per_sample": summ, "segments": rows}
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "segments"}, indent=1))


if __name__ == "__main__":
    main()
