"""Census of the render pyramids under ink/ in the scrollprize/datasets HF bucket (docs/preregistration.md).
For each store and child level L in (1, 2): fetch up to 2 non-constant child chunks (fixed probe order) plus the
parent-level voxels under them, and test which exact rule rebuilds the child from the parent. Metadata only + metrics."""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path
import numpy as np, numcodecs
ROOT = Path(__file__).resolve().parents[1]
B = "https://huggingface.co/buckets/scrollprize/datasets/resolve/"
PROBES = [(0.5, 0.5), (0.25, 0.25), (0.75, 0.75), (0.25, 0.75), (0.75, 0.25), (0.5, 0.25), (0.5, 0.75), (0.25, 0.5), (0.75, 0.5)]
ROUND = ["floor", "half_up", "half_even", "ceil"]
NBYTES = [0]

def fetch(path, ok404=False):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(B + path, headers={"User-Agent": "pyramid-audit"}), timeout=120) as r:
                b = r.read(); NBYTES[0] += len(b); return b
        except urllib.error.HTTPError as e:
            if e.code == 404 and ok404: return None
            if e.code == 404: raise
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    raise RuntimeError(path)

def jget(path):
    b = fetch(path, ok404=True); return None if b is None else json.loads(b)

def divide(s, d, mode):
    if mode == "floor": return s // d
    if mode == "half_up": return (s + d // 2) // d
    if mode == "half_even": return np.rint(s / d).astype(np.int64)
    return -((-s) // d)

class Arr:
    def __init__(self, store, level):
        self.base = f"{store}/{level}"; m = jget(self.base + "/.zarray")
        if m is None: raise FileNotFoundError(self.base)
        assert m.get("filters") in (None, []), "filters not supported"
        assert m.get("order", "C") == "C"
        self.meta = m; self.shape = tuple(m["shape"]); self.chunks = tuple(m["chunks"]); self.dtype = np.dtype(m["dtype"])
        self.sep = m.get("dimension_separator", "."); self.fill = m.get("fill_value") or 0
        self.codec = None if m.get("compressor") is None else numcodecs.get_codec(m["compressor"])
    def chunk(self, idx):
        b = fetch(self.base + "/" + self.sep.join(str(i) for i in idx), ok404=True)
        if b is None: return np.full(self.chunks, self.fill, self.dtype)
        if self.codec is not None: b = self.codec.decode(b)
        return np.frombuffer(bytes(b), self.dtype).reshape(self.chunks)
    def read(self, y0, y1, x0, x1):
        nz = self.shape[0]; cz, cy, cx = self.chunks
        out = np.zeros((nz, y1 - y0, x1 - x0), self.dtype)
        for iz in range(0, -(-nz // cz)):
            for iy in range(y0 // cy, -(-y1 // cy)):
                for ix in range(x0 // cx, -(-x1 // cx)):
                    c = self.chunk((iz, iy, ix))
                    zs, ys, xs = iz * cz, iy * cy, ix * cx
                    za, zb = zs, min(nz, zs + cz); ya, yb = max(y0, ys), min(y1, ys + cy); xa, xb = max(x0, xs), min(x1, xs + cx)
                    out[za:zb, ya - y0:yb - y0, xa - x0:xb - x0] = c[:zb - zs, ya - ys:yb - ys, xa - xs:xb - xs]
        return out

def rules(child, parent):
    """child (nzc,h,w), parent (nzp,2h',2w') int64. Returns {rule|rounding: (n_diff, max_abs)} on the overlapping pixels."""
    nzc, nzp = child.shape[0], parent.shape[0]
    h = min(child.shape[1], parent.shape[1] // 2); w = min(child.shape[2], parent.shape[2] // 2)
    c = child[:, :h, :w].astype(np.int64)
    S = parent[:, :2 * h, :2 * w].astype(np.int64).reshape(nzp, h, 2, w, 2).sum(axis=(2, 4))
    cand = {}
    if nzc == nzp: cand["INPLANE_ALL"] = (S, 4)
    if nzc <= nzp:
        cand["TRUNC"] = (S[:nzc], 4)
        off = (nzp - nzc) // 2
        if off > 0: cand["CTR"] = (S[off:off + nzc], 4)
    pool, den = [], []
    for k in range(nzc):
        if 2 * k + 1 < nzp: pool.append(S[2 * k] + S[2 * k + 1]); den.append(8)
        elif 2 * k < nzp: pool.append(S[2 * k]); den.append(4)
        else: pool = None; break
    out = {}
    for name, (A, d) in cand.items():
        for r in ROUND:
            dd = np.abs(divide(A, d, r) - c); out[f"{name}|{r}"] = (int((dd > 0).sum()), int(dd.max()))
    if pool is not None:
        for r in ROUND:
            P = np.stack([divide(p, d, r) for p, d in zip(pool, den)]); dd = np.abs(P - c)
            out[f"POOL|{r}"] = (int((dd > 0).sum()), int(dd.max()))
    return out, int(c.size)

ORDER = ["INPLANE_ALL", "TRUNC", "POOL", "CTR"]
def classify(agg):
    for rule in ORDER:
        for r in ROUND:
            k = f"{rule}|{r}"
            if k in agg and agg[k][0] == 0: return rule, r
    return "OTHER", None

def audit_level(store, L, ms):
    ch, pa = Arr(store, str(L)), Arr(store, str(L - 1))
    nzc, Hc, Wc = ch.shape; cz, cy, cx = ch.chunks
    cells, agg, nvox = [], {}, 0
    for fy, fx in PROBES:
        if len(cells) == 2: break
        iy, ix = min(int(fy * Hc) // cy, (Hc - 1) // cy), min(int(fx * Wc) // cx, (Wc - 1) // cx)
        y0, y1, x0, x1 = iy * cy, min(Hc, (iy + 1) * cy), ix * cx, min(Wc, (ix + 1) * cx)
        c = ch.read(y0, y1, x0, x1)
        if c.std() == 0: continue
        p = pa.read(2 * y0, min(pa.shape[1], 2 * y1), 2 * x0, min(pa.shape[2], 2 * x1))
        if p.std() == 0: continue
        res, n = rules(c, p); nvox += n; cells.append([iy, ix])
        for k, (nd, mx) in res.items():
            a = agg.get(k, (0, 0)); agg[k] = (a[0] + nd, max(a[1], mx))
    decl = None
    for d in ms.get("datasets", []):
        if str(d.get("path")) == str(L):
            for t in d.get("coordinateTransformations", []):
                if t.get("type") == "scale": decl = t.get("scale")
    rule, rnd = classify(agg) if cells else ("NO_DATA", None)
    return {"child_shape": list(ch.shape), "parent_shape": list(pa.shape), "child_chunks": list(ch.chunks),
            "declared_scale": decl, "cells": cells, "voxels_compared": nvox, "rule": rule, "rounding": rnd,
            "diffs": {k: list(v) for k, v in agg.items()}}

def main():
    stores = json.load(open(ROOT / "meta" / "stores.json"))["stores"]
    if len(sys.argv) > 1: stores = [s for s in stores if any(a in s for a in sys.argv[1:])]
    out = {}
    for s in stores:
        t = time.time(); za = jget(s + "/.zattrs") or {}; ms = (za.get("multiscales") or [{}])[0]
        rec = {"levels_declared": [str(d.get("path")) for d in ms.get("datasets", [])]}
        for L in (1, 2):
            try: rec[f"L{L}"] = audit_level(s, L, ms)
            except FileNotFoundError as e: rec[f"L{L}"] = {"rule": "ABSENT", "missing": str(e)}
            except Exception as e: rec[f"L{L}"] = {"rule": "ERROR", "error": repr(e)[:200]}
        rec["seconds"] = round(time.time() - t, 1); out[s] = rec
        print(s, rec["L1"].get("rule"), rec["L1"].get("rounding"), rec["L1"].get("child_shape"), rec["L1"].get("declared_scale"),
              "| L2", rec["L2"].get("rule"), rec["L2"].get("declared_scale"), f"{NBYTES[0]/1e6:.0f} MB", flush=True)
        json.dump({"stores": out, "bytes_fetched": NBYTES[0]}, open(ROOT / "results" / "audit.json", "w"), indent=1)

if __name__ == "__main__":
    main()
