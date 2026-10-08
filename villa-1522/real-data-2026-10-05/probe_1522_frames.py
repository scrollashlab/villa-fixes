#!/usr/bin/env python3
"""Real-data before/after probe for villa #1522.

Unmodified villa main has no vesuvius.tifxyz.meta_frames. A naive consumer that
treats matching meta.scale as “same physical frame” mis-scales open-data
multi-resolution siblings by up to ~40×.

The #1522 patch adds meta_frames: detect same-scale/different-µm groups,
annotate voxel_size_um from the dirname token, and frames_comparable() which
refuses to equate frames without matching voxel_size_um.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import shutil
import sys
import types
from pathlib import Path

import numpy as np

UM_RE = re.compile(r"(?P<um>\d+(?:\.\d+)?)um", re.I)
SENTINEL = -1.0


def dirname_um(path: Path) -> float | None:
    m = list(UM_RE.finditer(path.name))
    return float(m[-1].group("um")) if m else None


def load_meta(mesh: Path) -> dict:
    return json.loads((mesh / "meta.json").read_text())


def scale_pair(meta: dict) -> tuple[float, float] | None:
    s = meta.get("scale")
    if not (isinstance(s, (list, tuple)) and len(s) >= 2):
        return None
    return float(s[0]), float(s[1])


def um_per_grid_cell(scale_x: float, voxel_um: float) -> float:
    return (1.0 / scale_x) * voxel_um


def bbox_diag_vox(meta: dict) -> float | None:
    bbox = meta.get("bbox")
    if not bbox or len(bbox) != 2:
        return None
    a = np.asarray(bbox[0], dtype=float)
    b = np.asarray(bbox[1], dtype=float)
    return float(np.linalg.norm(b - a))


def median_edge_vox(mesh: Path) -> float | None:
    import tifffile

    x = tifffile.imread(mesh / "x.tif").astype(np.float64)
    y = tifffile.imread(mesh / "y.tif").astype(np.float64)
    z = tifffile.imread(mesh / "z.tif").astype(np.float64)
    valid = (x != SENTINEL) & (y != SENTINEL) & (z != SENTINEL) & np.isfinite(x + y + z)
    pts = np.stack([x, y, z], axis=-1)
    vh = valid[:, :-1] & valid[:, 1:]
    dh = np.linalg.norm(pts[:, 1:] - pts[:, :-1], axis=-1)[vh]
    vv = valid[:-1] & valid[1:]
    dv = np.linalg.norm(pts[1:] - pts[:-1], axis=-1)[vv]
    edges = np.concatenate([dh, dv]) if dh.size and dv.size else (dh if dh.size else dv)
    return float(np.median(edges)) if edges.size else None


def load_meta_frames(villa_src: Path):
    """Load patched meta_frames without executing broken vesuvius/__init__.py
    (this shallow worktree lacks vesuvius.data)."""
    root = villa_src / "vesuvius" / "src"
    ves = types.ModuleType("vesuvius")
    ves.__path__ = [str(root / "vesuvius")]
    sys.modules["vesuvius"] = ves
    tif = types.ModuleType("vesuvius.tifxyz")
    tif.__path__ = [str(root / "vesuvius" / "tifxyz")]
    sys.modules["vesuvius.tifxyz"] = tif
    path = root / "vesuvius" / "tifxyz" / "meta_frames.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location("vesuvius.tifxyz.meta_frames", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["vesuvius.tifxyz.meta_frames"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def naive_same_scale_groups(mesh_root: Path):
    kids = sorted(p for p in mesh_root.iterdir() if p.is_dir() and (p / "meta.json").is_file())
    buckets: dict[tuple[float, float], list[Path]] = {}
    for k in kids:
        sp = scale_pair(load_meta(k))
        if sp is None:
            continue
        key = (round(sp[0], 5), round(sp[1], 5))
        buckets.setdefault(key, []).append(k)
    return [
        {"scale": list(scale), "paths": paths}
        for scale, paths in buckets.items()
        if len(paths) >= 2
    ]


def probe_before(mesh_root: Path) -> dict:
    print(f"\n===== BEFORE (unmodified main) {mesh_root} =====")
    # Confirm no meta_frames on this tree
    mf_path = Path(sys.argv[0])  # placeholder
    result: dict = {"mesh_root": str(mesh_root)}
    groups = naive_same_scale_groups(mesh_root)
    out_groups = []
    for g in groups:
        ums = [dirname_um(p) for p in g["paths"]]
        known = [u for u in ums if u is not None]
        spread = max(known) / min(known) if len(known) >= 2 else 1.0
        ref_um = known[0] if known else None
        # Naive: scales match ⇒ same frame ⇒ reuse ref_um for all physical conversions
        rows = []
        for p, um in zip(g["paths"], ums):
            meta = load_meta(p)
            sp = scale_pair(meta)
            assert sp and um and ref_um
            true_cell = um_per_grid_cell(sp[0], um)
            naive_cell = um_per_grid_cell(sp[0], ref_um)
            diag = bbox_diag_vox(meta)
            true_diag = diag * um if diag is not None else None
            naive_diag = diag * ref_um if diag is not None else None
            ratio = (naive_diag / true_diag) if (true_diag and naive_diag) else None
            row = {
                "name": p.name,
                "dirname_um": um,
                "scale": list(sp),
                "voxel_size_um_in_meta": meta.get("voxel_size_um"),
                "true_um_per_grid_cell": true_cell,
                "naive_um_per_grid_cell": naive_cell,
                "bbox_diag_vox": diag,
                "true_bbox_diag_um": true_diag,
                "naive_bbox_diag_um": naive_diag,
                "naive_over_true_ratio": ratio,
            }
            rows.append(row)
            print(
                f"  {p.name}: um={um} scale={list(sp)} meta.voxel_size_um={meta.get('voxel_size_um')} "
                f"true_µm/cell={true_cell:.4f} naive_µm/cell={naive_cell:.4f} "
                f"diag_vox={diag:.2f} true_diag_µm={true_diag:.2f} naive_diag_µm={naive_diag:.2f} "
                f"ratio={ratio:.4f}"
            )
        print(
            f"  NAIVE: {len(rows)} meshes share scale={g['scale']} → treated as ONE frame; "
            f"dirname_um spread={spread:.2f}×; ref_um={ref_um}"
        )
        out_groups.append(
            {
                "scale": g["scale"],
                "ref_um": ref_um,
                "dirname_um_spread": spread,
                "rows": rows,
            }
        )
    result["naive_same_scale_groups"] = out_groups

    # TIFF edge demo if present
    tiff_kids = [
        p
        for p in sorted(mesh_root.iterdir())
        if p.is_dir() and (p / "x.tif").is_file()
    ]
    if len(tiff_kids) >= 2:
        ref_um = dirname_um(tiff_kids[0])
        trows = []
        for p in tiff_kids:
            med = median_edge_vox(p)
            um = dirname_um(p)
            assert med and um and ref_um
            true_e = med * um
            naive_e = med * ref_um
            trows.append(
                {
                    "name": p.name,
                    "median_edge_vox": med,
                    "dirname_um": um,
                    "true_edge_um": true_e,
                    "naive_edge_um": naive_e,
                    "naive_over_true": naive_e / true_e,
                }
            )
            print(
                f"  TIFF {p.name}: med_edge_vox={med:.4f} true_um={true_e:.4f} "
                f"naive_um(ref={ref_um})={naive_e:.4f} ratio={naive_e/true_e:.4f}"
            )
        result["tiff_edges"] = trows
    return result


def probe_after(mesh_root: Path, mf) -> dict:
    print(f"\n===== AFTER (patched) {mesh_root} =====")
    result: dict = {"mesh_root": str(mesh_root)}
    groups = mf.find_ambiguous_scale_frames(mesh_root)
    print(f"find_ambiguous_scale_frames → {len(groups)}")
    amb = []
    for g in groups:
        print(
            f"  scale={list(g.scale)} voxel_sizes_um={list(g.voxel_sizes_um)} "
            f"spread≈{g.spread_ratio:.2f}× n={len(g.records)}"
        )
        amb.append(
            {
                "scale": list(g.scale),
                "voxel_sizes_um": list(g.voxel_sizes_um),
                "spread_ratio": g.spread_ratio,
                "n": len(g.records),
                "names": [r.path.name for r in g.records],
            }
        )
    result["ambiguous_groups"] = amb

    kids = sorted(p for p in mesh_root.iterdir() if p.is_dir() and (p / "meta.json").is_file())
    metas_before = [load_meta(k) for k in kids]
    comparable_before_annotate = mf.frames_comparable(metas_before)
    print(f"frames_comparable(all metas, pre-annotate) = {comparable_before_annotate}")
    result["frames_comparable_pre_annotate"] = comparable_before_annotate

    annotate_rows = []
    for k in kids:
        before = load_meta(k).get("voxel_size_um")
        wrote = mf.annotate_meta_voxel_size_um(k, overwrite=False)
        after = load_meta(k).get("voxel_size_um")
        annotate_rows.append(
            {"name": k.name, "wrote": wrote, "before": before, "after": after}
        )
        print(f"  annotate {k.name}: wrote={wrote} {before}→{after}")
    result["annotate"] = annotate_rows

    metas_after = [load_meta(k) for k in kids]
    # Pairwise
    pairs = []
    for i, a in enumerate(kids):
        for b in kids[i + 1 :]:
            ok = mf.frames_comparable([load_meta(a), load_meta(b)])
            pairs.append({"a": a.name, "b": b.name, "comparable": ok})
            print(f"  frames_comparable({a.name[:40]}…, {b.name[:40]}…) = {ok}")
    result["pairwise_comparable"] = pairs
    result["frames_comparable_all_post_annotate"] = mf.frames_comparable(metas_after)

    phys = []
    for k in kids:
        meta = load_meta(k)
        sp = scale_pair(meta)
        um = meta["voxel_size_um"]
        cell = um_per_grid_cell(sp[0], float(um))
        phys.append({"name": k.name, "voxel_size_um": um, "um_per_grid_cell": cell})
        print(f"  physical µm/grid-cell {k.name}: {cell:.4f}")
    result["physical_after"] = phys
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("before", "after"), required=True)
    ap.add_argument("--villa-src", type=Path, required=True)
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument("--out-json", type=Path, required=True)
    args = ap.parse_args()

    print(f"mode={args.mode}")
    print(f"villa_src={args.villa_src}")
    print(f"python={sys.executable}")
    mf_file = args.villa_src / "vesuvius" / "src" / "vesuvius" / "tifxyz" / "meta_frames.py"
    print(f"meta_frames.py exists={mf_file.is_file()} path={mf_file}")

    mf = None
    if args.mode == "before":
        if mf_file.is_file():
            print("ERROR: unmodified tree unexpectedly has meta_frames.py")
            return 2
        print("confirmed: no meta_frames on unmodified main")
    else:
        mf = load_meta_frames(args.villa_src)
        print(f"loaded meta_frames from {mf.__file__}")

    labels = [
        "paris4-40x",
        "paris4-19x",
        "pherc0172-same-um",
        "pherc0139-8x",
    ]
    results = []
    for label in labels:
        root = args.fixtures / label / "mesh"
        if not root.is_dir():
            print(f"SKIP {label}")
            continue
        if args.mode == "before":
            r = probe_before(root)
        else:
            r = probe_after(root, mf)
        r["label"] = label
        results.append(r)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nWrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
