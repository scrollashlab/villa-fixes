# Pre-registration: catalog-wide QA audit of open-data catalog metadata vs actual mesh points

AI-assisted. Written before any declared value was compared with any computed value. No mesh x/y/z.tif has been read for this audit, and no level-0 `.zarray` has been fetched.

What had been read beforehand:
- the catalog's key structure;
- `metadata.schema.json` (field definitions);
- villa source, for the `area_vx2` formula;
- the S3 listing of mesh directory names and sizes;
- prior issues and PRs: #1211, #1468, #1503, #1516, #1617, #1618, #1635, #1730, #1734, #1769.

The sha256 and timestamp are recorded in `preregistration.sha256`.

## Inputs (fixed)

- **Catalog.** `metadata.json` as fetched 2026-10-07 (the copy used for xframe and sv-canvas-1727). Field semantics are taken from the bucket's `metadata.schema.json`, fetched 2026-10-07 18:26 HST. Those definitions are the "declared" meaning.
- **Meshes.** Every published tifxyz mesh in that catalog, read anonymously over HTTPS:

  | Type | Count |
  |---|---:|
  | `tifxyz` | 199 |
  | `tifxyz-normalized` | 307 |
  | `tifxyz-transformed` | 902 |
  | `tifxyz-flattened` | 123 |
  | **Total** | **1,531** |

  Raw `tifffile` decoding is used, payloads are streamed, and nothing is written to disk except metadata-derived numbers.
- **Volume shapes.** Taken from the level-0 `.zarray` of each volume in the bucket. The schema calls these authoritative and calls `properties.shape` "recorded at ingestion".
- **Notation.**
  - Transforms: `samples[S].sample.properties.volume_transforms`.
  - `s` = `original_volume_downscale`.
  - T_V = the catalog matrix from `original_volume_id` to V (identity if equal).
  - R_V = its 3×3 part.
  - σ(R_V) = the largest singular value of R_V.

## Definitions

- **Valid point.** Primary: VC's `isValidSurfacePoint` (x ≠ −1 and x, y, z finite). Secondary: xframe's stricter rule (no component = −1, all finite). Checks that compare a declared value with a point-derived value flag a mesh only if it fails under **both** rules.
- **Grid step.** In a mesh's own frame, g = max(1/scale_u, 1/scale_v), using that mesh's `meta.json` `scale`. In volume V's frame, g_V = g · s · σ(R_V).
- **Reference vertices of a segment** (for `volume_coverage`): the `tifxyz` (original) mesh if the segment has one, else its `tifxyz-normalized` mesh. These are in the original frame, so map them as T_V · (s · p). Coverage is also computed from `tifxyz-normalized` for every segment, as a sensitivity column only (not used to count defects).
- **Array bounds of V.** 0 ≤ x ≤ X−1, 0 ≤ y ≤ Y−1, 0 ≤ z ≤ Z−1, where [Z, Y, X] is the level-0 `.zarray` shape.

## Tolerances and why (fixed now)

| Check | Tolerance | Justification |
|---|---|---|
| `volume_coverage[V].bbox_transformed` vs computed bbox of T_V·(s·p) | each of the 6 components within g_V + 0.01 voxel | The builder may have used a different vertex sampling of the same surface (`obj` vs `tifxyz`, or a re-rasterized grid). Bilinear or barycentric resampling stays within the convex hull, so extremes differ by at most one grid step mapped into V. 0.01 covers float32 rounding of coordinates ≤ 2^17 (ulp ≤ 0.0078). |
| `overlap_ratio` vs fraction of valid reference vertices inside V's array bounds | \|Δ\| ≤ 0.01 + f_band. f_band = fraction of valid reference vertices whose per-axis distance to the nearest bound face, inside or outside, is ≤ g_V. | A different sampling of the same surface can only flip inside/outside for vertices within one grid step of a bound face. 0.01 covers vertex-density differences between samplings (≈ uniform-area grids) and the < vs ≤ bound convention. |
| `meta.json` `bbox` vs computed bbox of valid points, per mesh, own frame | each component within g + 0.01 | A file bbox written before a regrid or resample of the same mesh can differ by at most one grid step. Float term as above. |
| `meta.json` `scale` vs grid spacing | r = scale × median 3D distance between valid 4-neighbours (u and v pooled) must lie in [2^−0.5, 2^0.5] | The thresholds are the log-midpoints to the nearest wrong power-of-two pyramid level (2× or 0.5×). The test classifies which level the declared scale corresponds to. Flattening distortion of < √2 in edge length is tolerated by construction. |
| Segment `width` / `height` vs tifxyz grid size / scale | \|declared − n/scale\| < 1, with u = columns of `x.tif` for width and v = rows for height | The schema defines width = grid size ÷ scale. A tolerance of 1 admits floor, ceil or round of n/scale with scale stored as float32. A swap (width ↔ rows) is reported as its own sub-class. |
| `meta.json` `area_vx2` vs VC `computeSurfaceAreaVox2` | \|declared / computed − 1\| ≤ 0.25 | Computed with the formula in villa `core/include/vc/core/util/SurfaceArea.hpp` (two triangles per grid quad; triangles with a sentinel or non-finite vertex contribute 0). An older VC mask-based path or a pre-regrid grid gives a few-percent difference, while a frame or level error changes area by ≥ 4×. |
| `area_cm2` vs `area_vx2` | implied voxel = √(area_cm2 · 1e8 / area_vx2) must be within 2% of the frame voxel size | Frame voxel = the original volume's `pixel_size_um` × s for `tifxyz` / `-normalized` / `-flattened`, and the target volume's `pixel_size_um` for `-transformed`. 2% is far above the rounding of printed voxel sizes (≤ 0.05%) and below any factor-of-level error. |
| Voxel size token in paths (`-on-<V>-<px>um`, `<px>um-…-volume-<V>`) | Matches if it equals `pixel_size_um` of V rounded to the printed decimals, or equals the px token in V's `long_id` | The schema says long ids are lossy and can differ from `pixel_size_um`. A match to `long_id` but not to `pixel_size_um` is a schema quirk; matching neither is a defect. |
| Volume `properties.shape` vs level-0 `.zarray` shape | exact | Integers. |

## Defect classes (counted; "real defect" = declared value contradicts the schema definition or the data beyond tolerance)

| Id | Class | Denominator |
|---|---|---|
| B | `bbox_transformed` component outside tolerance. Sub-classes: B-marker (segment's `creation.metadata.bbox` contains −1; prior art #1734), B-short (computed vertices extend beyond the declared box), B-loose (declared box strictly contains the computed box beyond tolerance). | `volume_coverage` entries with computable reference vertices, transform and shape |
| O | `overlap_ratio` outside tolerance | as for B |
| F | per-mesh `meta.json` bbox outside tolerance. Sub-class F-marker: declared component exactly −1 (prior art #1618). | meshes with a `bbox` |
| S | `meta.json` `scale` level mismatch | meshes with ≥ 100 valid 4-neighbour pairs |
| W | segment `width`/`height` vs tifxyz grid size ÷ scale (W-swap sub-class) | segments with a `tifxyz` (original) mesh |
| A1 / A2 | `area_vx2` / `area_cm2` outside tolerance | meshes whose `meta.json` carries the field |
| N1 | `-on-<V>-<px>um` path: segment id ≠ entry's segment, V ≠ `parameters.target_volume`, or px mismatching both | 902 transformed meshes |
| N2 | `layers-zarr` path: V ≠ `parameters.target_volume`, or px mismatching both | `layers-zarr` entries |
| N3 | segment directory in a path ≠ segment `long_id` | all tifxyz / layers-zarr entries |
| D1 | segment `creation.derived_from` (type volume) id ≠ `original_volume_id` | segments with such a `derived_from` |
| D2 | `layers-zarr` `creation_info.derived_from` resolves to a mesh not in `target_volume`'s frame: a `tifxyz-transformed` with another target, or a `tifxyz-normalized` / `tifxyz` when target ≠ original volume or s ≠ 1 | `layers-zarr` entries whose `derived_from` resolves to a catalog mesh |
| D3 | cycles in the artifact `derived_from` graph (resolved by `copy_info.source_path`) | all entries |
| D4 | `tifxyz-transformed` `derived_from` not resolving to the same segment's `tifxyz-normalized` | 902 |
| P1 | `tifxyz-transformed` on V ≠ original volume while declared `overlap_ratio[V]` ≤ 0.3 (schema threshold) or V absent from `volume_coverage` | transformed meshes on non-original volumes |
| K1 | `volume_coverage` key with no catalog transform from the original volume | coverage entries |
| K2 | volume reachable through `volume_transforms` from the original volume, but missing from `volume_coverage` | (segment, reachable volume) pairs |
| V1 | volume `properties.shape` ≠ level-0 `.zarray` shape (prior art #1211, #1617, #1503/#1516) | public volumes with a readable `.zarray` |
| C1 | segment `creation.date` earlier than the original volume's scan date (prior art #1730) | segments with parseable dates |

**Schema quirks (counted, not defects).**
- null or missing optional fields, e.g. `shape: null` and `meta.json` without `area_vx2` (#1468);
- references that do not resolve, which the schema allows;
- `long_id` px ≠ `pixel_size_um` within the schema's "lossy" allowance;
- `creation.metadata` differing from the current `meta.json` (schema: opaque);
- `creation_info.derived_from.source_path` not resolving (opaque provenance);
- `volume_coverage` entries not computable for lack of a public shape.

## Hold-out split (fixed now)

- **Segment-level rows** (B, O, F, S, W, A, N1, N3, D1, D2, D4, P1, K, C1) are assigned by segment: h = sha256(`catalog-qa-audit-2026-10-07/<sample>/<segment id>`). The segment is held out iff int(h[:8], 16) mod 10 < 3, about 30%.
- **Volume-level rows** (V1, N2 grouped by segment as above) use the same rule on `<sample>/<volume id>`.
- **Discovery** is the remaining ~70%. All classes are counted on both splits in one run; nothing is tuned between them.

**Replication.** A class with ≥ 3 discovery instances replicates if both hold:
- the hold-out count is ≥ 1;
- a two-sided Fisher exact test of discovery vs hold-out rate gives p ≥ 0.01.

Classes whose expected hold-out count (discovery rate × hold-out denominator) is < 1 are reported as "not testable".

## Positive controls (scanner validity)

- **#1618:** F-marker must find the 28 PHercParis4 `w###` `tifxyz` meshes, or the current files must explain any difference.
- **#1734:** B-marker must find the 28 corresponding `bbox_transformed` entries on the segments' own volume, or as above.

If a control fails without such an explanation, the scanner is treated as broken. It is fixed (tolerances unchanged) and re-run before anything is reported.

## Per-class evidence required before a class is reported

1. Exact count / denominator, overall and by split.
2. Three worked examples (mesh or entry path, declared vs computed).
3. **Loader cross-check.** For the three examples, the computed value is recomputed from a fresh download with (a) villa's `vesuvius.tifxyz.read_tifxyz` at `main` and (b) raw `tifffile`. They must agree with the scan within 1e-6 relative (bbox, overlap, area) or exactly (shapes, counts).
4. **Prior-art search.** Unauthenticated GitHub search API over ScrollPrize/villa issues and PRs, using the class's field names, then reading the bodies and comments of every hit whose title concerns the field; plus `git grep` on a villa clone for the field and builder names. Prior art is credited by GitHub handle.

## Falsification / verdict rule (fixed now)

The audit is **negative** unless at least one class that is not already reported upstream meets all of:
- it is a real defect (not a quirk);
- it has ≥ 3 discovery instances;
- it replicates in the hold-out;
- it passes the loader cross-check.

If it is negative, the result is closed as a short negative note: counts reported, nothing published as a finding. Classes that only replicate prior art are reported as replications, credited, and not as new findings. Tolerances above are not changed after scoring; any added check is labelled exploratory and cannot make the verdict positive.
