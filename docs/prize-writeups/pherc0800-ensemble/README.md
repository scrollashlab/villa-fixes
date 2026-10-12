# PHerc0800: a five-model ink ensemble with depth sharpening finds no text signal on the six published segments

## Summary
We ran a fixed ensemble of five public ink models trained at about 9 µm on the six published PHerc0800 segments, with and without depth sharpening, under a preregistration sealed before any target was scored. A PHerc0009B segment with known text, scanned with the same 8.64 µm / 116 keV protocol, served as the positive control. The control passed. None of the six targets reached the preregistered text screen threshold in either arm, so the primary outcome is 0 of 6. This matches the preregistered prediction.

## Setup
- Targets T1 to T6: the six PHerc0800 auto-grown segments in the open-data catalog, surface volumes `8.64um-1.2m-116keV-volume-20250521135224.zarr`, level 0, 31 layers. Total canvas 19.52 cm². Segment ids are in `meta/segments.json`.
- Control C1: PHerc0009B segment `20250919125754-auto_grown_20250919055754487_inp_hr`, same scan protocol.
- Models: ink_9um hybrid 3D2D seeds 42 and 43 (m1, m2), Hecate 9.6 µm (m3), reader-v2 step 40000 (m4), dense_native step 16000 (m5).
- Arm A uses the raw 31-layer volume. Arm B uses the centred 21 layers after `depth_sharpen_9um.py --no-map --layer-um 8.64`.
- Ensemble E is the plain mean of the five model maps, per arm and per depth direction.
- S1 is the reader-v2 text screen (`textscore2.score2`, hi=180) on E, taking the better of the two directions. S2 is the row periodicity score from first-letters-survey `rowscore.py`, used for triage only.
- Decision rule: a target counts as positive only with S1 at least half of C1's S1 in the same arm and a visual verdict of candidate text.

## Control
C1 scored S1 = 0.00691 in arm A and 0.00556 in arm B. The gate required at least 0.005 in arm A. The forward ensemble map of C1 shows about eight rows of Greek letters (visual verdict V2), so the gate passed. Thresholds for the targets are 0.003455 (arm A) and 0.00278 (arm B).

## Results
| Item | S1 arm A | S1 arm B | S2 arm A | S2 arm B | Models over half their own C1 score, A / B |
|---|---|---|---|---|---|
| C1 (control) | 0.00691 | 0.00556 | 23.6 | 23.3 | |
| T1 | 0.00009 | 0.00033 | 16.7 | 16.4 | 2 / 2 |
| T2 | 0.00281 | 0.00163 | 13.0 | 9.7 | 5 / 4 |
| T3 | 0.00111 | 0.00054 | 21.6 | 13.5 | 4 / 2 |
| T4 | 0.00272 | 0.00036 | 9.1 | 10.1 | 0 / 0 |
| T5 | 0 | 0 | 3.0 | 3.8 | 0 / 0 |
| T6 | 0 | 0 | 3.9 | 3.2 | 0 / 0 |

No target reaches its threshold in either arm. The closest are T2 (0.00281 against 0.003455) and T4 (0.00272 against 0.003455), both in arm A.

Depth sharpening lowered S1 on the control (B minus A = minus 0.00135) and on T2, T3 and T4. It raised T1 by 0.00024 and left T5 and T6 at 0.

T2 in arm A is the one place where the single models agree: all five pass half of their own control score, while the ensemble does not pass. We report this as a descriptive note. It does not change the outcome, and the rule fixed in advance applies to the ensemble.

Full per-model and per-direction values are in `metrics.json`.

## Re-check
- A second code path written separately (numpy plus scikit-image, with no code shared with the scoring script) recomputed E and S1 from the saved model maps. All 168 S1 values (7 items, 2 arms, 6 maps, 2 directions) match exactly. The sha256 hashes of all 168 saved maps match the values recorded at scoring time.
- A second separate script, using numpy with scipy erosion and scikit-image labelling, recomputed S2 for all 14 item and arm pairs. All scores and periods match, as do the summary fields. Five peak angles differ by exactly 180 degrees, which is the mirror peak of a real-valued power spectrum and the same row orientation.
- reader-v2 (m4) was re-run on T1 arm A on the CPU instead of the GPU. The two runs differ by at most 1 grey level out of 255 in both directions. The mean difference is 0.0099 (forward) and 0.0121 (reverse). Both runs give the same m4 S1, 0.00346 forward and 0.01067 reverse.

## Deviations from the preregistration
- The inference tool opens its input as a zarr group, so a `.zgroup` marker was written into each surface volume folder after the arm stage. Array data was not changed.
- Hecate ran in bf16 to fit 8 GB of GPU memory.
- Visual verdicts were recorded for the control only. Every target failed the S1 threshold, so a visual verdict could not change the primary outcome.

## Files
- `metrics.json`: all S1 and S2 values, per item, arm, model and direction.
- `preregistration.md` and `preregistration.sha256`: the sealed plan, with hashes of the plan, scripts and segment list.
- `scripts/run.py`: the pipeline (fetch, arms, inference, scoring).
- `scripts/recheck_independent.py` and `scripts/recheck_s2_independent.py`: the independent re-check.
- Third-party scripts used by `run.py` are listed with repository, commit and license in `scripts/SOURCES.txt`. They are not copied here.

Ink maps and CT crops are not included, and neither are labels. The input data is CC BY-NC 4.0 and is available from the open-data bucket under the paths above.

AI-assisted.
