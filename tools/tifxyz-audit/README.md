# tifxyz-audit

CPU-only QA CLI for **tifxyz mesh directories**: check `meta.json`, TIFF presence/headers,
optional invalid-point stats, bbox vs volume shape, and the villa **#1522** failure mode
where sibling meshes share `scale` but differ in physical voxel size (µm).

Built by **Scroll Ash Lab** around `vesuvius.tifxyz.meta_frames` (see villa issue
[#1522](https://github.com/ScrollPrize/villa/issues/1522)). This folder is a **standalone**
package; a matching `vesuvius.tifxyz_audit` entry point is also offered as a villa
`format-patch` (applied on top of the #1522 patch).

## What it checks

| Check | Severity | Notes |
|-------|----------|-------|
| `meta.json` present / JSON object | error | |
| `scale` present, finite, `> 0` | error | |
| unusually small `scale` (`< 1e-4`) | warning | may indicate stretch-factor misuse (#1319 class) |
| `voxel_size_um` present | info | |
| missing `voxel_size_um` but `-<float>um` in dirname | warning | inferable; use `--fix-meta` |
| missing and not inferable | warning | |
| siblings: same `scale`, different voxel sizes | warning | #1522 ambiguity (files can still be internally valid) |
| `x.tif` / `y.tif` / `z.tif` present | error | |
| TIFF header shapes match | error | needs `tifffile` |
| `z.tif` NaN / `-1` sentinel fractions | info/warning | sampled on huge arrays; needs `tifffile`+`numpy` |
| `bbox` parse / `-1` marker | warning/info | |
| `bbox` inside `--volume-shape Z,Y,X` | error/info | only if shape given |

Exit codes: `0` = no errors; `2` = one or more errors; with `--strict`, `1` = warnings only.

## Install (standalone)

```bash
cd experiments/tifxyz-auditor
# metadata-only (stdlib): already runnable as a module from this directory
PYTHONPATH=. python -m tifxyz_audit --help

# TIFF checks (recommended):
pip install -e ".[tiff]"
# or: pip install numpy tifffile && PYTHONPATH=. python -m tifxyz_audit ...
```

Optional editable install exposes the `tifxyz-audit` console script via `pyproject.toml`.

## Usage

```bash
# Audit a segment (looks under mesh/) or an explicit tifxyz dir / parent of meshes
python -m tifxyz_audit /path/to/segment
python -m tifxyz_audit /path/to/segment/mesh --json
python -m tifxyz_audit mesh_a.tifxyz mesh_b.tifxyz --strict

# Annotate voxel_size_um from dirname — never silent:
python -m tifxyz_audit mesh/ --fix-meta --output-dir /tmp/annotated --skip-tiff
python -m tifxyz_audit mesh/foo-2.4um.tifxyz --fix-meta --in-place --skip-tiff
```

### Sample output (synthetic #1522 layout)

```
tifxyz-audit: scanned 4 tifxyz directories
summary: 0 error(s), 5 warning(s), …
[WARNING] scale_frame_ambiguity: villa #1522: 4 meshes share scale=[0.05, 0.05] but voxel sizes differ: [1.129, 2.4, 7.91, 45.532] (spread≈40.33x) @ …/mesh
[WARNING] voxel_size_um_inferable: voxel_size_um missing; dirname implies 1.129um …
```

## Limitations (please read)

- **Does not** prove meshes are spatially correct, registered, or ink-accurate.
- **#1522 ambiguity is a warning**, matching the upstream issue: each file can be
  internally valid; the trap is cross-mesh comparison.
- TIFF invalid-point stats on large files are **strided samples**, not always exact.
- `--volume-shape` is caller-supplied; the tool does not download volumes.
- Standalone mode vendors `meta_frames.py` from the #1522 work; keep it in sync if
  upstream changes.
- Open-data smoke tests use the public `vesuvius-challenge-open-data` bucket
  (**CC BY-NC 4.0**). That is not the Vesuvius `accept_terms` clickwrap; still respect
  the CC license for any redistribution.

## Tests

```bash
PYTHONPATH=. python -m pytest tests -v
```

## License

MIT. Upstream villa code remains under villa’s license.

## Open-data smoke (recorded)

Anonymous HTTPS GET from bucket `vesuvius-challenge-open-data` (`LICENSE.txt` =
**Creative Commons Attribution-NonCommercial 4.0**). No interactive clickwrap and
no `vesuvius.accept_terms` were used. CC BY-NC still restricts commercial reuse.

Paths fetched:

1. `PHercParis4/segments/20230702185753/mesh/20230702185753-on-20260608103018-1.129um.tifxyz/meta.json`
2. `…/20230702185753-on-20260411134726-2.4um.tifxyz/meta.json`
3. `…/20230702185753-on-20230205180739-7.91um.tifxyz/meta.json`
4. `…/20230702185753-on-20260310170716-45.532um.tifxyz/meta.json`
5. `…/20230702185753-on-20260310170716-45.532um.tifxyz/{x,y,z}.tif` (~52 KiB each)

Metadata audit result: 0 errors; `#1522` warning that **4** meshes share
`scale≈0.05` with voxel sizes `[1.129, 2.4, 7.91, 45.532]` (spread ≈ 40.33×).
See `smoke/smoke-meta-only.txt` and `smoke/smoke-small-tiff.txt`.
