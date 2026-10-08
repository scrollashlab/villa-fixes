"""Checks behind README statements for W and S (metadata-derived numbers only).
Usage: python -B verify_readme_claims.py AUDIT_RESULTS_JSON SCAN_JSONL OUT_JSON"""
import json, sys, urllib.request
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).parent))
from common import BUCKET, load_catalog
md = load_catalog(); R = json.load(open(sys.argv[1]))["rows"]
scan = {json.loads(l)["path"]: json.loads(l) for l in open(sys.argv[2])}


def zshape(p):
    for z in ("0/.zarray", ".zarray"):
        try:
            with urllib.request.urlopen(f"{BUCKET}/{quote(p + z, safe='/')}", timeout=60) as r:
                return json.load(r)["shape"]
        except Exception:
            pass
    return None


out = {"W": [], "S": {}}
for r in [x for x in R["W"] if x["defect"]]:
    seg = md["samples"][r["sample"]]["segments"][r["id"]]; w, h = r["declared_wh"]
    grids = []
    for d in seg["data"]:
        p = d["origins"][0]["path"]
        if p in scan and scan[p]["meta"].get("scale"):
            sc = scan[p]["meta"]["scale"]; grids.append((d["type"], round(scan[p]["cols"] / sc[0]), round(scan[p]["rows"] / sc[1])))
        if d["type"] == "layers-zarr":
            s = zshape(p)
            if s: grids.append(("layers-zarr:" + str((d.get("parameters") or {}).get("target_volume")), s[-1], s[-2]))
    exact = [g for g in grids if abs(g[1] - w) <= 1 and abs(g[2] - h) <= 1]
    out["W"].append({"sample": r["sample"], "segment": r["id"], "declared": [w, h], "candidates": grids, "matches_within_1px": exact})
ok = [x for x in R["S"] if not x["defect"] and x["sample"] == "PHerc0814"]
bad = [x for x in R["S"] if x["defect"]]
out["S"] = {"defect_spacing_range": [min(x["spacing_median"] for x in bad), max(x["spacing_median"] for x in bad)],
            "defect_ratio_range": [min(x["ratio"] for x in bad), max(x["ratio"] for x in bad)],
            "PHerc0814_pass_rows": len(ok), "PHerc0814_pass_segments": len({x["id"] for x in ok}),
            "PHerc0814_pass_ratio_range": [min(x["ratio"] for x in ok), max(x["ratio"] for x in ok)]}
json.dump(out, open(sys.argv[3], "w"), indent=1)
print("W rows", len(out["W"]), "with any published grid/render matching declared within 1 px:", sum(bool(x["matches_within_1px"]) for x in out["W"]))
for x in out["W"]:
    if x["matches_within_1px"]: print("  match", x["sample"], x["segment"], x["matches_within_1px"])
print(json.dumps(out["S"]))
