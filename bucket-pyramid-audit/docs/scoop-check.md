# Scoop check

Searched 2026-10-08 (HST) through the public GitHub search API and villa history:

- villa issues and PRs for `pyramid` (31 results) and `downsampl` (6 results). The closest are:
  - header-level pyramid audits of `dl.ash2txt.org` and the open-data bucket: #1755, #1756, #1757, #1759, #1760 (#1760 closed as not planned), #1950, #1963;
  - a metadata-unit issue for one ink prediction store (#1962);
  - the render-side scale-metadata PR #845.
  None reads chunk content, and none covers the `scrollprize/datasets` Hugging Face bucket or reports levels that hold only the first half of the depth.
- villa `vc_render_tifxyz` / `Zarr.cpp` history. #804 changed `createPyramidDatasets` back to keeping z, but neither it nor any issue mentions renders already published with the halved depth.
- The earlier finding for the four PHerc0841 / 500p2a stores is our own (`gpu-1648-intermediate-scale`, step 0a).

Nothing found reports this data issue.
