"""Load each pre-registered normalized mesh with whichever vesuvius tree is on PYTHONPATH.
Usage: PYTHONPATH=<villa>/vesuvius/src python load_arm.py unpatched|patched OUT_DIR OUT_JSON
Points are saved (local only, CC BY-NC derived) as float32 (rows, cols, 3) with invalid = -1."""
import json, sys, warnings, subprocess
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import CAT, CACHE, SEGMENTS
import vesuvius.tifxyz as tx

arm, outdir, outjson = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
outdir.mkdir(parents=True, exist_ok=True)
src_root = Path(tx.__file__).resolve().parents[3]
rev = subprocess.run(["git", "-C", str(src_root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "-C", str(src_root), "status", "--porcelain", "--", "vesuvius/src"], capture_output=True, text=True).stdout.strip()
md = json.load(open(CAT)); rows = []
for s, g in SEGMENTS:
    long_id = md["samples"][s]["segments"][g]["long_id"]
    d = Path(CACHE) / s / "segments" / long_id / "mesh" / "intermediate" / "tifxyz_normalized"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        if arm == "unpatched":
            surf = tx.read_tifxyz(d)                       # what a user of villa main does today
        else:
            surf = tx.read_open_data_normalized(d, CAT)    # patched, catalog-aware
    P = np.stack([surf._x, surf._y, surf._z], -1).astype(np.float32)
    v = surf._valid_mask
    P[~v] = -1.0
    np.save(outdir / f"{s}_{g}.npy", P)
    rows.append(dict(sample=s, segment=g, shape=list(P.shape[:2]), n_valid=int(v.sum()), bbox=surf.bbox,
                     scale=list(surf.get_scale_tuple()), full_resolution_shape=list(surf.full_resolution_shape),
                     applied=surf.extra.get("original_volume_downscale_applied"),
                     warnings=[f"{x.category.__name__}: {str(x.message)[:160]}" for x in w]))
json.dump(dict(arm=arm, vesuvius_tifxyz=str(Path(tx.__file__).resolve()), villa_head=rev,
               uncommitted_changes_in_vesuvius_src=bool(dirty), segments=rows), open(outjson, "w"), indent=1)
print(json.dumps(rows, indent=0)[:3000])
