# Pre-registration: #1648 held-out L0-vs-L2 input-scale matrix

Status: sealed before any inference was run on these crops and before any scoring.
Seal time and sha256 are recorded in `preregistration.sha256` next to this file.
AI-assisted: this design, its code and its analysis were prepared with AI assistance.

## Question

The #1648 patch logs a WARNING when the in-plane input scale is below 0.55 x 9.6 um, which
means the input is much finer than the ink_9um training grid. The only evidence so far comes
from one exploratory window on PHerc0814 segment 46527, rows 1624-2035 and columns 258-769
at L2. That window is inside this matrix's 46527 validation mask, so 46527 is not independent
of the earlier evidence. The other two segments are.

Question: does the public `scrollprize/ink_9um` hybrid_3d2d model score ink better from the
9.6 um (L2) input than from the 2.4 um (L0) input of the same physical region? Each segment is
scored only inside its released validation mask.

## Data (fixed before inference)

The held-out cases come from the HF bucket `scrollprize/datasets`, path
`ink_9um/labels/aligned-scrollprizeorg-21slices/<case>/`. Labels and masks are channel 10 of
`<case>_{inklabels,validation_mask}.zarr/0`, on the L2 grid. A pixel is positive if its label
is nonzero; a pixel is scored if its mask is nonzero.

| case | L2 shape | mask px | pos | neg |
|---|---|---|---|---|
| pherc0139-w016 | 7020x7220 | 178,146 | 41,253 | 136,893 |
| pherc0814-46527 | 2130x3455 | 161,051 | 60,127 | 100,924 |
| pherc1667-w029 | 9500x7830 | 382,353 | 88,034 | 294,319 |

Inputs come from the public source surface volume named in each label's metadata (level 2
and level 0; level 0 is exactly 4x level 2 in-plane).

- **Crop.** Each crop is the mask bbox +/-128 L2 px, clipped to the volume. The L0 crop is the
  same region x4.
  - pherc0139-w016: y[4816,5553) x[1675,4083)
  - pherc0814-46527: y[1496,2130) x[130,945)
  - pherc1667-w029: y[2982,5301) x[4789,7347)
- **Fetched chunks.** Only the source chunks intersecting the mask dilated by 128 L2 px (for
  L2) or by 32 L2 px = 128 L0 px (for L0) were fetched. Every model patch that covers a mask
  pixel lies inside these chunks. Other chunks in the crop are 0, which is the source
  fill_value.
- **Preparation.** Villa's own `prepare_isotropic_input` (villa main 8b63a2652) builds the
  21-plane input: centered 84 of 109 planes = [13,97], rounded mean of 4 planes, uint8. This
  matches the label metadata (`source_z_slice` [13,97], 21 slices).

## Arms and runs

- Model: `scrollprize/ink_9um` `hybrid_3d2d-seed42/step-075000.pth` (sha256 e635558a...9cab)
  and `hybrid_3d2d-seed43/step-075000.pth` (sha256 2aeaa85a...b28f).
- Runs: 3 cases x {L2, L0} x {seed42, seed43} x {forward, reverse} = 24 runs.
- Command: villa main 8b63a2652, unpatched, `python -m vesuvius.ink_detection.inference.infer
  <prepared.zarr> <ckpt> <out.tif> --direction <dir> --no-compile --num-workers 0
  --batch-size 16 --amp-dtype auto --mask-path <scheduling mask>`.
  - Everything else is at the default: overlap 0.5, blend auto (Hann), default layer
    selection.
- Scheduling mask: the validation mask cropped to the run's grid (for L0, nearest-upsampled
  x4). In villa, `--mask-path` only (a) skips patches that contain no mask pixel and (b)
  multiplies blend weights by the mask. Inside the mask the weight factor is 1, and every patch
  that overlaps a mask pixel is still scheduled. So predictions inside the mask equal those of
  an unmasked run of the same crop.
  - This is checked once before the matrix: pherc0814-46527, L2, seed42, forward, masked vs
    unmasked. They must match exactly on all mask pixels. If they do not, all runs go unmasked.
- GPU: one RTX 5060 on a shared desktop. If the projected matrix time exceeds about 15 min,
  the rest is deferred to after 22:00 HST. Deferral does not change the design.

## Prediction grid

- L2 arm: the uint8 output value v (0-255) at each mask pixel.
- L0 arm: the 16 uint8 outputs of the 4x4 L0 block under each L2 pixel are summed to
  s (0-4080). This is an exact 4x4 mean pool, kept as an integer sum.
- For scoring, both are mapped to a common 4096-bin integer score: L2 -> 16*v, L0 -> s. AUC
  depends only on ranks, so this mapping is exact.
- Sensitivity check (reported, not part of the verdict): L0 requantized to floor(s/16).

## Metrics

- Primary: ROC AUC over mask pixels, with label > 0 as positive. Computed exactly as
  Mann-Whitney U / (n_pos * n_neg), with ties counted as 0.5, from 4096-bin positive and
  negative score histograms.
- Secondary (descriptive only): average precision, computed from the same histograms by
  step-wise precision-recall over distinct score thresholds from high to low.
- Effect: delta = AUC_L2 - AUC_L0, for the same case, seed and direction.

## Confidence interval

- Method: paired block bootstrap on the L2 grid.
- Blocks: 64x64 L2 px tiles aligned to the global L2 origin (floor(y/64), floor(x/64)). Only
  blocks containing at least one mask pixel are used.
- Each replicate resamples blocks with replacement, matching the observed block count, and
  recomputes both AUCs from the summed per-block histograms of the resampled blocks.
- Draws: B = 2000 replicates, numpy `default_rng(1648)`. One draw matrix per case is shared
  by all of that case's seed/direction comparisons, and the L2 and L0 arms use the same draws
  (paired).
- CI: percentile 2.5 / 97.5 of the replicate deltas.

## Kill test and verdict (fixed)

- **Operative direction.** For each segment, the operative direction is the one with the
  higher mean of its four AUCs (L0 and L2, seed42 and seed43). Ties go to forward.
  - This choice is symmetric in L0 vs L2, so it cannot favour either arm.
  - It replaces the earlier "forward" shorthand: the depth order of these segments is not
    known in advance, and #1648 itself concerns order. Forward-only and reverse-only results
    are reported as secondary.
- **Segment outcomes.**
  - Confirms: for both seeds in the operative direction, delta > 0 and the 95% CI lower
    bound > 0.
  - Contradicts: for both seeds in the operative direction, the 95% CI upper bound < 0.
  - Otherwise: inconclusive.
  - A segment that cannot be scored (failed run or empty output) counts as not confirming.
- **Verdict.**
  - CONFIRM: 2 or more of the 3 segments confirm. The #1648 in-plane-scale WARNING stays and
    its evidence is updated with this matrix.
  - DOWNGRADE: otherwise. The in-plane-scale message in the #1648 patch becomes INFO, and its
    tests and write-up are updated and re-verified (git am on villa main, pytest).
  - Any segment that contradicts is reported explicitly.

## Validity checks (reported, not part of the verdict)

- Each output TIFF has the crop shape. No mask pixel has zero blend weight, checked as: no
  mask pixel falls in an all-zero input region.
- Fraction of mask pixels whose prepared 21-plane input is all zero, per case and level.
- Input checksums: decoded prepared arrays (sha256 of the C-order bytes) on the box and on
  the PC must match.
- Checkpoint sha256 must match the values above.

## Deviations

Any deviation from this document is listed in `results/deviations.md`, with its reason. This
file is not edited after sealing.

## Licensing

Ink labels, masks, source crops and predictions (CC BY-NC) stay in `data-do-not-redistribute`
folders on the box and the PC. Only metrics and code are published.
