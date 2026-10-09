import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts")); import align as A
import numpy as np
def test_recovers_flip_and_shift():
    rng = np.random.default_rng(0); H, W = 300, 200
    R = np.zeros((H, W), bool); R[60:240, 40:160] = True
    ink = R & (rng.random((H, W)) < 0.3)
    ink = np.asarray(np.convolve(ink.ravel().astype(float), np.ones(3), "same") > 0).reshape(H, W) & R
    # prediction = labels flipped LR then shifted by t=(+7,-11) (label p -> pred at p+t), plus noise
    Lo = A.orient(ink, "flip-LR").astype(float); Q = np.zeros((H, W)); dy, dx = 7, -11
    Q[max(0,dy):H+min(0,dy), max(0,dx):W+min(0,dx)] = Lo[max(0,-dy):H-max(0,dy), max(0,-dx):W-max(0,dx)]
    Q = np.clip(Q * 600 + rng.random((H, W)) * 400, 0, 1020).astype(np.uint16)
    half = np.broadcast_to(np.arange(W)[None] < 100, (H, W))
    T = A.select(Q, R, ink, half, s=20)
    assert (T["orientation"], T["dy"], T["dx"]) == ("flip-LR", 7, -11), T
    blk = (np.arange(H)[:, None] // 16) * 13 + np.arange(W)[None] // 16
    ev = A.evaluate(Q, R, ink, ~half, blk, T)
    assert ev["auc_T"] > 0.9 and abs(ev["auc_identity"] - 0.5) < 0.1 and ev["ci95"][0] > 0
def test_xcorr_matches_bruteforce():
    rng = np.random.default_rng(1); L = rng.random((30, 20)) < 0.2; Q = rng.integers(0, 1021, (30, 20)).astype(np.uint16)
    import scipy.fft as f; s = 5; shp = (f.next_fast_len(36), f.next_fast_len(26)); FQ = f.rfft2(Q.astype(float), s=shp)
    w = A.xcorr_window(L, FQ, shp, s); c = A.count_window(L, s)
    for dy in range(-s, s + 1):
        for dx in range(-s, s + 1):
            tot = cnt = 0
            for y, x in zip(*np.nonzero(L)):
                if 0 <= y + dy < 30 and 0 <= x + dx < 20: tot += int(Q[y + dy, x + dx]); cnt += 1
            assert abs(w[dy + s, dx + s] - tot) < 1e-6 and c[dy + s, dx + s] == cnt
def test_auc_hist_brute():
    rng = np.random.default_rng(2); v = rng.integers(0, 1021, 2000); y = rng.random(2000) < 0.4
    p, q = v[y], v[~y]; brute = ((p[:, None] > q[None]).sum() + 0.5 * (p[:, None] == q[None]).sum()) / (len(p) * len(q))
    assert abs(A.auc_hist(np.bincount(p, minlength=1021), np.bincount(q, minlength=1021)) - brute) < 1e-12
def test_pool():
    m = np.ones((3, 3), bool); assert A.pool_count(m).tolist() == [[4, 2], [2, 1]]
