# Deviations from the pre-registration

1. **No deviation in the pre-registered census.** The population, probes, rules, classes, positive control, primary and secondary outcomes and decision rule were run as sealed. They were scored once (`results/audit.json`, `results/run.log`).
2. **Added post hoc diagnostics, labelled as such in `summary.md`.** The pre-registered rule family has no strided-decimation rule. OTHER (47 stores at level 1) therefore did not say whether those stores keep the full depth. Two diagnostics were added after scoring, on the first probe cell of each OTHER store:
   - `scripts/diagnose_other.py`: an exact test of strided decimation and a best-matching parent plane for every child plane (`results/diagnose-other.json`, `results/diagnose-other.log`);
   - `scripts/diagnose_corr.py`: correlations for the 9 stores without an exact strided match (`results/diagnose-corr.json`, `results/diagnose-corr.log`).
   They change no pre-registered number. They add the count of 6 depth-truncated stores outside the exact TRUNC class, reported separately from the primary outcome.
3. **Code provenance was added after scoring.** The source of the TRUNC pattern (`createPyramidDatasets` vs `downsampleTileIntoPreserveZ` in villa `volume-cartographer/core/src/Zarr.cpp`, between #774 and #804) was read from public villa history after the census. It is explanatory and not part of the scored outcome.
4. **Data volume.** The census read 1,553,161,120 bytes (1553.2 MB) of chunks. The pre-registration set no cap. The diagnostics re-read the first probe cell of the 47 OTHER stores.
