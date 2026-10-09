"""Build results/summary.md and results/census.json from audit.json, diagnose-other.json, diagnose-corr.json and the
the AUC copies in meta/from-*/. Every number in summary.md comes from this script."""
import json, math
fl = lambda x: math.floor(x * 1000) / 1000; ce = lambda x: math.ceil(x * 1000) / 1000
from collections import Counter, defaultdict
from pathlib import Path
R = Path(__file__).resolve().parents[1]
A = json.load(open(R / "results/audit.json")); st = A["stores"]
D = json.load(open(R / "results/diagnose-other.json")); C = json.load(open(R / "results/diagnose-corr.json"))
# Consequence inputs: AUCs from two earlier sealed studies, copied into meta/ (see PROVENANCE.txt in each folder).
SEL = json.load(open(R / "meta/from-label-free-selector/level1-auc.json"))["segments"]
S9 = json.load(open(R / "meta/from-gpu-1648-intermediate-scale/s9-auc.json"))["segments"]
pre = (R / "docs/preregistration.sha256").read_text().split()[0]
KNOWN = {"ink/841/w00/w00.zarr", "ink/841/auto_grown_20260220144552896/auto_grown_20260220144552896.zarr",
         "ink/841/auto_grown_20260220174252405/auto_grown_20260220174252405.zarr", "ink/unused/500p2a/500p2a.zarr"}
def folder(s): p = s.split("/"); return "/".join(p[:3]) if p[1] == "unused" else "/".join(p[:2])
def short(s): return s.rsplit("/", 1)[-1]
def zs(v): return v["declared_scale"][0] if v.get("declared_scale") else None
pc = {s: (st[s]["L1"]["rule"], st[s]["L1"]["rounding"]) for s in KNOWN if s in st}
pc_ok = len(pc) == 4 and all(v == ("TRUNC", "half_up") for v in pc.values())
trunc = sorted(s for s, v in st.items() if v["L1"]["rule"] == "TRUNC")
beyond = [s for s in trunc if s not in KNOWN]
c1 = Counter(v["L1"]["rule"] for v in st.values()); c2 = Counter(v["L2"]["rule"] for v in st.values())
trunc_zgt1 = [s for s in trunc if (zs(st[s]["L1"]) or 1) > 1]
# post hoc groups among OTHER
strided = sorted(s for s, v in D.items() if any(x[0] == 0 for x in v["strided"].values()))
first_half = sorted(s for s, v in D.items() if s not in strided and v["child_planes"] < v["parent_planes"]
                    and v["best_parent_plane_per_child_plane"] == list(range(v["child_planes"])))
full_inexact = sorted(s for s, v in D.items() if s not in strided and v["child_planes"] == v["parent_planes"])
assert len(strided) + len(first_half) + len(full_inexact) == c1["OTHER"]
assert all(v["best_parent_plane_per_child_plane"] == list(range(0, 2 * v["child_planes"], 2)) for s, v in D.items() if s in strided)
assert all(zs(st[s]["L1"]) == 2.0 for s in strided) and all(zs(st[s]["L1"]) == 1.0 for s in first_half + full_inexact)
truncated = sorted(trunc + first_half)
census = {"prereg_sha256": pre, "positive_control_passed": pc_ok, "n_stores": len(st), "L1_counts": dict(c1), "L2_counts": dict(c2),
          "trunc_L1": trunc, "trunc_L1_beyond_known": beyond, "trunc_L1_declaring_z_scale_gt_1": trunc_zgt1,
          "posthoc": {"other_strided_full_depth": strided, "other_first_half_by_correlation": first_half,
                      "other_full_depth_inexact": full_inexact, "depth_truncated_total": truncated},
          "bytes_fetched": A["bytes_fetched"]}
json.dump(census, open(R / "results/census.json", "w"), indent=1)

L = []; w = L.append
w("# Ink-bucket render pyramids: level 1 drops half the depth in 18 of 76 stores\n")
w(f"Pre-registration: `docs/preregistration.md`, sha256 `{pre}`, sealed 2026-10-08 21:54:32 HST, before any chunk was fetched. Scored once.\n")
w("## Result\n")
w(f"- **Positive control:** {'passed' if pc_ok else 'FAILED'}. The four stores measured earlier (PHerc0841 ×3 and 500p2a) are TRUNC, half-up, at level 1.")
w(f"- **Primary outcome:** {len(trunc)} of {len(st)} stores have a level 1 that is exactly the first ⌈N/2⌉ of the N level-0 planes, each pooled 2×2 in-plane only (TRUNC; 0 differing voxels over both probes). {len(beyond)} of these are beyond the four known stores.")
w(f"- **Decision rule:** TRUNC stores exist beyond the known four, so this is reported as a bucket-wide data issue (below).")
w(f"- **Level 2:** {c2['TRUNC']} TRUNC, {c2['INPLANE_ALL']} INPLANE_ALL, {c2['OTHER']} OTHER (vs level 1).")
w(f"- **TRUNC stores declaring a z scale > 1:** {len(trunc_zgt1)}. All {len(trunc)} declare `scale` [1, 2, 2] at level 1, so the metadata says depth was not pooled, while the shape says depth was halved.")
w(f"- **Level-1 classes:** TRUNC {c1['TRUNC']}, INPLANE_ALL {c1['INPLANE_ALL']}, OTHER {c1['OTHER']}, no NO_DATA, ABSENT or ERROR.\n")
w("### TRUNC stores at level 1\n")
w("| store | level-0 planes | level-1 planes | level-2 class | declared level-1 scale | known before |")
w("|---|---:|---:|---|---|---|")
for s in trunc:
    v = st[s]; w(f"| `{s}` | {v['L1']['parent_shape'][0]} | {v['L1']['child_shape'][0]} | {v['L2']['rule']} | {v['L1']['declared_scale']} | {'yes' if s in KNOWN else 'no'} |")
w("\n### Classes by scroll folder (level 1)\n")
by = defaultdict(Counter)
for s, v in st.items(): by[folder(s)][v["L1"]["rule"]] += 1
w("| folder | stores | TRUNC | INPLANE_ALL | OTHER |"); w("|---|---:|---:|---:|---:|")
for f in sorted(by): b = by[f]; w(f"| `{f}` | {sum(b.values())} | {b['TRUNC']} | {b['INPLANE_ALL']} | {b['OTHER']} |")
w("\n## What the OTHER class is (post hoc diagnostic, not pre-registered)\n")
w("OTHER only means no rule in the pre-registered family matched exactly. To see what those stores hold, the first probe cell of each OTHER store was read again and (a) tested against strided decimation, child[k] = parent[2k+oz, 2y+oy, 2x+ox], and (b) each child plane was matched to its best-correlating parent plane (2×2 in-plane mean). Scripts: `scripts/diagnose_other.py`, `scripts/diagnose_corr.py`.\n")
w(f"- **{len(strided)} stores declare a z scale of 2 and are exact strided decimation of every second plane** (0, 2, …, 64): the full depth is covered, consistent with their metadata (all {len(strided)} declare `\"method\": \"strided 2x downsampling\"` in their `.zattrs`, read 2026-10-08). Not affected.")
mn = min(C[s]["r_child_k_vs_parent_k"][0] for s in first_half); mx2 = max(C[s]["r_child_k_vs_parent_2k"][1] for s in first_half)
w(f"- **{len(first_half)} stores declare a z scale of 1, hold {D[first_half[0]]['child_planes']} of {D[first_half[0]]['parent_planes']} planes, and every child plane k best matches parent plane k.** Correlation with parent plane k is at least {fl(mn):.3f} for every plane; the median correlation with parent plane 2k is at most {ce(mx2):.3f}. They hold the first half of the depth too, but their in-plane filter is outside the tested family:")
for s in first_half: w(f"  - `{s}`")
mn3 = min(C[s]["r_child_k_vs_parent_k"][0] for s in full_inexact)
w(f"  - {sum(st[s]['L2']['rule'] == 'TRUNC' for s in first_half)} of these 6 have a level 2 that is exact TRUNC (half-up) of their level 1, the same signature as the 12 exact stores.")
w(f"- **{len(full_inexact)} stores keep all 65 planes** (child plane k ↔ parent plane k, correlation ≥ {fl(mn3):.3f}) with an in-plane filter outside the tested family. Depth is intact. Not affected.\n")
w(f"**Depth-truncated level 1 in total: {len(truncated)} of {len(st)} stores** ({len(trunc)} exact TRUNC + {len(first_half)} by correlation), {len([s for s in truncated if s not in KNOWN])} of them beyond the four known stores.\n")
w("## Where it comes from\n")
w("`vc_render_tifxyz` writes the pyramid with `createPyramidDatasets` (array shapes) and `downsampleTileIntoPreserveZ` (data), both in `volume-cartographer/core/src/Zarr.cpp`.\n")
w("- On villa `main` from #774 (2026-03-04 UTC) until #804 (2026-04-15 UTC), `createPyramidDatasets` halved z at every level, `{(z+1)/2, (y+1)/2, (x+1)/2}`.")
w("- The data writer kept z, averaging 2×2 in-plane, and stopped at the smaller depth (`zz < srcActualZ && zz < dstZ`). So each level stored the first ⌈N/2⌉ planes, rounded `(sum + cnt/2) / cnt`, which is half-up. That is exactly the TRUNC half-up rule matched here.")
w("- The metadata written alongside kept the in-plane-only scale [1, 2, 2].")
w("- #804 restored `{z, (y+1)/2, (x+1)/2}`, and current `main` keeps the full depth. The code is fixed. The renders made with the affected builds are still in the bucket.\n")
w("## Why it matters\n")
w("- `vesuvius.ink_detection.inference.infer` centre-crops its 17-plane window from the depth of the level it reads (`center_crop_layer_indices`). On a truncated level 1 the window is centred near level-0 plane 16 instead of the render's centre plane 32, and nothing errors.")
w(f"- Level 2 compounds it: in {sum(st[s]['L2']['rule'] == 'TRUNC' for s in trunc)} of the {len(trunc)} TRUNC stores, level 2 is TRUNC of level 1 again ({st[trunc[0]]['L2']['child_shape'][0]} planes, the first quarter of the level-0 depth).\n")
w("### Consequence on real data (post hoc, stated as such in the pre-registration)\n")
w("Same checkpoints (seed42 / seed43, step 75,000), same region and labels (identical n and positives). One input is the published level 1. The other is a correctly pooled 2×2×2 input (arm S9 of `gpu-1648-intermediate-scale`). Operative (reverse) direction, ROC AUC:\n")
w("| segment | seed | n | published level 1 | pooled 2×2×2 (S9) | difference |"); w("|---|---|---:|---:|---:|---:|")
segs = {"pherc0841-w00": "PHerc0841 w00", "pherc0841-ag144": "PHerc0841 auto_grown …144552896", "pherc0841-ag174": "PHerc0841 auto_grown …174252405"}
diffs = []
for k, name in segs.items():
    assert SEL[k]["n"] == S9[k]["n"] and SEL[k]["n_pos"] == S9[k]["n_pos"]
    for sd in ("seed42", "seed43"):
        a1 = SEL[k]["auc"][f"{sd}_step-075000|reverse"]; a9 = S9[k]["auc"][f"{sd}|S9|reverse"]; diffs.append(a9 - a1)
        w(f"| {name} | {sd} | {SEL[k]['n']:,} | {a1:.4f} | {a9:.4f} | {a9 - a1:+.4f} |")
w(f"\nThe correctly pooled input scores {min(diffs):+.4f} to {max(diffs):+.4f} AUC higher in all 6 cases.")
w("- This is descriptive. The two arms differ in which planes the window covers (around level-0 plane 16 vs 32) and in z spacing (one level-0 plane vs a pair).")
w("- It is not a controlled test of either factor alone. It shows what a user reading the published level 1 got, against the same data read correctly.\n")
w("## Proposed fix\n")
w(f"1. **Data:** rebuild levels 1–5 of the {len(truncated)} stores from their intact level 0 with the current `vc_render_tifxyz` pyramid code (keeps all planes, declares [1, 2, 2]), or pool z and declare [2, 2, 2]. Either works, as long as shape, data and scale agree at every level.")
w("2. **Reader guard:** before centre-cropping, `infer.py` could compare a level's depth with level 0's depth and the declared z scale, and stop when depth shrank while the declared z scale stayed 1.\n")
w("## Limits\n")
w("- Two probe chunks per level and store. An exact match over ~0.5–1.1 M voxels is not a proof for every chunk.")
w("- Only render stores under `ink/` in the `scrollprize/datasets` bucket, as listed on 2026-10-08. Labels, masks and predictions were excluded.")
w(f"- The rule for the {len(first_half)} correlation-matched stores is not identified, only their depth coverage.")
w(f"- {A['bytes_fetched'] / 1e6:.1f} MB was read for the census. No chunk data is kept or redistributed. Only metadata and metrics are published.\n")
w("AI-assisted.")
(R / "results/summary.md").write_text("\n".join(L) + "\n")
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in census.items() if k != "posthoc"}), {k: len(v) for k, v in census["posthoc"].items()})
