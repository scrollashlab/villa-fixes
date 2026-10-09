"""Post hoc: for the OTHER stores without an exact strided rule, report the correlation of each child plane k with
parent plane k (first-planes mapping) and with parent plane 2k (full-depth mapping), on the first probe cell."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent)); import audit as A
ROOT = Path(__file__).resolve().parents[1]
a = json.load(open(ROOT / "results" / "audit.json"))["stores"]; d = json.load(open(ROOT / "results" / "diagnose-other.json"))
out = {}
for s, v in d.items():
    if any(x[0] == 0 for x in v["strided"].values()): continue
    ch, pa = A.Arr(s, "1"), A.Arr(s, "0"); cy, cx = ch.chunks[1:]; iy, ix = v["cell"]
    y0, y1, x0, x1 = iy * cy, min(ch.shape[1], (iy + 1) * cy), ix * cx, min(ch.shape[2], (ix + 1) * cx)
    c = ch.read(y0, y1, x0, x1).astype(float); p = pa.read(2 * y0, min(pa.shape[1], 2 * y1), 2 * x0, min(pa.shape[2], 2 * x1)).astype(float)
    h = min(c.shape[1], p.shape[1] // 2); w = min(c.shape[2], p.shape[2] // 2); c = c[:, :h, :w]
    S = p[:, :2 * h, :2 * w].reshape(p.shape[0], h, 2, w, 2).mean(axis=(2, 4))
    r = lambda u, t: float(np.corrcoef(u.ravel(), t.ravel())[0, 1])
    rk = [r(c[k], S[k]) for k in range(c.shape[0])]
    r2k = [r(c[k], S[2 * k]) for k in range(c.shape[0]) if 2 * k < S.shape[0]]
    mad = float(np.abs(c - S[: c.shape[0]]).mean())
    out[s] = {"r_child_k_vs_parent_k": [min(rk), float(np.median(rk))], "r_child_k_vs_parent_2k": [min(r2k), float(np.median(r2k))],
              "mean_abs_diff_vs_parent_k_2x2mean": mad}
    print(s.split("/")[-1], out[s], flush=True)
json.dump(out, open(ROOT / "results" / "diagnose-corr.json", "w"), indent=1)
