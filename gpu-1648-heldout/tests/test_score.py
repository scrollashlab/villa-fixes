import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import score as S

def brute_auc(s, y):
    p, n = s[y], s[~y]
    gt = (p[:, None] > n[None, :]).sum(); eq = (p[:, None] == n[None, :]).sum()
    return (gt + 0.5 * eq) / (len(p) * len(n))

def brute_ap(s, y):
    ap = 0.0
    for t in np.unique(s)[::-1]:
        sel = s >= t; tp = (sel & y).sum(); fp = (sel & ~y).sum()
        newpos = ((s == t) & y).sum()
        ap += newpos / y.sum() * tp / (tp + fp)
    return ap

def test_hist_auc_matches_brute_with_ties():
    rng = np.random.default_rng(0)
    for _ in range(20):
        s = rng.integers(0, 40, 400) * 16; y = rng.random(400) < 0.3
        P = np.bincount(s[y], minlength=S.NBINS); N = np.bincount(s[~y], minlength=S.NBINS)
        assert abs(S.auc_from_hist(P, N) - brute_auc(s, y)) < 1e-12

def test_hist_ap_matches_brute():
    rng = np.random.default_rng(1)
    for _ in range(10):
        s = rng.integers(0, 30, 300); y = rng.random(300) < 0.4
        P = np.bincount(s[y], minlength=S.NBINS); N = np.bincount(s[~y], minlength=S.NBINS)
        assert abs(S.ap_from_hist(P, N) - brute_ap(s, y)) < 1e-12

def test_common_score_scales():
    l2 = np.array([[0, 1, 255]], np.uint8); l0 = np.array([[0, 17, 4080]], np.uint16)
    assert S.common_score(l2, "L2").tolist() == [[0, 16, 4080]]
    assert S.common_score(l0, "L0").tolist() == [[0, 17, 4080]]
    assert S.common_score(l0, "L0", requant=True).tolist() == [[0, 16, 4080]]

def test_pooling_sum_is_exact_mean_times16():
    rng = np.random.default_rng(2)
    t = rng.integers(0, 256, (8, 12), dtype=np.uint8)
    s = t.reshape(2, 4, 3, 4).astype(np.uint16).sum(axis=(1, 3), dtype=np.uint16)
    assert np.array_equal(s, (t.reshape(2, 4, 3, 4).astype(np.float64).mean(axis=(1, 3)) * 16).astype(np.uint16))

def test_bootstrap_deterministic_and_counts():
    w1 = S.draw_weights(37, b=50); w2 = S.draw_weights(37, b=50)
    assert np.array_equal(w1, w2) and np.all(w1.sum(1) == 37)

def test_blocks_global_alignment():
    m = np.zeros((10, 10), bool); m[0, 0] = m[0, 9] = True
    _, _, inv, nb = S.block_ids(m, 60, 60)  # x 60 and 69 straddle the global 64 boundary
    assert nb == 2

def test_verdict_logic_on_synthetic():
    rng = np.random.default_rng(3)
    H, W = 192, 192
    mask = np.ones((H, W), bool); lab = rng.random((H, W)) < 0.3
    good = np.where(lab, 200, 50).astype(np.uint8) + rng.integers(0, 40, (H, W)).astype(np.uint8)
    noisy = (rng.integers(0, 256, (H, W))).astype(np.uint16) * 16
    red = {}
    for s in S.SEEDS:
        for d in S.DIRS:
            red[f"L2_{s}_{d}"] = good; red[f"L0_{s}_{d}"] = noisy
    out = S.score_case(red, mask, lab, 0, 0)
    assert out["outcome"] == "confirms"
    red2 = {k: (v if k.startswith("L2") else (good.astype(np.uint16) * 16)) for k, v in red.items()}
    red2 = {k: (noisy.astype(np.uint16) // 16).astype(np.uint8) if k.startswith("L2") else v for k, v in red2.items()}
    assert S.score_case(red2, mask, lab, 0, 0)["outcome"] == "contradicts"
