"""Post hoc diagnostic (not pre-registered; see results/deviations.md): for every store whose level 1 came out OTHER,
re-read the first probe cell and (a) test strided-decimation rules child[k] = parent[2k+oz, 2y+oy, 2x+ox], and
(b) map each child plane to its best-correlating parent plane (in-plane 2x2 mean), to measure depth coverage."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent)); import audit as A
ROOT = Path(__file__).resolve().parents[1]
a = json.load(open(ROOT / "results" / "audit.json"))["stores"]
out = {}
for s, v in a.items():
    L = v["L1"]
    if L.get("rule") != "OTHER": continue
    ch, pa = A.Arr(s, "1"), A.Arr(s, "0"); cy, cx = ch.chunks[1:]; iy, ix = L["cells"][0]
    y0, y1, x0, x1 = iy * cy, min(ch.shape[1], (iy + 1) * cy), ix * cx, min(ch.shape[2], (ix + 1) * cx)
    c = ch.read(y0, y1, x0, x1).astype(np.int64); p = pa.read(2 * y0, min(pa.shape[1], 2 * y1), 2 * x0, min(pa.shape[2], 2 * x1)).astype(np.int64)
    nzc, nzp = c.shape[0], p.shape[0]; h = min(c.shape[1], p.shape[1] // 2); w = min(c.shape[2], p.shape[2] // 2); c = c[:, :h, :w]
    stride = {}
    for oz in (0, 1):
        for oy in (0, 1):
            for ox in (0, 1):
                ks = [k for k in range(nzc) if 2 * k + oz < nzp]
                P = np.stack([p[2 * k + oz, oy:2 * h:2, ox:2 * w:2] for k in ks]); d = np.abs(P - c[ks])
                stride[f"{oz}{oy}{ox}"] = [int((d > 0).sum()), int(d.max()), len(ks)]
    S = p[:, :2 * h, :2 * w].reshape(nzp, h, 2, w, 2).mean(axis=(2, 4))
    best = []
    for k in range(nzc):
        ck = c[k].ravel().astype(float)
        r = [np.corrcoef(ck, S[j].ravel())[0, 1] if ck.std() > 0 and S[j].std() > 0 else -2 for j in range(nzp)]
        best.append(int(np.nanargmax(r)))
    out[s] = {"cell": [iy, ix], "strided": stride, "best_parent_plane_per_child_plane": best,
              "max_best_parent_plane": max(best), "parent_planes": nzp, "child_planes": nzc}
    print(s.split("/")[-1], "stride_exact:", [k for k, v in stride.items() if v[0] == 0], "best planes", best[:3], "...", best[-3:], flush=True)
json.dump(out, open(ROOT / "results" / "diagnose-other.json", "w"), indent=1)
