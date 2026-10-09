# Ink-bucket render pyramids: level 1 drops half the depth in 18 of 76 stores

Pre-registration: `docs/preregistration.md`, sha256 `9d8bfa3fa12a0681d8cc0ff0b24178e027c38395d5fae5e89b94eadffdb73c86`, sealed 2026-10-08 21:54:32 HST, before any chunk was fetched. Scored once.

## Result

- **Positive control:** passed. The four stores measured earlier (PHerc0841 ×3 and 500p2a) are TRUNC, half-up, at level 1.
- **Primary outcome:** 12 of 76 stores have a level 1 that is exactly the first ⌈N/2⌉ of the N level-0 planes, each pooled 2×2 in-plane only (TRUNC; 0 differing voxels over both probes). 8 of these are beyond the four known stores.
- **Decision rule:** TRUNC stores exist beyond the known four, so this is reported as a bucket-wide data issue (below).
- **Level 2:** 12 TRUNC, 16 INPLANE_ALL, 48 OTHER (vs level 1).
- **TRUNC stores declaring a z scale > 1:** 0. All 12 declare `scale` [1, 2, 2] at level 1, so the metadata says depth was not pooled, while the shape says depth was halved.
- **Level-1 classes:** TRUNC 12, INPLANE_ALL 17, OTHER 47, no NO_DATA, ABSENT or ERROR.

### TRUNC stores at level 1

| store | level-0 planes | level-1 planes | level-2 class | declared level-1 scale | known before |
|---|---:|---:|---|---|---|
| `ink/0009b/auto_grown_20250919055754487_inp_hr_2um/auto_grown_20250919055754487_inp_hr_2um.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | no |
| `ink/0139/w016_2025010815/w016_2025010815.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | no |
| `ink/0139/w017_2025010815/w017_2025010815.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | no |
| `ink/0139/w028_20260115221/w028_20260115221.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | no |
| `ink/0500p2/-1/-1.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | no |
| `ink/1667/w018_20240304144031_2um/w018_20240304144031_2um.zarr` | 65 | 33 | OTHER | [1.0, 2.0, 2.0] | no |
| `ink/1667/w029_20251212185248662_2um/w029_20251212185248662_2um.zarr` | 65 | 33 | OTHER | [1.0, 2.0, 2.0] | no |
| `ink/814/814_46527_2um_try2/814_46527_2um_try2.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | no |
| `ink/841/auto_grown_20260220144552896/auto_grown_20260220144552896.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | yes |
| `ink/841/auto_grown_20260220174252405/auto_grown_20260220174252405.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | yes |
| `ink/841/w00/w00.zarr` | 65 | 33 | TRUNC | [1.0, 2.0, 2.0] | yes |
| `ink/unused/500p2a/500p2a.zarr` | 65 | 33 | OTHER | [1.0, 2.0, 2.0] | yes |

### Classes by scroll folder (level 1)

| folder | stores | TRUNC | INPLANE_ALL | OTHER |
|---|---:|---:|---:|---:|
| `ink/0009b` | 1 | 1 | 0 | 0 |
| `ink/0139` | 11 | 3 | 0 | 8 |
| `ink/0500p2` | 1 | 1 | 0 | 0 |
| `ink/1667` | 6 | 2 | 0 | 4 |
| `ink/814` | 1 | 1 | 0 | 0 |
| `ink/841` | 3 | 3 | 0 | 0 |
| `ink/man5` | 1 | 0 | 0 | 1 |
| `ink/phercparis4` | 8 | 0 | 5 | 3 |
| `ink/unused/0139` | 30 | 0 | 0 | 30 |
| `ink/unused/500p2a` | 1 | 1 | 0 | 0 |
| `ink/unused/P343p` | 1 | 0 | 0 | 1 |
| `ink/unused/manbp` | 11 | 0 | 11 | 0 |
| `ink/unused/phercparis4` | 1 | 0 | 1 | 0 |

## What the OTHER class is (post hoc diagnostic, not pre-registered)

OTHER only means no rule in the pre-registered family matched exactly. To see what those stores hold, the first probe cell of each OTHER store was read again and (a) tested against strided decimation, child[k] = parent[2k+oz, 2y+oy, 2x+ox], and (b) each child plane was matched to its best-correlating parent plane (2×2 in-plane mean). Scripts: `scripts/diagnose_other.py`, `scripts/diagnose_corr.py`.

- **38 stores declare a z scale of 2 and are exact strided decimation of every second plane** (0, 2, …, 64): the full depth is covered, consistent with their metadata (all 38 declare `"method": "strided 2x downsampling"` in their `.zattrs`, read 2026-10-08). Not affected.
- **6 stores declare a z scale of 1, hold 33 of 65 planes, and every child plane k best matches parent plane k.** Correlation with parent plane k is at least 0.928 for every plane; the median correlation with parent plane 2k is at most 0.160. They hold the first half of the depth too, but their in-plane filter is outside the tested family:
  - `ink/0139/w029_202601261946/w029_202601261946.zarr`
  - `ink/0139/w030_202601301912/w030_202601301912.zarr`
  - `ink/1667/w013_20240304141531_2um/w013_20240304141531_2um.zarr`
  - `ink/1667/w023_20240304161941_2um/w023_20240304161941_2um.zarr`
  - `ink/1667/w028_20251208130119156_2um/w028_20251208130119156_2um.zarr`
  - `ink/1667/w031_2025122323_2um/w031_2025122323_2um.zarr`
  - 3 of these 6 have a level 2 that is exact TRUNC (half-up) of their level 1, the same signature as the 12 exact stores.
- **3 stores keep all 65 planes** (child plane k ↔ parent plane k, correlation ≥ 0.963) with an in-plane filter outside the tested family. Depth is intact. Not affected.

**Depth-truncated level 1 in total: 18 of 76 stores** (12 exact TRUNC + 6 by correlation), 14 of them beyond the four known stores.

## Where it comes from

`vc_render_tifxyz` writes the pyramid with `createPyramidDatasets` (array shapes) and `downsampleTileIntoPreserveZ` (data), both in `volume-cartographer/core/src/Zarr.cpp`.

- On villa `main` from #774 (2026-03-04 UTC) until #804 (2026-04-15 UTC), `createPyramidDatasets` halved z at every level, `{(z+1)/2, (y+1)/2, (x+1)/2}`.
- The data writer kept z, averaging 2×2 in-plane, and stopped at the smaller depth (`zz < srcActualZ && zz < dstZ`). So each level stored the first ⌈N/2⌉ planes, rounded `(sum + cnt/2) / cnt`, which is half-up. That is exactly the TRUNC half-up rule matched here.
- The metadata written alongside kept the in-plane-only scale [1, 2, 2].
- #804 restored `{z, (y+1)/2, (x+1)/2}`, and current `main` keeps the full depth. The code is fixed. The renders made with the affected builds are still in the bucket.

## Why it matters

- `vesuvius.ink_detection.inference.infer` centre-crops its 17-plane window from the depth of the level it reads (`center_crop_layer_indices`). On a truncated level 1 the window is centred near level-0 plane 16 instead of the render's centre plane 32, and nothing errors.
- Level 2 compounds it: in 9 of the 12 TRUNC stores, level 2 is TRUNC of level 1 again (17 planes, the first quarter of the level-0 depth).

### Consequence on real data (post hoc, stated as such in the pre-registration)

Same checkpoints (seed42 / seed43, step 75,000), same region and labels (identical n and positives). One input is the published level 1. The other is a correctly pooled 2×2×2 input (arm S9 of `gpu-1648-intermediate-scale`). Operative (reverse) direction, ROC AUC:

| segment | seed | n | published level 1 | pooled 2×2×2 (S9) | difference |
|---|---|---:|---:|---:|---:|
| PHerc0841 w00 | seed42 | 6,128,158 | 0.6459 | 0.6959 | +0.0500 |
| PHerc0841 w00 | seed43 | 6,128,158 | 0.6223 | 0.7194 | +0.0971 |
| PHerc0841 auto_grown …144552896 | seed42 | 3,720,168 | 0.6631 | 0.7357 | +0.0726 |
| PHerc0841 auto_grown …144552896 | seed43 | 3,720,168 | 0.6976 | 0.7556 | +0.0579 |
| PHerc0841 auto_grown …174252405 | seed42 | 4,846,350 | 0.6335 | 0.6630 | +0.0295 |
| PHerc0841 auto_grown …174252405 | seed43 | 4,846,350 | 0.6535 | 0.6717 | +0.0182 |

The correctly pooled input scores +0.0182 to +0.0971 AUC higher in all 6 cases.
- This is descriptive. The two arms differ in which planes the window covers (around level-0 plane 16 vs 32) and in z spacing (one level-0 plane vs a pair).
- It is not a controlled test of either factor alone. It shows what a user reading the published level 1 got, against the same data read correctly.

## Proposed fix

1. **Data:** rebuild levels 1–5 of the 18 stores from their intact level 0 with the current `vc_render_tifxyz` pyramid code (keeps all planes, declares [1, 2, 2]), or pool z and declare [2, 2, 2]. Either works, as long as shape, data and scale agree at every level.
2. **Reader guard:** before centre-cropping, `infer.py` could compare a level's depth with level 0's depth and the declared z scale, and stop when depth shrank while the declared z scale stayed 1.

## Limits

- Two probe chunks per level and store. An exact match over ~0.5–1.1 M voxels is not a proof for every chunk.
- Only render stores under `ink/` in the `scrollprize/datasets` bucket, as listed on 2026-10-08. Labels, masks and predictions were excluded.
- The rule for the 6 correlation-matched stores is not identified, only their depth coverage.
- 1553.2 MB was read for the census. No chunk data is kept or redistributed. Only metadata and metrics are published.

AI-assisted.
