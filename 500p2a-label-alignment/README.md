# Are the 500p2a ink labels misaligned with the render? (No rigid misalignment found)

**Short answer:** no. Over 4 orientations and ±256 px shifts (±2.2 mm at 8.64 µm), no rigid transform of the 500p2a labels makes any of the four organizer-published predictions read the fragment. The verdict was pre-registered: **ALIGNED-UNREAD**. All four predictions agree.

## Why we looked
ink_9um scores at chance on 500p2a (#1867 reports 0.4639–0.4983). A mirrored or shifted label map would produce exactly that. We tested this directly, and we did it on the organizers' own predictions so that the result does not depend on our model.

## Method (pre-registered, sha256 `3910d3f3…a1c5`, sealed 2026-10-08 20:30:27 HST; full text in `docs/preregistration.md`)
- **Inputs:** the four organizer predictions for 500p2a and `500p2a_inklabels.tif` / `500p2a_supervision_mask.tif`. All come from the HF bucket `scrollprize/datasets`, `ink/unused/500p2a/`.
- **Grid:** pooled 2 × 2 to 13120 × 8091. The prediction value is the exact 2 × 2 sum (0..1020).
- **Selection:** the transform T* is chosen on half A of the labelled region (left of the median column). The criterion is the ink-minus-non-ink mean-prediction separation over all (orientation, shift) pairs, computed with FFT cross-correlation.
- **Evaluation:** on half B, we compute the exact AUC at T* and at identity. A paired 64 × 64 block bootstrap (B = 2000) gives the CI on the difference.
- **Verdict rules, fixed in advance:**
  - MISREGISTERED needs T* away from identity, Δ ≥ 0.10 with CI > 0, and AUC ≥ 0.65.
  - ALIGNED-READ needs identity AUC ≥ 0.65.
  - Anything else is ALIGNED-UNREAD.

## Results (`results/metrics.json`)

| Pred | T* (orientation, dy, dx) | AUC_B(T*) | AUC_B(identity) | Δ | 95% CI |
|---|---|---|---|---|---|
| P1 canonical fwd (primary) | identity, −256, −177 | 0.4497 | 0.4072 | +0.0424 | [+0.0078, +0.0772] |
| P2 ps48 fwd | flip-UD, +91, −172 | 0.4909 | 0.4739 | +0.0170 | [−0.0282, +0.0598] |
| P3 ps512 fwd | rot180, −208, +256 | 0.5170 | 0.4968 | +0.0202 | [−0.0237, +0.0643] |
| P4 ps512 rev | identity, −256, +158 | 0.5019 | 0.5100 | −0.0081 | [−0.0481, +0.0337] |

Half B: 4,354,257 labelled pixels in 1,266 blocks.

- 3 of the 4 selected transforms sit on the edge of the search range, and none comes close to the 0.65 bar. We read this as no correlation peak anywhere in the family, not as a found offset.
- **Exploratory, pre-declared:** inverted IR luminance against the labels gives AUC 0.9897 at identity. The labels track the shipped IR photo almost exactly.

## What this means
- Rigid label misregistration is ruled out as the cause of chance-level ink scores on 500p2a.
- The organizer predictions are also at or below chance against these labels, so the effect is not specific to ink_9um.

## What it does not show
- **Non-rigid error or an IR-to-CT registration error.** The labels agree with the IR photo; whether the IR photo agrees with the CT render is not tested.
- **Training data.** The organizer models' training data is not documented.

## Reproduce
1. Put the four prediction TIFFs in `data-do-not-redistribute/preds/` and the IR PNG in `data-do-not-redistribute/`.
2. Put the labels in `../label-free-selector/data-do-not-redistribute/labels/`.
3. Run `python -B scripts/align.py`. It takes a few minutes on CPU; peak memory is several GB.
4. Tests: `python -B -m pytest -p no:cacheprovider tests/` (4 pass).

Deviations, including one re-execution after an out-of-memory kill in the exploratory step with byte-identical primary output: `results/deviations.md`.

This bundle holds code and metrics only, with no labels, predictions or images. The inputs are CC BY-NC 4.0 and are not redistributed.

AI-assisted.
