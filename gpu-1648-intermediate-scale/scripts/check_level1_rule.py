"""Step 0a: what is the producer's level 1 of the PHerc0841 bucket renders, in terms of level 0?
Fetches the level-0 and level-1 chunks of 3 planned level-1 cells per segment (first, middle and last in plan order).
For each level-1 plane k it finds the best-matching level-0 plane j (Pearson r of the 2x2 in-plane mean), then tests
exact reconstruction rules."""
import json, time, urllib.request
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
plan = json.load(open(ROOT.parent / "label-free-selector" / "meta" / "heldout-plan.json"))
def get(u):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "l1check"}), timeout=120) as r: return r.read()
        except Exception: time.sleep(2 * (i + 1))
    raise RuntimeError(u)
out = {}
for seg in ["pherc0841-w00", "pherc0841-ag144", "pherc0841-ag174"]:
    P = plan[seg]; b1 = P["render_level1"]; b0 = b1[:-1] + "0"; cells = P["cells"]; res = []
    for cy, cx in [cells[0], cells[len(cells) // 2], cells[-1]]:
        l1 = np.frombuffer(get(f"{b1}/0.{cy}.{cx}"), np.uint8).reshape(33, 128, 128).astype(np.int64)
        l0 = np.zeros((65, 256, 256), np.int64)
        for dy in (0, 1):
            for dx in (0, 1):
                l0[:, dy*128:(dy+1)*128, dx*128:(dx+1)*128] = np.frombuffer(get(f"{b0}/0.{2*cy+dy}.{2*cx+dx}"), np.uint8).reshape(65, 128, 128)
        s4 = l0.reshape(65, 128, 2, 128, 2).sum(axis=(2, 4))  # in-plane 2x2 sums per level-0 plane
        best = []
        for k in range(33):
            r = [np.corrcoef(s4[j].ravel(), l1[k].ravel())[0, 1] if l1[k].std() > 0 and s4[j].std() > 0 else -2 for j in range(65)]
            best.append(int(np.argmax(r)))
        rules = {}
        for name, fn in {"floor": lambda s: s // 4, "half_up": lambda s: (s + 2) // 4, "ceil": lambda s: (s + 3) // 4,
                         "half_even": lambda s: np.rint(s / 4).astype(np.int64)}.items():
            d = np.abs(fn(s4[:33]) - l1); rules[name] = {"max_abs": int(d.max()), "n_diff": int((d > 0).sum())}
        res.append({"cell": [cy, cx], "best_l0_plane_for_each_l1_plane": best, "inplane_2x2_planes_0_32": rules, "voxels": int(l1.size)})
        print(seg, cy, cx, "identity_map" if best == list(range(33)) else best, json.dumps(rules), flush=True)
    out[seg] = res
json.dump(out, open(ROOT / "results" / "step0a-level1-rule.json", "w"), indent=1)
