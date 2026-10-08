# Pre-registration: are #1727's "non-reproducible" surface volumes reproducible from the published *transformed* meshes?

Written: 2026-10-07 10:26:20 HST. This was written **before** any `.zattrs`, `.zarray` or `x.tif` header in the sample was fetched by this lab.
Scope: metadata only. That means the catalog `metadata.json`, surface-volume `.zattrs` and `0/.zarray`, mesh `meta.json`, and the first bytes of `x.tif` (TIFF header/IFD via HTTP Range). No volume or mesh payloads are downloaded. AI-assisted.

## What was known when this was written

- **What #1727 measured.** villa #1727 (ge-al, 2026-09-07; 1 comment by gaogao94, 2026-10-03) found that 366/628 surface volumes cannot be reproduced to the pixel from "any published mesh variant". The test used `vc_render_tifxyz`'s canvas formula with one isotropic render scale.
- **The issue's own hypothesis.** It names "applied the inter-scan affine before sizing" or "a mesh revision that is not the published one" as likely explanations. It also says nothing in the bucket records which mesh produced a volume.
- **Which meshes #1727 compared.** Its `scripts/inventory.py` (github.com/ge-al/vesuvius-cpu-repro @ 113bbb9) lists mesh dirs only when the directory name has no `.` (`elif "." not in leaf`). The published transformed meshes are named `<id>-on-<vol>-<um>.tifxyz`, so they are skipped. Its `audit/pairs.json` mesh kinds confirm this: `tifxyz_normalized` 628, `tifxyz_original` 394, `tifxyz_flattened` 234, `tifxyz` 4, and zero `*.tifxyz` transformed meshes.
- **What the catalog records** (this lab, `metadata.json` 2026-10-07):
  - 688 surface volumes (`layers-zarr`, process `render-tifxyz-to-zarr`) carry `creation_info.derived_from` = a `tifxyz-transformed` mesh path.
  - Their provenance parameters include `scale` ("1"), `group-idx` ("0" or "1"), crop, affine fields, and the villa commit.
  - 4 more come from `render-tifxyz-normalized-to-zarr`.
- **Already verified by xframe** (902/902): each transformed mesh's grid is regridded per axis (`round(n · float32 factor)`). Per-axis rounding would produce the per-axis implied-scale differences #1727 reports, e.g. 4.2542 vs 4.2553.
- **Renderer canvas rule.** From `vc_render_tifxyz.cpp` @ e0bbb8b4, lines 1839–1844:
  `full = max(1, lround(stored · render_scale / float32(meta.scale)))` per axis.
  `render_scale = scale · scale_seg · sA · 2^-group_idx`, where sA = cbrt|det A| if an affine is given, else 1.
  Crop (manual or auto) replaces the size.

## Hypothesis H1

For each surface volume whose catalog provenance names a `tifxyz-transformed` mesh, with empty affine and no crop:
- the `.zattrs` `canvas_size` and the level-0 `.zarray` (H, W) equal the renderer formula applied to **that** published transformed mesh's stored grid and `meta.json` scale;
- the inputs are `render_scale = float(scale) · 2^-group-idx` from the same provenance and `scale_seg` = 1 (the parameter is empty).

## Sample (stage 1), fixed before fetching

`out/geal-classes-reconstructed.json` re-derives #1727's classes from its public `audit/pairs.json`. A volume is "reproduced" if some listed mesh variant matches both axes at one isotropic scale. This rule gives 276 reproduced / 352 not, versus the issue's 262/366. Our rule is at least as permissive, so our 352 should be a subset of their 366; we could not re-run their exact clean-ratio step, which is not in their scripts.

The sample is selected by the lowest `sha1(seg + "|" + sv)` within each stratum:
- **T (test): 30 volumes** from the 352 not-reproduced. 5 per scroll for PHercParis4, PHerc0139, PHerc0500P2, PHerc1667, PHerc0814, PHerc0343P.
- **C1 (control): 10 volumes** reproduced at render scale 1 (`match_renderer` true).
- **C2 (control): 5 volumes** reproduced only at a non-1 isotropic scale.

Each volume is joined to the current catalog by path. Volumes not present in today's catalog are reported and not replaced.

## Measurements per volume

- **Catalog:** `derived_from` data_type/path, `scale`, `group-idx`, crop/affine/scale-segmentation fields, villa commit, and render date.
- **Volume:** `.zattrs` `canvas_size` and `0/.zarray` shape.
- **Mesh:** the named mesh's `meta.json` `scale` and the stored (H, W) from the `x.tif` IFD. Cross-checked against xframe's `published_shape` where available.
- **Mesh age:** `Last-Modified` of the named mesh's `x.tif` (HEAD) vs the render date, which flags possible mesh re-publication after the render.

## Pass/fail, fixed now

- **T:** H1 **supported** if ≥ 27/30 match exactly on both axes; **refuted** if ≤ 15/30; otherwise **inconclusive**, and non-matches are reported individually.
- **Controls:** C1 + C2 should match H1 too (expected ≥ 14/15). If < 12/15, H1's formula or join is wrong, and stage 1 is reported as inconclusive regardless of T.
- **Exclusions:** a volume whose provenance has a non-empty affine, crop or scale-segmentation is listed as not-applicable and not counted.
- No thresholds will be changed after fetching.

## Stage 2 (only if stage 1 supports H1)

Run the same measurement on **all** catalog `layers-zarr` volumes, and report counts exactly. No new criteria.

## Non-claims

This tests canvas size, not pixel content. Matching canvas sizes would show that each volume's grid is consistent with the named mesh. It would not show that the rendered voxels are correct.
