"""Download the pre-registered segments' tifxyz_normalized directories (all files) into the local CC BY-NC cache."""
import json, re, sys, hashlib, urllib.request
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).parent))
from common import CAT, CACHE, BASE, SEGMENTS
md = json.load(open(CAT)); out = []
for s, g in SEGMENTS:
    seg = md["samples"][s]["segments"][g]
    key = next(e["origins"][0]["path"] for e in seg["data"] if e["type"] == "tifxyz-normalized").rstrip("/")
    lst = urllib.request.urlopen(f"{BASE}/?list-type=2&prefix={quote(key + '/')}").read().decode()
    files = re.findall(r"<Key>([^<]+)</Key>", lst)
    rec = {"sample": s, "segment": g, "long_id": seg["long_id"], "downscale": seg["properties"]["original_volume_downscale"],
           "key": key, "files": {}}
    for f in files:
        dst = Path(CACHE) / f; dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            dst.write_bytes(urllib.request.urlopen(f"{BASE}/{quote(f)}").read())
        rec["files"][f.rsplit("/", 1)[1]] = {"bytes": dst.stat().st_size, "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}
    out.append(rec); print(s, g, rec["downscale"], sorted(rec["files"]))
json.dump(out, open(sys.argv[1], "w"), indent=1)
