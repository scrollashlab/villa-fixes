"""Reconstruct #1727's reproduced / not-reproduced classes from ge-al's public audit/pairs.json (selection only).
A volume counts as reproduced if some listed mesh variant matches both canvas axes at one isotropic render scale.
Usage: python reconstruct_geal_classes.py PATH/TO/pairs.json OUT_JSON"""
import json, math, sys, collections
import numpy as np
rows = json.load(open(sys.argv[1]))
def lr(x): return max(1, int(math.floor(x + 0.5)))
def iso_ok(h, w, sc, H, W):
    s32 = float(np.float32(sc))
    lo = max((H - 0.5) * s32 / h, (W - 0.5) * s32 / w); hi = min((H + 0.5) * s32 / h, (W + 0.5) * s32 / w)
    if lo > hi: return None
    s = (lo + hi) / 2
    return s if lr(h * s / s32) == H and lr(w * s / s32) == W else None
sv = {}
for r in rows:
    k = (r["seg"], r["sv"]); h, w = r["stored"]; H, W = r["ref"]
    sv.setdefault(k, []).append(iso_ok(h, w, r["scale"], H, W))
cls = {k: any(x is not None for x in v) for k, v in sv.items()}
print(collections.Counter(cls.values()))
json.dump([{"seg": k[0], "sv": k[1], "geal_reproduced": v} for k, v in sorted(cls.items())], open(sys.argv[2], "w"), indent=0)
