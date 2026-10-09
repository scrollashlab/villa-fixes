"""Independent re-check with zarr-python 3 + fsspec HTTP (no code shared with scripts/audit.py)."""
import json, sys, time
import numpy as np, zarr
B = "https://huggingface.co/buckets/scrollprize/datasets/resolve/"
STORES = {
 "ink/0139/w016_2025010815/w016_2025010815.zarr": "trunc",
 "ink/814/814_46527_2um_try2/814_46527_2um_try2.zarr": "trunc",
 "ink/0500p2/-1/-1.zarr": "trunc",
 "ink/1667/w028_20251208130119156_2um/w028_20251208130119156_2um.zarr": "other_trunc",
 "ink/unused/0139/w024_2026021572/w024_2026021572.zarr": "strided",
}
FRACS = [(0.45, 0.55), (0.6, 0.35), (0.35, 0.65), (0.55, 0.4), (0.4, 0.3), (0.65, 0.6)]
def op(url, lv):
    for i in range(4):
        try: return zarr.open_array(url + f"/{lv}", mode="r", zarr_format=2)
        except Exception as e: err = e; time.sleep(5 * (i + 1))
    raise err
def rd(a, sl):
    for i in range(4):
        try: return a[sl]
        except Exception as e: err = e; time.sleep(5 * (i + 1))
    raise err
out = {}
for s, kind in STORES.items():
    url = B + s
    za = json.loads(zarr.open_group(url, mode="r", zarr_format=2).attrs.asdict().__repr__().replace("'", '"')) if False else zarr.open_group(url, mode="r", zarr_format=2).attrs.asdict()
    ms = za["multiscales"][0]["datasets"]; sc1 = [t["scale"] for t in ms[1]["coordinateTransformations"] if t["type"] == "scale"][0]
    a0, a1 = op(url, 0), op(url, 1)
    rec = {"kind": kind, "L0_shape": list(a0.shape), "L1_shape": list(a1.shape), "L1_chunks": list(a1.chunks), "L1_declared_scale": sc1, "checks": []}
    cy, cx = a1.chunks[1:]
    for fy, fx in FRACS:
        if len(rec["checks"]) == 2: break
        iy, ix = int(fy * a1.shape[1]) // cy, int(fx * a1.shape[2]) // cx
        y0, x0 = iy * cy, ix * cx; y1, x1 = min(a1.shape[1], y0 + cy), min(a1.shape[2], x0 + cx)
        h = min(y1 - y0, (a0.shape[1] - 2 * y0) // 2); w = min(x1 - x0, (a0.shape[2] - 2 * x0) // 2)
        c = rd(a1, (slice(None), slice(y0, y0 + h), slice(x0, x0 + w))).astype(np.int64)
        p = rd(a0, (slice(None), slice(2 * y0, 2 * y0 + 2 * h), slice(2 * x0, 2 * x0 + 2 * w))).astype(np.int64)
        if c.std() == 0 or p.std() == 0: continue
        n = c.shape[0]; r = {"chunk": [iy, ix], "voxels": int(c.size)}
        if kind == "strided":
            for oy in (0, 1):
                for ox in (0, 1):
                    d = np.abs(p[0:2 * n:2, oy::2, ox::2][:n] - c); r[f"stride_z2_y{oy}x{ox}"] = [int((d > 0).sum()), int(d.max())]
        else:
            S = p[:n].reshape(n, h, 2, w, 2).sum(axis=(2, 4)); d = np.abs((S + 2) // 4 - c)
            r["halfup_first_planes"] = [int((d > 0).sum()), int(d.max())]
            M = p.reshape(p.shape[0], h, 2, w, 2).mean(axis=(2, 4))
            r["min_r_k_vs_k"] = float(min(np.corrcoef(c[k].ravel(), M[k].ravel())[0, 1] for k in range(n)))
            r["median_r_k_vs_2k"] = float(np.median([np.corrcoef(c[k].ravel(), M[2 * k].ravel())[0, 1] for k in range(n) if 2 * k < p.shape[0]]))
        rec["checks"].append(r)
    out[s] = rec; print(s, json.dumps(rec), flush=True)
json.dump(out, open("verify_zarr.json", "w"), indent=1)
