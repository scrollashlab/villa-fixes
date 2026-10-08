"""Byte sizes of every published tifxyz mesh directory (S3 ListObjectsV2, anonymous). Metadata only."""
import json, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
BASE = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com"
CAT = sys.argv[1]; OUT = sys.argv[2]
md = json.load(open(CAT))
rows = []
for s, e in md["samples"].items():
    for g, seg in e["segments"].items():
        for d in seg.get("data", []):
            if d["type"] in ("tifxyz", "tifxyz-normalized", "tifxyz-transformed", "tifxyz-flattened"):
                rows.append({"sample": s, "segment": g, "type": d["type"], "path": d["origins"][0]["path"]})
def ls(r):
    x = urllib.request.urlopen(f"{BASE}/?list-type=2&prefix={quote(r['path'])}", timeout=120).read().decode()
    r["files"] = {}
    for blk in re.findall(r"<Contents>(.*?)</Contents>", x, re.S):
        k = re.search(r"<Key>([^<]+)</Key>", blk).group(1)
        r["files"][k[len(r["path"]):]] = {"bytes": int(re.search(r"<Size>(\d+)</Size>", blk).group(1)),
                                          "last_modified": re.search(r"<LastModified>([^<]+)</LastModified>", blk).group(1)}
    r["truncated"] = "<IsTruncated>true</IsTruncated>" in x
    return r
with ThreadPoolExecutor(16) as ex:
    rows = list(ex.map(ls, rows))
json.dump(rows, open(OUT, "w"), indent=0)
import collections
c = collections.Counter(); b = collections.Counter()
for r in rows:
    c[r["type"]] += 1; b[r["type"]] += sum(v["bytes"] for k, v in r["files"].items() if k in ("x.tif", "y.tif", "z.tif"))
for k in c: print(k, c[k], round(b[k] / 1e9, 2), "GB")
print("truncated", sum(r["truncated"] for r in rows), "missing xyz", sum(not all(f in r["files"] for f in ("x.tif","y.tif","z.tif","meta.json")) for r in rows))
print("extra files", collections.Counter(k for r in rows for k in r["files"] if k not in ("x.tif","y.tif","z.tif","meta.json")).most_common(10))
