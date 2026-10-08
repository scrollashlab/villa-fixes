"""Level-0 .zarray shape of every catalog volume (metadata only)."""
import json, sys, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).parent))
from common import load_catalog, url_of
md = load_catalog(); out = []
for s, e in md["samples"].items():
    for vid, v in e["volumes"].items():
        ent = [d for d in v["data"] if d["type"] == "ome-zarr"]
        row = {"sample": s, "volume": vid, "long_id": v["long_id"], "catalog_shape": (v.get("properties") or {}).get("shape"),
               "pixel_size_um": (v.get("properties") or {}).get("pixel_size_um"), "n_ome_zarr": len(ent)}
        if ent:
            u = url_of(ent[0]["origins"][0]).rstrip("/") + "/0/.zarray"
            row["zarray_url"] = u
            try:
                z = json.loads(urllib.request.urlopen(quote(u, safe=":/"), timeout=60).read())
                row["zarray_shape"] = z["shape"]
            except urllib.error.HTTPError as ex:
                row["zarray_error"] = f"HTTP {ex.code}"
        out.append(row)
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(len(out), "volumes;", sum("zarray_shape" in r for r in out), "with level-0 .zarray;", [ (r['sample'],r['volume'],r.get('zarray_error')) for r in out if 'zarray_shape' not in r])
