# xframe findings: published cross-frame tifxyz meshes in the Vesuvius open-data bucket

Scroll Ash Lab, 2026-10-07 (HST). **AI-assisted:** an AI agent wrote the code and ran every measurement here.
Catalog: `metadata.json` snapshot fetched 2026-10-07 09:14 HST. All numbers below come from the files in `results/`. Nothing is estimated.

## 1. Every published cross-frame mesh reproduces: 902/902

Each segment ships a `tifxyz_normalized` mesh (in its original volume) plus meshes in other scan frames ("derived", made by `transform-tifxyz-normalized`, and same-volume "copies").
For every one of them, `xframe verify` rebuilt the published mesh from the normalized mesh and the catalog. The rebuild is
`regrid(T · (s · normalized))`, where:
- T is the current sample-level catalog matrix original→target;
- s is `original_volume_downscale`;
- regrid is a port of VC's `transformSurfacePoints` / `resamplePointsLinearPreservingInvalids`.

| | |
|---|---|
| Meshes | **902/902 CONSISTENT**: 707/707 derived + 195/195 copies (byte-identical) |
| Coverage | 307 segments in 11 samples (13 sample × downscale groups), including all 414 derived meshes of downscaled segments |
| Grid shape predicted from the source alone = published shape | 902/902 |
| Cells compared / validity-mask mismatches | 4,787,278,260 / 0 |
| Worst cell | 0.0358 voxel = 0.086 µm. Highest per-mesh p99: 0.0087 voxel. No cell > 0.5 voxel anywhere |

The class rules were frozen before the full run (`results/protocol-2026-10-07.md`): CONSISTENT means ≤ 1% of cells > 0.5 voxel.
- Run: 3 workers, streamed over anonymous HTTPS, 1,410 s wall.
- Per-mesh rows: `results/full-verify-2026-10-07.jsonl` (metadata only).
- Summary: `results/full-verify-summary-2026-10-07.json`.

## 2. 112 downscaled segments: `meta.json` omits the factor, and the `vesuvius` Python package has no code for it

In 112 segments the normalized mesh is stored in 1/s coordinates of its original volume. The catalog carries `properties.original_volume_downscale` > 1 for them:

| Scroll (sample) | s | Segments | Derived meshes that depend on the pre-scale |
|---|---|---|---|
| PHercParis4 | 4 | 67 | 204 |
| PHerc0139 | 4 | 38 | 189 |
| PHerc0500P2 | 2 | 7 | 21 |

- **What the files say.** All 112 normalized `meta.json` files carry only `{bbox, format, scale, type, uuid}`. Nothing there marks the coordinates as downscaled.
- **Who applies the factor.**
  - VC3D's open-data loader does apply it (`apps/VC3D/OpenDataSegmentCache.cpp` calls `transformSurfacePoints(surface, downscale, …)`).
  - The publishing pipeline also applies it; the 414 derived meshes above verify only with the pre-scale.
  - The `vesuvius` Python package does not. In villa `main` @ `e0bbb8b4` (2026-10-06), no `.py` file mentions `original_volume_downscale`, `tifxyz_normalized` or `tifxyz-normalized`. `vesuvius/src/vesuvius/tifxyz/` has no downscale handling.
- **Who is affected.** Anyone who loads `mesh/intermediate/tifxyz_normalized/` in Python and uses it against the original volume, or applies a catalog matrix to it, gets wrong coordinates without any warning.
- **Known issues.** The factor itself is not secret: it is a catalog field, #1734 (and its comments) uses `original_volume_downscale` when explaining a bbox bug, and #1727 reproduces 103 surface volumes from `tifxyz_normalized` at an exact render scale of 4.0. What we did not find in any villa issue (unauthenticated GitHub searches, 2026-10-07) is the mesh-side statement: that the normalized mesh files themselves carry no marker, that the `vesuvius` Python package never applies the factor, and how large the resulting offset is across all 112 segments. This is closely related to #1522 (mesh `scale` cannot distinguish frames).

**Measured offset if the factor is ignored.** This covers all 112 segments and every valid point, streamed: `scripts/downscale_offsets.py` → `results/downscale-offsets-2026-10-07.json`. The offset is the per-point distance |(s−1)·p|, or |A·(s−1)·p| for a derived target with A the linear part of the catalog matrix. That is exactly the error implied by the verified rule above.

| Scroll | Own-volume offset, median per segment | Derived-frame offset, median per mesh | Smallest single-point offset |
|---|---|---|---|
| PHercParis4 (×4, 2.4 µm) | 33,442–41,373 vox = 80–99 mm | 80–100 mm | 24.6 mm |
| PHerc0139 (×4, 2.399 µm) | 19,283–30,234 vox = 46–73 mm | 46–73 mm | 16.0 mm |
| PHerc0500P2 (×2, 4.317 µm) | 5,750–6,087 vox = 25–26 mm | 25–26 mm | 13.2 mm |

In target voxels the derived medians range from 1,770 to 86,858, depending on the target voxel size.

This is not a subtle error. A mesh read without the factor lands centimetres away, often outside the scanned region. Someone looking at it in a viewer would notice; a script would not.
`xframe explain` prints a warning for these segments, and `xframe convert` applies the factor.

## 3. Matrix errors propagate exactly, so fixing a matrix means regenerating meshes

Section 1 shows that every derived mesh is the current catalog matrix applied to the source, to float32 precision. Consequences:
- Any error in a catalog matrix is inherited bit-for-bit by every mesh derived with it.
- Correcting the matrix in `metadata.json` does not correct those meshes. They have to be regenerated.

Example: #1843 flags the PHerc1667 transform into the 1.129 µm frame (see also #1835 / PR #1994). The 19 published PHerc1667 meshes in that frame were derived through that chain (`20231117161658-20251217075048⁻¹.20251217075048-20260323082859⁻¹`). If that matrix changes, those 19 meshes need regenerating. **We did not assess whether that matrix, or any other, is correct.**

## 4. 67.2 GB of finer-frame meshes are up-sampled only

A derived mesh in a finer frame has more grid points than its source. The extra density is bilinear interpolation of the source grid (VC's regrid), not newly traced geometry. Its nominal grid step (e.g. 48 µm in a 2.4 µm frame) is not its geometric resolution. This matters wherever "finer grid" is used to pick which mesh to use (#1845 / PR #1851).

There are two counts, and both are correct for their own definition:
- **480 meshes, 67.2 GB.** Source: HEAD-only size census, `scripts/corpus_sizes.py` → `results/corpus-mesh-sizes-2026-10-07.json`. Rule: target voxel < source voxel × s / 1.05, i.e. a target frame at least 5% finer than the source's effective voxel. Payload size is x/y/z.tif bytes from HTTP HEAD, decimal GB.
- **518 meshes.** Source: the verify run's regrid factor. Rule: regrid factor > 1 on both axes, i.e. any up-sampling at all.
  - The extra 38 are all PHerc0139 (×4) meshes onto the 9.362 µm volume. Effective source 9.596 µm → target 9.362 µm is about 2.4% finer, below the 5% threshold. Their regrid factor is about 1.029, and they total 0.06 GB.
  - Every one of the 480 is also in the 518.

For comparison, the census also found:
- coarser-frame (down-sampled) meshes: 136, 0.09 GB;
- same-density: 91, 0.47 GB;
- copies: 195, 0.62 GB;
- normalized sources: 307, 1.7 GB.

## Caveats

- This is one catalog snapshot (2026-10-07 09:14 HST). Segments or matrices added or changed later are not covered.
- **Consistency is not correctness.** We do not assess matrix accuracy (#1835 / #1843 / PR #1994), on-papyrus placement (#1912), or ink.
- The regrid ports follow villa @ `e0bbb8b4`. The bucket pipeline's exact commit is unknown to us; agreement to 0.086 µm suggests the same rule.
- Quantiles come from log-bin histograms with ≤ 0.115% relative bin width. Max values are exact.
- The Python-side statement in section 2 rests on a source search (`rg`) of villa `main` @ `e0bbb8b4`. Third-party code was not surveyed.
- The novelty statement in section 2 rests on unauthenticated GitHub issue searches on 2026-10-07; Discord and other forums were not searched.
- The downscale offsets are computed from the verified rule. We did not separately open the misplaced meshes against volume data.

## Reproduce

Install and test:
```
pip install .            # numpy, tifffile, imagecodecs
pip install .[test] && XFRAME_REAL=1 pytest tests   # 19 tests: 16 offline (synthetic) + 3 live bucket
```
Run the verify and the offsets:
```
python scripts/full_verify.py metadata.json rows.jsonl 3
python scripts/downscale_offsets.py metadata.json offsets.json 4
```
- `metadata.json` is the gzip catalog at the bucket root.
- `scripts/corpus_sizes.py` and `summarize_full.py` keep the lab's directory layout (they read `data/cache/metadata-2026-10-07.json` / `out/`), so adjust the paths before running them.
- Clean-venv test log: `results/xframe-pytest-clean-venv-2026-10-07.log` (19 passed; Python 3.13.5, numpy 2.5.3, tifffile 2026.9.20, imagecodecs 2026.8.16).

## Data and license

- Code is MIT.
- The open data is CC BY-NC 4.0. This bundle contains **no** bucket payloads (no TIFFs or meshes): only metadata-derived numbers, bucket keys, and synthetic test fixtures generated at test time.

## Credits

- **villa #1468 / #1469, `tifxyz-audit` by jaideepsaipadhi** (scrollprize.org community projects). It checks cross-scan bbox-centre consistency through catalog transform chains.
  - It is distinct from Scroll Ash Lab's earlier `vesuvius.tifxyz_audit` villa entry point, which shares the name but is unrelated.
  - It is also distinct from `xframe`, which checks every grid point and converts points.
- **#1522** (jonmarrs): frames that `scale` cannot distinguish, with a census. **PR #1944** (saschaivanov-lgtm): metadata frame-provenance preflight.
- **#1843**: PHerc1667 matrix. **#1835 / PR #1994**: matrix vs landmarks.
- **#1845 / PR #1851**: which mesh to use.
- **#1734**: bbox through downscale.
- **#1727**: surface-volume reproducibility. **#1912**: PHerc0139 placement.
- VC / villa authors: `transformSurfacePoints` and the resample code that `xframe` ports.
- The Vesuvius Challenge open-data team.
