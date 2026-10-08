# villa-downscale — `vesuvius.tifxyz` ignores the open data's `original_volume_downscale` (fix)

Upstream: no villa issue (id `villa-downscale`). This is a `git format-patch`, not an upstream PR. Related: [#1734](https://github.com/ScrollPrize/villa/issues/1734), [#1522](https://github.com/ScrollPrize/villa/issues/1522), [#1727](https://github.com/ScrollPrize/villa/issues/1727); also [#1618](https://github.com/ScrollPrize/villa/issues/1618) / [#1731](https://github.com/ScrollPrize/villa/pull/1731) / [#1769](https://github.com/ScrollPrize/villa/pull/1769)  
Evidence: `villa-downscale/` (`README.md`, the patch, `docs/preregistration.md` + sha256, `results/`, `tests/`). The transform rule and offsets come from `xframe/`.  
Credit: kadenpool (#1734, #1769, #1731), gaogao94 (#1734 comment), bkalita-git (#1618), jonmarrs (#1522), ge-al (#1727)  
Author on patch: Scroll Ash Lab \<scrollash.lab@gmail.com\> (AI-assisted)

## Problem

In 112 of 323 open-data segments (2026-10-07 catalog: PHercParis4 ×4 67, PHerc0139 ×4 38, PHerc0500P2 ×2 7), the `mesh/intermediate/tifxyz_normalized` coordinates are stored at 1/s of the segment's original volume.

- The factor s is only given as the catalog field `samples[S].segments[G].properties.original_volume_downscale`. The mesh's `meta.json` does not carry it (checked on 112/112).
- VC3D's Open Data cache applies it, and the published transformed meshes include it.
- The `vesuvius` Python package has no reference to it at villa `e0bbb8b4`. `read_tifxyz` therefore silently returns coordinates 2× or 4× too small, which is centimetres off.

## What changed

- **`read_tifxyz(path, downscale=s)`.** Applies the factor through the existing `Tifxyz.retarget(1/s)`:
  - valid points are scaled bit-exactly and holes stay `-1`;
  - the bbox is recomputed and the grid scale is divided by s;
  - the factor is recorded in `meta.json` extras.
- **Never scales twice.** A mesh already marked as scaled, by this package or by VC3D's `vc_open_data_coordinates_scaled_to_original_volume`, raises instead.
- **New `vesuvius.tifxyz.open_data` module** (offline):
  - `original_volume_downscale(catalog, sample, segment)` reads the real catalog field, accepting a segment id or `long_id` and a plain or gzip catalog;
  - `read_open_data_normalized(path, catalog)` infers sample and segment from the bucket layout.
- **`OpenDataDownscaleWarning`.** Emitted when a `tifxyz_normalized` directory is read without `downscale=`. `downscale=1` silences it.
- **Docs.** An `API.md` section. Default behaviour is otherwise unchanged.

## Real-data numbers (pre-registered 2026-10-07 11:28:30 HST, before scoring)

The run covered 6 segments (smallest + median normalized mesh per scroll), **all 23 of their derived meshes** and 142,749,273 compared cells.

- Both arms load the same local copy of the normalized mesh:
  - villa `main` `read_tifxyz` (unpatched);
  - `read_open_data_normalized` (patched).
- Each arm then gets the catalog matrix, xframe's VC resampler to the published grid, and a cell-by-cell comparison with the published mesh.

| Scroll (s) | Meshes | Patched worst cell | Patched cells > 0.5 vox | Validity mismatches | Unpatched median offset | Unpatched max |
|---|---:|---|---:|---:|---|---|
| PHerc0139 (×4) | 9 | 0.0088 vox / 0.0195 µm | 0 | 0 | 47.1–72.8 mm | 78.7 mm |
| PHercParis4 (×4) | 8 | 0.0309 vox / 0.0389 µm | 0 | 0 | 81.8–99.2 mm | 142.2 mm |
| PHerc0500P2 (×2) | 6 | 0.0048 vox / 0.0106 µm | 0 | 0 | 25.2–26.3 mm | 35.8 mm |

The pre-registered pass rules all held on **23/23** meshes:
- patched max ≤ 0.5 vox, with no cells > 0.5 and no validity mismatches;
- unpatched median ≥ 1,000 vox and ≥ 10 mm;
- unpatched median within 2% of xframe's earlier published offsets. The largest difference was 0.30%.

The patched points are bit-exact s × the unpatched points on all 6 segments. Read directly as original-volume voxels (no transform), the unpatched points are 25.3–98.1 mm off (per-segment median).

## Tests

Clean env (Python 3.13.5, numpy 2.5.3, tifffile 2026.9.20, `PYTHONPATH=src`).

- **New tests.** 12 tests fail on `main` (12 failed, each individually) and pass patched (12 passed).
- **Existing suite.**

  | Tree | Failed | Passed | Skipped |
  |---|---:|---:|---:|
  | `main` | 2 | 227 | 6 |
  | Patched | 2 | 239 | 6 |
  | 9-patch stack + this patch, on `0e14cf48` | 2 | 253 | 6 |
  | 9-patch stack + this patch, on `e0bbb8b4` | 2 | 253 | 6 |

  The same 2 environment-only CLI-help failures (missing `nnunetv2` / `pytorch_optimizer`) occur with and without the patch.
- **Stacking.** Plain `git am` applies cleanly on bare `e0bbb8b4` and after the 9-patch stack in README order on both bases (`villa-1855` excluded).

## Limitations

- **Coverage.** One catalog snapshot, and 6 of the 112 segments (23 of their 414 derived meshes) checked on real data. xframe's 902/902 covers the scaling rule corpus-wide.
- **Matrices.** The check proves the loader matches the publishing pipeline, not that any catalog matrix is correct.
- **Warning.** It keys on the bucket path layout. A renamed copy loads silently, so the catalog stays the source of truth.
- **VC3D marker.** Interop is unit-tested only. VC3D was not run.
- **Segments with s = 1.** Covered by unit tests only.
- **Upstream.** Not an upstream PR; nothing has been posted upstream.

## How to reproduce

See `villa-downscale/README.md` § Reproduce: `scripts/fetch_normalized.py`, then `load_arm.py` for each arm, `score.py` and `run_checks.sh`. The open-data payloads are CC BY-NC and not redistributed; `results/normalized-inputs-2026-10-07.json` lists their paths and sha256.
