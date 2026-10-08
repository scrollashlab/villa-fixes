"""Diagnostic for B-loose: recompute bbox_transformed / overlap from the segment's obj-normalized vertices
(streamed, never stored) and compare with the declared values and with the tifxyz-normalized reference.
Usage: python diag_obj_reference.py SAMPLE SEGMENT [SAMPLE SEGMENT ...]  -> prints JSON lines (metadata-derived numbers only)"""
import json, sys, urllib.request
from pathlib import Path
from urllib.parse import quote
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import BUCKET, CAT, XFRAME_SRC, load_catalog
sys.path.insert(0, XFRAME_SRC)
from xframe.catalog import Catalog

SHAPES = {(r["sample"], r["volume"]): r.get("zarray_shape") for r in json.load(open(Path(__file__).parent.parent / "out" / "volume-shapes-2026-10-07.json"))}


def obj_vertices(path):
    vs = []
    with urllib.request.urlopen(f"{BUCKET}/{quote(path, safe='/')}", timeout=600) as r:
        for line in r:
            if line.startswith(b"v "):
                vs.append(line.split()[1:4])
    return np.asarray(vs, dtype=np.float64)


def main():
    md = load_catalog(); cat = Catalog.load(CAT)
    a = sys.argv[1:]
    for s, g in zip(a[::2], a[1::2]):
        seg = md["samples"][s]["segments"][g]; ov = seg["original_volume_id"]
        ds = float(seg["properties"].get("original_volume_downscale") or 1)
        objp = next(d for d in seg["data"] if d["type"] == "obj-normalized")["origins"][0]["path"]
        V0 = obj_vertices(objp)
        for V, dv in seg["properties"]["volume_coverage"].items():
            M, _ = cat.matrix(s, ov, V); M = np.asarray(M, float)
            Q = (V0 * ds) @ M[:, :3].T + M[:, 3]
            shp = SHAPES.get((s, V)); ext = np.array([shp[2], shp[1], shp[0]], float) - 1
            inside = float(((Q >= 0) & (Q <= ext)).all(1).mean())
            bb = [Q.min(0).tolist(), Q.max(0).tolist()]
            diff = max(abs(dv["bbox_transformed"][i][j] - bb[i][j]) for i in range(2) for j in range(3))
            print(json.dumps({"sample": s, "segment": g, "volume": V, "obj_vertices": int(len(V0)),
                              "declared_bbox": dv["bbox_transformed"], "obj_bbox": bb, "max_abs_diff_obj": diff,
                              "declared_overlap": dv.get("overlap_ratio"), "obj_inside_frac": inside}))


if __name__ == "__main__":
    main()
