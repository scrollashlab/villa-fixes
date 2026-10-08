# villa#1522 — mesh meta.json scale does not distinguish frames

Upstream: https://github.com/ScrollPrize/villa/issues/1522

## Problem

`meta.json` `"scale"` means grid cells per voxel of **that mesh's own scan**.
Segments often ship several meshes that all declare nearly the same `scale`
(e.g. `0.05`) while voxel sizes in the directory name differ by up to ~40×.
Consumers that treat matching `scale` as “same frame” silently mix coordinates.

## Fix (Python)

- Document the trap in `vesuvius/tifxyz/API.md`.
- Optional `voxel_size_um` field on `meta.json` (reader/writer first-class).
- New `vesuvius.tifxyz.meta_frames`: parse `-<float>um` from directory names,
  annotate existing `meta.json`, detect same-scale / different-voxel-size
  groups, and `frames_comparable()`.
- **Scale equality uses `math.isclose` with `SCALE_RTOL=1e-6` (`SCALE_ATOL=0`)**:
  open-data metas mix JSON `0.05` with float32→float64 `0.05000000074505806`
  (observed rel ≈ 1.49e-8 on PHercParis4 / PHerc0172). `1e-6` is ~67× that gap
  and still far tighter than intentional scale steps (e.g. 0.05 vs 0.1).

Does not change C++ writers, which still omit the field until updated.

## Base revision

Verified against villa `main` @ `0e14cf48c8cee74b11e5e40a9d1d520b74e35423`
(2026-10-05 HST).

## Apply

```bash
cd /path/to/villa
git am 0001-tifxyz-record-optional-voxel_size_um-and-detect-scal.patch
```

## Tests

```bash
PYTHONPATH=vesuvius/src python -m pytest vesuvius/tests/tifxyz/ -q
```

Verified on a **full** villa checkout (no stubs) at `/tmp/v8clean` =
`0e14cf48` + all 8 handoff patches, `/workspace/envs/zarr3` (2026-10-05 HST):
**43 passed** across `vesuvius/tests/tifxyz/` (includes the 12 `test_meta_frames`
float-tolerance regressions). Log: `real-data-2026-10-05/pytest-tifxyz-v8clean.log`.

Do **not** cite `experiments/villa-1522-evidence/stack8-verify` — that tree
previously had stubbed `vesuvius.data` / `vesuvius.install` and fails the lab's
no-stubs gate.

## Evidence on real scroll data (2026-10-05 HST)

**Env:** `/workspace/envs/zarr3` (CPython 3.13.5).  
**Trees:** unmodified `origin/main` @ `0e14cf48` vs same tip + this patch only.  
**Data:** public `vesuvius-challenge-open-data` metas (CC BY-NC 4.0), anonymous HTTPS — see `real-data-2026-10-05/OPEN_DATA_NOTE.txt`.  
**Script / raw output:** `real-data-2026-10-05/probe_1522_frames.py`, `probe-before.txt`, `probe-after.txt`, `SUMMARY.json`.

### What goes wrong without this API (numbers)

**Before** here means the **naive same-scale rule a consumer would apply** —
“matching `scale` ⇒ same physical frame; reuse first mesh’s µm.” Unmodified
`main` has **no** `meta_frames` module, so there is no library API to refuse
that merge; the before probe measures that consumer footgun on real metas.

| Segment group | Meshes | dirname µm spread | Worst naive/true bbox-diag ratio |
| --- | ---: | ---: | ---: |
| PHercParis4 `20230702185753` | 4 | **40.33×** (1.129…45.532) | **7.01×** (1.129um mesh interpreted at 7.91um) |
| PHercParis4 `20230929220926` | 3 | **18.97×** | **3.30×** |
| PHerc0139 `20250108000000-w025_…` | 5 | **8.29×** | **8.29×** |
| PHerc0172 same-µm twins (contrast) | 2 | **1.00×** | 1.00× (no footgun) |

Paris4-40× detail (ref_um=7.91): true µm/grid-cell is 22.58 / 48 / 158.2 / 910.64 across the four remaps; naive forces all to 158.2. True bbox diagonals in µm are ~112k for every remap (physically consistent segment); naive diagonals explode to **0.17×–7.01×** of truth. TIFF median-edge check on 7.91um vs 45.532um meshes: naive/true edge ratio **0.1737** (= 7.91/45.532).

### What the patch changes on the same fixtures (after float-tolerance fix)

| Group | `find_ambiguous_scale_frames` | `annotate_meta_voxel_size_um` | `frames_comparable` after annotate |
| --- | --- | --- | --- |
| Paris4-40× | 1 group, spread **40.33×**, **4 of 4** meshes (µm {1.129,2.4,7.91,45.532}) | writes all 4 metas | all cross-µm pairs **False** |
| Paris4-19× | 1 group, **18.97×**, 3 of 3 | writes 3 | all pairs **False** |
| PHerc0139-8× | 1 group, **8.29×**, 5 of 5 | writes 5 | cross-µm **False**; the two **2.403um** twins **True** |
| PHerc0172 same-µm | **0** ambiguous groups | writes 7.91 on both | pair **True** (scale jitter tolerated) |

Physical µm/grid-cell after annotate matches dirname truth (22.58 / 48 / 158.2 / 910.64 on Paris4-40×).

### Plain limits (do not overclaim)

1. The patch **does** change real-data behavior: detection + annotate + comparable gate for differing `voxel_size_um`. It does **not** rewrite C++ writers or auto-fix the public bucket.
2. Earlier exact-float builds of this patch missed Paris4’s 7.91 meta (`0.05` vs `0.050000000745…`) and falsely rejected PHerc0172 twins; those are fixed with `SCALE_RTOL=1e-6` and covered by regression tests using the exact observed floats.

## Full handoff stack

All **8** handoff patches (1970, 1481, 1522, tifxyz-audit, 1520, 1586, 1300, 1507) `git am` cleanly on `0e14cf48` (log: `real-data-2026-10-05/stack8-apply.log`). Full `vesuvius/tests/tifxyz/` on `/tmp/v8clean` (no stubs): **43 passed**. Standalone `tools/tifxyz-audit`: **15 passed**.

Author: Scroll Ash Lab \<scrollash.lab@gmail.com\>.
