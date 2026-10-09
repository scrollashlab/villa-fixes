# Deviations and notes

Prereg: `docs/preregistration.md`, sha256 `b2a6e08d3840acab5923edf7d9744b58f649697615c288394a0584b3a599b4df`, sealed 2026-10-08 20:56:14 HST.

1. **Timing.** The PC run started at 20:56:23 HST, 9 s after sealing, as an on-demand hidden scheduled task with no time trigger. The earlier plan was a run after 22:00 HST; it was brought forward on request. The run used the same code, flags and inputs.
2. **Design changes from the draft** were made before sealing and are recorded in the sealed text (step 0a: the level-1 rule; step 0b: `--num-workers 0`). They are not deviations from the sealed prereg.
3. **Run record.** The run ended at 21:31:34 HST. It completed 42/42 arm-runs (3 segments × 2 seeds × (S9 + 6 S4 tiles)) in 2,083.3 s of inference: S9 403.4 s, S4 1,679.9 s. The time-weighted mean GPU utilization was 10.4% (max 100%), and the peak process-tree RSS was 2,659.8 MiB. The task removed itself (log line `TASK_REMOVED`). The hand-back files were checked by sha256 on both sides, and the hand-back folder was then deleted. The S4 tile w00/seed42/t0_0 reproduced the step-0b probe outputs byte for byte (forward d2f8ce52…, reverse 5638ef87…).
4. **Interruption.** The agent session was interrupted at about 21:16 HST while the PC run was in progress (22/42 arm-runs done). The PC task was not affected: it was one instance with no trigger and ran to completion. The only casualty was a waiting command on the analysis machine. Nothing was restarted, and the scoring ran once after the run finished (21:38 HST).
5. **Independent check.** Every point AUC in `summary.md` was recomputed from the histogram files by a separate implementation, and all 24 values match to 4 decimals. The pos/neg totals equal the prereg R/ink counts for all three segments.
