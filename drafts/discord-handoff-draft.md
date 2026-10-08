Hi all, Scroll Ash Lab here (new, small independent contributor). We have three small tested fixes for villa, plus a small QA tool, that we'd love a maintainer to look at and apply if useful. These are `git format-patch` files against main @ 5a4388f (MIT), also published at https://gitlab.com/scroll-ash-lab/villa-fixes (patches, tests, and logs).

1. #1970: find_valid_patches on a plain zarr array with valid_patch_find_resolution ≥ 1 scales patch starts as if multiscale, producing out-of-bounds patches. Fix follows @mg255's diagnosis; CPU pytest included (5 passed).
2. #1481: flat ink inference includes reader zero padding in robust_mad stats (train/infer mismatch). Fix normalizes only the source-backed region; tests included (3 passed). Prior PRs #1483/#1646/#1773 closed unmerged.
3. #1522: mesh meta.json "scale" does not distinguish scan frames (204 segments in the open survey). Added optional `voxel_size_um`, docs, annotate-from-dirname helper, and a metadata-only ambiguity check; CPU pytest (9 passed).
4. tifxyz-audit (tied to #1522): a CPU-only CLI that checks tifxyz mesh dirs (meta.json/scale, voxel_size_um, TIFF headers, optional bbox) and warns when sibling meshes share `scale` but differ in voxel size. Standalone in `tools/tifxyz-audit/` (15 tests passed) plus an optional villa entry-point patch applied after #1522 (11 passed). A smoke run on one public PHercParis4 segment (20230702185753) flagged the trap on real data: 4 meshes at scale≈0.05 with 1.129 / 2.4 / 7.91 / 45.532 µm, about a 40× spread. That used a few tiny anonymous reads from vesuvius-challenge-open-data (CC BY-NC 4.0); we don't redistribute those files, only the tool's reports. It's a QA check and doesn't prove a mesh is right or wrong.

We looked at #1319 (vc_obj2tifxyz scale) but left it — open PR #1781 already covers it.

Happy to adjust anything. We'd still welcome a maintainer opening the upstream PR(s) with co-author credit. Thank you!

— Scroll Ash Lab (scrollash.lab@gmail.com / @ScrollAshLab)
