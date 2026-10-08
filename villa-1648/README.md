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
