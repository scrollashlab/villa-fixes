# xframe

> Corpus results (902/902 consistent, the 112-segment downscale trap, 67.2 GB of up-sampled-only meshes): see `FINDINGS.md` and `results/` in the published bundle.

CPU-only command-line tool and library for working with **tifxyz meshes across scan frames** in the Vesuvius Challenge open data (`vesuvius-challenge-open-data`). It needs only the catalog (`metadata.json`) and the mesh files: no CT reads, no GPU.

Each published segment ships several meshes, one per scan volume (`<id>-on-<volume>-<µm>.tifxyz`). They all declare `scale` 0.05 (villa #1522), so the bucket alone doesn't tell you which mesh is traced geometry, how the others were made, or how to move your own points between frames. `xframe` answers those questions with the pipeline's own rule. That rule was read from villa `vc_transform_geom` / `transformSurfacePoints` / `QuadSurface::resample` and ported line-for-line:

> derived mesh = regrid( T · (s · normalized) ), with T = the sample-level catalog matrix original→target, s = `original_volume_downscale`, regrid = spacing-ratio bilinear resample that skips invalid corners and keeps `scale`.

## Commands
```bash
pip install .            # numpy, tifffile, imagecodecs (some published TIFFs are LZW); Python >= 3.9
xframe frames  PHerc0139                              # volumes, voxel sizes, catalog transforms
xframe explain PHerc0139 20250108000004               # each mesh: role, frame, µm, transform, UP/DOWN-sampled grid
xframe verify  PHerc0139 20250108000004               # rebuild every derived mesh from its source; residual in voxels and µm
xframe convert --sample PHerc0139 --from 20260102150214 --to 20250728140407 points.csv out.csv
xframe convert --sample PHerc0139 --from-normalized-of 20250108000004 --to 20250728140407 \
    PHerc0139/segments/20250108000004-w029_2025010827/mesh/intermediate/tifxyz_normalized/ out.tifxyz
```
Options common to all commands:
- `--catalog metadata.json` uses a local catalog copy.
- `--bucket-root DIR` reads offline from a bucket-shaped directory.
- `--cache-dir DIR` keeps downloads.

By default files are streamed over anonymous HTTPS and nothing is written to disk. `verify` exits 0 if every mesh is CONSISTENT, 1 otherwise, and 2 on errors.

Classes (fixed before any real data was compared):
- **CONSISTENT:** at most 1% of cells off by more than 0.5 target voxel.
- **DRIFT:** more than 50% of cells off by more than 1 voxel.
- **PARTIAL:** anything in between.
- **NOT_COMPARABLE:** the predicted grid shape differs from the published one.

## What it does not do
- It does **not** check whether a catalog matrix is *correct*. Published meshes inherit any matrix error exactly. For landmark checks see villa #1835 and PR #1994; for the PHerc1667 1.129 µm case see #1843.
- It does **not** check whether a mesh sits on papyrus (e.g. #1912).
- "UP-sampled" means the extra grid cells come from bilinear interpolation of the source mesh. That says nothing about ink-reading quality.

## Tests
```bash
python -m venv .venv && .venv/bin/pip install ".[test]"
.venv/bin/python -m pytest tests -q                         # offline: ports vs reference code, fake bucket, CLI
XFRAME_REAL=1 .venv/bin/python -m pytest tests -q           # + live bucket checks (PHerc0139 w029, downscale 4)
```
The offline fake-bucket tests check internal consistency, including a shifted-mesh negative control. Fidelity to VC itself comes from the live tests and the corpus run, because the published meshes there were produced by VC.

## Related work and credit
- villa #1522 (jonmarrs): frames that the `scale` field can't tell apart, with a corpus census. PR #1944 (saschaivanov-lgtm): metadata-only frame-provenance preflight.
- **`tifxyz-audit` by jaideepsaipadhi** (villa #1468/#1469, listed on scrollprize.org community projects): cross-scan bbox-centre consistency through catalog transform chains. Scroll Ash Lab's earlier `vesuvius.tifxyz_audit` villa entry point (#1522 follow-up: `meta.json` checks, `voxel_size_um`) is a **separate, unrelated tool** that happens to share the name. `xframe` is new and distinct from both: it checks every grid point, not just bbox centres, and converts points.
- #1835 / PR #1994 (matrix vs landmarks), #1843, #1845 / PR #1851 (which mesh to use), #1727 (surface-volume reproducibility), #1734 (bbox through downscale).

## Data and license
Code: MIT. The open data is **CC BY-NC 4.0**; `xframe` reads it anonymously and redistributes none of it. No test fixture contains bucket data: the offline fixtures are synthetic.

Built by Scroll Ash Lab with AI assistance: an AI agent wrote the code, tests and this README.
