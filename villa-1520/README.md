# villa #1520 — README entrypoints vs `[project.scripts]`

**Issue:** https://github.com/ScrollPrize/villa/issues/1520 (verified open 2026-10-04)  
**Base:** villa `main` @ `5a4388f`  
**Author:** Scroll Ash Lab \<scrollash.lab@gmail.com\>  
**License:** MIT (same as villa)

## Problem

`vesuvius/README.md` documented console scripts `vesuvius.render_obj`, `vesuvius.flatten_obj`, and `vesuvius.proofreader` that are not in `[project.scripts]`. Proofreading / rendering sections still told users to run those entrypoints. Prior closed unmerged attempt: PR #1616.

## Fix

- Rebuild the Entrypoints table from current `[project.scripts]` (adds missing scripts such as `accept_terms`, `find_patches`, `zarr_tasks`, `blend_and_finalize`, `surface_preflight`; corrects module paths).
- Retire the three ghost names with pointers to `segmentation/vc_proofreader`, `deprecated/thaumato-anakalyptor`, and `volume-cartographer` / `vc_render_tifxyz`.
- Fix stale image / docs links (`docs/docs/...` → `docs/...`).
- Add `tests/test_readme_entrypoints.py` so the table cannot drift again.

## Tests

```text
3 failed  (before) → 3 passed (after) on the #1520 assertions
```

After also applying `villa-1300`, the same file has **4 passed** (extra install-note assertion).

Exact count for this patch alone: **3 passed** (`pytest vesuvius/tests/test_readme_entrypoints.py` before the #1300 hunk).

## Limits

Docs + regression test only; does not restore the removed rendering/proofreader packages.
