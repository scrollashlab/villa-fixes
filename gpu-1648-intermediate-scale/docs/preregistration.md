# Pre-registration: #1648 in-plane-scale WARNING at 4.681 µm vs 9.362 µm on held-out PHerc0841 (3 segments)

Supersedes `preregistration-DRAFT.md`. Sealed before any inference of the arms below. What was run before sealing:
- step 0a: a level-0/level-1 reconstruction check on raw CT chunks;
- step 0b: the loader probe on one S4 tile. Its outputs are byte hashes, run time, peak RSS and GPU utilization. No AUC, histogram or image of any prediction was computed or viewed.

## Question

The villa #1648 patch (ours) emits a WARNING in flat ink inference when `in_plane_scale_um < 0.55 × 9.6 = 5.28 µm`. Held-out evidence so far covers 2.4 µm vs 9.6 µm only (CONFIRM 3/3, `experiments/gpu-1648-heldout/`). Does ink_9um read the same out-of-training array worse at 4.681 µm in-plane than at 9.362 µm in-plane?

## Step-0 findings that fixed the design

- **0a** (`results/step0a-level1-rule.json`, `scripts/check_level1_rule.py`). The producer's level 1 of these renders is not a 2×2×2 mean. It is the in-plane 2×2 half-up mean of level-0 planes 0–32 only; planes 33–64 are not in level 1.
  - This is exact (0 differing voxels) on 9 of 9 checked cells (3 per segment, 540,672 voxels each). It was confirmed on 2 cells of the 500p2a render as well.
  - The draft's fallback ("use the producer rule for both arms") is therefore not used: that rule would centre the 17-plane model window about 16 level-0 planes away from the render's central plane.
  - Both arms are instead built from all 65 level-0 planes with identical z pooling, as the draft's primary definition says.
- **0b** (`results/step0b-probe.json`): on w00 tile t0_0 (seed42), num_workers 0 / 2 / 0 took 13.7 / 23.3 / 6.2 s with peak process-tree RSS 2635.9 / 3200.8 / 2361.6 MiB; all three runs gave byte-identical outputs (forward sha256 d2f8ce52…6e35, reverse 5638ef87…4509). 2 workers is byte-identical but its peak (3200.8 MiB) is not under the 2048 MiB limit, so it is not kept. Fixed: `--num-workers 0`.

## Data (fixed)

- Segments: PHerc0841 `w00`, `auto_grown_20260220144552896` (ag144), `auto_grown_20260220174252405` (ag174). These are the organizer label-bucket renders: level 0 is (65, H, W) uint8 at 4.681 µm, chunks (65, 128, 128), uncompressed. PHerc0841 is not in ink_9um's training set.
- Region R and labels on the level-1 crop grid: identical to the sealed label-free-selector study (sha256 `8ffae804…b9dd`). R = all 4 level-0 pixels in `supervision_mask_v2 ∩ validation_mask_v2`; ink = at least 2 of 4 in `inklabels_v2`. R/ink counts: w00 6,128,158 / 1,363,830; ag144 3,720,168 / 1,206,403; ag174 4,846,350 / 1,101,717.
- Fetched: only level-0 chunks under the planned level-1 mask-box cells (1,556 level-1 cells → 6,224 level-0 chunks of 1,064,960 B).

## Arms

- **S9 (9.362 µm in-plane):** 2×2×2 half-up mean of level 0. z pairs (0,1)…(62,63); plane 64 is 2×2 in-plane only. Result: 33 planes.
- **S4 (4.681 µm in-plane):** z pairs half-up with the identical z rule (plane 64 alone); native in-plane. Result: 33 planes.
- Both arms are checked byte-exact against an independent float reconstruction (box test).
- Model: ink_9um hybrid_3d2d seed42 and seed43 step-075000.
- Directions: forward and reverse (`--direction both`).

## Inference (fixed)

- villa 8b63a2652 `vesuvius.ink_detection.inference.infer`, unpatched, in-process.
- Flags: `--direction both --mask-path <R mask on the arm's grid> --no-compile --num-workers 0 --batch-size 32 --amp-dtype auto`.
- S9: one crop per segment on the level-1 crop grid.
- S4: tiles of ≤ 4096 × 4096 level-0 px core with a 256 px margin. The mask is R upsampled ×2 (nearest). Only core pixels are kept.
- S4 output is summed over each 2×2 block onto the level-1 grid (values 0..1020). That is a constant multiple of the mean, so AUC is identical.

## Scoring (once, after all runs)

- Exact Mann–Whitney AUC over R (ties 0.5), from per-64×64-block histograms computed on the PC (S9: 256 bins, S4: 1021 bins). Only these histograms, not prediction images, leave the PC.
- 95% CI: paired block bootstrap of Δ = AUC(S9) − AUC(S4) over the 64×64 blocks of the level-1 crop grid. B = 2000, numpy seed 20261008, the same block draw for both arms.
- Operative direction per segment: the direction with the larger mean of its 4 AUCs (2 arms × 2 seeds). The rule is symmetric in S4/S9.

## Kill test (operative direction)

- **SUPPORTED:** Δ > 0 with the CI excluding 0 for both seeds on ≥ 2 of 3 segments. The WARNING threshold stays.
- **REFUTED:** Δ < 0 with the CI excluding 0 for both seeds on ≥ 2 of 3 segments. Pre-committed patch change: emit INFO instead of WARNING for 3.84 µm ≤ scale < 5.28 µm (0.4 × 9.6 to 0.55 × 9.6). The #1648 unit tests and real-data tests are then re-run, and the writeup states the result.
- **INCONCLUSIVE:** anything else. The patch is unchanged, and the writeup says that between 2.4 and 9.6 µm the threshold has only this inconclusive point.
- Reported, not part of the verdict: the non-operative direction, per-seed AUCs and Δ, and run times and GPU utilization.

## Rules

- Prediction images stay on the PC (do-not-redistribute). Metrics, histograms and code only.
- Deviations go in `results/deviations.md`. Scored once.

AI-assisted.
