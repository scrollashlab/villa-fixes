# villa-downscale: `vesuvius.tifxyz` applies the open-data `original_volume_downscale` to `tifxyz_normalized` meshes

Scroll Ash Lab, 2026-10-07 (HST). **AI-assisted:** an AI agent designed, wrote, tested and measured this.
This is a `git format-patch` for ScrollPrize/villa, published on GitLab alongside the lab's other villa fixes at `villa-downscale/`. It is **not** an upstream PR and nothing has been posted upstream.

- **Id:** `villa-downscale` (there is no villa issue for this gap).
- **Related:** #1734 (the catalog's `bbox_transformed` is the stored bbox pushed through this factor), #1522 (meta `scale` does not identify the frame), #1727 (renders reproduce from `tifxyz_normalized` at ×4.0). Also #1618 / #1731 / #1769 (the `-1` bbox marker on the same segments).
- **Patch:** `0001-tifxyz-apply-open-data-original_volume_downscale-to-.patch`, sha256 `f94dde2d2e646682dafafd09f98390c769a3965d404a9f4de9fe82c728bade2d`. 5 files, +470 lines, no deletions. Author Scroll Ash Lab <scrollash.lab@gmail.com>.
- **Base:** villa `main` @ `e0bbb8b4` (the tip at 2026-10-07 11:44 HST). It also applies on top of the lab's 9-patch stack, on `0e14cf48` and on `e0bbb8b4` (see Tests).

## Problem

In the open-data bucket every segment has a normalized mesh at `<sample>/segments/<long_id>/mesh/intermediate/tifxyz_normalized/`. On the 2026-10-07 catalog, **112 of 323 segments** store those coordinates at `1/s` of the segment's original volume:

| Scroll | s | Segments |
|---|---|---|
| PHercParis4 | 4 | 67 |
| PHerc0139 | 4 | 38 |
| PHerc0500P2 | 2 | 7 |

- The factor is in the bucket catalog `metadata.json`, at `samples[<sample>].segments[<id>].properties.original_volume_downscale`. It is present on all 323 segments, as 1, 2 or 4.
- The mesh's own `meta.json` does not record it. We checked 112/112 of these meshes (xframe `results/downscale-offsets-2026-10-07.json`, `meta_has_downscale: false`). The six used below carry only `bbox`, `format`, `scale`, `type`, `uuid`.
- VC3D already applies the factor (`apps/VC3D/OpenDataSegmentCache.cpp`, `applyOriginalVolumeDownscale` → `transformSurfacePoints(surface, downscale, …)`). The published transformed meshes (`<id>-on-<volume>-<µm>.tifxyz`) include it too (xframe, 902/902).
- The `vesuvius` Python package has no reference to it. A `git grep` for `original_volume_downscale` / `volume_downscale` under `vesuvius/` at `e0bbb8b4` returns nothing.
- So `vesuvius.tifxyz.read_tifxyz` returns these coordinates 2× or 4× too small, with no warning. Measured on the 23 meshes below, that puts points **25–99 mm (median) and up to 142 mm** from where the published meshes have them.

## Change

All additions are in `vesuvius/src/vesuvius/tifxyz/`. Default behaviour is unchanged apart from a new warning.

1. **`read_tifxyz(path, downscale=s)`**, a new optional argument.
   - It calls the existing `Tifxyz.retarget(1/s)`. Valid coordinates are multiplied by `s` (bit-exact for 2 and 4) and invalid points stay `-1`.
   - The bbox is recomputed from the valid points, and the grid `scale` is divided by `s`, so `full_resolution_shape` stays one pixel per original-volume voxel.
   - It records `extra["original_volume_downscale_applied"] = s`, which `write_tifxyz` saves.
   - A `factor` that is ≤ 0, NaN or inf raises `ValueError`.
2. **Never scale twice.** A mesh whose `meta.json` carries `original_volume_downscale_applied`, or VC3D's `vc_open_data_coordinates_scaled_to_original_volume` (written by VC3D's Open Data cache after it scales a segment), is treated as already in original-volume voxels. Any `downscale` other than 1 raises `ValueError`.
3. **Catalog helpers, in the new `open_data.py`.** None of them use the network.
   - `original_volume_downscale(catalog, sample, segment)` reads the real catalog field. It accepts a segment id or a `long_id`, and a plain or gzip `metadata.json` path or the parsed dict. It returns 1.0 if the field is absent.
   - `read_open_data_normalized(path, catalog)` takes sample and segment from the bucket-layout path (or `sample=` / `segment=`) and applies the factor.
   - `load_open_data_catalog(path)`.
4. **Warning path.** `read_tifxyz` on a `…/mesh/intermediate/tifxyz_normalized` directory without `downscale=` emits `OpenDataDownscaleWarning`, which names the catalog field and the fix. `downscale=1` silences it.
5. **Docs.** There is a new `API.md` section. `list_tifxyz` / `TifxyzInfo.bbox` stay unscaled, because they never see the catalog; `TifxyzInfo.load(downscale=s)` applies the factor.

```python
from vesuvius.tifxyz import read_open_data_normalized, original_volume_downscale, read_tifxyz
surf = read_open_data_normalized(".../PHerc0139/segments/20250108000004-w029_2025010827/mesh/intermediate/tifxyz_normalized",
                                 "metadata.json")                    # local copy of the bucket catalog
s = original_volume_downscale("metadata.json", "PHerc0139", "20250108000004")   # 4.0
surf = read_tifxyz(path, downscale=s)
```

## Real-data before/after (pre-registered)

**Pre-registration.** `docs/preregistration.md` was written at 2026-10-07 11:28:30 HST, before any real-data scoring. Its sha256 `181bd431…` is in `docs/preregistration.sha256` and is recorded in the result JSON.

**Selection.** It fixed 6 segments: per scroll, the smallest and the median by normalized-mesh bytes (xframe `results/corpus-mesh-sizes-2026-10-07.json`). Every derived mesh of those segments is scored, **23 meshes** and **142,749,273 compared cells**.

**Inputs.** Both arms read the same local copy of each normalized mesh, downloaded anonymously. Files and sha256 are in `results/normalized-inputs-2026-10-07.json`; the payloads are not included.

**Arms.**
- **Unpatched:** `read_tifxyz(dir)` at villa `e0bbb8b4`.
- **Patched:** `read_open_data_normalized(dir, metadata.json)` at the patch commit `f18316b8`.
- `results/load-*.json` records which source tree each arm imported.

**Scoring.** For each arm and mesh:
1. Q = T·P, with T the catalog matrix (original → target volume). The scorer adds no prescale.
2. Resample Q to the published grid with xframe's port of VC's `resamplePointsLinearPreservingInvalids`.
3. Compare cell by cell with the published mesh, streamed from the bucket.

**Pass rule (fixed beforehand).**
- **Patched:** max ≤ 0.5 target voxel, no cell > 0.5, and 0 validity mismatches, on every mesh.
- **Unpatched:** median ≥ 1,000 target voxels **and** ≥ 10 mm on every mesh, and within 2% of xframe's previously published offset for that mesh.

**Result: all three rules pass on 23/23 meshes** (`results/realdata-before-after-2026-10-07.json`, scored 11:47:22 HST).

| Scroll (s) | Meshes | Cells | Patched: worst max | Patched: cells > 0.5 vox | Validity mismatches | Unpatched: median offset | Unpatched: max | vs xframe offsets |
|---|---:|---:|---|---:|---:|---|---|---|
| PHerc0139 (×4) | 9 | 13,960,773 | 0.0088 vox (0.0195 µm) | 0 | 0 | 47.1–72.8 mm (5,046–41,753 vox) | 78.7 mm | ≤ 0.017% |
| PHercParis4 (×4) | 8 | 127,520,721 | 0.0309 vox (0.0389 µm) | 0 | 0 | 81.8–99.2 mm (1,805–86,837 vox) | 142.2 mm | ≤ 0.301% |
| PHerc0500P2 (×2) | 6 | 1,267,779 | 0.0048 vox (0.0106 µm) | 0 | 0 | 25.2–26.3 mm (2,702–11,837 vox) | 35.8 mm | ≤ 0.066% |

- **Patched.** The patched loader's points are bit-exact `s ×` the unpatched points on all 6 segments, with identical validity masks. Its residual is float32 rounding: the median is 2^-10 vox at most coordinates, and the worst cell is 0.039 µm.
- **Unpatched.** Here the catalog transform is applied to unscaled coordinates. Used directly as original-volume voxels (no transform), the same points are 25.3–98.1 mm off (median per segment) and up to 140.7 mm.
- **Detail.** Per-mesh rows are in `results/realdata-table-2026-10-07.md`.
- **Validity.** Mismatches are 0 in both arms, because scaling never changes which cells are valid.

## Tests

Clean env `/workspace/envs/zarr3`: Python 3.13.5, numpy 2.5.3, tifffile 2026.9.20, cv2 5.0.0, zarr 3.4.0, pytest 9.1.1. `vesuvius` is not installed; the tests run with `PYTHONPATH=src`. Logs are in `tests/`.

- **New tests** in `tests/tifxyz/test_open_data_downscale.py`: 12, on a synthetic 12×9 grid with holes, laid out like the bucket, plus a catalog dict shaped like the real one.
  - On `main`: **12 failed** (`pytest-new-tests-on-main.log`). The failures are `TypeError: read_tifxyz() got an unexpected keyword argument 'downscale'` and `AttributeError` for the new names. Each test fails on its own, not as a collection error.
  - Patched: **12 passed** (`pytest-new-tests-patched.log`).
- **Existing suite:** `tests/tifxyz`, `src/vesuvius/tifxyz/test_reader_bbox.py`, `src/vesuvius/tifxyz/test_labels.py`, `tests/tifxyz_label_transfer`, `tests/test_surface_preflight.py`, `tests/test_imports.py`.

  | Tree | Failed | Passed | Skipped |
  |---|---:|---:|---:|
  | `main` | 2 | 227 | 6 |
  | Patched | 2 | 239 | 6 |
  | 9-patch stack + this patch, on `e0bbb8b4` | 2 | 253 | 6 |
  | 9-patch stack + this patch, on `0e14cf48` | 2 | 253 | 6 |

  - The same 2 failures appear on every tree, with and without the patch. They are environment-only: `test_cli_entrypoints_show_help` for `models.training.train` / `models.run.inference` need `pytorch_optimizer` / `nnunetv2`, which this env does not have.
  - The 6 skips are the unbuilt native rasterizer.
- **Stacking** (`stacking-2026-10-07.log`), plain `git am` with no `--3way`:
  - The patch applies on bare `e0bbb8b4`.
  - It also applies after the 9-patch stack in README order (1970 → 1481 → 1522 → tifxyz-audit → 1520 → 1586 → 1300 → 1507 → 1648; `villa-1855` excluded), on `0e14cf48` and on `e0bbb8b4`.
  - Every step applies cleanly.

## Limits

- **Single catalog snapshot (2026-10-07).** The real-data check covers 6 of the 112 affected segments and 23 of their 414 derived meshes. xframe's full-corpus check (902/902) covers the scaling rule itself.
- **What the check proves.** It shows the loader applies the same factor the publishing pipeline applied. It says nothing about whether any catalog matrix is right.
- **Warning scope.** The warning depends on the bucket path layout (`mesh/intermediate/tifxyz_normalized`). A normalized mesh copied to a differently named directory loads without a warning. The catalog is the only reliable source of the factor.
- **No catalog download.** The catalog helpers take a local `metadata.json`; the patch never downloads it.
- **VC3D marker interop.** Recognising `vc_open_data_coordinates_scaled_to_original_volume` follows VC3D's source. It is unit-tested on a synthetic mesh only; we did not run VC3D to produce a cache.
- **Cache keys.** A scaled `Tifxyz` has a different grid `scale`, so cache keys that include it (e.g. patch caches) differ from the unscaled mesh. That is intended.
- **Segments with s = 1** are covered by unit tests, not by the real-data run.
- **Upstream.** This is not an upstream PR; nothing has been posted upstream.

## Novelty check (2026-10-07, ~11:43 HST)

- **Searches.** GitHub issue/PR search in ScrollPrize/villa for:
  - `original_volume_downscale`: 3 hits, #1734, #1769, #1875;
  - `tifxyz_normalized`: #1727;
  - downscale PRs: 8 hits, none about the Python reader;
  - `metadata.json tifxyz`: 26 hits.
- **Read in full, bodies and comments:** #1734, #1769, #1875, plus #1134, #1848 and #1912. #1727 had been read earlier the same day.
- **Result.** None proposes applying the factor in the `vesuvius` Python package.
  - #1734 and #1769 are about the catalog's `bbox_transformed` and VC3D's placeholder bbox.
  - #1731 (merged) made the Python reader recompute a bbox that carries the `-1` marker; the patch's `retarget` also recomputes the bbox from valid points.
- **Earlier work.** The catalog factor itself is known: #1734 uses it, and #1727 found renders reproduce from `tifxyz_normalized` at exactly ×4.0. Our contribution is the Python-side handling plus the measured before/after.

## Reproduce

Scripts are in `scripts/`. Their defaults are the lab's box paths; override with `VDS_CATALOG`, `VDS_CACHE`, `XFRAME_SRC`, `VDS_OFFSETS`.

```bash
python scripts/fetch_normalized.py results/normalized-inputs.json        # 6 normalized meshes -> local cache (CC BY-NC, do not redistribute)
PYTHONPATH=<villa@e0bbb8b4>/vesuvius/src python scripts/load_arm.py unpatched /tmp/arms/unpatched out/load-unpatched-2026-10-07.json
PYTHONPATH=<villa+patch>/vesuvius/src    python scripts/load_arm.py patched   /tmp/arms/patched   out/load-patched-2026-10-07.json
python scripts/score.py /tmp/arms out/realdata-before-after-2026-10-07.json   # streams the 23 published meshes (largest 5259×20841); ran on a 15 GB box
scripts/run_checks.sh                                                         # tests, fail-on-main, stacking (expects the lab's worktrees)
```

After the scored run, `score.py` was changed only in how it finds its input paths (env overrides, `results/` fallback); the scoring code is unchanged. A first, non-blockwise version of the scorer was OOM-killed on the largest mesh before writing any output. It was made blockwise (as xframe `verify` is) and the whole run was repeated. `score.py` reads `out/load-*.json` (or `results/load-*.json`) beside its parent directory, as in the lab's experiment layout (`experiments/villa-downscale/`). It needs the xframe package (`xframe/src`) for the catalog matrices, the bucket reader and the VC resampler.

## Files

- `0001-…patch`: the change.
- `docs/preregistration.md` and `.sha256`.
- `results/`:
  - `realdata-before-after-2026-10-07.json`: per mesh, both arms, pass flags; metadata only.
  - `realdata-table-2026-10-07.md`.
  - `normalized-inputs-2026-10-07.json`.
  - `load-unpatched-2026-10-07.json`, `load-patched-2026-10-07.json`.
  - `score-run-2026-10-07.log`.
- `tests/`: the five logs above.
- `scripts/`: `common.py`, `fetch_normalized.py`, `load_arm.py`, `score.py`, `run_checks.sh`.
- `OPEN_DATA_NOTE.txt`.

## Credits

- kadenpool: #1734, #1769, #1731.
- gaogao94: the #1734 catalog-wide bound.
- bkalita-git: #1618.
- jonmarrs: #1522.
- ge-al: #1727.
- The villa VC3D Open Data cache code supplied the reference behaviour.
- xframe (`xframe/`, published) supplied the transform rule, resampler and offsets this check builds on.

## License

Patch: MIT, the same as villa. Open-data payloads are CC BY-NC 4.0; none are included here.
