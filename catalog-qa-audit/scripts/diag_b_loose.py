"""Exploratory diagnosis of B-loose (not pre-registered; cannot change the verdict).
Splits B rows by reference mesh type and, for failing rows, tests whether the declared bbox_transformed equals the
corner-transform of the segment's stored creation.metadata.bbox (x original_volume_downscale) under the catalog matrix.
Usage: python -B diag_b_loose.py AUDIT_RESULTS_JSON OUT_JSON"""
import itertools, json, sys, collections
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import CAT, XFRAME_SRC, load_catalog
sys.path.insert(0, XFRAME_SRC)
from xframe.catalog import Catalog
md = load_catalog(); cat = Catalog.load(CAT); R = json.load(open(sys.argv[1]))["rows"]["B"]
by_ref = collections.Counter((r["reference"], r["defect"]) for r in R)
rows = []
for r in R:
    if not r["defect"]: continue
    s, g, V = r["sample"], r["id"], r["volume"]; seg = md["samples"][s]["segments"][g]
    cb = ((seg.get("creation") or {}).get("metadata") or {}).get("bbox")
    ds = float(seg["properties"].get("original_volume_downscale") or 1)
    M = np.asarray(cat.matrix(s, seg["original_volume_id"], V)[0], float)
    diff = None
    if cb:
        C = np.array([[cb[i][0], cb[j][1], cb[k][2]] for i, j, k in itertools.product((0, 1), repeat=3)], float) * ds
        Q = C @ M[:, :3].T + M[:, 3]
        d = r["declared"]; diff = max(max(abs(d[0][j] - Q.min(0)[j]), abs(d[1][j] - Q.max(0)[j])) for j in range(3))
    rows.append({"sample": s, "segment": g, "volume": V, "own_volume": V == seg["original_volume_id"],
                 "has_published_tifxyz_original": any(x["type"] == "tifxyz" for x in seg["data"]),
                 "declared_minus_stored_bbox_corner_transform_max_abs": diff, "declared_minus_normalized_max_abs": r["max_abs_diff_vc"], "tol": r["tol"]})
own = [x for x in rows if x["own_volume"]]
summary = {"B_rows_by_reference_and_flag": {f"{k[0]}|{k[1]}": v for k, v in by_ref.items()}, "failing_rows": len(rows),
           "failing_rows_with_published_tifxyz_original": sum(x["has_published_tifxyz_original"] for x in rows),
           "failing_own_volume_rows": len(own),
           "failing_own_volume_rows_equal_to_stored_bbox_times_ds(<0.01)": sum(1 for x in own if x["declared_minus_stored_bbox_corner_transform_max_abs"] is not None and x["declared_minus_stored_bbox_corner_transform_max_abs"] < 0.01),
           "failing_other_volume_rows_equal_to_corner_transform(<0.01)": sum(1 for x in rows if not x["own_volume"] and x["declared_minus_stored_bbox_corner_transform_max_abs"] is not None and x["declared_minus_stored_bbox_corner_transform_max_abs"] < 0.01),
           "segments": len({(x["sample"], x["segment"]) for x in rows})}
json.dump({"summary": summary, "rows": rows}, open(sys.argv[2], "w"), indent=1)
print(json.dumps(summary, indent=1))
