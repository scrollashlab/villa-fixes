# Preregistration: PHerc0800 team segments with a 5-model ink ensemble and depth sharpening

Written 2026-10-11 (HST). This file and the scripts it names are hashed in `docs/preregistration.sha256` before any target segment is run through any model.

## Question
Does a fixed ensemble of five public 9 µm ink models, with or without fixed depth sharpening, show text (letter-like strokes in rows) on any of the six published PHerc0800 segments, in either depth direction?

## Data
- **Targets (T1–T6):** the six PHerc0800 surface volumes listed in `meta/segments.json`, as given by the open-data catalog `metadata.json` (fetched 2026-10-11, copy at `meta/catalog-2026-10-11.json`). Path pattern `PHerc0800/segments/<id>/surface-volumes/8.64um-1.2m-116keV-volume-20250521135224.zarr`, level 0 (31 layers, uint8). Total canvas 19.52 cm².
- **Positive control (C1, known text, same scan protocol):** PHerc0009B segment `20250919125754-auto_grown_20250919055754487_inp_hr`, 8.64 µm / 116 keV surface volume. References: the published 2.401 µm team ink-detection map, and the ink labels `ink-labels/2.401um-volume-20250820154339/20260918/`. reader-v2 held this segment out of training; ink_9um's training list does not include PHerc0009B.
- Nothing from the targets is used for training, tuning or threshold selection.

## Models (fixed)
| key | checkpoint | source |
|---|---|---|
| m1 | ink_9um `hybrid_3d2d-seed42/step-075000.pth` | huggingface.co/scrollprize/ink_9um |
| m2 | ink_9um `hybrid_3d2d-seed43/step-075000.pth` | same |
| m3 | Hecate `hecate_9.6um.pth` | huggingface.co/scrollprize/hecate |
| m4 | reader-v2 `reader-v2-step040000.pth` | huggingface.co/domenicor046/reader-v2 |
| m5 | dense_native `dense_native_016000` (safetensors wrapped into a .pth with the ink_9um config, as its README documents) | huggingface.co/Nieuwlaar/ink9um-dense-native |

- m1, m2, m4 and m5 run through `vesuvius.ink_detection.inference.infer` (villa main, pinned commit recorded in the run log) with `--overlap 0.5 --blend-mode hann`, default centred layer selection, `--direction both`.
- m3 runs through `hecate.py` on the input resampled to 9.6 µm in all three axes: XY area average, Z linear, as in reader-v2's `scripts/infer_with_hecate.py`. Its map is resized back to the native canvas (bilinear). It runs in both directions (`--reverse`).

## Arms
- **A (raw):** the native 31-layer surface volume.
- **B (depth-sharpened):** the centred 21 layers (villa `centred_slice`), passed through `depth_sharpen_9um.py --no-map --layer-um 8.64` (github.com/AndreasHad04/villa-apple-silicon, MIT; villa #1898). The result is the model input. B uses the no-map variant because PHerc0800 was never in training, and #1898 reports no-map as the better variant on never-trained scrolls.

## Ensemble and scores (fixed)
- **Per-model probability:** ink_9um-format outputs are read as uint8/255. Hecate's PNG is read as value/255.
- **Ensemble E** = plain mean of the five model probabilities, per arm and per direction. No weights, no rescaling.
- **S1, text screen:** reader-v2 `textscore2.score2` with hi=180. It is applied to E×255 with pf = the forward map and pr = the reverse map. CT is the middle layer of the input; valid = CT>0 and pf>0. The screen is also computed with the directions swapped (pf = reverse), and the larger value is reported as S1.
- **S2, row score:** first-letters-survey `analysis/rowscore.py` on E (best direction). It is a triage aid only.
- **Visual verdict V:** per target and arm, on E (both directions) shown next to the middle CT layer at the same scale as C1. The verdict is exactly one of these three sentences:
  - V0 "No letter-like ink."
  - V1 "Isolated letter-like forms, no rows."
  - V2 "Candidate text: three or more letter-like forms aligned in a row parallel to the fibers."

## Decision rules
- **Control gate (run first):** C1 must reach S1 ≥ 0.005 in arm A and show visible rows (verdict V2). If it fails, the target run is stopped and the failure is reported. Thresholds are not changed.
- **Primary outcome:** the number of targets (0–6) with S1 ≥ 0.5 × S1(C1, same arm) and verdict V2, in arm A or arm B.
- **Positive** = primary outcome ≥ 1. Any V2 target then gets the replication check: the same forms must appear in at least 3 of the 5 single-model maps, in the same direction. Nothing is called text without that check.
- **Secondary outcomes (descriptive):**
  - per-target S1 and S2 for each arm, direction and model;
  - B minus A for S1 on C1 and on each target;
  - the agreement count (number of models with S1 ≥ 0.5 × that model's own C1 score).

## Re-check
A second, independent code path recomputes E, S1 and S2 from the saved per-model maps (numpy reimplementation, no shared code). It also re-runs m4 on T1 arm A on a different device. Every reported number must match within 1e-6 for scores computed from the same maps, and within a stated tolerance for the device re-run.

## Not redistributed
Ink maps, CT crops and labels stay out of any bundle. The bundle carries scripts, numbers, hashes of outputs, and public source paths.

## Prediction
Expected outcome is 0 (negative), given the 14-checkpoint ink_9um null on these segments (scoop check item 1). A negative still gives the first ensemble and depth-sharpening measurement on these segments, plus the control result for the same 116 keV protocol.
