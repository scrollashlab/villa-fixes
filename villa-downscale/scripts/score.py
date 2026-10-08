"""Score both loader arms against every published derived mesh of the pre-registered segments
(docs/preregistration.md, written before scoring). Metadata-only JSON output.
Usage: python score.py ARMS_DIR OUT_JSON   (ARMS_DIR/<arm>/<sample>_<segment>.npy from load_arm.py)
Published meshes are streamed anonymously from the open-data bucket via xframe (nothing written to disk)."""
import json, sys, time, hashlib
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import os
sys.path.insert(0, os.environ.get("XFRAME_SRC") or "/workspace/vesuvius-lab/handoff/xframe/src")   # xframe/src of the published xframe bundle
from common import CAT, SEGMENTS
from xframe.catalog import Catalog
from xframe.tifxyz import Source, read_tifxyz
from xframe import geom

_candidates = [
    Path(os.environ["VDS_OFFSETS"]) if os.environ.get("VDS_OFFSETS") else None,
    Path("/workspace/vesuvius-lab/handoff/xframe/results/downscale-offsets-2026-10-07.json"),
    Path("/workspace/vesuvius-lab/experiments/cross-frame-toolkit/out/downscale-offsets-2026-10-07.json"),
]
OFFSETS = next(str(p) for p in _candidates if p is not None and p.exists())
arms_dir, out_json = Path(sys.argv[1]), sys.argv[2]
cat = Catalog.load(CAT); src = Source()
offsets = {(r["sample"], r["segment"]): {d["mesh"]: d for d in r["derived"]} for r in json.load(open(OFFSETS))["segments"]}
ARMS = ("patched", "unpatched")


def q(P, M):
    V = geom.valid_mask(P)
    Q = np.full(P.shape, geom.INVALID, np.float32)
    Q[V] = geom.apply_affine(P[V], M).astype(np.float32)      # no pre-scale added by the scorer
    Q[~geom.valid_mask(Q)] = geom.INVALID
    return Q


class Acc:
    """Exact residual statistics in bounded memory: per-block counts/max in float64, residuals kept as float32 for quantiles."""
    def __init__(self):
        self.parts = []; self.max = 0.0; self.gt05 = 0; self.zero = 0

    def add(self, r):
        if r.size:
            self.max = max(self.max, float(r.max())); self.gt05 += int((r > 0.5).sum()); self.zero += int((r == 0).sum())
            self.parts.append(r.astype(np.float32))

    def stats(self, um):
        if not self.parts:
            return None
        r = np.concatenate(self.parts); self.parts = []
        o = {"n": int(r.size), "median_vox": float(np.median(r)), "p99_vox": float(np.quantile(r, 0.99)),
             "max_vox": self.max, "frac_gt_0_5_vox": self.gt05 / r.size, "n_exact_zero": self.zero}
        if um:
            o.update(median_um=o["median_vox"] * um, p99_um=o["p99_vox"] * um, max_um=o["max_vox"] * um)
        return o


def stats(r, um):
    a = Acc(); a.add(r); return a.stats(um)


BLOCK = 256

rows = []
for s, g in SEGMENTS:
    seg = cat.segment(s, g)
    P = {a: np.load(arms_dir / a / f"{s}_{g}.npy") for a in ARMS}
    ou = cat.voxel_um(s, seg.original_volume)
    vu, vp = geom.valid_mask(P["unpatched"]), geom.valid_mask(P["patched"])
    d0 = np.linalg.norm(P["patched"][vu & vp].astype(np.float64) - P["unpatched"][vu & vp], axis=1)
    seg_row = {"sample": s, "segment": g, "long_id": seg.long_id, "downscale": seg.downscale,
               "original_volume": seg.original_volume, "original_um": ou, "normalized_shape": list(P["patched"].shape[:2]),
               "valid_mask_equal_between_arms": bool((vu == vp).all()),
               "patched_equals_s_times_unpatched_exactly": bool(np.array_equal(P["patched"][vp], P["unpatched"][vu] * np.float32(seg.downscale))),
               "own_frame_offset": stats(d0, ou), "derived": []}
    for m in sorted([m for m in seg.meshes if m.kind == "derived"], key=lambda m: m.key):
        t0 = time.time()
        M, prov = cat.matrix(s, seg.original_volume, m.target_volume)
        tu = cat.voxel_um(s, m.target_volume)
        D, meta = read_tifxyz(src, m.key)
        H, W = D.shape[:2]
        vD = geom.valid_mask(D)
        row = {"mesh": m.key, "target_volume": m.target_volume, "target_um": tu, "matrix": prov,
               "published_shape": [H, W], "published_meta_scale": meta.get("scale"), "arms": {}}
        for a in ARMS:
            Q = q(P[a], M)
            same = Q.shape[:2] == (H, W)
            acc = Acc(); only_l = only_p = 0
            for r0 in range(0, H, BLOCK):              # bounded memory, as xframe verify
                r1 = min(H, r0 + BLOCK)
                R = Q[r0:r1] if same else geom.resample_linear_preserving_invalids(Q, H, W, (r0, r1))
                vR = geom.valid_mask(R); vB = vD[r0:r1]; both = vR & vB
                only_l += int((vR & ~vB).sum()); only_p += int((~vR & vB).sum())
                acc.add(np.linalg.norm(R[both].astype(np.float64) - D[r0:r1][both].astype(np.float64), axis=1))
            row["arms"][a] = {"resampled": not same, "loaded_shape": list(Q.shape[:2]),
                              "valid_only_loaded": only_l, "valid_only_published": only_p,
                              "residual": acc.stats(tu)}
            del Q, acc
        ref = offsets[(s, g)].get(m.key)
        row["xframe_offsets_median_target_vox"] = ref["offset_target_vox"]["median"] if ref else None
        pa, ua = row["arms"]["patched"], row["arms"]["unpatched"]
        pr, ur = pa["residual"], ua["residual"]
        row["pass_patched"] = bool(pr and pr["max_vox"] <= 0.5 and pr["frac_gt_0_5_vox"] == 0
                                   and pa["valid_only_loaded"] == 0 and pa["valid_only_published"] == 0)
        row["pass_unpatched_offset"] = bool(ur and ur["median_vox"] >= 1000 and tu and ur["median_um"] >= 10000)
        row["unpatched_vs_xframe_rel_diff"] = (abs(ur["median_vox"] - ref["offset_target_vox"]["median"]) / ref["offset_target_vox"]["median"]) if (ur and ref) else None
        row["pass_agreement_2pct"] = row["unpatched_vs_xframe_rel_diff"] is not None and row["unpatched_vs_xframe_rel_diff"] <= 0.02
        row["elapsed_s"] = round(time.time() - t0, 1)
        seg_row["derived"].append(row); del D
        print(s, g, m.target_volume, [H, W], "patched max", pr and round(pr["max_vox"], 4), "unpatched median vox/mm",
              ur and round(ur["median_vox"]), ur and ur.get("median_um") and round(ur["median_um"] / 1000, 1),
              "xframe", ref and round(ref["offset_target_vox"]["median"]), row["pass_patched"], row["pass_unpatched_offset"], row["pass_agreement_2pct"], flush=True)
    rows.append(seg_row)

allm = [d for r in rows for d in r["derived"]]
summary = {"n_segments": len(rows), "n_derived_meshes": len(allm),
           "patched_pass": sum(d["pass_patched"] for d in allm),
           "unpatched_offset_pass": sum(d["pass_unpatched_offset"] for d in allm),
           "agreement_2pct_pass": sum(d["pass_agreement_2pct"] for d in allm)}
prereg = HERE.parent / "docs" / "preregistration.md"
arms_heads = {}
for a in ARMS:
    for cand in (HERE.parent / "out" / f"load-{a}-2026-10-07.json",
                 HERE.parent / "results" / f"load-{a}-2026-10-07.json"):
        if cand.exists():
            arms_heads[a] = json.load(open(cand))["villa_head"]; break
    else:
        arms_heads[a] = None
json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S HST"), "catalog": "metadata.json fetched 2026-10-07",
           "preregistration_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest(),
           "arms": arms_heads, "summary": summary, "segments": rows}, open(out_json, "w"), indent=1)
print(json.dumps(summary))
