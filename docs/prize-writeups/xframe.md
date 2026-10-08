# xframe — point-level verify / explain / convert for cross-frame tifxyz meshes

Upstream: standalone tool, not a villa patch. Related: [#1522](https://github.com/ScrollPrize/villa/issues/1522), [#1734](https://github.com/ScrollPrize/villa/issues/1734), [#1843](https://github.com/ScrollPrize/villa/issues/1843), [#1845](https://github.com/ScrollPrize/villa/issues/1845), [#1468](https://github.com/ScrollPrize/villa/issues/1468)/[#1469](https://github.com/ScrollPrize/villa/issues/1469)  
Evidence: `xframe/` (`FINDINGS.md`, `results/`)  
Credit: jaideepsaipadhi (`tifxyz-audit`, #1468/#1469, bbox-centre cross-scan check); jonmarrs (#1522 census); saschaivanov-lgtm (PR #1944); #1835 / PR #1994, #1843, #1845 / PR #1851, #1734, #1727 authors; VC authors (`transformSurfacePoints`, which xframe ports)  
Author: Scroll Ash Lab \<scrollash.lab@gmail.com\> (AI-assisted)

## Problem

Each open-data segment ships several tifxyz meshes in different scan frames, and they all declare `scale` ≈ 0.05 (#1522). From the bucket alone, users cannot tell:
- how a "derived" mesh relates to its source: matrix only, or matrix plus a grid regrid;
- whether a finer-frame mesh carries more traced detail or only bilinear up-sampling;
- that 112 segments' `tifxyz_normalized` meshes are stored in 1/`original_volume_downscale` coordinates. Their `meta.json` does not say so, and the `vesuvius` Python package has no code for it.

Existing checks work at the matrix or bbox level (#1835 / PR #1994, #1468/#1469 `tifxyz-audit`, PR #1944). None reproduces the published meshes point by point.

## What it does

`xframe` is a CPU-only Python CLI and library (MIT; deps numpy, tifffile, imagecodecs) with four commands:
- `xframe frames`: list a segment's meshes, frames and voxel sizes from the catalog.
- `xframe explain`: show how each mesh was made. It covers the downscale pre-scale (with a warning), the catalog matrix and derivation path, and grid UP/DOWN-sampling with the nominal vs source step in µm. Byte copies are named as copies.
- `xframe verify`: rebuild each published mesh as `regrid(T · (s · normalized))` and compare every cell, streamed over anonymous HTTPS. Results fall into frozen classes CONSISTENT / PARTIAL / DRIFT / NOT_COMPARABLE, with exit codes 0/1/2.
- `xframe convert`: convert points (CSV) or a whole tifxyz between frames the way the pipeline does. Output carries a provenance JSON and `voxel_size_um`.

It does **not** assess whether a matrix is correct (#1835 / #1843 / PR #1994), or on-papyrus placement or ink.

## Real-data numbers

Public `vesuvius-challenge-open-data` only (CC BY-NC); catalog snapshot 2026-10-07 09:14 HST. Source: `xframe/results/` and `FINDINGS.md`.

### Full corpus verify

| | Result |
| --- | ---: |
| Published cross-frame meshes | **902/902 CONSISTENT** (707 derived + 195 byte-identical copies) |
| Segments / samples | 307 / 13 |
| Downscale meshes | PHercParis4 ×4 **204/204** · PHerc0139 ×4 **189/189** · PHerc0500P2 ×2 **21/21** |
| Grid shape predicted from the source alone = published | **902/902** |
| Cells compared / validity mismatches | 4,787,278,260 / **0** |
| Worst cell | **0.0358 vox = 0.086 µm**; no cell > 0.5 vox |

### Downscale trap: offset if `original_volume_downscale` is ignored (all 112 segments, every valid point)

| Scroll | s | Segments / derived meshes | Median offset per segment / mesh | Smallest point offset |
| --- | ---: | ---: | ---: | ---: |
| PHercParis4 | 4 | 67 / 204 | **80–100 mm** | 24.6 mm |
| PHerc0139 | 4 | 38 / 189 | **46–73 mm** | 16.0 mm |
| PHerc0500P2 | 2 | 7 / 21 | **25–26 mm** | 13.2 mm |

The catalog factor is already known: #1734 uses `original_volume_downscale` for a bbox bug and #1727 reproduces renders from normalized meshes at exactly ×4.0. Unauthenticated GitHub searches on 2026-10-07 found no issue stating the mesh-side gap (no marker in the mesh files, no handling in the Python package) or measuring the offset. Closely related to #1522.

### Corollaries

- **Matrix errors propagate exactly.** Fixing a catalog matrix does not fix published meshes; they must be regenerated. Example: the 19 PHerc1667 meshes in the 1.129 µm frame that #1843 concerns. We did not judge that matrix.
- **67.2 GB of finer-frame meshes are up-sampled only.** That is 480 meshes, counted as target voxel < source effective voxel / 1.05 by HEAD byte census. Counting any regrid factor > 1 gives 518; the extra 38 are PHerc0139 → 9.362 µm meshes at factor ≈ 1.029, 0.06 GB. Their extra density is interpolation, which is relevant to "use the finer mesh" heuristics (#1845 / PR #1851).

## Unit tests

There are **19 passed** in a clean venv with a non-editable install (Python 3.13.5, numpy 2.5.3, tifffile 2026.9.20, imagecodecs 2026.8.16), with `XFRAME_REAL=1`:
- **16 offline**, on synthetic fixtures. The resample port is checked against a per-pixel reference implementation. A fake bucket includes downscale ×4 and a shifted-mesh negative control, and the CLI is tested end to end.
- **3 live-bucket** tests on PHerc0139 w029: CONSISTENT, a wrong-prescale negative control that is caught, and convert == published.

The parent re-ran the suite independently (19/19). The handoff copy was re-run from a fresh venv as well (19/19). The clean venv also exposed a real missing dependency, `imagecodecs` (needed for LZW TIFFs), which is now declared.

## Limitations

- Single catalog snapshot (2026-10-07). Later catalog changes are not covered.
- Consistency only: no matrix-accuracy, placement or ink claims.
- The regrid port follows villa @ `e0bbb8b4`. The bucket pipeline's exact commit is unknown; agreement to 0.086 µm suggests the same rule.
- The Python-side "no downscale handling" rests on a source search of villa `main` @ `e0bbb8b4`. VC3D's C++ open-data loader does apply the factor.
- Quantiles are log-binned (≤ 0.115% relative width); max values are exact.
- Downscale offsets are computed from the verified rule, not by visually inspecting misplaced meshes.
- AI-assisted end to end.

## How to reproduce (no CC BY-NC redistribution)

The bundle holds metadata-derived numbers, bucket keys and synthetic fixtures only. It contains no TIFFs or meshes. Data is read anonymously from  
`https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/`.

```bash
cd xframe
pip install '.[test]' && XFRAME_REAL=1 pytest tests          # 19 tests
python scripts/full_verify.py metadata.json rows.jsonl 3       # ~23.5 min, 3 workers
python scripts/downscale_offsets.py metadata.json offsets.json 4
xframe explain --catalog metadata.json PHerc0139 20250108000004
```

Results: `results/full-verify-summary-2026-10-07.json`, `results/full-verify-2026-10-07.jsonl` (one row per mesh), `results/downscale-offsets-2026-10-07.json`, `results/corpus-mesh-sizes-2026-10-07.json`, `results/xframe-pytest-clean-venv-2026-10-07.log`.
