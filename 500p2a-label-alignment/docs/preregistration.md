# Pre-registration: are the 500p2a ink labels geometrically aligned with the render they ship with?

Sealed before any score, AUC, correlation or image of these predictions or labels was computed or viewed. What was read before sealing: file listings and sizes, and TIFF/PNG headers (shape, dtype, compression).

## Question

ink_9um is at chance on the bucket's 500p2a render: #1867 reports 0.4639–0.4983, and our label-free selector study measured a best arm of 0.5246. Both directions are affected. Is that because the labels (`500p2a_inklabels.tif`, `500p2a_supervision_mask.tif`, traced on an IR photo) are mirrored or offset relative to the CT render grid, or are they aligned and the fragment is simply not read?

## Data (fixed; HF bucket `scrollprize/datasets`, `ink/unused/500p2a/`; CC BY-NC, kept in do-not-redistribute folders)

All of these are uint8, (26239, 16182), the render's level-0 canvas (4.32 µm):

- P1 (primary): `preds/500p2a_canonical_030726_forward_070326.tif`
- P2: `preds/ps48_640_640_smooth_0.1_500p2a_ckpt_130000_forward_210326.tif`
- P3: `preds/ps512_ema_0.9995_500p2a_ckpt_080000_forward_230326.tif`
- P4: `preds/ps512_ema_0.9995_500p2a_ckpt_080000_reverse_230326.tif`
- Labels: `500p2a_inklabels.tif`, `500p2a_supervision_mask.tif`
- Exploratory only: `PHerc.500_ACass.28M1050IR_017_aligned.png` (RGBA, 16182 × 26239)

## Grid and labels

- Grid G: level 1 of the canvas, 13120 × 8091 (8.64 µm). Level-0 arrays are zero-padded to even size and pooled 2 × 2.
- R (scored region): G pixels whose 4 level-0 pixels are all > 0 in the supervision mask.
- Ink: ≥ 2 of the 4 level-0 pixels > 0 in inklabels. This is the same rule as the selector study.
- Prediction value on G: the 2 × 2 sum of level-0 uint8 values (0..1020). This is exact, with no rounding.

## Transform family (fixed)

- Orientation o ∈ {identity, flip-LR, flip-UD, rot180}, applied to the label maps (R and ink) about the full canvas G.
- Then an integer shift t = (dy, dx) ∈ [−256, 256]² G pixels (±2.2 mm): label pixel p is compared with the prediction at p + t.
- Pairs whose p + t falls outside G are dropped.

## Split

Using label coordinates before the transform:
- Half A (selection): R pixels with column < median column of R.
- Half B (evaluation): R pixels with column ≥ median column of R.

## Procedure (per prediction Pk, k = 1..4)

1. **Selection on A.** For every (o, t), compute the separation: mean prediction over ink pairs − mean over non-ink pairs. This uses FFT cross-correlation in float64. T*k = the (o, t) that maximizes it. Ties go to the smallest |dy| + |dx|, then the orientation order above.
2. **Evaluation on B.** Exact Mann–Whitney AUC (ties 0.5) from 1021-bin histograms, at T*k and at identity (o = identity, t = (0, 0)).
3. **CI.** Paired block bootstrap of Δk = AUC_B(T*k) − AUC_B(identity): 64 × 64 G-pixel blocks in label coordinates over half B, B = 2000, numpy seed 20261008.

## Verdict (decided on P1; P2–P4 are reported as replication)

- **MISREGISTERED:** T*1 is not near identity (o ≠ identity or max(|dy|, |dx|) > 8), and Δ1 ≥ 0.10 with the 95% CI lower bound > 0, and AUC_B(T*1) ≥ 0.65.
- **ALIGNED-READ:** not misregistered, and AUC_B(identity) for P1 ≥ 0.65. Meaning: the labels fit the render, and the organizers' model reads the fragment where ink_9um does not.
- **ALIGNED-UNREAD:** everything else.
- **Replication (reported):** the number of P2–P4 whose own verdict agrees with P1's, and whether their T* is within 8 px of T*1 (same orientation).

## Exploratory (not part of the verdict)

- AUC on the whole of R at identity of (255 − IR luminance), with luminance from RGB as 0.299R + 0.587G + 0.114B. Ink is expected dark in IR. Used to tell whether the labels follow the IR photo.
- The same AUC for the IR at T*1.

## Limitations stated in advance

- The organizer predictions' training data is not documented. If a model was trained on 500p2a, a high AUC at identity says the labels and the predictions agree, not that the fragment is readable out of sample. ALIGNED-READ is worded accordingly.
- ink_9um predictions are not used here: ours are on the PC, at the published level 1, which turned out to contain only planes 0–32 of the 65.

## Outputs

`results/metrics.json`, `results/summary.md`, `results/deviations.md`. Metrics only; no images. Scored once.

AI-assisted.
