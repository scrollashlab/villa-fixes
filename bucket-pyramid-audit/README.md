# Ink-bucket render pyramids: level 1 holds only the first half of the depth in 18 of 76 stores

**Short answer:** in the Hugging Face bucket `scrollprize/datasets`, 18 of the 76 render stores under `ink/` have a level 1 that holds only the first 33 of their 65 level-0 planes. All 18 still declare the in-plane-only scale [1, 2, 2]. 14 of them were not known before.
- 12 match the rule exactly: the first ⌈N/2⌉ planes, 2×2 in-plane mean, half-up, with 0 differing voxels.
- 6 more were found by plane correlation.

On three PHerc0841 segments, the same two checkpoints score 0.018–0.097 AUC lower on the published level 1 than on a correctly pooled input.

## Why we looked
`vesuvius.ink_detection.inference.infer` centre-crops its 17-plane window from whatever depth the chosen level holds. We had found four stores whose level 1 kept only planes 0–32. This census measures how widespread that is.

## Method (pre-registered, sha256 `9d8bfa3f…3c86`, sealed 2026-10-08 21:54:32 HST; full text in `docs/preregistration.md`)
- **Population:** every `<segment>/<segment>.zarr` render under `ink/` (76 stores, `meta/stores.json`).
- **Probes:** for level 1 vs 0 and level 2 vs 1, two probe chunks over the full depth per store, at fixed positions.
- **Rules:** tested exactly, each with four roundings:
  - INPLANE_ALL: all planes kept;
  - TRUNC: first planes only;
  - POOL: 2×2×2 mean;
  - CTR: centred planes.
- **Positive control:** the four known stores must come out TRUNC half-up. They did.
- **Decision rule:** if TRUNC appears beyond the known four, report a bucket-wide data issue.

## Results (`results/summary.md`, `results/census.json`, `results/audit.json`)
| | level 1 | level 2 |
|---|---:|---:|
| TRUNC (exact) | 12 | 12 |
| INPLANE_ALL | 17 | 16 |
| OTHER | 47 | 48 |

- The 12 exact TRUNC stores are 1 in PHerc0009B, 3 in PHerc0139, 1 in PHerc0500P2, 2 in PHerc1667, 1 in PHerc0814, 3 in PHerc0841 and the unused 500p2a. None declares a z scale > 1.
- Post hoc, the OTHER class splits three ways (labelled as post hoc in `results/deviations.md`):
  - **38 stores, full depth:** exact strided decimation of every second plane, matching their declared z scale of 2.
  - **6 stores, first half only:** they hold the first 33 planes (each child plane best matches parent plane k, r ≥ 0.928).
  - **3 stores, full depth:** all 65 planes kept, with an in-plane filter outside the tested family.

**Source.** On villa `main` between #774 (2026-03-04 UTC) and #804 (2026-04-15 UTC), `createPyramidDatasets` halved z in the level shapes. Meanwhile `downsampleTileIntoPreserveZ` wrote 2×2 in-plane means plane by plane and stopped at the halved depth, with half-up rounding. #804 fixed the code. Renders built with the affected code remain in the bucket.

**Consequence (post hoc, descriptive).** PHerc0841 w00 and two auto_grown segments, seed42/43 step 75,000, reverse direction, same pixels:

| segment | seed | published level 1 | pooled 2×2×2 | difference |
|---|---|---:|---:|---:|
| w00 | 42 | 0.6459 | 0.6959 | +0.0500 |
| w00 | 43 | 0.6223 | 0.7194 | +0.0971 |
| auto_grown …144552896 | 42 | 0.6631 | 0.7357 | +0.0726 |
| auto_grown …144552896 | 43 | 0.6976 | 0.7556 | +0.0579 |
| auto_grown …174252405 | 42 | 0.6335 | 0.6630 | +0.0295 |
| auto_grown …174252405 | 43 | 0.6535 | 0.6717 | +0.0182 |

The two inputs differ in both window position and z spacing, so this measures what a user of the published level 1 got. It does not isolate either factor.

## Independent re-check (`verify/`)
A second reader with no code shared with `scripts/audit.py` (zarr-python 3.4 + fsspec over HTTPS) re-read 5 stores at chunk positions different from the census probes, 2 chunks each:
- `ink/0139/w016_2025010815`, `ink/814/814_46527_2um_try2` and `ink/0500p2/-1`: level 0 has 65 planes and level 1 has 33. Level 1 equals the half-up 2×2 mean of the first 33 level-0 planes, with 0 differing voxels in 6 of 6 chunks.
- `ink/1667/w028_20251208130119156_2um` (one of the 6 correlation-matched stores): 65 → 33 planes. It is not the exact rule, but every child plane k matches parent plane k with r ≥ 0.985.
- `ink/unused/0139/w024_2026021572` (strided): 65 → 33 planes, declared scale [2, 2, 2]. Level 1 equals level 0 at planes 0, 2, …, 64, with 0 differing voxels in 2 of 2 chunks.

The code cause is quoted from the public villa sources in `verify/code_cause.log`.

## Proposed fix
- Rebuild levels 1–5 of the 18 stores from their intact level 0 with the current pyramid code (keep all planes, scale [1, 2, 2]), or pool z and declare [2, 2, 2].
- Optionally, add a reader guard in `infer.py` that stops when a level's depth shrank while its declared z scale stayed 1.

## Reproduce
```
python -B scripts/discover.py        # meta/stores.json (HTML directory listings)
python -B scripts/audit.py           # results/audit.json (~1.55 GB of chunks read, nothing kept)
python -B scripts/diagnose_other.py  # post hoc
python -B scripts/diagnose_corr.py   # post hoc
python -B scripts/build_summary.py   # results/summary.md, results/census.json
python -B -m pytest -q -p no:cacheprovider tests/test_audit.py
```
Python 3 with numpy and numcodecs. Read-only, unauthenticated HTTPS.

AI-assisted.
