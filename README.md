# Scroll Ash Lab — villa fixes

Small, tested patches for [ScrollPrize/villa](https://github.com/ScrollPrize/villa),
plus a standalone `tifxyz-audit` CLI.

**Authorship:** AI-assisted lab engineering (Grok Bot / Scroll Ash Lab).

**Contact:** scrollash.lab@gmail.com  
**Public mirror:** https://gitlab.com/scroll-ash-lab/villa-fixes  
**Base tip:** villa `main` @ `0e14cf48`  
**Hold / excluded:** #1855

See [`docs/prize-writeups/`](docs/prize-writeups/) for honest evidence classes, caveats,
and reproduction pointers to public S3/HF data. We do **not** redistribute CC BY-NC
open-data payloads.

See [`docs/negative-results-2026-10/`](docs/negative-results-2026-10/) for two pre-registered negative results (Oct 2026).

See [`xframe/`](xframe/) for the cross-frame mesh audit tool (Oct 2026).
See [`sv-canvas-1727/`](sv-canvas-1727/) for a pre-registered check that all 692 published surface volumes reproduce their canvas size from the catalog-named mesh (villa #1727, Oct 2026).
See [`villa-downscale/`](villa-downscale/) for a patch that makes `vesuvius.tifxyz` apply the open data's `original_volume_downscale` to `tifxyz_normalized` meshes; pre-registered before/after on 23 published meshes (Oct 2026).
See [`catalog-qa-audit/`](catalog-qa-audit/) for a pre-registered metadata audit of all 1,531 published meshes across 323 segments; it found 15 segments whose declared width/height don't match mesh grid ÷ scale (findings only, no patch; Oct 2026).
See [`gpu-1648-heldout/`](gpu-1648-heldout/) for a pre-registered held-out GPU test of the `villa-1648` in-plane-scale warning on 3 validation masks × 2 seeds; it confirms the warning (3/3 segments, 2/3 required; code and metrics only; Oct 2026).
See [`gpu-1648-intermediate-scale/`](gpu-1648-intermediate-scale/) for a pre-registered test of the `villa-1648` warning at an intermediate scale (4.68 µm vs 9.36 µm) on PHerc0841, which is held out of ink_9um's training; 3/3 segments support the warning (code and metrics only; Oct 2026).
See [`500p2a-label-alignment/`](500p2a-label-alignment/) for a pre-registered check of whether the 500p2a ink labels are rigidly misaligned with the render; verdict ALIGNED-UNREAD, so rigid misalignment does not explain chance-level scores there (negative result, code and metrics only; Oct 2026).
See [`bucket-pyramid-audit/`](bucket-pyramid-audit/) for a pre-registered census of the 76 ink render pyramids in the `scrollprize/datasets` bucket: in 18 stores level 1 holds only the first 33 of 65 planes while declaring in-plane-only scale, traced to villa `vc_render_tifxyz` builds between #774 and #804 (findings only, code and metrics only; Oct 2026).
See [`docs/prize-writeups/pherc0800-ensemble/`](https://gitlab.com/scroll-ash-lab/villa-fixes/-/tree/main/docs/prize-writeups/pherc0800-ensemble) for a pre-registered five-model ink ensemble, with and without depth sharpening, on the six published PHerc0800 segments; the PHerc0009B control passed and 0 of 6 targets reached the text screen threshold (negative result, code and metrics only; Oct 2026).

## Shipping fixes

| Folder | What | Evidence class |
|--------|------|----------------|
| `villa-1648/` | report `depth_order` + `in_plane_scale_um`; INFO both-dirs; WARN fine scale | Real-data holdout AUC (w/ caveats) |
| `villa-1586/` | seed CacheStore LRU so `cache_max_gb` bounds disk | Real-data cache-byte probe |
| `villa-1522/` | optional `voxel_size_um` + `meta_frames` (`SCALE_RTOL=1e-6`) | Real-data open-data metas |
| `villa-tifxyz-audit/` + `tools/tifxyz-audit/` | mesh meta QA CLI (apply after 1522) | Real-data smoke + unit tests |
| `villa-1481/` | flat ink `robust_mad` excludes reader padding | Real-data Paris4 CT window |
| `villa-1507/` | native full-3D loader passes `input_pad_depth_to` | **Wiring-only** |
| `villa-1520/` | README entrypoints match `[project.scripts]` | Docs + tests |
| `villa-1300/` | README: pip on Python 3.14 → vesuvius 0.1.10 | Live pip dry-run |
| `villa-1970/` | plain zarr + `valid_patch_find_resolution` ≥ 1 | Synthetic; **prefer upstream [PR #1980](https://github.com/ScrollPrize/villa/pull/1980)** |

## Apply order (verified clean on `0e14cf48`)

```bash
git am villa-1970/0001-*.patch
git am villa-1481/0001-*.patch
git am villa-1522/0001-*.patch
git am villa-tifxyz-audit/0001-*.patch   # requires 1522 first
git am villa-1520/0001-*.patch
git am villa-1586/0001-*.patch
git am villa-1300/0001-*.patch           # requires 1520 first
git am villa-1507/0001-*.patch
git am villa-1648/0001-*.patch
```

Do **not** apply `villa-1855/` (on hold).

## Scope notes

- #1507 has wiring tests only; there is no real-data before/after.
- The w035 ~0.99 AUC is on windows that overlap ink_9um's training data (no validation_mask), so it is not a held-out result; the #1648 primary table uses the validation_mask carve-out on 46527.
- The #1648 reverse-better w035 table from the issue was not reproduced on public S3.
- No open-data scan payloads are redistributed (see per-folder `OPEN_DATA_NOTE` / `OPEN_DATA_NOTE.txt`).
- #1970: we recommend independent upstream PR #1980 over our earlier patch.

## Credits

@mg255 (#1970 diagnosis); prior unmerged #1481 work (#1483/#1646/#1773); @flummoxjr (#1586/#1587); prior unmerged #1507 work (#1645/#1772).

## Bundle hygiene

This directory must not contain open-data scan payloads or stub/`DO-NOT-CITE` logs.
See `REMOVED_OPEN_DATA_PAYLOADS.txt` and `../check_bundle.sh` in the lab handoff.
