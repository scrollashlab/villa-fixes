# Close-out: 500p2a label alignment (negative)

- **Result: ALIGNED-UNREAD on the pre-registered primary (P1). The three other organizer predictions agree (3/3).** No rigid transform in the family (4 orientations × ±256 px at 8.64 µm) lifts any organizer prediction to a usable AUC on held-out half B. The best is P3 at 0.517, and the largest Δ is P1's +0.042 (CI [+0.008, +0.077]).
- **What it rules out:** a simple mirror or a ≤ 2.2 mm offset between the labels and the render is not why models score at chance on 500p2a. The organizers' own four predictions are at or below chance against these labels as well (identity AUC_B 0.407–0.510). So the issue is not specific to ink_9um.
- **What it does not rule out:** non-rigid misregistration, or an IR-to-CT registration error. The labels match the IR photo almost perfectly (exploratory AUC 0.990), so any error would sit between the IR photo and the CT render.
- **Decision:** stop. Do not spend more GPU time trying to "fix" 500p2a alignment. Treat 500p2a as a fragment that current models do not read on this render. #1867's chance-level numbers are consistent with this.
- Files: `docs/preregistration.md` (+ `.sha256`), `results/{metrics.json, summary.md, deviations.md, run.log, run1-oom-killed.log}`, `scripts/{align.py, test_align.py}`. Data is CC BY-NC and stays in `data-do-not-redistribute/` (~0.43 GB downloaded).

AI-assisted.
