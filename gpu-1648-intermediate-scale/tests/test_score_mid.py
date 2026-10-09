import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts")); import score_mid as S
import numpy as np
def test_auc_rows_matches_auc_hist():
    rng = np.random.default_rng(0); pos = rng.integers(0, 50, (7, 1021)).astype(float); neg = rng.integers(0, 50, (7, 1021)).astype(float)
    W = np.ones((1, 7)); assert abs(S.auc_rows(W, pos, neg)[0] - S.auc_hist(pos.sum(0), neg.sum(0))) < 1e-12
def test_score_seg_synthetic():
    rng = np.random.default_rng(1); nb = 40; z = {"blocks": np.arange(nb)}
    lab = rng.random((nb, 500)) < 0.3; n = lab.size; z["n"] = n; z["n_pos"] = int(lab.sum())
    for ck in S.CK:
        for d in S.DIRS:
            for arm, nbins, sig in (("S9", 256, 120 if d == "reverse" else 10), ("S4", 1021, 60 if d == "reverse" else 5)):
                v = np.clip(rng.normal(nbins * 0.3, nbins * 0.1, lab.shape) + lab * sig * nbins / 256, 0, nbins - 1).astype(int)
                z[f"{ck}|{arm}|{d}|pos"] = np.stack([np.bincount(v[b][lab[b]], minlength=nbins) for b in range(nb)])
                z[f"{ck}|{arm}|{d}|neg"] = np.stack([np.bincount(v[b][~lab[b]], minlength=nbins) for b in range(nb)])
    r = S.score_seg(z)
    assert r["operative_direction"] == "reverse"
    x = r["delta"]["seed42|reverse"]; assert x["delta"] > 0 and x["ci95"][0] > 0
