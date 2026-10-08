# #1648 held-out matrix: does ink_9um score better at 9.6 µm (L2) than at 2.4 µm (L0)?

AI-assisted: the design, code and analysis were prepared with AI assistance.

## Result

**Verdict: CONFIRM (3/3 segments confirm; 2/3 required).** The #1648 in-plane-scale WARNING (`scale < 0.55 * 9.6 µm`) stays as written. No patch change was needed. The patch was re-verified on villa main 8b63a2652: 6 passed.

Operative direction (forward on all three segments), exact AUC inside each validation mask, with a 95% paired block-bootstrap CI on Δ = AUC_L2 − AUC_L0:

| segment | seed | AUC L2 | AUC L0 | Δ | 95% CI |
|---|---|---|---|---|---|
| pherc0139-w016 | 42 | 0.8829 | 0.5676 | +0.3153 | [+0.2571, +0.3719] |
| pherc0139-w016 | 43 | 0.9143 | 0.6027 | +0.3116 | [+0.2445, +0.3864] |
| pherc0814-46527 | 42 | 0.8861 | 0.6388 | +0.2473 | [+0.1765, +0.3066] |
| pherc0814-46527 | 43 | 0.8568 | 0.6701 | +0.1867 | [+0.1139, +0.2556] |
| pherc1667-w029 | 42 | 0.9007 | 0.5361 | +0.3646 | [+0.3147, +0.4145] |
| pherc1667-w029 | 43 | 0.8980 | 0.5435 | +0.3545 | [+0.2967, +0.4107] |

- Reverse-direction cells, mean AUC per direction and per-run average precision are in `results/summary.md` and `results/metrics.json`.
- The verdict is unchanged when L0 is requantized to uint8 (`sensitivity_floor16`).

## Design (pre-registered)

`docs/preregistration.md`, sha256 `157a375acfff539253ac75cdf6dbe752d2eb0b83003c26fca3633d5febb32ec6`, sealed 2026-10-08 07:57:22 HST, before any inference on these crops.

- **Cases:** the three `online_validation_cases` that ship a `validation_mask` (HF `scrollprize/datasets`, aligned 21-slice set, channel 10).
- **Inputs:** the open-data source surface volume at level 2 and level 0, cropped to the mask bbox ±128 L2 px. The 21-plane input is prepared by villa's own `prepare_isotropic_input`.
- **Runs:** villa main 8b63a2652, unpatched infer CLI, seed42/43 × forward/reverse. Flags: `--no-compile --num-workers 0 --batch-size 16 --amp-dtype auto`; overlap and blend left at their defaults.
- **Scoring:**
  - L0 outputs are summed 4×4 onto the L2 grid.
  - Exact Mann–Whitney AUC (ties = 0.5) from 4096-bin histograms.
  - Paired bootstrap over 64×64 L2-px blocks, B=2000, `default_rng(1648)`; percentile CI.
- **Kill test:**
  - A segment confirms if, in its operative direction, both seeds have Δ > 0 and a CI lower bound > 0.
  - The verdict is CONFIRM if at least 2/3 segments confirm, otherwise the WARNING is downgraded to INFO.
- **Deviations and validity checks:** see `results/deviations.md`. Notably, the pre-registered masked-vs-unmasked equivalence check differed by ±1/255 on 4 and 11 of 161,051 pixels on the GPU, so all runs used the plain unmasked CLI.

## Caveats

- All three cases are training segments with validation-mask carve-outs, so spatial adjacency leakage cannot be excluded.
- pherc0814-46527 overlaps the earlier exploratory window.
- These results support "fine input underperforms the training scale". They say nothing about other models or other preparation pipelines.

## Compute

- **Hardware:** one RTX 5060 (8 GB, sm_120).
- **Software:**
  - Python 3.14.8 (uv-managed, self-contained) and torch 2.14.1+cu130; GPU check in `results/gpu-check.json`.
  - cu130 is used because the cu128 cp314 Windows wheels stop below villa's torch>=2.12 floor.
- **GPU time:** 595 s for the full matrix, including the equivalence check.
- **Data:** about 2.41 GB of source chunks were fetched, plus 1.3 MB of labels/masks. The prepared crops are 0.30 GB.

## Layout

- `docs/`: the pre-registration and its sha256.
- `scripts/`, in pipeline order:
  1. `fetch_hf_zarr.py`: labels and masks.
  2. `prep_crops.py`: the chunk-limited fetch and villa prepare.
  3. `make_pc_inputs.py`: masks, transfer parts and the manifest.
  4. `score.py`: the pre-registered scoring.
- `pc/bootstrap/`: the headless, self-contained Windows setup (uv Python, venv, torch, checkpoints).
- `pc/phase2/`: input verification and the matrix runner.
- `tests/test_score.py`: 7 tests checking the histogram AUC and AP against brute force, pooling, bootstrap determinism, block alignment and the verdict logic.
- `results/`: metrics only.

See `OPEN_DATA_NOTE.txt` for the data sources. No CC BY-NC payloads are included.
