"""Score the #1648 held-out matrix exactly as pre-registered (docs/preregistration.md, sealed).

Inputs (local, never published): data-do-not-redistribute/labels/*, data-do-not-redistribute/pc-results/<case>.npz
  npz keys: "<L2|L0>_<seed42|seed43>_<forward|reverse>" on the L2 crop grid
  (L2: uint8 villa output; L0: uint16 sum of the 4x4 L0 outputs under each L2 pixel).
Outputs (metrics only): results/metrics.json, results/summary.md
"""
import json, sys
from pathlib import Path
import numpy as np

NBINS = 4096; BLOCK = 64; B = 2000; SEED = 1648
SEEDS = ("seed42", "seed43"); DIRS = ("forward", "reverse")
CASES = ["pherc0139-w016", "pherc0814-46527", "pherc1667-w029"]

def common_score(arr, level, requant=False):
    """Map an arm's prediction to the shared 4096-bin integer score."""
    a = np.asarray(arr)
    if level == "L2":
        assert a.dtype == np.uint8; return a.astype(np.int64) * 16
    assert a.dtype == np.uint16 and int(a.max(initial=0)) <= 4080
    s = a.astype(np.int64)
    return (s // 16) * 16 if requant else s

def auc_from_hist(pos, neg):
    """Exact Mann-Whitney AUC (ties = 0.5) from score histograms; works on stacked [..., NBINS]."""
    pos = np.asarray(pos, dtype=np.float64); neg = np.asarray(neg, dtype=np.float64)
    below = np.cumsum(neg, axis=-1) - neg
    u = (pos * (below + 0.5 * neg)).sum(axis=-1)
    return u / (pos.sum(axis=-1) * neg.sum(axis=-1))

def ap_from_hist(pos, neg):
    """Average precision with tied scores grouped (step-wise over distinct thresholds, high to low)."""
    p = np.asarray(pos, dtype=np.float64)[::-1]; n = np.asarray(neg, dtype=np.float64)[::-1]
    tp = np.cumsum(p); fp = np.cumsum(n); keep = (p + n) > 0
    prec = np.where(keep, tp / np.maximum(tp + fp, 1), 0.0)
    return float((p * prec).sum() / p.sum())

def block_ids(mask, y0, x0):
    ys, xs = np.nonzero(mask)
    gy, gx = (ys + y0) // BLOCK, (xs + x0) // BLOCK
    keys = gy.astype(np.int64) * 1_000_000 + gx
    uniq, inv = np.unique(keys, return_inverse=True)
    return ys, xs, inv, len(uniq)

def block_hists(score, lab, inv, nb):
    pos = np.zeros((nb, NBINS), np.int64); neg = np.zeros((nb, NBINS), np.int64)
    np.add.at(pos, (inv[lab], score[lab]), 1); np.add.at(neg, (inv[~lab], score[~lab]), 1)
    return pos, neg

def draw_weights(nb, seed=SEED, b=B):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nb, size=(b, nb))
    w = np.zeros((b, nb), np.float64)
    np.add.at(w, (np.repeat(np.arange(b), nb), idx.ravel()), 1)
    return w

def score_case(red, mask, lab, y0, x0, requant=False):
    ys, xs, inv, nb = block_ids(mask, y0, x0)
    labv = lab[ys, xs]
    W = draw_weights(nb)
    out = {"n_blocks": nb, "mask_px": int(mask.sum()), "pos": int(labv.sum()), "neg": int((~labv).sum()), "runs": {}, "deltas": {}}
    H = {}
    for key, arr in red.items():
        lv = key.split("_")[0]
        sc = common_score(arr, lv, requant=requant)[ys, xs]
        pos, neg = block_hists(sc, labv, inv, nb); H[key] = (pos, neg)
        P, N = pos.sum(0), neg.sum(0)
        out["runs"][key] = {"auc": float(auc_from_hist(P, N)), "ap": ap_from_hist(P, N)}
    for seed in SEEDS:
        for d in DIRS:
            k2, k0 = f"L2_{seed}_{d}", f"L0_{seed}_{d}"
            if k2 not in H or k0 not in H: continue
            a2 = auc_from_hist(W @ H[k2][0], W @ H[k2][1]); a0 = auc_from_hist(W @ H[k0][0], W @ H[k0][1])
            delta = out["runs"][k2]["auc"] - out["runs"][k0]["auc"]; bd = a2 - a0
            lo, hi = np.percentile(bd, [2.5, 97.5])
            out["deltas"][f"{seed}_{d}"] = {"auc_L2": out["runs"][k2]["auc"], "auc_L0": out["runs"][k0]["auc"], "delta": float(delta),
                                            "ci_lo": float(lo), "ci_hi": float(hi), "boot_mean": float(bd.mean())}
    means = {d: float(np.mean([out["runs"][f"{lv}_{s}_{d}"]["auc"] for lv in ("L2", "L0") for s in SEEDS])) for d in DIRS
             if all(f"{lv}_{s}_{d}" in out["runs"] for lv in ("L2", "L0") for s in SEEDS)}
    op = None if len(means) < 2 else ("forward" if means["forward"] >= means["reverse"] else "reverse")
    out["direction_mean_auc"] = means; out["operative_direction"] = op
    if op is None:
        out["outcome"] = "unscorable"
    else:
        ds = [out["deltas"][f"{s}_{op}"] for s in SEEDS]
        if all(x["delta"] > 0 and x["ci_lo"] > 0 for x in ds): out["outcome"] = "confirms"
        elif all(x["ci_hi"] < 0 for x in ds): out["outcome"] = "contradicts"
        else: out["outcome"] = "inconclusive"
    return out

def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import zarr
    D = root / "data-do-not-redistribute"
    crops = json.load(open(root / "meta" / "crops.json"))
    res = {"prereg": (root / "docs" / "preregistration.sha256").read_text().split()[0], "B": B, "seed": SEED, "block": BLOCK,
           "rng_note": "numpy default_rng(1648) re-seeded per case; one draw matrix per case shared by all its comparisons",
           "cases": {}, "sensitivity_floor16": {}}
    for case in CASES:
        y0, y1, x0, x1 = crops[case]["crop_l2_yx"]
        mask = zarr.open_array(str(D / "labels" / f"{case}_validation_mask.zarr" / "0"), mode="r", zarr_format=2)[10][y0:y1, x0:x1] > 0
        lab = zarr.open_array(str(D / "labels" / f"{case}_inklabels.zarr" / "0"), mode="r", zarr_format=2)[10][y0:y1, x0:x1] > 0
        npz = D / "pc-results" / f"{case}.npz"
        if not npz.exists():
            res["cases"][case] = {"outcome": "unscorable", "reason": "no results"}; continue
        red = dict(np.load(npz))
        res["cases"][case] = score_case(red, mask, lab, y0, x0)
        s = score_case(red, mask, lab, y0, x0, requant=True)
        res["sensitivity_floor16"][case] = {"outcome": s["outcome"], "operative_direction": s["operative_direction"], "deltas": s["deltas"]}
        print(case, res["cases"][case]["operative_direction"], res["cases"][case]["outcome"], flush=True)
    n_conf = sum(1 for c in res["cases"].values() if c["outcome"] == "confirms")
    res["n_confirm"] = n_conf; res["n_contradict"] = sum(1 for c in res["cases"].values() if c["outcome"] == "contradicts")
    res["verdict"] = "CONFIRM" if n_conf >= 2 else "DOWNGRADE"
    (root / "results").mkdir(exist_ok=True)
    json.dump(res, open(root / "results" / "metrics.json", "w"), indent=1)
    L = ["# #1648 held-out matrix: results", "", f"Pre-registration sha256 `{res['prereg']}`. Verdict: **{res['verdict']}** ({n_conf}/3 segments confirm, {res['n_contradict']} contradict).", "",
         "| case | seed | dir | AUC L2 | AUC L0 | delta (L2-L0) | 95% CI | operative |", "|---|---|---|---|---|---|---|---|"]
    for case, c in res["cases"].items():
        for k, v in c.get("deltas", {}).items():
            s, d = k.split("_")
            L.append(f"| {case} | {s} | {d} | {v['auc_L2']:.4f} | {v['auc_L0']:.4f} | {v['delta']:+.4f} | [{v['ci_lo']:+.4f}, {v['ci_hi']:+.4f}] | {'yes' if d == c['operative_direction'] else ''} |")
    L += ["", "| case | operative direction | mean AUC fwd / rev | outcome |", "|---|---|---|---|"]
    for case, c in res["cases"].items():
        m = c.get("direction_mean_auc", {})
        L.append(f"| {case} | {c.get('operative_direction')} | {m.get('forward', float('nan')):.4f} / {m.get('reverse', float('nan')):.4f} | {c['outcome']} |")
    L += ["", "Sensitivity (L0 requantized to floor(sum/16)): " + ", ".join(f"{k}: {v['outcome']}" for k, v in res["sensitivity_floor16"].items())]
    L += ["", "Average precision per run is in metrics.json (descriptive only)."]
    (root / "results" / "summary.md").write_text("\n".join(L) + "\n")
    print("VERDICT", res["verdict"], n_conf)

if __name__ == "__main__":
    main()
