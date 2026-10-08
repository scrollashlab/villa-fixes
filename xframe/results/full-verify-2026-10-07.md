# xframe v0.1.0: full streamed corpus verify (2026-10-07 HST)

Run: `scripts/full_verify.py` with the xframe package installed non-editable in a clean venv (`/tmp/xframe-venv`; Python 3.13.5, numpy 2.5.3, tifffile 2026.9.20, imagecodecs 2026.8.16).
- 3 workers, anonymous HTTPS, no payload cache. Wall time 1,410 s (about 23.5 min).
- Catalog snapshot: `metadata.json` fetched 2026-10-07 09:14 HST.
- Rules: `docs/protocol-2026-10-07.md` (frozen classes, A1, A2).

Raw: `out/full-verify-2026-10-07.jsonl` (one row per mesh). Summary: `out/full-verify-summary-2026-10-07.json` (from `scripts/summarize_full.py`). Log: `out/full-verify.log`.
Tests: `out/xframe-pytest-clean-venv-2026-10-07.log`, 19/19 passed (16 offline + 3 live bucket).

## Result: **902/902 CONSISTENT** (0 PARTIAL, 0 DRIFT, 0 NOT_COMPARABLE, 0 ERROR)
| | count |
|---|---|
| Segments | 307, in 11 samples (13 sample × downscale groups) |
| Derived (`transform-tifxyz-normalized`) | **707/707 CONSISTENT** |
| Copies (`copy-normalized-for-original`) | 195/195 identical (max residual 0.0) |
| Downscale segments | PHercParis4 ×4: 204/204 · PHerc0139 ×4: 189/189 · PHerc0500P2 ×2: 21/21 |
| Predicted grid shape (from the source alone, VC spacing rule) = published | **902/902** |
| Cells compared | 4,787,278,260 |
| Validity-mask mismatches | 0 |
| Worst derived cell | 0.0358 voxel = 0.086 µm (PHerc1667 w011…merged_v4, on-20251217075048-2.399um) |
| Highest per-mesh p99 | 0.0087 voxel; no cell > 0.5 voxel anywhere |
| Regrid | 518 up-sampled, 136 down-sampled, 248 none |

Per sample (ds = downscale): PHerc0009B 36 · PHerc0139 (ds4) 189 · PHerc0172 106 · PHerc0343P 16 · PHerc0500P2 118 + (ds2) 21 · PHerc0800 6 · PHerc0814 56 · PHerc0841 6 · PHerc1447 15 · PHerc1667 79 · PHercParis4 50 + (ds4) 204.

## What this establishes (and does not)
- Every published cross-frame tifxyz in the bucket (catalog of 2026-10-07) is, to float32 precision, `regrid(T · (s · normalized))`. Here T is the **current** sample-level catalog matrix and s is `original_volume_downscale`. Point conversions done with `xframe convert` therefore match the published meshes.
- Corollary: any error in a catalog matrix is carried exactly into every derived mesh, and correcting a matrix in `metadata.json` would not correct published meshes. They would need regenerating. This applies to the PHerc1667 1.129 µm matrix flagged in #1843 / PR #1994; we did not assess that matrix's correctness ourselves.
- Downscale: 112 segments' `tifxyz_normalized` meshes are in 1/`original_volume_downscale` coordinates (414 derived meshes depend on this pre-scale). Their own `meta.json` does not say so. The catalog factor is already used in #1734 (bboxes) and implied in #1727 (exact ×4.0 renders); no issue we found (2026-10-07) states the mesh-side gap or measures the offset. Related: #1522.
- Not established: matrix correctness, on-papyrus placement, or ink quality.

## Differences from the pilot
- The pilot's resample-then-affine order is replaced by VC's literal affine-then-regrid order (mathematically equivalent).
- Grid shape is now predicted independently instead of being taken from the published file.
