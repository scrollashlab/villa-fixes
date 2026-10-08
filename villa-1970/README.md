# villa#1970 — plain zarr + `valid_patch_find_resolution` ≥ 1

Upstream: https://github.com/ScrollPrize/villa/issues/1970

## Problem

When a label/image volume is a **plain zarr Array** (not an OME-Zarr multiscale
group) and `valid_patch_find_resolution` is ≥ 1, `find_valid_patches` treated
the full-resolution array as already downsampled and multiplied patch starts by
`2**level`, writing out-of-bounds positions into the patch cache.

## Repro (CPU)

Synthetic plain array shape `(221, 132, 132)`, patch `(128, 128, 128)`, labeled
blob in the first corner:

| level | before | after |
|------:|--------|-------|
| 0 | `[[0,0,0]]` | `[[0,0,0]]` |
| 1 | OOB starts | `[[0,0,0]]` |
| 2 | OOB | `[[0,0,0]]` |

OME groups with a real level `1/` still use that level. Level-0-only groups
still fall back to full resolution.

## Fix

In both `_resolve_resolution` helpers: plain arrays (no `.keys`) only satisfy
level `0`; higher levels return `None` so the existing full-resolution fallback
runs. Multiscale groups are unchanged.

Diagnosis and fix direction: **@mg255** on #1970. Related CLI work in #1969
uses `valid_patch_find_resolution: 0` as a config workaround and does not fix
this bug.

## Base revision

Built against villa `main` at `5a4388f08cc547e6a1a037f949173e731a3e7aa2`
(“Fix & simplify progress prize automation (#1948)”).

## Apply

```bash
cd /path/to/villa
git checkout main   # at or after 5a4388f
git am /path/to/0001-find_valid_patches-do-not-scale-plain-zarr-arrays-as.patch
# or: git apply /path/to/0001-find_valid_patches-do-not-scale-plain-zarr-arrays-as.patch
```

## Tests

```bash
python -m pytest vesuvius/tests/models/datasets/test_find_valid_patches_resolution.py -v
```

Local CPU result (2026-10-04 PT): **5 passed** in ~1.8s. See `pytest-results.log`.

Author on the patch: Scroll Ash Lab \<scrollash.lab@gmail.com\>.

## Upstream status (2026-10-05)

An independent upstream PR, [ScrollPrize/villa#1980](https://github.com/ScrollPrize/villa/pull/1980), fixes the same bug with the same core approach: a plain zarr array only counts as level 0, and anything else falls back to full resolution. It looks like a strict improvement on this patch. It uses one shared helper, makes the unlabeled-FG image level follow the label fallback, and bumps the patch-cache schema so stale out-of-bounds caches are discarded.

Both patches apply cleanly on villa `main` @ `0e14cf48`. In a real install (zarr 3.4.0), #1980 passes its own 6 tests. Our 3 plain-array #1970 tests also pass on its code. Our 2 OME tests error in fixture setup (`Group.create_dataset` is gone in zarr 3), not in assertions against the fix.

We recommend #1980 as the upstream path for #1970. This folder stays as earlier independent work.
