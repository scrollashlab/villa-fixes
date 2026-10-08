"""Positive control #1734 against the current catalog: for the 28 F-marker segments, report the own-volume
bbox_transformed vs the computed bbox, and re-score the B predicate with the marker values #1734 describes
(each marker axis of the lower corner set to -original_volume_downscale) to show the predicate would flag them.
Usage: python -B control_1734.py AUDIT_RESULTS_JSON OUT_JSON"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import load_catalog
md = load_catalog(); R = json.load(open(sys.argv[1]))["rows"]
segs = {(r["sample"], r["id"]) for r in R["F"] if r.get("sub") == "F-marker"}
rows = []
for r in R["B"]:
    if (r["sample"], r["id"]) not in segs: continue
    seg = md["samples"][r["sample"]]["segments"][r["id"]]
    if r["volume"] != seg["original_volume_id"]: continue
    ds = float(seg["properties"].get("original_volume_downscale") or 1)
    cm = seg["creation"]["metadata"]["bbox"]
    sim_lo = [(-ds if float(cm[0][j]) == -1 else r["declared"][0][j]) for j in range(3)]
    sim_diff = max(abs(sim_lo[j] - r["computed_vc"][0][j]) for j in range(3))
    rows.append({"sample": r["sample"], "segment": r["id"], "volume": r["volume"], "declared_lo": r["declared"][0],
                 "computed_lo_vc": r["computed_vc"][0], "max_abs_diff_current": r["max_abs_diff_vc"], "tol": r["tol"],
                 "current_flagged": r["defect"], "declared_has_minus_ds": any(v == -ds for v in r["declared"][0]),
                 "simulated_1734_lo": sim_lo, "simulated_max_abs_diff_lo": sim_diff, "simulated_flagged": sim_diff > r["tol"]})
json.dump(rows, open(sys.argv[2], "w"), indent=1)
print("segments", len(segs), "own-volume rows", len(rows), "current flagged", sum(x["current_flagged"] for x in rows),
      "current carrying -ds", sum(x["declared_has_minus_ds"] for x in rows), "simulated #1734 values flagged", sum(x["simulated_flagged"] for x in rows),
      "max current diff", max(x["max_abs_diff_current"] for x in rows))
