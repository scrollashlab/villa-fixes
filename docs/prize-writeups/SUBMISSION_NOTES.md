# Progress Prize submission notes

**Status:** Corrected October form submitted 2026-10-06 (predates xframe, sv-canvas-1727 and villa-downscale).  
**Who did the work:** Scroll Ash Lab, AI-assisted (Grok Bot).

---

## Headline tool item: `xframe` (added 2026-10-07; not yet in any submitted form)

The previously submitted form packet predates `xframe`. Published on GitLab at `xframe/`.

**Suggested title (if the form is updated):** Scroll Ash Lab: `xframe`, full-corpus point-level verification of the open data's cross-frame meshes (902/902), plus nine tested villa tooling fixes

**Short summary:** `xframe` (MIT CLI, AI-assisted) rebuilt all 902 published cross-frame tifxyz meshes from their source mesh and the catalog. It compared every grid cell (4.79 billion) and found all 902 consistent to ≤ 0.086 µm. It showed that in 112 segments the catalog's `original_volume_downscale` factor is not recorded in the mesh files themselves and is not applied by villa's Python package (PHercParis4, PHerc0139, PHerc0500P2): ignoring the factor misplaces points by 13–146 mm. It also showed that 67.2 GB of finer-frame meshes are interpolation only.

**Form bullet (headline, before the villa items):**

0. **`xframe`.** The commands are `frames` / `explain` / `verify` / `convert`.
   - **Full corpus 902/902 CONSISTENT** (707 derived + 195 copies, 11 samples, 0 validity mismatches, worst cell 0.086 µm).
   - **Downscale trap:** 112 segments whose `tifxyz_normalized` meta.json omits `original_volume_downscale`, with no handling in the `vesuvius` Python package. The measured offset if ignored is 25–100 mm median per scroll; `explain` warns and `convert` applies the factor.
   - **Matrix fixes require mesh regeneration**, e.g. #1843.
   - **67.2 GB of up-sampled-only finer meshes** (480; 518 by the any-up-sampling definition).
   - **Tests:** 19/19 in a clean venv, including 3 live-bucket tests.
   - **Caveats:** no matrix-correctness, placement or ink claims; single catalog snapshot.
   - **Credit:** #1468/#1469 `tifxyz-audit` (jaideepsaipadhi), #1522, PR #1944, #1835/PR #1994, #1843, #1845/PR #1851, #1734.
   - Evidence: `xframe/FINDINGS.md`, `docs/prize-writeups/xframe.md`.

**Non-claims for xframe:**
- It does not show any matrix is right or wrong.
- It does not open misplaced meshes against volumes; the offsets are computed from the verified rule.


## Second headline item: `sv-canvas-1727` (added 2026-10-07; not yet in any submitted form)

Not yet in the submitted form. Published on GitLab at `sv-canvas-1727/`.

**Form bullet (after xframe):**

0b. **`sv-canvas-1727`.** A pre-registered, metadata-only measurement built on xframe's verified transform rule.
   - **692/692** published surface volumes reproduce exactly (`canvas_size` and level-0 shape) from the mesh the catalog names as their source, using the renderer's canvas formula and the catalog's recorded render scale and level.
   - That includes **627/628** of villa #1727's inventory, so at least 365 of its 366 "non-reproducible" volumes reproduce. The one remaining volume has been removed from the catalog.
   - **Mechanism:** renders used the per-axis-regridded transformed meshes, which #1727's inventory did not list.
   - **Checks:** pre-registered sample 29/29 present, controls 15/15; wrong-mesh control clean; independent spot-check 10/10.
   - **Caveats:** canvas sizes only; we can't tell whether the catalog had the source fields in September; single snapshot.
   - **Credit:** #1727 ge-al, gaogao94, #1699 (ge-al, Bullo27), #1845, PR #1901, #1892/#1963.
   - Evidence: `sv-canvas-1727/README.md`, `docs/prize-writeups/sv-canvas-1727.md`.

**Non-claims for sv-canvas-1727:**
- It says nothing about whether rendered voxels are correct.
- It is not a criticism of #1727, whose measurement is careful and whose hypothesis this confirms.
- No upstream comment has been posted.


## Third headline item: `villa-downscale` (added 2026-10-07; not yet in any submitted form)

Not yet in the submitted form. Published on GitLab at `villa-downscale/` (check_bundle OK, 2026-10-07).

**Form bullet (after sv-canvas-1727):**

0c. **`villa-downscale`.** A villa `git format-patch` (MIT; not an upstream PR) so the `vesuvius` Python package handles the open data's `original_volume_downscale`.
   - **What it adds:**
     - `read_tifxyz(path, downscale=s)`;
     - offline catalog helpers that read the real `metadata.json` field;
     - a warning when a `tifxyz_normalized` mesh is read without the factor;
     - a guard against scaling twice, which also respects VC3D's own marker.
   - **Pre-registered real-data before/after, 23/23 published derived meshes** on 6 segments (PHerc0139 ×4, PHercParis4 ×4, PHerc0500P2 ×2):
     - patched loader + catalog matrix reproduces each published mesh to ≤ 0.031 voxel (0.039 µm), with 0 validity mismatches;
     - unpatched `main` is off by 25–99 mm (median per mesh), matching xframe's published offsets within 0.3%.
   - **Tests:** 12 new tests fail on `main` and pass patched; the existing suite is unchanged apart from the new tests. It applies cleanly on bare `main` and after the 9-patch stack.
   - **Caveats:** 6 of 112 affected segments checked on real data; no matrix-correctness claim; the warning keys on the bucket path layout; single snapshot.
   - **Credit:** kadenpool (#1734, #1769, #1731), gaogao94, bkalita-git (#1618), jonmarrs (#1522), ge-al (#1727).
   - Evidence: `villa-downscale/README.md`, `docs/prize-writeups/villa-downscale.md`.

**Non-claims for villa-downscale:**
- It does not claim to have found the downscale factor. The catalog factor is known (#1734 uses it; #1727 found renders reproduce from `tifxyz_normalized` at ×4.0). The claim is the Python-side handling plus the measured before/after.
- It does not show any catalog matrix is right.
- It is not an upstream PR, and nothing was posted upstream.

---

## Suggested title (form)

Scroll Ash Lab: nine tested villa tooling fixes (depth/scale reporting #1648, cache budget #1586, tifxyz frames #1522 + audit CLI, flat ink robust_mad padding #1481, plus docs/wiring items), with real-data evidence where claimed

## Short summary (1–2 sentences)

Scroll Ash Lab (AI-assisted) packaged nine MIT-licensed villa fixes as `git format-patch` files against `main` @ `0e14cf48`, with CPU pytest coverage and, where claimed, before/after numbers on public Vesuvius open data or HF assets. The strongest real-data items are #1648 (held-out validation_mask AUC), #1586 (cache disk budget across reopen), #1522 (mesh scale/frame ambiguity on open-data metas), and #1481 (flat ink padding vs robust_mad on a Paris4 CT window); #1507 is wiring-only, and #1970 should prefer independent upstream PR #1980.

## Suggested GitLab README blurb (top)

```markdown
# Scroll Ash Lab — villa fixes

Small, tested patches for [ScrollPrize/villa](https://github.com/ScrollPrize/villa),
plus a standalone `tifxyz-audit` CLI.

**Authorship:** AI-assisted lab engineering (Grok Bot / Scroll Ash Lab).

**Contact:** scrollash.lab@gmail.com  
**Base tip:** villa `main` @ `0e14cf48`  
**Hold / excluded:** #1855

See `docs/prize-writeups/` in vesuvius-lab (or the per-folder READMEs here) for
honest evidence classes, caveats, and reproduction pointers to public S3/HF
data. We do **not** redistribute CC BY-NC open-data payloads.
```

## Problem / solution bullets (form body — condensed)

**Real-data strongest four (detail write-ups: `1648.md`, `1586.md`, `1522.md`, `1481.md`):**

1. **#1648** — Report `depth_order` + `in_plane_scale_um`; INFO both-dirs; WARN fine scale. Primary AUC on `pherc0814-46527` validation_mask: L2 forward **0.8705 / 0.8462** (seed42/43). **Caveats:** w035 A/B are train-overlap; depth flip vs issue not reproduced on public S3 w035; 46527 still a training segment with spatial mask carve-out.
2. **#1586** — Seed CacheStore LRU so `cache_max_gb` bounds disk. Paris4 level-3 probe: reopen **1.96× / 1.82×** budget unmodified vs **0.98×** patched. Credit @flummoxjr.
3. **#1522** — Optional `voxel_size_um` + `meta_frames` with `SCALE_RTOL=1e-6`. Paris4-40× naive bbox-diag error up to **~7.01×**; after annotate, cross-µm pairs incomparable; same-µm twins comparable. Float-tolerance required for open-data `0.05` vs `0.050000000745…`.
4. **#1481** — Exclude reader padding from flat ink `robust_mad`. Paris4 window: buggy MAE **~3.17 / ~2.32** → fixed **0**. Prior unmerged #1483/#1646/#1773.

**Also shipping (honest class):**

5. **tifxyz-audit** — QA CLI on #1522 helpers (after 1522).
6. **#1520** — README entrypoints ↔ `[project.scripts]` (docs + tests).
7. **#1300** — README: pip on Python 3.14 resolves to vesuvius **0.1.10** (live dry-run: 3.14.8→0.1.10, 3.13.5→0.2.4).
8. **#1507** — Pass `input_pad_depth_to` in native full-3D loader — **wiring-only**; no published ckpt with non-null pad found in survey.
9. **#1970** — Plain zarr + `valid_patch_find_resolution` ≥ 1 — synthetic tests; **recommend upstream PR #1980** (credit @mg255 for diagnosis). Folder retained as earlier independent work.

**Excluded:** #1855 on hold.

## Demonstration / evidence (form)

Point reviewers at:

- Public repo: https://gitlab.com/scroll-ash-lab/villa-fixes
- Per-issue folders at the repo root (`villa-<issue>/`)
- Lab write-ups: `docs/prize-writeups/OVERVIEW.md` and `1648.md` / `1586.md` / `1522.md` / `1481.md`
- JSON: e.g. `villa-1648/real-data-2026-10-05/AUC_TABLE.json`, `villa-1522/.../SUMMARY.json`, `villa-1481/.../SUMMARY.json`, `villa-1586/.../probe-1586-run1.txt`
- OPEN_DATA_NOTE files for S3/HF paths — **do not attach CC BY-NC volumes**

Apply stack (exclude 1855):

```bash
git am villa-1970/0001-*.patch
git am villa-1481/0001-*.patch
git am villa-1522/0001-*.patch
git am villa-tifxyz-audit/0001-*.patch
git am villa-1520/0001-*.patch
git am villa-1586/0001-*.patch
git am villa-1300/0001-*.patch
git am villa-1507/0001-*.patch
git am villa-1648/0001-*.patch
```

## Explicit non-claims (keep in form or README)

- Not claiming Grand Prize / ink-reading breakthroughs — tooling and correctness fixes.
- Not claiming #1507 real-data before/after.
- Not claiming w035 ~0.99 AUC as held-out generalization.
- Not claiming we reproduced the issue #1648 reverse-better table on public S3 w035.
- Not redistributing open-data scan payloads.

## License

MIT for patches (villa-compatible). Open data remains CC BY-NC 4.0 at source.
