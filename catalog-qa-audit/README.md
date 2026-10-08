# catalog-qa-audit: open-data catalog metadata vs the published mesh points

AI-assisted.

We ran a pre-registered audit of every published tifxyz mesh in the Vesuvius Challenge open-data catalog (`metadata.json`, fetched 2026-10-07). It compares the declared metadata with values computed from the actual points: 1,531 meshes, 323 segments, 1,331 `volume_coverage` entries and 70 public volume shapes.

## Result in brief

**One new real-defect class meets every pre-registered criterion: W.**

- **What W is.** Segment `properties.width` / `height` contradict the schema's own definition ("for tifxyz segments, the tifxyz grid size divided by its `scale`", at the original volume's voxel size).
- **Counts.**
  - 15 of 199 segments with a published `tifxyz` original. Discovery 11/143, hold-out 4/56, Fisher p = 1.0.
  - 13 of the 15 are the PHerc0500P2 `wrap01`–`wrap13_0919` segments. Their declared size is **1.83–1.93×** the size of their own mesh, on both axes.
  - The other 2 (PHerc0332) differ by at most 21 px.
- **Pattern.** All 15, and only these 15, carry a `creation.metadata.dimension_source` that names a rendered-layers directory. No segment without that field fails, and no segment with it passes.
- **Example.** PHerc0500P2 `20250919184432` (wrap05) declares 4746 × 4241. Its mesh is 124 × 110 cells at scale 0.05, i.e. 2480 × 2200. Its published render on its own original volume (4.317 µm) is 2440 × 2140.
- **Prior art.** None found (see below).

**A second new class, S, is a new data instance of a known tool-level failure mode.**

- **What S is.** The `meta.json` `scale` is off by a pyramid level.
- **Counts.**
  - 29 of 1,531 meshes. Discovery 24/1,076, hold-out 5/455, Fisher p = 0.156.
  - All 29 belong to 6 PHerc0814 `auto_grown` segments that have no published `tifxyz` original: their normalized, flattened and every transformed mesh.
- **Measurement.** They declare `scale` 0.05 (20 voxels per cell), but the median spacing between valid neighbours is **77.3–78.6 voxels**. That is 3.86–3.93× the declared step, in every frame the segment is published in.
- **Consequence.** The segments' published renders follow the declared scale. For example, the 192 × 116 grid of `20260226113324` renders at 3840 × 2320 on its 2.399 µm original volume, about 3.9 voxels per pixel.
- **Caveat.** The hold-out holds only 1 of the 6 segments.

Everything else either replicates prior reports, is explained by documented behaviour, has fewer than 3 instances, or could not be attributed to the catalog (B-loose, details below).

## Pre-registration

| | |
|---|---|
| File | `docs/preregistration.md` |
| sha256 | `b9c39080cb847c148dfa23ffb270f978052c623125d49daba4b7ecec08e018ce` |
| Sealed | 2026-10-07 18:28:45 HST, before any mesh or `.zarray` was read |
| Inputs | catalog sha256 `40517076dc5f2128599868b337e25a17922ebe70a22b238b990e109b6f82af0f`; `metadata.schema.json` sha256 `873c0eb4397e696a93899f71ae86576ad9e6eb62ae4c4bea4543ab3cf1d87376` |
| Scan | 1,531/1,531 meshes, 0 errors. Per-mesh JSONL sha256 `20c3f627faec4baedf19b191a8f733e13aeff9d877f4b59f0b836637225cb257`, kept local |

**Scripts edited after the seal.** All edits were memory and I/O only:
- streaming block size;
- an opt-in disk-memmap decoder for meshes ≥ 300 MB;
- a one-line catalog-load fix.

No definition, tolerance, class, split or verdict rule changed. Equivalence tests are in `tests/`.

## All pre-registered classes (count / denominator; discovery | hold-out)

| Class | Count | Discovery \| hold-out | Status |
|---|---|---|---|
| **W** width/height vs grid ÷ scale | **15 / 199** | 11/143 \| 4/56 | **New, real defect.** Replicates; loader cross-check passed |
| **S** `scale` level mismatch | **29 / 1,531** | 24/1,076 \| 5/455 | **New data instance** of the failure mode in #1319 / #1379. Replicates (one hold-out segment); cross-check passed |
| F (meta.json bbox) | 30 / 1,531 | 20 \| 10 | 28 are F-marker = **#1618**, the positive control (28/28 found). F-other has 2 instances (< 3, not reportable) |
| B (`bbox_transformed`) | 57 / 1,331 | 35 \| 22 | All B-loose. **Not attributable** (below). B-marker 0 (see the #1734 control) |
| O (`overlap_ratio`) | **0 / 1,331** | 0 \| 0 | Clean |
| A1 (`area_vx2` vs VC triangle area) | 44 / 830 | 33 \| 11 | 28 are the #1618 spiral w-series. In the one checked (`w010-027`), `area_vx2` equals valid quads × step² exactly (the spiral formula quoted in #1379), not the triangle area. 16 others are unexplained. Not claimed |
| A2 (`area_cm2` vs `area_vx2` × voxel²) | 56 / 123 | 35 \| 21 | The implied voxel is another volume's voxel size or a default. Consistent with documented behaviour (#728 keeps `area_cm2` across transforms; #1833, #1226 voxel-size defaults). Overlaps #1730. Not claimed |
| C1 (segment date before scan) | 20 / 323 | 13 \| 7 | Replicates **#1730** exactly (20) |
| V1 (volume shape) | 1 / 70 | 1 \| 0 | PHercParis4 `20230205180739` 14369 vs 14258 = **#1617** |
| D1 (`derived_from` id) | 1 / 323 | 0 \| 1 | PHerc0009B `20250910185200` = **#1504** |
| N1, N2, N3, D2, D3, D4, P1, K1, K2 | 0 each | | Clean (denominators: 902, 692, 2,223, 692, 1 graph, 902, 595, 1,011, 1,011) |

**Schema quirks (not defects):**
- `meta.json` without `area_vx2`: 701 meshes (the class in #1468);
- `shape: null` on 4 volumes (#1516);
- 2 unresolvable ink-detection `derived_from` entries.

## Positive controls

- **#1618: passed.** F-marker finds exactly the 28 PHercParis4 w-series `tifxyz` meshes.
- **#1734: explained by the current files.**
  - On those 28 segments' own volumes, the current `bbox_transformed` (`computed_at` 2026-10-05 00:17 HST) contains no `-downscale` value and equals our computed bbox exactly (max abs diff 0.0).
  - Example, `20260701183134`. #1734 reported a lower corner of [-4.0, -2664.1, -4.0]; the file now reads [2523.46, -2664.11, 12000.06].
  - Re-scoring the B predicate with the values #1734 describes flags 28/28 (`results/control-1734-2026-10-07.json`).

## W: worked examples

| Segment | Declared w × h | Grid ÷ scale (`read_tifxyz` full-res) | Render on original volume (w × h) |
|---|---|---|---|
| PHerc0500P2 `20250919184432` wrap05 | 4746 × 4241 | 2480 × 2200 | 2440 × 2140 (4.317 µm) |
| PHerc0500P2 `20250919184431` wrap04 | 4046 × 5523 | 2120 × 2880 | 2060 × 2820 (4.317 µm) |
| PHerc0332 `20240828190516` | 25309 × 2739 | 25320 × 2760 | (none published) |

- **Scope.** All 15 rows are in `results/audit-results-defects-2026-10-07.json`.
- **What the declared sizes match.** None of the 15 declared sizes matches, within 1 px, any of the segment's published mesh grids ÷ scale or any of its published render canvases (`results/verify-readme-claims-2026-10-07.json`). For the 13 wrap segments the ratio to the true size is 1.83–1.93 and differs per segment. The provenance field names a rendered-layers directory, not the tifxyz.
- **Likely fix (catalog builder).** For segments that have a tifxyz, compute width/height from the grid and scale, as the schema states. Do not take them from `dimension_source`.
- **Status of the fix.** The builder repository is not public, so no code change is proposed here.

## S: worked examples (PHerc0814, original volume `20260309142202`, 2.399 µm)

| Segment | Mesh | Declared step | Measured mean step u / v (voxels) | Render canvas on original volume |
|---|---|---|---|---|
| `20260226113324` (hold-out) | `tifxyz_normalized` 116 × 192 | 20 | 77.93 / 78.05 | 3840 × 2320 |
| `20250928235954` | `tifxyz_normalized` 117 × 174 | 20 | 78.36 / 78.06 | 3480 × 2340 |
| `20260225160055` | `tifxyz_normalized` 128 × 127 | 20 | 78.47 / 78.48 | 2540 × 2560 |

The 13 other PHerc0814 segments (65 meshes) pass, with ratios of 0.998–1.04. We do not claim a mechanism.

## Loader cross-check

- **Method.** For 9 meshes (3 each from W, S and A1), files were downloaded afresh and read with villa's `vesuvius.tifxyz.read_tifxyz` (villa main `e0bbb8b40`) and with raw `tifffile`.
- **Arrays.** Identical between the two readers, 9/9.
- **meta.json.** Equal to the scanned fields, 9/9.
- **Statistics.** Every statistic matches the scan exactly or within 1e-6 relative, 9/9: rows, cols, valid counts, both bboxes, pair count, spacing median and area.
- **Files.** `results/crosscheck-{W,S,A1}-2026-10-07.json`, `results/evidence-S-W-2026-10-07.json`.

## B-loose: not attributable to the catalog (exploratory diagnosis)

- **Where the failures are.** All 57 failing entries (21 segments) are on segments **without a published tifxyz original**, where the pre-registered reference falls back to `tifxyz-normalized`. All 906 entries referenced to a published original pass.
- **Own-volume entries.** On the segment's own volume, 17/17 failing entries equal the segment's stored original-mesh bbox (`creation.metadata.bbox` × downscale) exactly.
- **What this means.** The builder evidently used the unpublished original mesh. The published normalized mesh is a different, smaller rasterization, so the values cannot be checked from published points.
- **File.** `results/diag-b-loose-2026-10-07.json`.

## Prior-art search

**Method.**
- Cached all 1,995 ScrollPrize/villa issues and PRs (titles and bodies) with the unauthenticated REST API.
- Ran keyword searches and GitHub search-API queries for each class's fields and segment names.
- Read bodies and comments of every relevant hit: #1319, #1379, #1391, #1468, #1470, #1504, #1617, #1618, #1635, #1683, #1694, #1699, #1727, #1730, #1734, #1781, #1840, #1845, #1860, #1861, #1922, #1977, #1978.
- Read the scroll-audit source (#1635).

**W.**
- No report found.
- scroll-audit's width check requires `tiff_dimensions`, which none of the 15 carry.
- #1727 (ge-al) concerns render canvases, not segment `width`/`height`.

**S.**
- No report of these PHerc0814 meshes found.
- The failure mode, `scale` not matching the grid, is reported for other files in #1319 (Aleredfer) and #1379 (Nicodol).
- It is addressed for `vc_obj2tifxyz` by #1391 (olgaiv39), #1683 (Bullo27; closed unmerged) and #1781 (CVasilopoulos; open), and for a repair script by #1470 (jaideepsaipadhi).
- #1730 (kadenpool) lists one of the six segments (`20250928235954`) for a different reason (scan date).

**Replications credited.**
- #1618, #1635 (bkalita-git);
- #1734 (kadenpool, with gaogao94);
- #1730 (kadenpool);
- #1617 (bkalita-git);
- #1504, #1516 (nerln);
- #1468 (jaideepsaipadhi);
- #728 (giorgioangel), #1833 (evilaliv3) and #1226 (Bullo27) for the A2 mechanisms.

## Layout

| Path | Contents |
|---|---|
| `docs/` | pre-registration and its sha256 |
| `results/` | `audit-results-2026-10-07.json` (all rows); `audit-results-defects-2026-10-07.json` (defect rows only); controls, cross-checks and diagnosis; mesh listing; volume shapes; scan summary |
| `scripts/` | the exact scripts that ran (`SHA256SUMS`) |
| `tests/` | 9 synthetic unit tests and their log |

**Reproducing.**
- **Run from** an `experiments/catalog-qa-audit/` layout with `out/` holding `mesh-listing-2026-10-07.json` and `volume-shapes-2026-10-07.json`.
- **Environment.** Set `CQA_CATALOG` to the catalog copy and `XFRAME_SRC` to the xframe `src/` directory.
- **Commands.**
  - Scan: `python -B scripts/scan_meshes.py out/mesh-scan.jsonl 4 0 1e12`, with `SCAN_MEMMAP=1` for large meshes.
  - Analysis: `python -B scripts/analyze.py out/mesh-scan.jsonl out/volume-shapes-2026-10-07.json out/audit-results.json`.
