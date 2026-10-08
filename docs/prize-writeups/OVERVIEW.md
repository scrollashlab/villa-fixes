# Scroll Ash Lab — villa fixes overview (Progress Prize / GitLab)

**Lab:** Scroll Ash Lab (`scrollash.lab@gmail.com`)  
**Work:** AI-assisted (Grok Bot) engineering against ScrollPrize/villa.  
**Evidence root:** this repository (https://gitlab.com/scroll-ash-lab/villa-fixes) (READMEs, JSON, OPEN_DATA_NOTE files).  
**Base tip verified:** villa `main` @ `0e14cf48` (also earlier `5a4388f`).  
**Excluded from shipping:** `#1855` (min-edge retain; on hold).

## Headline tool item: `xframe` (added 2026-10-07)

**What:** a standalone CPU CLI and library (MIT) with four commands: `frames` / `explain` / `verify` / `convert`. It works on the open data's cross-frame tifxyz meshes. It is not a villa patch.  
**Status:** published on GitLab at `xframe/`.  
**Evidence:** `xframe/` (`FINDINGS.md`, `results/`). Write-up: `xframe.md`.  
**Evidence class:** **Real-data, full corpus.** Public catalog snapshot 2026-10-07 09:14 HST; payloads streamed, none redistributed.

- **902/902** published cross-frame meshes reproduce point by point as `regrid(T · (s · normalized))`:
  - 707 derived + 195 byte-identical copies;
  - 307 segments, 11 samples;
  - 4.79 billion cells, 0 validity mismatches;
  - worst cell 0.086 µm;
  - grid shape predicted = published, 902/902.
- **Downscale trap.**
  - Affected: 112 segments (PHercParis4 ×4: 67; PHerc0139 ×4: 38; PHerc0500P2 ×2: 7).
  - Their `tifxyz_normalized` coordinates are in a 1/s grid.
  - `meta.json` does not say so, and the `vesuvius` Python package has no code for it (source search, villa @ `e0bbb8b4`). The `villa-downscale` patch (third item below) adds it.
  - Measured offset if the factor is ignored: **13–146 mm** per point; per-scroll medians **25–26 / 46–73 / 80–100 mm** (PHerc0500P2 / PHerc0139 / PHercParis4).
  - The catalog factor is known (#1734, #1727); no issue we found (2026-10-07) states the mesh-side gap or measures the offset. Related to #1522.
- **Corollaries.**
  - Matrix errors propagate exactly into every derived mesh, so fixing a matrix (e.g. #1843's PHerc1667 1.129 µm chain, 19 meshes) means regenerating meshes.
  - **67.2 GB** (480 meshes) of finer-frame meshes are bilinear up-sampled only. Counting any regrid factor > 1 gives 518 instead (FINDINGS §4).
- **Tests:** 19/19 in a clean venv (16 offline synthetic + 3 live bucket), re-run independently by the parent and again from the handoff copy.
- **Caveats:** consistency ≠ correctness (no matrix, placement or ink claims); single catalog snapshot; AI-assisted.
- **Credits:** #1468/#1469 `tifxyz-audit` (jaideepsaipadhi; distinct tool despite the name overlap with the lab's earlier entry point), #1522 (jonmarrs), PR #1944, #1835 / PR #1994, #1843, #1845 / PR #1851, #1734, #1727.

## Second headline item: `sv-canvas-1727` (added 2026-10-07)

**What:** a pre-registered, metadata-only measurement that answers the canvas-size question in villa #1727 (canvas sizes only; voxel content not checked). It uses xframe's verified transform rule. It is not a villa patch.  
**Status:** published on GitLab at `sv-canvas-1727/`.  
**Evidence:** `sv-canvas-1727/` (`README.md`, `docs/preregistration.md` + sha256, `results/`). Write-up: `sv-canvas-1727.md`.  
**Evidence class:** **Real-data, full catalog**, metadata only (2026-10-07 snapshot).

- **692/692** published surface volumes reproduce exactly (`canvas_size` and level-0 shape) from the mesh the catalog names in `creation_info.derived_from`. The rule is the renderer's own canvas formula with the catalog's recorded `scale` and `group-idx`.
- This covers **627/628** of #1727's inventory. One volume has been removed from the catalog (#1892/#1963), so at least 365 of #1727's 366 "non-reproducible" volumes reproduce.
- **Mechanism.** Renders were made from the published transformed meshes, which are regridded separately per axis (xframe, 902/902). Worked example: 354×331 → 3012×2817 → 30120×28170.
- **Why it was missed.** #1727's careful inventory listed only undotted mesh directory names, so it never compared the `*.tifxyz` transformed meshes.
- **Checks.**
  - Pre-registered sample: 29/29 present; controls 15/15.
  - Wrong-mesh control: no other mesh matches where the named mesh was regridded.
  - Parent independent spot-check: 10/10.
- **Caveats.**
  - Canvas sizes only, not voxel correctness.
  - We cannot tell whether `metadata.json` had the source fields in September.
  - Our class reconstruction gives 352 vs #1727's 366 (used only for sampling).
  - Single snapshot; AI-assisted.
- **Credits:** #1727 ge-al, gaogao94 (comment), #1699 (ge-al, Bullo27), #1845, PR #1901, #1892/#1963.

## Third headline item: `villa-downscale` (added 2026-10-07)

**What:** a villa `git format-patch` (MIT, not an upstream PR). It makes the `vesuvius` Python package apply the open data's `original_volume_downscale` to `tifxyz_normalized` meshes. There is no villa issue for it; related issues are #1734, #1522 and #1727.  
**Status:** published on GitLab at `villa-downscale/` (check_bundle OK, 2026-10-07).  
**Evidence:** `villa-downscale/` (`README.md`, patch, `docs/preregistration.md` + sha256, `results/`, `tests/`). Write-up: `villa-downscale.md`.  
**Evidence class:** **Real-data, pre-registered** before/after on 6 segments / 23 published meshes (2026-10-07 snapshot), plus unit tests.

- **Change.**
  - `read_tifxyz(path, downscale=s)`: exact pre-scale via the existing `retarget(1/s)`; bbox and grid scale updated.
  - Catalog helpers `original_volume_downscale` / `read_open_data_normalized`, reading the real `metadata.json` field, offline.
  - `OpenDataDownscaleWarning` when a `tifxyz_normalized` dir is read without `downscale=`.
  - Never scales twice: it respects its own marker and VC3D's `vc_open_data_coordinates_scaled_to_original_volume`.
- **Real data (23/23 pass the pre-registered rules).**
  - Patched loader + catalog matrix reproduces every published derived mesh: worst cell **0.0309 vox / 0.039 µm**, 0 cells > 0.5 vox, 0 validity mismatches, over 142.7 M cells.
  - Unpatched `main` is off by a median of **25.2–99.2 mm** per mesh (max 142.2 mm), within 0.30% of xframe's published offsets.
- **Tests.**
  - 12 new tests: 12 fail on `main`, 12 pass patched.
  - Existing suite unchanged: 227 → 239 passed. The same 2 env-only CLI-help failures appear with and without the patch.
  - Applies cleanly on bare `e0bbb8b4` and after the 9-patch stack on `0e14cf48` and `e0bbb8b4` (253 passed on both stacked trees).
- **Caveats:**
  - 6 of 112 affected segments checked on real data;
  - no matrix-correctness claim;
  - the warning keys on the bucket path layout;
  - the VC3D-marker interop is unit-tested only;
  - AI-assisted; not posted upstream.
- **Credits:** kadenpool (#1734, #1769, #1731), gaogao94, bkalita-git (#1618), jonmarrs (#1522), ge-al (#1727).

This note summarizes the **9 shipping items** (eight villa patches + the `tifxyz-audit` entry-point patch). It does not invent metrics; figures come from per-folder READMEs / `SUMMARY.json` / `AUC_TABLE.json`.

## The nine shipping fixes

| # | Folder | One-line | Evidence class |
|---|--------|----------|----------------|
| 1648 | `villa-1648/` | Log `depth_order` + `in_plane_scale_um`; INFO both-dirs; WARN fine scale only | **Real-data** holdout AUC (w/ caveats) |
| 1586 | `villa-1586/` | Seed CacheStore LRU so `cache_max_gb` bounds disk across reopen | **Real-data** cache-byte probe |
| 1522 | `villa-1522/` | Optional `voxel_size_um` + `meta_frames` helpers (`SCALE_RTOL=1e-6`) | **Real-data** open-data metas |
| tifxyz-audit | `villa-tifxyz-audit/` + `tools/tifxyz-audit/` | CLI QA on mesh meta / siblings (apply after 1522) | Real-data smoke + unit tests |
| 1481 | `villa-1481/` | Flat ink `robust_mad` excludes reader padding | **Real-data** Paris4 CT window |
| 1507 | `villa-1507/` | Native full-3D loader passes `input_pad_depth_to` | **Wiring-only** (unit/wiring) |
| 1520 | `villa-1520/` | README entrypoints match `[project.scripts]` | Docs + regression tests |
| 1300 | `villa-1300/` | README warns pip on 3.14 → vesuvius 0.1.10 | Live pip dry-run resolve |
| 1970 | `villa-1970/` | Plain zarr + `valid_patch_find_resolution` ≥ 1 → no OOB starts | Synthetic CPU tests; **prefer upstream PR #1980** |

Apply order (clean on `0e14cf48`, per handoff README):

```text
1970 → 1481 → 1522 → tifxyz-audit → 1520 → 1586 → 1300 → 1507 → 1648
```

(Do not include `villa-1855/`.) `villa-downscale/` applies after the stack (or on bare `main` @ `e0bbb8b4`), verified 2026-10-07.

## Real-data proven vs wiring-only

**Real-data (public open-data / HF; payloads not redistributed):**

- **#1648** — `pherc0814-46527` validation_mask re-score; L2 forward AUC **0.8705 / 0.8462** (seed42/43). See `1648.md`.
- **#1586** — PHercParis4 2.4 µm zarr, `cache_max_gb=0.03`: unmodified reopen ~**1.96×** budget; patched stays ~**0.98×**. See `1586.md`.
- **#1522** — Paris4 / PHerc0139 / PHerc0172 metas: naive same-scale footgun up to **~7.01×** bbox-diag error (Paris4-40×); after annotate, cross-µm pairs incomparable. See `1522.md`.
- **#1481** — Paris4 45.532 µm masked chunk window: buggy pad-then-norm MAE **~3.17 / ~2.32**; fixed **0 / 0**. See `1481.md`.
- **#1300** — CPython **3.14.8 → vesuvius 0.1.10**; **3.13.5 → 0.2.4** (pip dry-run reports in folder).
- **tifxyz-audit** — smoke on public Paris4 segment metas (reports only in repo).

**Wiring / synthetic / docs (do not overclaim):**

- **#1507** — Explicitly **wiring-verified only**. No published native-3D checkpoint with non-null `input_pad_depth_to` found in the 2026-10-05 survey (`scrollprize/ink_3d_dino_guided` has no such field). Unit: **15 passed**.
- **#1970** — Synthetic plain-array repro (**5 passed**). Independent upstream [PR #1980](https://github.com/ScrollPrize/villa/pull/1980) fixes the same bug and is the recommended merge path; this folder is retained as earlier independent work.
- **#1520** — Docs + **3 passed** entrypoint assertions (4 after #1300).

## Caveats that must stay in any public write-up

1. **#1648 / w035 training overlap.** Windows A/B on `pherc0139-w035` overlap training (`pherc0139-w035` in checkpoint datasets; no `validation_mask`). L2-forward AUC ≈ **0.995–0.999** on those windows is **not** a generalization claim. Primary table is holdout **46527** (still a training *segment*; holdout is a spatial validation-mask carve-out — adjacency leakage possible).
2. **#1648 / depth flip vs issue.** On public S3 w035, CLI **`forward` beats `reverse`**; we could **not** reproduce the issue’s reverse-better w035 table on that store. Tutorial notes `--flip-normals` matches published-render / training-label orientation. Limitation: author’s exact `prepare_9um_isotropic_input` path was not re-run end-to-end. Product wording (recommend `--direction both`) stays.
3. **#1522 / float tolerance.** Scale equality uses `math.isclose` with **`SCALE_RTOL=1e-6`** (`SCALE_ATOL=0`). Open-data metas mix JSON `0.05` with float32→float64 `0.05000000074505806` (rel ≈ 1.49e-8). Exact-float builds falsely missed Paris4’s 7.91 meta and rejected PHerc0172 same-µm twins; regressions cover the observed floats.
4. **#1507 / wiring-only.** No CONTRIBUTING-grade real-data before/after.
5. **#1970 / leave to PR #1980.** Do not present our patch as the preferred upstream fix when #1980 exists and looks strictly better (shared helper, unlabeled-FG level follow, patch-cache schema bump).

## Credits (from handoff README)

@mg255 (#1970 diagnosis); prior unmerged #1481 work (#1483/#1646/#1773); @flummoxjr (#1586/#1587); prior unmerged #1507 work (#1645/#1772).

## License / data

Patches: MIT (same lane as villa). Open-data scan payloads are **CC BY-NC 4.0** — **do not redistribute** TIFFs/zarr/npy in the public bundle; point reviewers at S3 / Hugging Face and each folder’s `OPEN_DATA_NOTE` / `OPEN_DATA_NOTE.txt`.
