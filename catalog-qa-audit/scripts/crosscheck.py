"""Loader cross-check (pre-registration, per-class evidence item 3).
For each mesh path: fresh anonymous download of x/y/z.tif + meta.json into data/cache/xcheck/ (local only, CC BY-NC,
never redistributed), then recompute the scan statistics from (a) villa's vesuvius.tifxyz.read_tifxyz at main and
(b) raw tifffile, and compare both with the scan row. Output is metadata-derived numbers only.
Usage: PYTHONPATH=<villa main>/vesuvius/src python -B crosscheck.py SCAN_JSONL OUT_JSON PATH [PATH ...]"""
import json, sys, urllib.request
from pathlib import Path
from urllib.parse import quote
import numpy as np, tifffile
sys.path.insert(0, str(Path(__file__).parent))
from common import BUCKET
import scan_meshes as sm
from vesuvius.tifxyz import read_tifxyz

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "xcheck"
KEYS = ("rows", "cols", "n_valid_vc", "n_valid_strict", "bbox_vc", "bbox_strict", "n_pairs", "spacing_median", "area_vx2_computed")


def fetch(path):
    d = CACHE / path.strip("/").replace("/", "__")
    d.mkdir(parents=True, exist_ok=True)
    for f in ("x.tif", "y.tif", "z.tif", "meta.json"):
        if not (d / f).exists():
            with urllib.request.urlopen(f"{BUCKET}/{quote(path + f, safe='/')}", timeout=600) as r:
                (d / f).write_bytes(r.read())
    return d


def rel(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    return float(np.max(np.abs(a - b) / np.maximum(np.abs(b), 1e-12))) if a.size else 0.0


def compare(st, row):
    out = {}
    for k in KEYS:
        a, b = st.get(k), row.get(k)
        if k in ("rows", "cols", "n_valid_vc", "n_valid_strict", "n_pairs"):
            out[k] = {"value": a, "scan": b, "ok": a == b}
        elif a is None or b is None:
            out[k] = {"value": a, "scan": b, "ok": a == b}
        else:
            r = rel(a, b); out[k] = {"value": a, "scan": b, "max_rel_diff": r, "ok": r <= 1e-6}
    return out


def main():
    scan = {json.loads(l)["path"]: json.loads(l) for l in open(sys.argv[1])}
    res = []
    for path in sys.argv[3:]:
        row = scan[path]; d = fetch(path)
        meta = json.loads((d / "meta.json").read_text())
        # (a) villa reader at main
        t = read_tifxyz(d, load_mask=False)
        Pv = np.stack([t._x, t._y, t._z], -1).astype(np.float32)
        sv = sm.point_stats(Pv)
        # (b) raw tifffile from the same fresh files
        Pr = np.stack([tifffile.imread(d / f"{c}.tif") for c in "xyz"], -1).astype(np.float32)
        sr = sm.point_stats(Pr)
        res.append({"path": path, "sample": row["sample"], "segment": row["segment"], "type": row["type"],
                    "arrays_identical_vesuvius_vs_tifffile": bool(np.array_equal(Pv, Pr, equal_nan=True)),
                    "meta_scale_file": meta.get("scale"), "meta_scale_scan": row["meta"].get("scale"),
                    "vesuvius_scale_yx": list(t._scale),
                    "meta_fields_equal_scan": all(meta.get(k) == row["meta"].get(k) for k in row["meta"]),
                    "vesuvius": compare(sv, row), "tifffile": compare(sr, row)})
        r = res[-1]
        print(path[-75:], "identical arrays:", r["arrays_identical_vesuvius_vs_tifffile"], "meta equal:", r["meta_fields_equal_scan"],
              "all ok vesuvius:", all(v["ok"] for v in r["vesuvius"].values()), "tifffile:", all(v["ok"] for v in r["tifffile"].values()), flush=True)
        del Pv, Pr, t
    json.dump(res, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
