# Progress Prize submission draft: Scroll Ash Lab villa fixes (#1970, #1481, #1522) + tifxyz-audit

> DRAFT, not submitted. Paste each section into the matching field of the Progress Prize Submission Form on https://scrollprize.org/prizes.
> Deadline: **Oct 31, 2026, 11:59pm Pacific** (that's Oct 31, 8:59pm HST).
> Everything below comes from the READMEs in https://gitlab.com/scroll-ash-lab/villa-fixes and the Discord handoff draft. Fill in each `TBD` before submitting.

---

## Title

Scroll Ash Lab: three tested villa fixes, #1970 (plain zarr patch finding), #1481 (flat ink robust_mad padding), and #1522 (meta.json scale/frame ambiguity), plus a tifxyz-audit QA tool for #1522

## Short summary (1–2 sentences)

Three small, tested, MIT-licensed patches for ScrollPrize/villa. One fixes out-of-bounds patch starts from `find_valid_patches` on plain zarr arrays when `valid_patch_find_resolution >= 1` (#1970). One fixes the flat ink inference mismatch with training, where reader zero padding gets folded into `robust_mad` normalization stats (#1481). One adds an optional `voxel_size_um` field and metadata-only helpers so meshes whose `meta.json` `scale` matches but whose scan voxel sizes differ are no longer silently treated as the same frame (#1522). All are `git format-patch` files against villa `main` @ `5a4388f`, each with CPU pytest coverage, published at https://gitlab.com/scroll-ash-lab/villa-fixes. The repo also ships `tifxyz-audit`, a small CPU-only CLI built on the #1522 helpers that flags this scale/frame ambiguity (and basic mesh-dir problems) before meshes get compared.

## Problem

**#1970: `find_valid_patches` with a plain zarr array.** https://github.com/ScrollPrize/villa/issues/1970
When a label/image volume is a plain zarr Array (not an OME-Zarr multiscale group) and `valid_patch_find_resolution` is ≥ 1, `find_valid_patches` treated the full-resolution array as if it were already downsampled. It multiplied patch starts by `2**level` and wrote out-of-bounds positions into the patch cache. The CLI work in #1969 uses `valid_patch_find_resolution: 0` as a config workaround, but it doesn't fix the bug.

**#1481: flat ink inference normalizes over reader padding.** https://github.com/ScrollPrize/villa/issues/1481
Flat ink training normalizes only the voxels read from the source and leaves reader padding at zero. Flat inference padded first and then ran `normalize_robust()` over the whole tensor, so the artificial zeros shifted the percentiles, median, and MAD for every real CT voxel. The result was a train/infer mismatch. Earlier PRs for this bug (#1483, #1646, #1773) were closed without being merged (staleness / account limits).

**#1522: mesh `meta.json` `scale` does not distinguish scan frames.** https://github.com/ScrollPrize/villa/issues/1522
`meta.json` `"scale"` means grid cells per voxel of that mesh's own scan. Segments often ship several meshes that declare the same `scale` (e.g. `0.05`) while the voxel sizes in their directory names differ by up to ~40×, so consumers that treat matching `scale` as "same frame" silently mix coordinates (204 affected segments in the open survey).

## Solution

**#1970:** In both `_resolve_resolution` helpers, a plain array (one with no `.keys`) now only satisfies level `0`. Higher levels return `None`, so the existing full-resolution fallback runs. Multiscale groups are unchanged: OME groups with a real level `1/` still use that level, and level-0-only groups still fall back to full resolution. The diagnosis and fix direction come from **@mg255** on #1970.

**#1481:** `FlatPatchReader.read` and normalization now share placement through `source_placement` / `valid_region_zyx`. For `tifxyz_robust`, only the source-backed region is normalized and padding stays at zero, which matches the training semantics. `divide_255` is unchanged. The patch follows the shared-placement approach from the earlier unmerged attempts.

**#1522:** Documents the trap in `vesuvius/tifxyz/API.md`, adds an optional first-class `voxel_size_um` field to the `meta.json` reader/writer, and adds `vesuvius.tifxyz.meta_frames`: parse the `-<float>um` token from directory names, annotate existing `meta.json` files, detect same-scale / different-voxel-size groups, and `frames_comparable()`. Does not change C++ writers, which still omit the field until updated. Annotating from directory names can cover the open corpus if the annotator is run over those meshes.

**tifxyz-audit (#1522 follow-on tool):** a standalone CLI (`tools/tifxyz-audit/`, stdlib for metadata checks, optional `numpy`/`tifffile` for TIFF checks) plus an optional villa patch adding `vesuvius.tifxyz_audit` (apply after the #1522 patch). It checks `meta.json`/`scale`, `voxel_size_um` (present, or inferable from the dirname, with explicit `--fix-meta` only), x/y/z TIFF presence and shapes, invalid-point fractions, and optional bbox vs a given volume shape, and it warns when siblings share `scale` but differ in voxel size. It's a QA check: it doesn't prove a mesh is spatially correct.

All three patches are small, scoped changes inside villa's existing code paths. Input/output formats are unchanged (zarr / OME-Zarr, tifxyz).

## Demonstration / evidence

**#1970: synthetic CPU repro.** Plain array of shape `(221, 132, 132)`, patch `(128, 128, 128)`, labeled blob in the first corner:

| `valid_patch_find_resolution` | before | after |
|------:|--------|-------|
| 0 | `[[0,0,0]]` | `[[0,0,0]]` |
| 1 | out-of-bounds starts | `[[0,0,0]]` |
| 2 | out-of-bounds | `[[0,0,0]]` |

Test: `python -m pytest vesuvius/tests/models/datasets/test_find_valid_patches_resolution.py -v`
Local CPU result (2026-10-04 PT): **5 passed** in ~1.8s (`villa-1970/pytest-results.log`).

**#1481: deterministic numbers from the issue.** A 3×4×4 source (`100..147`) centered into 5×4×4:

| | train semantics | buggy inference |
|--|----------------:|----------------:|
| padded zeros | `0` | `≈ -2.266` |
| real-voxel MAE | — | `≈ 0.488` |
| real-voxel max AE | — | `≈ 1.136` |

With the fix, the padding stays at zero and only the source-backed region is normalized, which matches training.
Test: `python -m pytest vesuvius/tests/ink_detection/test_flat_robust_padding.py -v`
Local CPU result (2026-10-04 PT): **3 passed** in-tree, and the experiment suite also **3 passed** (`villa-1481/pytest-in-tree-results.log`, `pytest-results.log`, `repro.log`, `repro_bug_numbers.py`).

**#1522: metadata-only repro.** Four sibling dirs under `mesh/` with identical `scale: [0.05, 0.05]` and names containing `1.129um`, `2.4um`, `7.91um`, `45.532um` (the issue example); no TIFFs needed. `find_ambiguous_scale_frames` reports one group with a voxel-size spread of ≈ 40.3×.
Test: `python -m pytest vesuvius/tests/tifxyz/test_meta_frames.py -v`
Local CPU result (2026-10-04 PT): **9 passed** in 0.03s (`villa-1522/pytest-results.log`).

**tifxyz-audit: real-data smoke.** On one public PHercParis4 segment (`20230702185753`), the auditor reported 0 errors and the #1522 warning: 4 sibling meshes share `scale≈0.05` with voxel sizes 1.129 / 2.4 / 7.91 / 45.532 µm (≈40.3× spread). That run used a few tiny anonymous reads (4 `meta.json` files plus one ~52 KiB x/y/z TIFF set) from the public `vesuvius-challenge-open-data` bucket, which is CC BY-NC 4.0. We don't redistribute those files; the repo has only the auditor's reports (`tools/tifxyz-audit/smoke/`).
Tests: standalone **15 passed** (`tools/tifxyz-audit/pytest-results.log`). The villa patch applies after #1522 on `5a4388f`, with `test_meta_frames.py` + `test_tifxyz_audit.py` at **11 passed** (`villa-tifxyz-audit/pytest-results.log`).

All three patches were built and tested against villa `main` @ `5a4388f08cc547e6a1a037f949173e731a3e7aa2` ("Fix & simplify progress prize automation (#1948)").

## Documentation / links

- Open-source repository (MIT): https://gitlab.com/scroll-ash-lab/villa-fixes
- Upstream issues: https://github.com/ScrollPrize/villa/issues/1970, https://github.com/ScrollPrize/villa/issues/1481, https://github.com/ScrollPrize/villa/issues/1522
- Vesuvius Challenge Discord post linking the repository: **TBD (paste the message link after posting)**
- Merged villa commit(s) / PR opened by a maintainer: **TBD (add if merged before the deadline or during review)**
- Documentation in the repository: a top-level `README.md`, plus a `README.md` in each of `villa-1970/`, `villa-1481/`, and `villa-1522/` covering the problem, repro, fix, base revision, apply steps, and test commands. `tools/tifxyz-audit/README.md` and `villa-tifxyz-audit/README.md` cover the auditor (checks, usage, limitations, open-data smoke).

Usage (from the repository READMEs):

```bash
git clone https://gitlab.com/scroll-ash-lab/villa-fixes.git
cd /path/to/villa
git checkout main   # at or after 5a4388f
git am /path/to/villa-fixes/villa-1970/0001-find_valid_patches-do-not-scale-plain-zarr-arrays-as.patch
git am /path/to/villa-fixes/villa-1481/0001-ink_detection-exclude-reader-padding-from-robust-fla.patch
git am /path/to/villa-fixes/villa-1522/0001-tifxyz-record-optional-voxel_size_um-and-detect-scal.patch
# optional auditor entry point (after 1522):
git am /path/to/villa-fixes/villa-tifxyz-audit/0001-tifxyz-add-vesuvius.tifxyz_audit-CLI-for-mesh-metada.patch
# or use `git apply` for any patch

# standalone auditor, no villa install:
cd /path/to/villa-fixes/tools/tifxyz-audit && PYTHONPATH=. python -m tifxyz_audit /path/to/segment
```

## License

MIT (the same license villa uses). Copyright (c) 2026 Scroll Ash Lab. A `LICENSE` file is included in the repository.

## Open-source / hosting note (for reviewers)

The code is open source under the MIT license at https://gitlab.com/scroll-ash-lab/villa-fixes (patches, tests, logs, and READMEs). The open-data files used for the auditor smoke (CC BY-NC 4.0) aren't redistributed. This is a tooling/bugfix package, not a new reading or unwrapping result, and we aren't claiming a particular award tier. We'd also like the fixes to land as merged commits in ScrollPrize/villa; a maintainer is welcome to open the upstream PR(s), with co-author credit appreciated. If the team needs anything else, we're happy to adjust.

## Contact

- Name / team: Scroll Ash Lab
- Email: scrollash.lab@gmail.com
- X: @ScrollAshLab

## Discord handle

**TBD: add the Scroll Ash Lab Vesuvius Challenge Discord username.** Use the same account that posts the handoff message, so reviewers can find the thread and see community feedback. (The prize pages note that registering on the Discord is a requirement, at least for the milestone prizes.)

## Attachments

- No separate attachment needed: everything is in the public repository https://gitlab.com/scroll-ash-lab/villa-fixes (top-level `README.md`, `LICENSE`, and for each of `villa-1970/`, `villa-1481/`, `villa-1522/` the `0001-*.patch`, a README, the test file(s), and the pytest logs, plus `repro.log` / `repro_bug_numbers.py` for #1481), as well as `tools/tifxyz-audit/` and `villa-tifxyz-audit/`.
- If the form requires a file upload, use a GitLab archive of `main` (Code → Download source code) or link the repository.

## Credits

- @mg255: diagnosis and fix direction for #1970.
- Authors of the earlier unmerged #1481 PRs (#1483, #1646, #1773): the shared-placement approach.

---

### Pre-submit checklist (not for pasting)

- [ ] Post the handoff on the Vesuvius Challenge Discord (see `discord-handoff-draft.md`), then paste the message link above.
- [ ] Fill in the Discord handle.
- [ ] Add the merged commit / PR links if a maintainer has applied the patches.
- [ ] Submit before Oct 31, 2026, 11:59pm Pacific. Submitting earlier is better, since the criteria favor work that's released early and actually gets used.
