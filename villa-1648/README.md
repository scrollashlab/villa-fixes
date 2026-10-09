# villa#1648 — report depth order and in-plane scale (do not prescribe reverse)

## What changed

Flat ink inference (`infer.py`) logs effective `depth_order` and `in_plane_scale_um`:

- **INFO** summary of the values used
- **INFO** note: orientation is **segment/render-dependent**; when undeclared, run
  `--direction both` (do **not** prescribe reverse; do **not** WARN on forward alone)
- **WARNING** only when in-plane scale is much finer than ~9.6 µm
  (`scale < 0.55 * 9.6`). Default `--direction` remains `forward`.

## Memorization gate (resolved)

**Windows A/B on PHerc0139 w035 overlap training data.** Evidence:

| Source | Finding |
|--------|---------|
| Checkpoint `config.datasets` (seed42/43 step-075000) | `pherc0139-w035` in `public_2p4_level2_zmean4`; `w035` in `native_9p362_level0` |
| `data_provenance` | `online_validation_cases` / `reserved_validation_cases` do **not** list w035 |
| HF aligned labels attrs | `"online_validation": false` for w035; **no** `validation_mask` |
| HF model card + tutorial | Trained on those segments; tutorial calls w035 “from the models' own training set” |
| Issue #1648 | w035 matrix scored on `pherc0139-w035_inklabels.zarr` ch10 (**training labels**, not held-out). Separate w024 table is non-train with proxy labels |

L2-forward AUC ≈ **0.995–0.999** on A/B is therefore **not** a clean generalization claim (consistent with train-pixel memorization). Those tables are retained under `train_overlap_windows_AB_superseded` for transparency only.

## Primary real-data evidence (held-out mask)

**Segment:** `pherc0814-46527` (in `online_validation_cases`; HF ships `*_validation_mask.zarr`).
Scored **only** where `validation_mask[ch10] > 0`, against HF aligned inklabels ch10, volume from open-data 2.399 µm with training `source_z_slice [13,97]` → 21× z-mean-4. Both seeds, 2×2 depth×scale.

Window L2 `yxhw=[1624,258,411,512]`; val pixels in window **150770**; L2 pos/neg on mask **57911 / 92859**.

| cell | AUC seed42 / seed43 |
|------|---------------------|
| L0 forward (~2.4 µm) | 0.642 / 0.678 |
| L0 reverse | 0.533 / 0.488 |
| **L2 forward (~9.6 µm)** | **0.871 / 0.846** |
| L2 reverse | 0.615 / 0.613 |

Qualitative match to #1648 without train ceiling: better depth×coarse is clearly best; opposite depth collapses; fine underperforms coarse for the better depth; L0 emits the scale WARNING, L2 does not.

**Caveat:** 46527 is still a training *segment*; the holdout is a spatial validation-mask carve-out (adjacency leakage possible per public ink_9um audits). It is still the strongest public binary-label holdout we could bind to these checkpoints.

## Pre-registered held-out matrix (3 segments, 2026-10-08)

The single-window result above was re-tested on all three `online_validation_cases` that ship a `validation_mask`: pherc0139-w016, pherc0814-46527 and pherc1667-w029.
- The kill test was pre-registered before any inference (`heldout-matrix-2026-10-08/preregistration.md`, sha256 `157a375a…2ec6`, sealed 2026-10-08 07:57 HST).
- Scoring used whole validation masks only. The L2 input (~9.6 µm) was compared with the L0 input (~2.4 µm) of the same crop: 2 seeds × 2 directions, villa main 8b63a2652, unpatched CLI, RTX 5060, torch 2.14.1+cu130.
- L0 output was mean-pooled 4×4 onto the L2 grid.
- Exact Mann–Whitney AUC; 95% CI from a paired 64×64-px block bootstrap (B=2000).

| segment | seed | AUC L2 fwd | AUC L0 fwd | Δ (L2−L0) | 95% CI |
|---|---|---|---|---|---|
| pherc0139-w016 | 42 | 0.883 | 0.568 | +0.315 | [+0.257, +0.372] |
| pherc0139-w016 | 43 | 0.914 | 0.603 | +0.312 | [+0.245, +0.386] |
| pherc0814-46527 | 42 | 0.886 | 0.639 | +0.247 | [+0.177, +0.307] |
| pherc0814-46527 | 43 | 0.857 | 0.670 | +0.187 | [+0.114, +0.256] |
| pherc1667-w029 | 42 | 0.901 | 0.536 | +0.365 | [+0.315, +0.415] |
| pherc1667-w029 | 43 | 0.898 | 0.544 | +0.355 | [+0.297, +0.411] |

The operative direction was forward on all three segments, chosen by the mean of all 4 AUCs, a choice symmetric in L0/L2.

**Verdict: CONFIRM (3/3 segments; 2/3 required).** The in-plane-scale WARNING stays as written; the patch is unchanged.
- The result also holds when L0 is requantized to uint8.
- Reverse-direction results and per-run average precision are in `heldout-matrix-2026-10-08/` (`summary.md`, `metrics.json`).
- Re-verified: `git am` on main 8b63a2652, then pytest: **6 passed**.

**Caveats:**
- All three are training segments with validation-mask carve-outs, so spatial adjacency leakage within a segment cannot be excluded.
- 46527 overlaps the earlier exploratory window.
- The GPU masked-vs-unmasked check showed ±1/255 differences, so per the pre-registration all runs used the plain unmasked CLI (`deviations.md`).

## Pre-registered intermediate-scale test: 4.68 µm vs 9.36 µm (PHerc0841, 3 segments, 2026-10-08)

The held-out matrix above covers ~2.4 µm vs ~9.6 µm only. This test checks a point just inside the WARNING band (4.681 µm < 5.28 µm) on a scroll that is not in ink_9um's training set.
- **Pre-registration:** sealed before any inference (`intermediate-scale-2026-10-08/preregistration.md`, sha256 `b2a6e08d…b4df`, sealed 2026-10-08 20:56 HST).
- **Data:** PHerc0841 segments w00, ag144 and ag174, using the organizer label-bucket renders (level 0: 65 planes at 4.681 µm).
- **Arms:** both are built from all 65 level-0 planes with identical z pooling. S9 is a 2×2×2 mean (9.362 µm in-plane). S4 is z pairs only (4.681 µm in-plane), and its output is summed 2×2 onto the S9 grid.
  - Pre-check: the published level 1 of these renders turned out to hold level-0 planes 0–32 only (0 differing voxels on 9/9 cells), so it was not used as an arm.
- **Inference:** 2 seeds × 2 directions; villa main 8b63a2652, unpatched; RTX 5060.
- **Statistics:** exact Mann–Whitney AUC over the region; 95% CI from a paired 64×64 block bootstrap (B=2000).

| segment | seed | AUC 9.36 µm | AUC 4.68 µm | Δ | 95% CI |
|---|---|---|---|---|---|
| PHerc0841 w00 | 42 | 0.6959 | 0.6042 | +0.0917 | [+0.0707, +0.1115] |
| PHerc0841 w00 | 43 | 0.7194 | 0.5965 | +0.1229 | [+0.1028, +0.1436] |
| PHerc0841 ag144 | 42 | 0.7357 | 0.6150 | +0.1207 | [+0.0978, +0.1441] |
| PHerc0841 ag144 | 43 | 0.7556 | 0.6214 | +0.1342 | [+0.1116, +0.1568] |
| PHerc0841 ag174 | 42 | 0.6630 | 0.5526 | +0.1104 | [+0.0848, +0.1351] |
| PHerc0841 ag174 | 43 | 0.6717 | 0.5675 | +0.1042 | [+0.0775, +0.1312] |

**Verdict: SUPPORTED (3/3 segments; 2/3 required).** At 4.68 µm, ink_9um reads this held-out scroll worse than at 9.36 µm. The WARNING threshold (`scale < 0.55 × 9.6`) stays, and the patch is unchanged.
- **Operative direction:** reverse on all three segments, by the same symmetric rule as above. This is the opposite of the forward-preferring held-out matrix, which is one more reason the patch recommends `--direction both`.
- **Non-operative (forward) direction:** both arms are near chance (0.52–0.58); see `summary.md`.
- **Caveat:** this is one scroll and one intermediate scale. There are 1,033–1,630 blocks of 64×64 per segment, and the CIs are from the block bootstrap only.

## Depth-order flip vs the issue

On the **public S3** w035 volume, CLI **`forward` beats `reverse`** for both open-data L2 labels and HF aligned ch10, with either the training Z window `[13,97]` or a center pool (HF vs open agree **99.31%** on window A). Holdout 46527 also prefers forward at L2.

We **could not reproduce** the issue’s reverse-better w035 table on this store. Tutorial text: ``--flip-normals`` “reproduces the depth orientation of the published renders and the training labels”; the issue’s “as the renderer writes it” vs “reversed” cells likely assume a prepare/render path whose native Z convention differs from the raw public zarr. **Limitation:** we did not re-run the author’s exact `prepare_9um_isotropic_input` CLI end-to-end. Neutral CLI wording (recommend `--direction both`) remains the right product behavior.

## Tests

6 tests in `tests/test_inference_orientation_1648.py` (helpers + `infer_single_zarr` log path).
On bare `main`: ImportError for new symbols (stated plainly — these exercise new code).
Clean `git am` + pytest: **6 passed**.

## Apply

```bash
git am /path/to/villa-fixes/villa-1648/0001-*.patch
```

## Contents

- patch, tests, OPEN_DATA_NOTE
- `real-data-2026-10-05/AUC_TABLE.json` (holdout primary + memorization verdict + depth probe)
- `real-data-2026-10-05/MEMORIZATION_AND_HOLDOUT.json`
- `real-data-2026-10-05/ckpt_config_seed42.excerpt.json`
- pytest logs
- `heldout-matrix-2026-10-08/` (pre-registration + sha256, metrics-only results, deviations; code in the separate `gpu-1648-heldout` bundle)
- `intermediate-scale-2026-10-08/` (pre-registration + sha256, step-0 checks, metrics-only results, deviations; code in the separate `gpu-1648-intermediate-scale` bundle)
