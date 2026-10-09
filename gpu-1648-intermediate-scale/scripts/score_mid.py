"""Score the #1648 intermediate-scale study exactly as pre-registered (docs/preregistration.md).
Input: data-do-not-redistribute/pc-results/<seg>.npz (per-64x64-block histograms from pc/run_mid.py reduce).
Output: results/metrics.json, results/summary.md"""
import json
from pathlib import Path
import numpy as np
SEGS = ["pherc0841-w00", "pherc0841-ag144", "pherc0841-ag174"]; CK = ["seed42", "seed43"]; DIRS = ["forward", "reverse"]
B = 2000; SEED = 20261008

def auc_hist(pos, neg):
    pos = np.asarray(pos, np.float64); neg = np.asarray(neg, np.float64); below = np.cumsum(neg) - neg
    return float((pos * (below + 0.5 * neg)).sum() / (pos.sum() * neg.sum()))

def auc_rows(W, pos, neg):
    P = W @ pos; N = W @ neg; below = np.cumsum(N, 1) - N
    return (P * (below + 0.5 * N)).sum(1) / (P.sum(1) * N.sum(1))

def score_seg(z):
    nb = len(z["blocks"]); res = {"n": int(z["n"]), "n_pos": int(z["n_pos"]), "n_blocks": nb, "auc": {}}
    for ck in CK:
        for d in DIRS:
            for arm in ("S9", "S4"):
                p, n = z[f"{ck}|{arm}|{d}|pos"], z[f"{ck}|{arm}|{d}|neg"]
                assert int(p.sum()) == res["n_pos"] and int(p.sum() + n.sum()) == res["n"]
                res["auc"][f"{ck}|{arm}|{d}"] = auc_hist(p.sum(0), n.sum(0))
    mean = {d: float(np.mean([res["auc"][f"{ck}|{arm}|{d}"] for ck in CK for arm in ("S9", "S4")])) for d in DIRS}
    op = "forward" if mean["forward"] >= mean["reverse"] else "reverse"
    res["direction_mean_auc"] = mean; res["operative_direction"] = op
    rng = np.random.default_rng(SEED); draws = rng.integers(0, nb, size=(B, nb))
    W = np.stack([np.bincount(r, minlength=nb) for r in draws]).astype(np.float64)
    res["delta"] = {}
    for d in DIRS:
        for ck in CK:
            p9, n9 = z[f"{ck}|S9|{d}|pos"].astype(np.float64), z[f"{ck}|S9|{d}|neg"].astype(np.float64)
            p4, n4 = z[f"{ck}|S4|{d}|pos"].astype(np.float64), z[f"{ck}|S4|{d}|neg"].astype(np.float64)
            bd = auc_rows(W, p9, n9) - auc_rows(W, p4, n4); lo, hi = np.percentile(bd, [2.5, 97.5])
            res["delta"][f"{ck}|{d}"] = {"auc_S9": res["auc"][f"{ck}|S9|{d}"], "auc_S4": res["auc"][f"{ck}|S4|{d}"],
                                         "delta": res["auc"][f"{ck}|S9|{d}"] - res["auc"][f"{ck}|S4|{d}"], "ci95": [float(lo), float(hi)]}
    return res

def main():
    root = Path(__file__).resolve().parents[1]; D = root / "data-do-not-redistribute" / "pc-results"
    per = {s: score_seg(dict(np.load(D / f"{s}.npz"))) for s in SEGS}
    sup = ref = 0
    for s, r in per.items():
        ds = [r["delta"][f"{ck}|{r['operative_direction']}"] for ck in CK]
        r["supports"] = all(x["delta"] > 0 and x["ci95"][0] > 0 for x in ds); r["refutes"] = all(x["delta"] < 0 and x["ci95"][1] < 0 for x in ds)
        sup += r["supports"]; ref += r["refutes"]
    verdict = "SUPPORTED" if sup >= 2 else ("REFUTED" if ref >= 2 else "INCONCLUSIVE")
    out = {"prereg_sha256": (root / "docs" / "preregistration.sha256").read_text().split()[0], "verdict": verdict,
           "segments_supporting": sup, "segments_refuting": ref, "segments": per}
    (root / "results").mkdir(exist_ok=True); json.dump(out, open(root / "results" / "metrics.json", "w"), indent=1)
    L = ["# #1648 at 4.681 µm vs 9.362 µm (PHerc0841, held out): results", "", f"Pre-registration sha256 `{out['prereg_sha256']}`. **Verdict: {verdict}** "
         f"({sup}/3 segments support, {ref}/3 refute; 2/3 needed).", "",
         "| segment | operative dir | seed | AUC S9 (9.36 µm) | AUC S4 (4.68 µm) | Δ (S9−S4) | 95% CI |", "|---|---|---|---|---|---|---|"]
    for s, r in per.items():
        for ck in CK:
            x = r["delta"][f"{ck}|{r['operative_direction']}"]
            L.append(f"| {s} | {r['operative_direction']} | {ck} | {x['auc_S9']:.4f} | {x['auc_S4']:.4f} | {x['delta']:+.4f} | [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}] |")
    L += ["", "Non-operative direction (reported, not part of the verdict):", "", "| segment | dir | seed | AUC S9 | AUC S4 | Δ | 95% CI |", "|---|---|---|---|---|---|---|"]
    for s, r in per.items():
        d = "reverse" if r["operative_direction"] == "forward" else "forward"
        for ck in CK:
            x = r["delta"][f"{ck}|{d}"]
            L.append(f"| {s} | {d} | {ck} | {x['auc_S9']:.4f} | {x['auc_S4']:.4f} | {x['delta']:+.4f} | [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}] |")
    (root / "results" / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L))

if __name__ == "__main__":
    main()
