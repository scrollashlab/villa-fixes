"""List every render store <seg>/<seg>.zarr under the ink/ prefix of the scrollprize/datasets HF bucket (directory listings only)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); from hfdir import ls
ROOT = Path(__file__).resolve().parents[1]
SKIP = ("_inklabels", "_supervision_mask", "_validation_mask", "_max_")
def segdirs(prefix):
    return [d for d in ls(prefix) if not d.rsplit("/", 1)[-1].startswith(".") and "." not in d.rsplit("/", 1)[-1]]
stores, notes = [], []
scrolls = [d for d in segdirs("ink") if not d.endswith("/unused")] + segdirs("ink/unused")
def renders(kids):
    return [k for k in kids if k.endswith(".zarr") and not any(t in k.rsplit("/", 1)[-1] for t in SKIP)]
for sc in scrolls:
    top = ls(sc)
    stores += renders(top)  # a store placed directly in a scroll-level folder (e.g. ink/unused/500p2a)
    if renders(top): continue
    for seg in segdirs(sc):
        name = seg.rsplit("/", 1)[-1]; kids = ls(seg)
        z = renders(kids)
        if not z: notes.append({"segment_dir": seg, "note": "no render .zarr listed", "children": len(kids)})
        stores += z
json.dump({"stores": sorted(stores), "dirs_without_render_zarr": notes}, open(ROOT / "meta" / "stores.json", "w"), indent=1)
print(len(stores), "stores;", len(notes), "segment dirs without a render zarr")
