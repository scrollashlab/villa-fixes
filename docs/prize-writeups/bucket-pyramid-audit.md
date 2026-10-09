# Ink-bucket render pyramids that drop half the depth

**Folder:** `bucket-pyramid-audit/`. Pre-registered (sha256 `9d8bfa3fa12a0681d8cc0ff0b24178e027c38395d5fae5e89b94eadffdb73c86`, sealed 2026-10-08 21:54:32 HST, before any chunk was fetched). Scored once.

## Finding
In the Hugging Face bucket `scrollprize/datasets`, 18 of the 76 render stores under `ink/` have a level 1 that holds only the first 33 of their 65 level-0 planes, while their metadata declares scale [1, 2, 2] (in-plane only).
- 12 match exactly: the first ⌈N/2⌉ planes, each a 2×2 in-plane mean rounded half-up, with 0 differing voxels over both probes.
- 6 more were found post hoc by plane correlation: every child plane k matches parent plane k, r ≥ 0.928.
- In 9 of the 12 exact stores, level 2 repeats the cut (17 planes).
- The affected stores are in PHerc0009B, PHerc0139, PHerc0500P2, PHerc0814, PHerc0841 and PHerc1667, plus the unused 500p2a.

The other stores keep the full depth: 17 keep all planes, 38 are strided z decimation that matches their declared z scale 2, and 3 keep all planes with another in-plane filter.

## Why it matters
`vesuvius` ink inference centre-crops its 17-plane window from the depth of the level it reads. On a truncated level 1 that window is centred near level-0 plane 16 instead of plane 32, and nothing errors. On PHerc0841 (3 segments × seeds 42/43, step 75,000, reverse direction, identical pixels), the published level 1 scores 0.018–0.097 AUC below a correctly pooled 2×2×2 input. This comparison is post hoc and mixes window position with z spacing.

## Source and fix
Between villa #774 (2026-03-04 UTC) and #804 (2026-04-15 UTC), `createPyramidDatasets` halved z in the level shapes. `downsampleTileIntoPreserveZ` then wrote in-plane means plane by plane and stopped at the halved depth. The result is exactly the measured rule, including the half-up rounding. #804 fixed the code.

The proposed data fix is to rebuild levels 1–5 of the 18 stores from their intact level 0 with the current code, or to pool z and declare a z scale of 2. An optional reader guard in `infer.py` would stop when a level's depth shrank but its declared z scale stayed 1.

## Caveats
- Two probe chunks per level and store.
- `ink/` renders only, bucket state of 2026-10-08.
- The in-plane rule of the 6 correlation-matched stores is not identified.
- No chunk data is redistributed.
- AI-assisted.
