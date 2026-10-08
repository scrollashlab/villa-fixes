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
