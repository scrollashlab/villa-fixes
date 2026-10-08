# catalog-qa-audit: pre-registered audit of open-data catalog metadata against the published mesh points

**Upstream.** No villa issue yet (id `catalog-qa-audit`). These are findings only; no code change is proposed.
Related: [#1618](https://github.com/ScrollPrize/villa/issues/1618), [#1734](https://github.com/ScrollPrize/villa/issues/1734), [#1730](https://github.com/ScrollPrize/villa/issues/1730), [#1617](https://github.com/ScrollPrize/villa/issues/1617), [#1504](https://github.com/ScrollPrize/villa/issues/1504), [#1468](https://github.com/ScrollPrize/villa/issues/1468), [#1516](https://github.com/ScrollPrize/villa/issues/1516), [#1319](https://github.com/ScrollPrize/villa/issues/1319), [#1379](https://github.com/ScrollPrize/villa/issues/1379), [#1635](https://github.com/ScrollPrize/villa/pull/1635), [#1727](https://github.com/ScrollPrize/villa/issues/1727)

**Evidence.** [`catalog-qa-audit/`](https://gitlab.com/scroll-ash-lab/villa-fixes/-/tree/main/catalog-qa-audit) (`README.md`, `docs/preregistration.md` + sha256, `results/`, `scripts/`, `tests/`).

**Credit.**
- bkalita-git (#1618, #1617, #1635);
- kadenpool (#1734, #1730);
- gaogao94 (#1734 comment);
- nerln (#1504, #1516);
- jaideepsaipadhi (#1468, #1470);
- Aleredfer (#1319);
- Nicodol (#1379);
- Bullo27 (#1683, #1226);
- CVasilopoulos (#1781);
- olgaiv39 (#1391);
- giorgioangel (#728);
- evilaliv3 (#1833);
- ge-al (#1727).

AI-assisted.

## What was done

**Pre-registration.** Written before any mesh was read: sha256 `b9c39080cb847c148dfa23ffb270f978052c623125d49daba4b7ecec08e018ce`, sealed 2026-10-07 18:28:45 HST. It fixes:
- exact definitions;
- tolerances justified from grid step and float32 error;
- 19 defect classes;
- a 30% hash-based hold-out;
- two positive controls;
- a verdict rule.

**Scan.**
- Every one of the 1,531 published tifxyz meshes was streamed anonymously (199 original, 307 normalized, 902 transformed, 123 flattened).
- Valid-point bboxes, neighbour spacing, the VC triangle area and per-volume coverage were computed.
- These were compared with the catalog (323 segments, 1,331 `volume_coverage` entries, 70 public level-0 shapes) and each mesh's `meta.json`.
- 0 scan errors.

## Findings

**1. New: segment `width`/`height` in the wrong pixel frame (class W). 15 of 199 segments with a tifxyz original.**

- **Schema definition.** Width is "the tifxyz grid size divided by its `scale`", at the original volume's voxel size.
- **PHerc0500P2.** The 13 `wrap01`–`wrap13_0919` segments declare 1.83–1.93× their real size on both axes. For example, `20250919184432` declares 4746 × 4241; its mesh is 2480 × 2200, and its published render on its own 4.317 µm volume is 2440 × 2140.
- **PHerc0332.** 2 segments are off by ≤ 21 px.
- **Pattern.** All 15, and only these, take their size from a `dimension_source` that names a rendered-layers directory. None matches, within 1 px, any published grid or render of the segment.
- **Replication.** Discovery 11/143, hold-out 4/56.
- **Prior art.** None found. scroll-audit's size check needs `tiff_dimensions`, which these lack.

**2. New data instance of a known failure mode (class S). 29 of 1,531 meshes, all in 6 PHerc0814 `auto_grown` segments without a published original.**

- **Measurement.** `meta.json` `scale` 0.05 declares 20 voxels per cell, while the median neighbour spacing is 77.3–78.6 voxels (3.86–3.93×) in every published frame.
- **Consequence.** Their renders follow the declared scale. For example, 3840 × 2320 for a 192 × 116 grid on the 2.399 µm original volume, about 3.9 voxels per pixel.
- **Known failure mode.** Scale not matching the grid is reported for other files in #1319 and #1379.
- **Replication.** Discovery 24/1,076, hold-out 5/455. The hold-out contains one of the six segments.

**3. Replications of prior reports.**
- F-marker 28/28, the positive control (#1618).
- C1, 20 segments (#1730).
- V1, PHercParis4 `20230205180739` (#1617).
- D1, PHerc0009B `20250910185200` (#1504).
- `area_vx2` absent from 701 meshes (#1468).
- `shape: null` on 4 volumes (#1516).

**4. Fixed upstream since reported.** #1734's marker-derived `bbox_transformed`. The 2026-10-05 recomputation equals our computed bbox exactly on all 28 segments. The pre-registered predicate flags the values #1734 reported, 28/28.

**5. Clean.**
- `overlap_ratio` 0/1,331.
- Path tokens: N1 0/902, N2 0/692, N3 0/2,223.
- `derived_from` resolution, type and cycles: D2 0/692, D3 none, D4 0/902.
- The 0.3 overlap threshold: P1 0/595.
- Coverage keys versus transforms: K1, K2 0/1,011.

**6. Not claimed.**
- **B-loose (57 entries, 21 segments).** All are on segments without a published original. Their own-volume values equal the unpublished original's stored bbox exactly, so they cannot be checked from published points.
- **`area_vx2` (44).** 28 come from the spiral quad-count formula.
- **`area_cm2` (56).** Consistent with documented behaviour (#728, #1833, #1226).

## Checks

- **Loader cross-check.** 9 meshes (3 each from W, S and the area class) were freshly downloaded and read with villa's `read_tifxyz` (main `e0bbb8b40`) and with raw `tifffile`. The arrays were identical, and every statistic matched the scan exactly or within 1e-6.
- **Unit tests.** 9 synthetic tests cover block-boundary handling, sentinels and NaNs against a naive area, transforms and inside fractions, Fisher p, voxel-token rounding, the split, and memmap equivalence.
- **Process.** All scripts ran with `-B`; check_bundle passes.

## Limits

- W and S are each concentrated in one ingestion batch, so the hold-out tests repeatability within the catalog, not independence of cause.
- The catalog builder is not public, so the cause of W is inferred from the provenance field, not from code.
