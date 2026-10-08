# sv-canvas-1727: every published surface volume's canvas follows from the mesh the catalog names

Scroll Ash Lab, 2026-10-07 (HST). **AI-assisted:** an AI agent designed, ran and wrote this.
Everything here is **metadata only**, read anonymously from the public bucket on 2026-10-07: the catalog `metadata.json`, surface-volume `.zattrs` and `0/.zarray`, mesh `meta.json`, and the TIFF header of `x.tif`. No volume or mesh payloads were downloaded or included.

## Finding

**692/692** surface volumes (`layers-zarr`) in the 2026-10-07 catalog reproduce exactly from the mesh the catalog names as their source:
- the `canvas_size` in `.zattrs` matches;
- the level-0 array shape (H, W) matches.

This covers **627 of the 628** volumes in villa #1727's inventory. The 628th is no longer in the catalog (see Caveats). Since #1727's 366 "non-reproducible" volumes are drawn from those 628, at least 365 of the 366 reproduce. The 65 volumes published since #1727's inventory also match.

The rule is the renderer's own canvas formula (`vc_render_tifxyz.cpp`, unchanged at all five villa commits the renders were built from), applied per axis:

```
canvas = max(1, lround(stored * render_scale / float32(meta.scale)))
render_scale = scale * 2^-group_idx
```

- `stored` and `meta.scale` come from the mesh named in the volume's catalog entry, `creation_info.derived_from`. For 688 volumes that is the published transformed mesh `<id>-on-<volume>-<µm>.tifxyz`; for 4 it is `tifxyz_normalized`.
- `scale` and `group-idx` come from the same entry's render parameters: scale is "1" in all 688 transformed renders; group-idx is 0 for 577 and 1 for 111, exactly the 111 `-L1.zarr` volumes.
- Affine, crop and segmentation-scale parameters are empty in all 692 records.

## Mechanism

The renders were made from the transformed meshes, sized directly from their stored grids. A transformed mesh is the normalized mesh regridded **separately on each axis**: `round(n · factor)`, with a factor measured per axis. Our xframe tool verified this rule on all 902 published transformed meshes (`xframe/`).

That is why no single isotropic scale links a surface volume to the normalized mesh. #1727 observed exactly this as a per-axis difference in implied scale.

**Worked example** (the one #1727 cites): PHerc0139 `20250108000000-w025_2025010863` on the 1.129 µm volume `20260413113053`.

| Step | Rows × cols |
|---|---|
| `tifxyz_normalized` grid | 354 × 331 |
| Published transformed mesh `20250108000000-on-20260413113053-1.129um.tifxyz`. xframe regrid factors 8.5096 / 8.5081; predicted shape = x.tif header | 3012 × 2817 |
| Canvas: 3012 · 2^-1 / float32(0.05) and 2817 · 2^-1 / float32(0.05) (group-idx 1) | **30120 × 28170** = the published `canvas_size` [28170, 30120] (W, H) |

From the normalized grid, 30120 · 0.05 / 354 = 4.2542 but 28170 · 0.05 / 331 = 4.2553. These are the two implied scales #1727 reported. They differ only because of the per-axis regrid.

## Why #1727 did not see this

#1727 (ge-al) is a careful, fully documented measurement:
- It inventoried every mesh directory across 315 segments.
- It pinned the renderer's canvas formula (with @Bullo27's binary measurements in #1699).
- It published per-volume data, and it named "a different mesh / transform applied before sizing" as the likeliest explanation.

Its inventory script (`scripts/inventory.py` in github.com/ge-al/vesuvius-cpu-repro @ 113bbb9) lists mesh sub-directories only when the name contains no `.`. The transformed meshes are named `*.tifxyz`, so they were not among the compared variants. `audit/pairs.json` contains `tifxyz_normalized`, `tifxyz_original`, `tifxyz_flattened` and `tifxyz`, and no `-on-` meshes. Once those meshes are included, the canvas-size question in #1727 is answered (voxel content was not checked).

On "nothing in the bucket says which mesh produced a volume":
- That is accurate for the volume's own `.zattrs`. All 692 carry only `canvas_size`, `chunk_size`, `multiscales`, `note_axes_order`, `num_slices`, `source_group`, `source_zarr` and (688 of them) `slice_step`. Open PR #1901 would record provenance there for future renders.
- The bucket-root `metadata.json` does name the source mesh and render parameters, at least as of 2026-10-07.

## Method and controls

- **Pre-registration.** `docs/preregistration.md` was written 2026-10-07 10:26:20 HST, before any sample metadata was fetched; its hash is in `docs/preregistration.sha256`.
  - Hypothesis, sample and pass/fail thresholds were fixed there.
  - The sample: 30 volumes #1727 could not reproduce (5 per scroll × 6 scrolls), plus 15 controls #1727 did reproduce.
  - Pass: ≥ 27/30 exact.
- **Stage 1** (`results/stage1-2026-10-07.json`, generated 10:26:34 HST):
  - Test volumes matched **29/29** present. One of the 30 is no longer in the catalog and was reported, not replaced.
  - Controls matched **15/15**.
- **Stage 2** (`results/stage2-all-2026-10-07.json`): all 692 volumes, **692/692**, both `canvas_size` and level-0 shape.
- **Wrong-mesh control** (`scripts/controls.py` → `results/controls-2026-10-07.txt`):
  - Predicting each volume's canvas from every *other* published transformed mesh of the same segment matches in 53 of 1,563 pairs.
  - All 53 are expected ties: the named mesh is a byte-copy of the normalized grid, and the other is an unregridded derived mesh with the identical grid.
  - For every volume whose named mesh was regridded, no other mesh matches.
- **Cross-check.** For all 688 transformed meshes, the stored grid read from the x.tif header equals xframe's independently predicted and verified shape.
- **Parent spot-check.** The lab's parent agent independently re-fetched 10 volumes live from the bucket with its own code: the w025 1.129 µm example plus 9 chosen at random with seed 1727. **10/10** match on `canvas_size` and level-0 shape. It also confirmed that the inventory skips dotted names and that `pairs.json` has 0 `-on-` meshes.

## Caveats

- **Canvas sizes only.** This shows that each volume's grid size is consistent with the named mesh and recorded parameters. It does not show that the rendered voxels are correct.
- **Catalog history unknown.** We cannot tell whether `metadata.json` carried the `derived_from` / render-parameter fields on 2026-09-07, when #1727 was measured.
- **352 vs 366.** #1727's exact "reproduced at a clean isotropic ratio" step is not in its scripts. Our reconstruction (`scripts/reconstruct_geal_classes.py`, any isotropic scale) is more permissive and gives 276/352 rather than 262/366. It is used only to pick the stage-1 sample and for the per-scroll breakdown. The 627/628 statement does not depend on it.
- **One volume untested.** PHerc0814 `20260226123353-auto_grown_20260226123353106/surface-volumes/1.129um-0.22m-59keV-volume-20260521123630-L1.zarr` is in #1727's inventory but not in today's catalog. It is the empty-chunk volume of #1892 / #1963.
- **Single snapshot.** One catalog snapshot (2026-10-07 09:14 HST) and one day's bucket state.
- **Not used for any conclusion.** S3 `Last-Modified` of a mesh's `x.tif` is later than the catalog render date for 169 meshes. It reflects the copy into the open-data bucket.

## Practical use

To size labels or masks for a published surface volume without downloading it:
- take the mesh in the catalog's `creation_info.derived_from`, not `tifxyz_normalized`;
- take `render_scale = scale · 2^-group-idx` from the same entry.

villa's Python canvas helper from #1699 then reproduces the exact canvas.

## Reproduce

```
python scripts/reconstruct_geal_classes.py <vesuvius-cpu-repro>/audit/pairs.json results/geal-classes-reconstructed.json
python scripts/measure.py stage1 results/stage1.json      # pre-registered sample
python scripts/measure.py stage2 results/stage2.json      # all catalog surface volumes (~30 s, 12 threads)
python scripts/controls.py
```

The scripts need Python 3 and numpy, and use the standard library for HTTPS. They were run from the lab's working layout, where outputs lived in `out/` (here `results/`); `controls.py` reads `out/stage2-all-2026-10-07.json`. Path constants at the top of `measure.py` and `controls.py` point at the lab's local copies; set them for your checkout:
- `CAT`: catalog `metadata.json` from the bucket root;
- `XF`: xframe's `full-verify-2026-10-07.jsonl`, published under `xframe/`;
- `GEAL`: ge-al's `pairs.json`.

## Data and license

- Code: MIT.
- Results: metadata-derived numbers and bucket keys only.
- The open data is CC BY-NC 4.0; nothing from it is redistributed here.

## Credits

- **villa #1727, ge-al.** The question, the inventory, and the renderer canvas formula.
- **gaogao94.** The #1727 comment showing the non-reproducible set is not the unitless-scale class (#1951).
- **#1699** (ge-al, with @Bullo27's renderer measurements): the canvas formula in `vesuvius.tifxyz`.
- **#1845** (kadenpool): which mesh to render from.
- **PR #1901** (DarthCeltic): render provenance in `.zattrs`.
- **#1892 / #1963** (Sartoshirelli, Svyable): the empty PHerc0814 volume.
- VC / villa authors: `vc_render_tifxyz`.
- The Vesuvius Challenge open-data team, for the catalog provenance.
