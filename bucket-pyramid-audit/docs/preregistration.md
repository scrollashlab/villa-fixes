# Pre-registration: do the ink-bucket render pyramids keep the full depth at level 1 and level 2?

Sealed before any audit chunk was fetched. What was read before sealing:
- directory listings of the `ink/` prefix of the Hugging Face bucket `scrollprize/datasets` (`meta/stores.json`, 76 render stores);
- the `.zattrs` and `.zarray` metadata of three stores (`ink/841/w00/w00.zarr`, `ink/0009b/auto_grown_20250919055754487_inp_hr_2um/…zarr`, `ink/unused/0139/w024_2026021572/…zarr`);
- the earlier result that the four PHerc0841 / 500p2a stores' level 1 is planes 0–32 of level 0, pooled in-plane only (`gpu-1648-intermediate-scale/results/step0a-level1-rule.json`).

## Why

- `vesuvius.ink_detection.inference.infer` centre-crops its 17-plane window from whatever depth the selected level holds (`center_crop_layer_indices`).
- If level 1 of a 65-plane render holds only planes 0–32, `--resolution 1` centres the window near level-0 plane 16 instead of the render's central plane 32. The input also keeps level-0 z spacing.
- Our selector study read exactly this level and lost depth without any error. This census measures how widespread that is.

## Population (fixed)

All 76 stores in `meta/stores.json`: every `<segment>/<segment>.zarr` render under `ink/`. Label, mask and `_max_` zarrs are excluded.

## Procedure per store and child level L ∈ {1, 2} (parent L − 1)

1. **Probes.** Probe points are taken in this fixed order, as (row, column) fractions of the child canvas: (.5,.5), (.25,.25), (.75,.75), (.25,.75), (.75,.25), (.5,.25), (.5,.75), (.25,.5), (.75,.5).
   - For each point, read the child chunk containing it over the full child depth.
   - Keep the point if both the chunk and the parent voxels under it are non-constant.
   - Stop after 2 kept points.
2. **Rules.** For each child plane k, from in-plane 2×2 sums S_j of the parent planes:
   - INPLANE_ALL: same plane count as the parent, child k = S_k / 4.
   - TRUNC: child k = S_k / 4 for k < child depth, i.e. the first planes only.
   - POOL: child k = (S_2k + S_2k+1) / 8 (a last unpaired plane uses S_2k / 4), i.e. a 2×2×2 mean.
   - CTR: child k = S_(k+off) / 4, with off = (parent depth − child depth) // 2, i.e. the centred planes.
   - Each rule is tried with four roundings (floor, half-up, half-even, ceil). Only pixels with a full 2×2 parent footprint are compared.
3. **Class.** The class is the first rule, in the order above, that matches exactly (0 differing voxels over both probes). Otherwise the class is OTHER. NO_DATA means there was no usable probe; ABSENT and ERROR are recorded as such.
4. **Metadata.** Record the child shape, the parent shape and the declared OME `scale` for the child level.

## Positive control (validity)

The four stores already measured must come out TRUNC, half-up, at level 1: `ink/841/{w00, auto_grown_20260220144552896, auto_grown_20260220174252405}` and `ink/unused/500p2a`. If any does not, the audit is invalid and is reported as such.

## Outcomes (descriptive census; scored once)

- **Primary:** the number of stores whose level 1 is TRUNC, i.e. holds only the first ⌈N/2⌉ of the N level-0 planes.
- **Secondary:**
  - the same count at level 2 (vs level 1);
  - among the TRUNC stores, how many declare a z scale > 1 (the metadata then states depth pooling that did not happen);
  - the class table by scroll folder.
- **Decision rule:**
  - If TRUNC stores exist beyond the four known ones, report a bucket-wide data issue with the full store list and the proposed fix (pool z, or keep all planes, at every level).
  - If only the four known stores are TRUNC, close out with a note.

## Consequence (post hoc, stated in advance as such)

No new inference is run. For PHerc0841 ×3, both sets of AUCs already exist on the same region R and labels:
- seed42/seed43 step-075000 on the published level 1 (selector study, `label-free-selector/results/metrics.json`);
- the same checkpoints on a correctly pooled 2×2×2 input (`gpu-1648-intermediate-scale/results/metrics.json`, arm S9).

The difference is reported as a descriptive, post hoc comparison of numbers produced under two earlier sealed protocols, not as a pre-registered test.

## Outputs

- `results/audit.json`, `results/summary.md`, `results/deviations.md`.
- Metadata and metrics only: no chunk data is kept or redistributed.

AI-assisted.
