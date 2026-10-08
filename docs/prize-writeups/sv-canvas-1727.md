# sv-canvas-1727 — #1727's "non-reproducible" surface volumes reproduce exactly from the published transformed meshes

Upstream: [villa #1727](https://github.com/ScrollPrize/villa/issues/1727). This is a measurement, not a patch. Related: [#1699](https://github.com/ScrollPrize/villa/pull/1699), [#1845](https://github.com/ScrollPrize/villa/issues/1845), [PR #1901](https://github.com/ScrollPrize/villa/pull/1901), [#1892](https://github.com/ScrollPrize/villa/issues/1892)/[#1963](https://github.com/ScrollPrize/villa/issues/1963)  
Evidence: `sv-canvas-1727/` (`README.md`, `docs/preregistration.md`, `results/`). The transform rule comes from `xframe/`.  
Credit: ge-al (#1727 question, inventory and per-volume data; #1699 canvas formula), Bullo27 (renderer measurements in #1699), gaogao94 (#1727 comment), kadenpool (#1845), DarthCeltic (PR #1901), Sartoshirelli / Svyable (#1892/#1963)  
Author: Scroll Ash Lab \<scrollash.lab@gmail.com\> (AI-assisted)

## Problem

#1727 measured that 366 of 628 published surface volumes cannot be reproduced to the pixel from any published mesh variant using `vc_render_tifxyz`'s canvas formula at one isotropic render scale. It also noted that nothing in a volume's `.zattrs` says which mesh or transform produced it. Downstream tools therefore could not size labels or masks for those volumes from mesh metadata.

## What we found

- **692/692** surface volumes in the 2026-10-07 catalog reproduce exactly, on both `canvas_size` and the level-0 shape, from the mesh the catalog names in `creation_info.derived_from`. The canvas is the renderer's formula `lround(stored · render_scale / float32(meta.scale))` with `render_scale = scale · 2^-group-idx`, taken from the same catalog record.
- That covers **627/628** of #1727's inventory. The remaining volume is no longer in the catalog. So at least 365 of #1727's 366 reproduce, plus the 65 volumes published since.
- **Mechanism.** The renders used the published transformed meshes (`*-on-<volume>-<µm>.tifxyz`). Those meshes are regridded separately on each axis, which xframe verified 902/902, so no single isotropic scale links a volume to the normalized mesh.
- **Worked example** (the one #1727 cites), PHerc0139 w025 on 1.129 µm:
  1. The normalized grid is 354×331.
  2. The transformed mesh is 3012×2817.
  3. At group-idx 1 the canvas is 30120×28170, which equals the published canvas.
- **Why it was missed.** #1727's inventory script lists only mesh directories without a `.` in the name, so the transformed meshes were not compared. #1727's measurement is otherwise careful and fully documented, and it named this family of explanation as the likeliest.

## Real-data numbers

Public metadata only, catalog snapshot 2026-10-07 09:14 HST. Source: `sv-canvas-1727/results/`.

| Stage | Result |
| --- | ---: |
| Pre-registered sample (written 10:26:20 HST, sha256 recorded), #1727-not-reproduced volumes | **29/29** present (29/30 planned; 1 no longer in the catalog). Pass bar ≥ 27/30 |
| Pre-registered controls (#1727-reproduced) | **15/15** |
| All catalog surface volumes | **692/692** (canvas and level-0 shape) |
| #1727's inventory still in the catalog | **627/627** (of 628) |
| Wrong-mesh control (other meshes, same segment) | 53/1,563 match, all byte-identical-grid ties. No other mesh matches when the named mesh was regridded |
| Parent independent spot-check (own code, live bucket; the w025 example + 9 random, seed 1727) | **10/10** |

Renderer formula lines are identical at all five villa commits that built the renders (530584554c, 650bd566, 862bd172, bc28564d, ae2ecce9).

## Limitations

- Canvas sizes only, not voxel correctness.
- We cannot tell whether `metadata.json` carried the source-mesh fields on 2026-09-07, when #1727 was measured. The volumes' `.zattrs` still lack them (PR #1901 addresses future renders).
- Our reconstruction of #1727's classes gives 276/352 rather than 262/366, because its clean-ratio step is not in its scripts. The reconstruction is used only for sample selection; the 627/628 result does not depend on it.
- One volume is untested: the empty PHerc0814 1.129 µm L1 volume (#1892/#1963), which has been removed from the catalog.
- Single catalog snapshot. AI-assisted.

## How to reproduce (no CC BY-NC redistribution)

Metadata only: `.zattrs`, `.zarray`, `meta.json`, and the `x.tif` TIFF header via HTTP Range, from  
`https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/`.

```bash
cd sv-canvas-1727
python scripts/reconstruct_geal_classes.py <vesuvius-cpu-repro>/audit/pairs.json results/geal-classes-reconstructed.json
python scripts/measure.py stage1 results/stage1.json
python scripts/measure.py stage2 results/stage2.json     # ~30 s
python scripts/controls.py
```

Set the path constants at the top of the scripts: catalog, `xframe/results/full-verify-2026-10-07.jsonl`, and ge-al's `pairs.json`.
