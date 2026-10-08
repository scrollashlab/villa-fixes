# Deviations and notes against the sealed pre-registration

Pre-registration: `docs/preregistration.md`, sha256 `157a375acfff539253ac75cdf6dbe752d2eb0b83003c26fca3633d5febb32ec6`, sealed 2026-10-08 07:57:22 HST.
No inference had been run on these crops before the seal.

1. **Scheduling-mask check failed on GPU, so every run went unmasked.**
   - This is the pre-registered fallback, not a deviation.
   - The check compared masked and unmasked runs on pherc0814-46527, L2, seed42, on the RTX 5060 (bf16 autocast). Of 161,051 mask pixels:
     - forward: 4 differed by 1/255;
     - reverse: 11 differed by 1/255.
   - On the box CPU (fp32) the same comparison was exact (0 differences).
   - The cause is floating-point accumulation order changing with batch composition. As the prereg requires, all 24 matrix runs were unmasked, i.e. the plain villa CLI on the crop.
2. **Bootstrap seeding.** `default_rng(1648)` is re-seeded for each case. One draw matrix per case is shared by all four seed/direction comparisons, and the L2 and L0 arms are paired.
3. **`patches` in `pc-run-log.json` is a nominal count**, not the number of patches villa scheduled.
   - It is 2 × the masked per-direction count, used only to project GPU time.
   - Because the runs were unmasked, villa actually scheduled more patches per direction: 107/1106 (46527 L2/L0), 225/1526 (w016), 352/2632 (w029).
   - Measured GPU time for the whole matrix including the check: 595 s. The longest single invocation (w029 L0, both directions) took 136 s.
4. **Input preparation ran on the box, not the PC.** The PC received the prepared crops as sha256-verified parts.
   - Before running, the PC re-verified the sha256 of every decoded array (the C-order bytes) and every mask against the box manifest. All matched.
5. **Validity checks:**
   - Every output TIFF had the crop shape (asserted during reduction).
   - Mask pixels whose prepared input is all-zero: 0.094% (L2) and 0.129% (L0) for pherc0814-46527 (at the volume edge or absent source chunks, where the source fill is 0); 0 for the other two cases.
   - Checkpoint sha256s matched.
6. **CPU vs GPU numerics (descriptive):** pherc0814-46527, L2, seed42, box CPU fp32 vs PC GPU bf16, over mask pixels: max |diff| 1/255; 4.2% (forward) and 3.7% (reverse) of pixels differ.
7. **Independence:** all three cases are training segments in the checkpoints' dataset list, with validation-mask carve-outs listed in `online_validation_cases`. Spatial adjacency leakage within a segment cannot be excluded. pherc0814-46527 also overlaps the earlier exploratory window.
