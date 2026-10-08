"""Mirror one public HF-bucket zarr (scrollprize/datasets) to a local dir: list stored objects, download each.
Only stored chunks are fetched (missing chunks = fill value)."""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
API = "https://huggingface.co/api/buckets/scrollprize/datasets/tree/"
RES = "https://huggingface.co/buckets/scrollprize/datasets/resolve/"
UA = {"User-Agent": "gpu-1648-heldout"}
def listing(prefix):
    url, out = API + prefix + "?recursive=true", []
    while url:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            out += json.load(r); link = r.headers.get("Link") or ""
        m = re.search(r'<([^>]+)>;\s*rel="next"', link); url = m.group(1) if m else None
    return [i for i in out if i.get("type") == "file"]
def get(item, prefix, dest):
    rel = item["path"][len(prefix):].lstrip("/"); path = os.path.join(dest, rel)
    if os.path.exists(path) and os.path.getsize(path) == item["size"]: return item["size"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(RES + item["path"], headers=UA), timeout=120) as r: data = r.read()
            if len(data) != item["size"]: raise IOError("size mismatch")
            open(path + ".part", "wb").write(data); os.replace(path + ".part", path); return len(data)
        except Exception:
            if attempt == 4: raise
if __name__ == "__main__":
    prefix, dest = sys.argv[1].rstrip("/"), sys.argv[2]
    items = listing(prefix)
    with ThreadPoolExecutor(16) as ex: total = sum(ex.map(lambda i: get(i, prefix, dest), items))
    print(json.dumps({"prefix": prefix, "files": len(items), "bytes": total}))
