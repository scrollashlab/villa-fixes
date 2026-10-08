# Pre-registration: real-data before/after for the `vesuvius.tifxyz` open-data downscale patch

Written: 2026-10-07 11:28:30 HST, before any real-data scoring of the patched or unpatched loader. AI-assisted.

## Arms

- **Unpatched.** villa `main` @ e0bbb8b4: `vesuvius.tifxyz.read_tifxyz(<local copy of mesh/intermediate/tifxyz_normalized>)`.
- **Patched.** The same commit plus this patch. The factor `s` comes from the catalog through the patch's helper, which reads `samples[S].segments[G].properties.original_volume_downscale` from the 2026-10-07 `metadata.json`. The mesh is loaded with `read_tifxyz(..., downscale=s)`, or the equivalent catalog-aware helper.

Both arms read the same local copy of the normalized mesh files (`x/y/z.tif`, `meta.json`, plus `mask.tif` if the bucket has one). These are CC BY-NC payloads and stay in the local cache only.

## Segments (fixed by rule before any scoring)

Two downscaled segments per scroll are chosen from the HEAD census `corpus-mesh-sizes-2026-10-07.json`, ranked by normalized-mesh bytes: the smallest, and the median (index n//2 of the ascending list).

| Scroll | s | Smallest | Median |
|---|---|---|---|
| PHerc0139 | 4 | 20260422000000 | 20250108000002 |
| PHercParis4 | 4 | 20260602204401 | 20260623153216 |
| PHerc0500P2 | 2 | 20250825181939 | 20250825181917 |

Every derived mesh (`transform-tifxyz-normalized`) of these 6 segments is scored.

## Scoring (identical for both arms)

For each derived mesh D, with published shape (H, W), catalog matrix T (original→target, as in xframe) and loaded points P:
1. Compute Q = T·P on valid points only; invalid points stay -1. No pre-scale is added by the scorer.
2. Resample Q to (H, W) with xframe's port of VC `resamplePointsLinearPreservingInvalids`, the same resampler that reproduced 902/902 published meshes. If (H, W) equals P's own shape, skip the resample.
3. Compare cell by cell with D, over cells valid in both. Report median, p99 and max error in target voxels and µm, the fraction of cells > 0.5 voxel, and validity mismatches.

Also reported: the own-frame offset |P_patched − P_unpatched| per valid point, in original voxels and µm.

## Pass rule (fixed now)

- **Patched arm, per derived mesh:** max error ≤ 0.5 target voxel, fraction > 0.5 voxel = 0, and 0 validity mismatches.
  - The patch passes only if **every** scored derived mesh of all 6 segments meets this.
- **Unpatched arm, per derived mesh:** median error ≥ 1,000 target voxels **and** ≥ 10 mm.
  - The "off by the measured cm offset" claim holds only if **every** scored mesh meets this.
  - For each mesh, the unpatched median is also compared with that mesh's entry in `downscale-offsets-2026-10-07.json` (xframe, computed before this patch). The claim holds if the two agree within 2% relative.
- **Failure handling.** Any mesh that fails a rule is reported individually, and the claim is weakened accordingly. Thresholds are not changed after scoring.

## Non-claims

- Whether any catalog matrix is correct.
- Pixel-level render effects.
- Anything about meshes from segments with s = 1. The patch must leave them unchanged; this is covered by unit tests, not by this scoring.
