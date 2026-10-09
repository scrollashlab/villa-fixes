import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts")); import audit as A
import numpy as np
rng = np.random.default_rng(0)
P = rng.integers(0, 256, (65, 64, 64)).astype(np.int64)
S = P.reshape(65, 32, 2, 32, 2).sum(axis=(2, 4))
def test_trunc_detected():
    c = (S[:33] + 2) // 4
    res, n = A.rules(c, P); assert A.classify(res) == ("TRUNC", "half_up") and n == 33 * 32 * 32
def test_pool_detected():
    pool = [S[2*k] + S[2*k+1] for k in range(32)] + [S[64]]
    c = np.stack([(p + 4) // 8 for p in pool[:32]] + [(pool[32] + 2) // 4])
    res, _ = A.rules(c, P); assert A.classify(res) == ("POOL", "half_up")
def test_ctr_detected():
    c = S[16:49] // 4
    res, _ = A.rules(c, P); assert A.classify(res) == ("CTR", "floor")
def test_inplane_all_and_other():
    res, _ = A.rules(S // 4, P); assert A.classify(res)[0] == "INPLANE_ALL"
    res, _ = A.rules(rng.integers(0, 256, (33, 32, 32)), P); assert A.classify(res) == ("OTHER", None)
def test_odd_edges():
    c = (S[:33, :31, :30] + 2) // 4
    res, n = A.rules(c, P[:, :63, :61]); assert A.classify(res) == ("TRUNC", "half_up") and n == 33 * 31 * 30
