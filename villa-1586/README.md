# villa #1586 — `cache_max_gb` double accounting (~2× on disk)

**Issue:** https://github.com/ScrollPrize/villa/issues/1586 (verified open 2026-10-04)  
**Base:** villa `main` @ `5a4388f`  
**Author:** Scroll Ash Lab \<scrollash.lab@gmail.com\>  
**License:** MIT  
**Credit:** @flummoxjr for the diagnosis and prior closed PR #1587 (auto-closed for inactivity).

## Problem

`open_volume_root` hands the same byte budget to (1) an open-time directory sweep and (2) a fresh zarr `CacheStore` whose in-memory LRU starts empty and never scans files left by an earlier run. Reopening an at-budget cache directory therefore spends a *second* full budget on disk (~1.9–2× steady state).

## Fix

- Always snapshot the volume cache subdirectory when a budget is set.
- After constructing `CacheStore`, seed its private LRU (`_state`) from the retained files (oldest-first) before `zarr.open`.
- If the installed zarr build exposes no seedable state, emit `RuntimeWarning` (fail loudly) rather than silently overshooting.
- Docs updated in `ink_detection` README and `docs/ink_detection.md`.

## Tests

Requires **Zarr ≥ 3** (the disk-cache path already requires Zarr 3).

Environment used for the verified full-file run (2026-10-04 PT): `/tmp/zarr3-venv` (CPython 3.13.5, zarr 3.4.0, torch 2.14.1+cpu, fsspec, plus minimal deps for `vesuvius.ink_detection.data.dataset`). Editable `pip install -e …/vesuvius --no-deps --ignore-requires-python` (package declares `requires-python >=3.14,<3.15`).

| Tree | Command | Result |
|------|---------|--------|
| unmodified `5a4388f` | `pytest tests/ink_detection/test_volume_io.py -v` | **13 passed** / 0 failed |
| handoff stack incl. this patch | same | **16 passed** / 0 failed |

The three new tests from this patch all passed:

- `test_reopening_reuses_one_budget_instead_of_granting_a_new_one`
- `test_seeded_entries_evict_oldest_first_and_survive_reuse`
- `test_unseedable_cache_store_is_reported_not_silently_overfilled`

The four previously env-blocked tests all passed on **both** base and patched (no patch regression):

- `test_cached_and_uncached_volume_reads_are_byte_identical`
- `test_shared_cache_multiprocess_reads_are_not_torn`
- `test_parent_populated_dataset_cache_misses_after_fork`
- `test_public_substring_http_uses_real_backend_without_s3_options`

Logs: `pytest-base-full.log`, `pytest-patched-full.log`.

## Limits

- Seeds `CacheStore._state` (no public zarr API); guarded + warned if layout changes.
- Concurrent multi-process writers can still overshoot until the next open-time sweep (documented).
- Does not fix the separate upstream zarr bug where `max_size` smaller than one chunk never tracks full-key writes.

## Evidence on real scroll data (2026-10-05 HST, villa `main` @ `0e14cf48`)

Volume: public PHercParis4 scan `s3://vesuvius-challenge-open-data/PHercParis4/volumes/20260411134726-2.400um-0.2m-78keV-masked.zarr`, level `3` (128³ uint8 chunks, 2 MiB each), opened anonymously through `open_volume_root(..., cache_dir=..., cache_max_gb=0.03)`.
Each run is a fresh process that reads 20 different non-empty chunks near the volume centre, then measures the cache directory. Script and raw output: `real-data-2026-10-05/`.

| Run (fresh process) | Unmodified main: cache on disk | With this patch: cache on disk |
|---|---|---|
| 1 (empty cache) | 29,360,128 B (0.98× budget) | 29,360,128 B (0.98× budget) |
| 2 (reopen, new chunks) | 58,720,256 B (**1.96×** budget) | 29,360,128 B (0.98× budget) |
| 3 (reopen, new chunks) | 54,525,952 B (**1.82×** budget) | 29,360,128 B (0.98× budget) |

All 60 blocks read through the patched cache were byte-identical (SHA-256) to uncached reads of the same volume.

Retest in a fresh env (`/workspace/envs/zarr3`: CPython 3.13.5, zarr 3.4.0, torch 2.14.1+cu130 running on CPU, s3fs 2026.9.0; source via `PYTHONPATH=<tree>/vesuvius/src`): unmodified main `test_volume_io.py` **13 passed**; patched **16 passed**; the patched test file run against unmodified source gives **3 failed, 13 passed** (exactly the three new tests).
