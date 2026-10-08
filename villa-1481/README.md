# villa#1481 — flat ink robust_mad folds zero padding into stats

Upstream: https://github.com/ScrollPrize/villa/issues/1481

## Problem

Flat ink **training** normalizes only voxels read from the source and leaves
reader padding at zero. Flat **inference** padded first, then ran
`normalize_robust()` over the whole tensor, so artificial zeros changed
percentiles, median, and MAD for every real CT voxel.

Issue’s deterministic numbers (3×4×4 source `100..147` centered into 5×4×4):

| | train semantics | buggy inference |
|--|----------------:|----------------:|
| padded zeros | `0` | `≈ -2.266` |
| real-voxel MAE | — | `≈ 0.488` |
| real-voxel max AE | — | `≈ 1.136` |

## Fix

Share placement between `FlatPatchReader.read` and normalization via
`source_placement` / `valid_region_zyx`. For `tifxyz_robust`, normalize only
that region; leave padding at zero. `divide_255` unchanged.

Prior unmerged PRs (#1483, #1646, #1773) addressed the same bug and were closed
without merge (staleness / account limits). This patch follows the
placement-shared approach from those attempts.

## Base revision

Built against villa `main` at `5a4388f`; re-verified apply + tests on `0e14cf48` / `/tmp/v8clean` (2026-10-05 HST).

## Apply

```bash
cd /path/to/villa
git checkout main   # at or after 5a4388f
git am /path/to/0001-ink_detection-exclude-reader-padding-from-robust-fla.patch
# or: git apply ...
```

## Tests

```bash
python -m pytest vesuvius/tests/ink_detection/test_flat_robust_padding.py -v
```

Local CPU (2026-10-04 PT): **3 passed** in-tree; experiment suite also **3 passed**.
See `pytest-in-tree-results.log` / `pytest-results.log` / `repro.log`.

Author on the patch: Scroll Ash Lab \<scrollash.lab@gmail.com\>.

## Evidence on real scroll CT (2026-10-05 HST)

**Env:** `/tmp/v8clean` (full villa + 8-patch stack, **no stubs**) + `/workspace/envs/zarr3`.  
**Data:** anonymous HTTPS from `vesuvius-challenge-open-data`  
`PHercParis4/volumes/20260310170716-45.532um-11.0m-74keV-masked.zarr` chunk `0/1/10/5` (CC BY-NC).  
**Window:** densest 32³ subcube in that chunk (origin zyx=(48,80,0); zero_frac=0; mean≈108.7).

**Before** = pad-then-`normalize_robust` (pre-#1481 flat-inference footgun).  
**After** = normalize only the valid source region (train / #1481 semantics).  
Reference = train paste (normalize source, leave pad at 0).

| Placement | Pad fraction | Before real-voxel MAE / maxAE | After MAE / maxAE |
| --- | ---: | --- | --- |
| Corner into 32×96×96 | 88.9% | **3.17 / 4.62** | **0 / 0** |
| Centered into 32×64×64 | 75% | **2.32 / 4.16** | **0 / 0** |

Artifacts: `real-data-2026-10-05/SUMMARY.json`, `arrays.npz`, `volume-chunk/`.

On this masked CT window the padded corners stay numerically 0 after robust norm (many pad zeros dominate the lower tail); the bug still **shifts every real CT voxel** by O(1)–O(4) in normalized units until #1481’s valid-region path is used.
