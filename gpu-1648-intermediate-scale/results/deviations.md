# Deviations and notes

Prereg: `docs/preregistration.md`, sha256 `b2a6e08d3840acab5923edf7d9744b58f649697615c288394a0584b3a599b4df`, sealed 2026-10-08 20:56:14 HST.

1. **No deviations from the sealed prereg.** The design changes relative to the earlier unsealed version were made before sealing and are recorded in the sealed text: step 0a (the level-1 rule) and step 0b (`--num-workers 0`).
2. **Run record.** Inference ran from 20:56:23 to 21:31:34 HST on 2026-10-08 and completed 42/42 arm-runs: 3 segments × 2 seeds × (S9 + 6 S4 tiles).
   - Inference time: 2,083.3 s in total (S9 403.4 s, S4 1,679.9 s).
   - GPU utilization: time-weighted mean 10.4%, max 100%.
   - Peak process-tree RSS: 2,659.8 MiB.
   - The S4 tile w00/seed42/t0_0 reproduced the step-0b probe outputs byte for byte (forward d2f8ce52…, reverse 5638ef87…).
   - Scoring ran once, after all runs.
3. **Independent check.** Every point AUC in `summary.md` was recomputed from the histogram files by a separate implementation; all 24 values match to 4 decimals. The pos/neg totals equal the prereg R/ink counts for all three segments.
