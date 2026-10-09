# #1648 in-plane-scale WARNING: intermediate-scale test at 4.68 µm vs 9.36 µm

**Result: SUPPORTED (3/3 segments; 2/3 required).** On PHerc0841, which is held out of ink_9um's training, the model reads the same data worse at 4.681 µm in-plane than at 9.362 µm. This holds for both seeds on all three segments, with every CI excluding 0. The #1648 WARNING threshold (`scale < 0.55 × 9.6 = 5.28 µm`) is supported at a point inside the band, not only at the ~2.4 µm extreme tested earlier. The patch is unchanged.

## Design (pre-registered: `docs/preregistration.md`, sha256 `b2a6e08d3840acab5923edf7d9744b58f649697615c288394a0584b3a599b4df`, sealed 2026-10-08 20:56:14 HST)

### Step-0 checks (done before sealing)
- **0a (`results/step0a-level1-rule.json`):** the published level 1 of these renders is the in-plane 2×2 half-up mean of level-0 planes 0–32 only. Planes 33–64 are absent. This was exact (0 differing voxels) on 9/9 PHerc0841 cells and 2/2 500p2a cells.
- **0b (`results/step0b-probe.json`):** `--num-workers 2` gave byte-identical output but a 3,200.8 MiB peak, so `--num-workers 0` was fixed.

### Arms and inference
- **S9 and S4** are both built from all 65 level-0 planes with identical z pooling.
  - S9 is a 2×2×2 half-up mean.
  - S4 uses z pairs only, at native in-plane resolution. It runs in 4096 px tiles with a 256 px margin, and its output is summed 2×2 onto the S9 grid.
- **Model and runs:** ink_9um hybrid_3d2d, seeds 42/43 (step 75000), both directions. villa main 8b63a2652, unpatched, `--batch-size 32 --amp-dtype auto --no-compile --num-workers 0`. RTX 5060, torch 2.14.1+cu130.

### Scoring
- Exact Mann–Whitney AUC over the region, from per-64×64-block histograms.
- Paired block bootstrap of Δ = AUC(S9) − AUC(S4): B = 2000, seed 20261008.
- **Operative direction:** the direction with the larger mean of its 4 AUCs, chosen per segment.

## Results (`results/summary.md`, `results/metrics.json`)

Operative direction: reverse on all three segments.

| segment | seed | AUC S9 (9.36 µm) | AUC S4 (4.68 µm) | Δ | 95% CI |
|---|---|---|---|---|---|
| w00 | 42 | 0.6959 | 0.6042 | +0.0917 | [+0.0707, +0.1115] |
| w00 | 43 | 0.7194 | 0.5965 | +0.1229 | [+0.1028, +0.1436] |
| ag144 | 42 | 0.7357 | 0.6150 | +0.1207 | [+0.0978, +0.1441] |
| ag144 | 43 | 0.7556 | 0.6214 | +0.1342 | [+0.1116, +0.1568] |
| ag174 | 42 | 0.6630 | 0.5526 | +0.1104 | [+0.0848, +0.1351] |
| ag174 | 43 | 0.6717 | 0.5675 | +0.1042 | [+0.0775, +0.1312] |

- The forward direction (non-operative) is near chance in both arms (0.52–0.58). Its table is in `summary.md`.
- **Run:** 42/42 arm-runs, 2,083 s of GPU inference, peak RSS 2,660 MiB.
- Every point AUC was recomputed independently from the histograms (`results/deviations.md` item 5).

## Limitations
- One scroll and one intermediate scale.
- The region and labels are the organizer label-bucket labels on the level-1 grid.
- CIs come from a block bootstrap only (1,033–1,630 blocks of 64×64 per segment).

## Reproduce
The pre-registration defines region R and the labels by reference to the label-free-selector study. Everything needed from that study is in this bundle:
- `meta/from-label-free-selector/heldout-plan.json`: crop boxes, chunk cells and the R/ink counts. It is a verbatim copy; see `PROVENANCE.txt` and `SHA256SUMS` in that folder.
- `scripts/make_region_labels.py`: rebuilds the region masks and packed labels from the public label TIFFs (`ink/841/<segment>/<segment>_{supervision_mask_v2,validation_mask_v2,inklabels_v2}.tif` in the bucket). It checks the R/ink counts against the plan. Its output is identical, array for array, to the files the run used.

Steps:
- `scripts/make_region_labels.py <root>`: writes `<root>/data-do-not-redistribute/lfs/{masks,labels}/`. Copy `meta/from-label-free-selector/heldout-plan.json` to `<root>/lfs/heldout-plan.json`, where `pc/phase1.ps1` picks it up.
- `pc/run_mid.py <root> prep | probe | run --num-workers 0 | reduce`: fetch, build arms, infer, reduce to histograms.
- `scripts/score_mid.py`: scoring.
- `scripts/check_level1_rule.py`: step 0a.
- Tests: `python -B -m pytest -p no:cacheprovider tests/` (2 pass).

The input data sources are listed in `OPEN_DATA_NOTE.txt`.

AI-assisted.
