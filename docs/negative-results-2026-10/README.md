# What didn't work: two pre-registered tests for detecting segmentation failures from published outputs (Oct 2026)

*Scroll Ash Lab. AI-assisted analysis and write-up: an AI agent planned and ran the code and wrote this note. Every number below comes from our own runs on public `vesuvius-challenge-open-data` (CC BY-NC 4.0) and the windcheck v0.3.2 topology benchmark. No data payloads are included here, only summary numbers (`*-summary.json`).*

**Why share this:** both ideas sound natural ("a bad segment should show up in its ink map / its flattened texture"). Both looked promising on a first sample, and both failed to replicate on data we had not looked at. The aim is to save others the same detour.

Labels in both tests: windcheck v0.3.2 self-crossing ("transverse self-intersection") dispositions, i.e. *dirty* = transformed by windcheck, *clean* = already_clean.

---

## A. Does a segment's published ink-detection output reveal geometry failure? **No.**

**Test:** Published `ink-detection/downsampled/*-ds8.jpg` per segment: presence, the fraction of ink-like pixels, and an "empty" flag. Thresholds were frozen label-blind before any class comparison (on-mesh V=1, ink-like T=128, empty if max ink fraction < E=0.0393).

| | Result |
|---|---|
| Presence | 63/63 pilot segments have ink outputs → no signal |
| Pilot empty flag (61 scored: 38 dirty / 23 clean) | 3/38 dirty vs 0/23 clean empty, Fisher p = 0.28 |
| Pilot pooled AUC (dirty > clean, max ink fraction) | 0.48 (95% CI 0.34–0.63) |
| Pilot, exploratory, within scroll × ink model (PHercParis4, PHerc0139) | dirty lower ink fraction, p = 0.026; size-residualized p = 0.006 |
| **Pre-registered replication** (only stratum with ≥3 per class: PHerc0500P2 × canonical 2.4 µm model, 19 dirty / 17 clean) | p = 0.27; size-residualized p = 0.45 → **FAIL** |
| Replication empty flag (177 scored) | 6/132 dirty vs 8/45 clean empty: OR 0.22, p = 0.009, **opposite direction** |

**Why it fooled us first:** confounds.
- *Scroll mix:* several scrolls are clean-only or dirty-only. The "opposite" empty-flag result is carried by clean-only PHerc0009B (4 empty) and PHerc0343P (2 empty).
- *Ink-model mix:* TimeSformer 7.91 µm outputs (PHerc0172) vs canonical 2 µm and 1 µm L1 outputs elsewhere.
- *Mesh size:* dirty meshes are larger (pilot stratified canvas permutation p = 0.0001).
- *Repair history:* `displacement_repaired` traces cluster among dirty ones.

We also saw a windcheck-dirty PHercParis4 segment with clearly letter-like ink output. Self-intersection does not mean an empty ink map.

## B. Do flattened renders show texture breaks (or seam darkening) where a segment crosses itself? **No.**

**Test:** Within each segment, compare a zone around windcheck's real self-crossing contacts against 1,000 randomly shifted copies of that zone in the *same* segment (removing scroll/model/size confounds by design).
- Render: published surface volume at matching voxel size, level 2, middle slice.
- Primary metric: texture break b = 1 − structure-tensor coherence (σ_d 1, σ_i 3 px).
- Secondary metric: intensity darkening near contacts, i.e. the seam-darkening idea in villa #1641/labelscope.
- Decision rule (pre-registered): Fisher combined p < 0.05 and z > 0 in at least half the segments.

| | Primary (texture break) | Secondary (darkening) |
|---|---|---|
| Pilot, 8 segments (PHerc0814 3, PHerc0172 4, PHerc0139 1) | p = 0.95, 3/8 z > 0, median z −0.70 → **NO** | p = 9e-8, 7/8 zI > 0 (looked real) |
| Held-out, 19 segments (PHerc0172 16, PHerc0139 3) | p = 0.93, 6/19 z > 0, median z −0.83 | p = 0.028 but 8/19 zI > 0, median zI −0.05 → **FAIL** (confirmation rule written before held-out scoring) |

**Why the secondary fooled us first:** strong darkening shows up in a few hand-made `wNNN_flatboi` segments (PHerc0172: 4/4 in the pilot, z 3.1–5.1; held-out: only w081 and w085 in PHerc0172 plus w046 in PHerc0139 are strong). It is absent in others and in a 9-segment auto-grown family (one parent run, null). The pilot happened to draw the strong family.
- *Scroll mix:* large in PHerc0172, ~null in PHerc0814.
- *Segment-family mix:* hand-traced vs auto-grown.
- *Zone/mesh size:* 22 to 203,663 zone cells.

Self-crossing contact zones were, if anything, slightly *more* texture-coherent than the rest.

**Limits:** one slice, one pyramid level, fixed σ; structure-tensor metrics depend on resolution (see the sheetcheck caveat). We deliberately did not search over slices or σ after seeing results.

---

## Take-aways
1. Cross-segment comparisons of published outputs are dominated by scroll × model × mesh-size × family confounds. Use within-segment nulls and keep a held-out set.
2. At 9.362 µm, a self-crossing contact usually leaves no reliable local trace in the flattened texture or intensity. 3D topology checks (windcheck / `vc_tifxyz_selfcross`) are not replaceable by 2D render audits.
3. A strong pilot can come from one segment family. Cap per-family counts, not just per-scroll.

## Files
- `A-ink-emptiness-summary.json`, `B-fiber-continuity-summary.json`: numbers above, generated from our run outputs.
- The full scripts, pre-registrations and per-segment outputs live in our lab tree (`experiments/pipeline-failure-triage/`, `experiments/fiber-continuity-auditor/`). Cached open data is not redistributed. Reproduce from the public bucket under CC BY-NC 4.0.

Related prior work: windcheck (self-crossing census; VC3D `vc_tifxyz_selfcross`), villa #1641 + labelscope (seam darkening, validated on planted defects), sheetcheck (structure-tensor resolution caveat).
