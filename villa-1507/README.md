# villa #1507 — native full-3D inference drops `input_pad_depth_to`

**Issue:** https://github.com/ScrollPrize/villa/issues/1507 (verified open 2026-10-04; no open PR; closed unmerged #1645/#1772)  
**Base:** villa `main` @ `5a4388f`  
**Author:** Scroll Ash Lab \<scrollash.lab@gmail.com\>  
**License:** MIT

## Problem

Training and flat inference center-pad BCZYX inputs to `model_config.input_pad_depth_to` via `TargetModel`. Native `_load_native_model` built `TargetModel(base_model.eval())` without that argument, so a checkpoint trained with depth padding saw unpadded depth at native inference.

## Fix

Pass `input_pad_depth_to=config.model.input_pad_depth_to` into `TargetModel` in `_load_native_model` (same contract as flat inference).

## Tests (hard gate — verified)

Env: `/tmp/zarr3-venv`, real editable install, no stubs.

| Suite | Result |
|-------|--------|
| New tests only, **before** fix | **1 failed**, 1 passed (`honours…` fails with depth 3≠5; `leaves_depth_alone…` passes) |
| Full `test_native_full3d_inference.py` with new tests, **before** fix | **1 failed, 14 passed** |
| Full file **after** fix | **15 passed** / 0 failed |
| Original 13 tests only after fix | **13 passed**, 2 deselected |

No other test outcome changed: the sole failure before the fix was the new padding regression; after the fix all 15 pass.

Logs in this folder: `pytest-new-tests-before-fix.log`, `pytest-base-with-new-tests.log`, `pytest-patched-full.log`, `pytest-patched-original13.log`, `pytest-stack-apply-full.log`.

## Limits

**Status: wiring-verified only** (not CONTRIBUTING-grade real-data before/after).

## Status: wiring-verified only (2026-10-05 HST)

Villa CONTRIBUTING wants before/after on **real** data. For #1507 that means a
published native full-3D checkpoint whose embedded config sets a non-null
`input_pad_depth_to`, then a CPU (or lab) run showing wrong depth / crash vs
correct output.

**Survey:** `scrollprize/ink_3d_dino_guided` (`ckpt_78k_fullsup.pth`, ~1.70 GB)
is the public native-3D villa-lineage checkpoint. Its `config.json` has **no**
`input_pad_depth_to` field (`model_config` only has `autoconfigure` /
`z_projection_mode`). Downloading and running it would **not** exercise this
bug. No other published villa native-3D checkpoint with a non-null pad setting
was found in this pass. A 142M-param 256³ U-Net is also a poor CPU interactive
validation target even though disk (~100 GB free) would allow the download.

**What is verified:**
| Check | Result |
| --- | --- |
| `origin/main` `_load_native_model` passes `input_pad_depth_to` | **No** |
| `/tmp/v8clean` (patched) passes kwarg | **Yes** |
| `TargetModel(..., input_pad_depth_to=5)` pads depth 3→5 | **Yes** (unit / wiring) |
| Full `test_native_full3d_inference.py` after patch | **15 passed** |

Artifacts: `real-data-2026-10-05/SUMMARY.json`, pytest logs in this folder.
