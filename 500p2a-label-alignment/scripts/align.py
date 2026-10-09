"""500p2a label-alignment test, exactly as pre-registered (docs/preregistration.md, sha256 3910d3f3...a1c5).
python -B scripts/align.py            -> results/metrics.json, results/summary.md (scored once)"""
import json, sys
from pathlib import Path
import numpy as np
import scipy.fft as sfft

ORIENT = ["identity", "flip-LR", "flip-UD", "rot180"]
S = 256; NEAR = 8; B = 2000; SEED = 20261008; BLK = 64

def orient(a, o):
    return {"identity": a, "flip-LR": a[:, ::-1], "flip-UD": a[::-1, :], "rot180": a[::-1, ::-1]}[o]

def pool_count(mask0):  # level-0 bool -> G count of true pixels in each 2x2 (zero-padded to even)
    H, W = mask0.shape; m = np.zeros((H + H % 2, W + W % 2), np.uint8); m[:H, :W] = mask0
    return m.reshape(m.shape[0] // 2, 2, m.shape[1] // 2, 2).sum(axis=(1, 3), dtype=np.uint8)

def pool_sum(a0):
    H, W = a0.shape; m = np.zeros((H + H % 2, W + W % 2), np.uint16); m[:H, :W] = a0
    return m.reshape(m.shape[0] // 2, 2, m.shape[1] // 2, 2).sum(axis=(1, 3), dtype=np.uint16)

def xcorr_window(L, FQ, shape_fft, s):
    """S(t) = sum_p L(p) Q(p+t) for t in [-s,s]^2, from FQ = rfft2(Q padded). Returns (2s+1, 2s+1) indexed [dy+s, dx+s]."""
    FL = sfft.rfft2(L.astype(np.float64), s=shape_fft, workers=-1)
    FL = np.conj(FL, out=FL); FL *= FQ
    c = sfft.irfft2(FL, s=shape_fft, workers=-1); del FL
    idx_y = np.arange(-s, s + 1) % shape_fft[0]; idx_x = np.arange(-s, s + 1) % shape_fft[1]
    out = c[np.ix_(idx_y, idx_x)].copy(); del c
    return out

def count_window(L, s):
    """C(t) = sum of L(p) over p with p+t inside the grid, for t in [-s,s]^2 (2-D prefix sums)."""
    H, W = L.shape; I = np.zeros((H + 1, W + 1), np.float64); I[1:, 1:] = L.astype(np.float64).cumsum(0).cumsum(1)
    d = np.arange(-s, s + 1)
    y0 = np.maximum(0, -d); y1 = np.minimum(H, H - d); x0 = np.maximum(0, -d); x1 = np.minimum(W, W - d)
    return I[y1][:, x1] - I[y0][:, x1] - I[y1][:, x0] + I[y0][:, x0]

def select(Q, R, ink, A, s=S):
    """Argmax over orientation and shift of the separation on half A. Q: G prediction (2x2 sums)."""
    H, W = Q.shape; shape_fft = (sfft.next_fast_len(H + s + 1), sfft.next_fast_len(W + s + 1))
    FQ = sfft.rfft2(Q.astype(np.float64), s=shape_fft, workers=-1)
    best = None; table = {}
    d = np.arange(-s, s + 1); dist = np.abs(d)[:, None] + np.abs(d)[None, :]
    for o in ORIENT:
        Li = orient(ink & A & R, o); Lr = orient(R & A, o)
        Si = xcorr_window(Li, FQ, shape_fft, s); Sr = xcorr_window(Lr, FQ, shape_fft, s)
        Ci = count_window(Li, s); Cr = count_window(Lr, s)
        with np.errstate(invalid="ignore", divide="ignore"):
            sep = Si / Ci - (Sr - Si) / (Cr - Ci)
        sep = np.where((Ci > 0) & (Cr - Ci > 0), sep, -np.inf)
        m = sep.max(); cand = np.argwhere(sep == m); k = cand[np.argmin(dist[cand[:, 0], cand[:, 1]])]
        table[o] = {"best_sep": float(m), "dy": int(k[0] - s), "dx": int(k[1] - s), "sep_at_zero_shift": float(sep[s, s])}
        if best is None or m > best[0]: best = (m, o, int(k[0] - s), int(k[1] - s))
    del FQ
    return {"orientation": best[1], "dy": best[2], "dx": best[3], "sep": float(best[0]), "per_orientation": table}

def paired(Q, R, ink, half, blk, o, dy, dx):
    """For label pixels in `half` (label coords), transformed by o and compared with Q at p+t: values, ink, block ids."""
    Ro, Io, Ho, Bo = (orient(x, o) for x in (R, ink, half, blk))
    H, W = Q.shape
    y0, y1 = max(0, -dy), min(H, H - dy); x0, x1 = max(0, -dx), min(W, W - dx)
    sel = (Ro & Ho)[y0:y1, x0:x1]
    v = Q[y0 + dy:y1 + dy, x0 + dx:x1 + dx][sel].astype(np.int64)
    return v, Io[y0:y1, x0:x1][sel], Bo[y0:y1, x0:x1][sel]

def auc_hist(pos, neg):
    pos = np.asarray(pos, np.float64); neg = np.asarray(neg, np.float64)
    below = np.cumsum(neg) - neg
    return float((pos * (below + 0.5 * neg)).sum() / (pos.sum() * neg.sum()))

def block_hists(v, lab, b, ublocks, nbins=1021):
    bi = np.searchsorted(ublocks, b); nb = len(ublocks); key = bi * nbins + v
    pos = np.bincount(key[lab], minlength=nb * nbins).reshape(nb, nbins)
    neg = np.bincount(key[~lab], minlength=nb * nbins).reshape(nb, nbins)
    return pos, neg

def auc_rows(Wt, pos, neg):  # Wt: (B, nb) block weights -> AUC per replicate
    P = Wt @ pos; N = Wt @ neg; below = np.cumsum(N, 1) - N
    return (P * (below + 0.5 * N)).sum(1) / (P.sum(1) * N.sum(1))

def evaluate(Q, R, ink, Bhalf, blk, T, rng_seed=SEED):
    vt, lt, bt = paired(Q, R, ink, Bhalf, blk, T["orientation"], T["dy"], T["dx"])
    vi, li, bi_ = paired(Q, R, ink, Bhalf, blk, "identity", 0, 0)
    ub = np.union1d(np.unique(bt), np.unique(bi_))
    pt, nt = block_hists(vt, lt, bt, ub); pi, ni = block_hists(vi, li, bi_, ub)
    a_t = auc_hist(pt.sum(0), nt.sum(0)); a_i = auc_hist(pi.sum(0), ni.sum(0))
    rng = np.random.default_rng(rng_seed); nb = len(ub)
    Wt = np.zeros((B, nb)); draws = rng.integers(0, nb, size=(B, nb))
    for r in range(B): Wt[r] = np.bincount(draws[r], minlength=nb)
    d = auc_rows(Wt, pt.astype(np.float64), nt.astype(np.float64)) - auc_rows(Wt, pi.astype(np.float64), ni.astype(np.float64))
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"auc_T": a_t, "auc_identity": a_i, "delta": a_t - a_i, "ci95": [float(lo), float(hi)], "n_pairs_T": int(len(vt)),
            "n_pairs_identity": int(len(vi)), "n_blocks": int(nb)}

def verdict_for(T, ev):
    near = T["orientation"] == "identity" and max(abs(T["dy"]), abs(T["dx"])) <= NEAR
    if (not near) and ev["delta"] >= 0.10 and ev["ci95"][0] > 0 and ev["auc_T"] >= 0.65: return "MISREGISTERED"
    if ev["auc_identity"] >= 0.65: return "ALIGNED-READ"
    return "ALIGNED-UNREAD"

def load_labels(D):
    import tifffile
    R = pool_count(tifffile.imread(D / "labels" / "500p2a_supervision_mask.tif") > 0) == 4
    ink = pool_count(tifffile.imread(D / "labels" / "500p2a_inklabels.tif") > 0) >= 2
    return R, ink

def main():
    import tifffile
    root = Path(__file__).resolve().parents[1]; D = root / "data-do-not-redistribute"
    L = root.parent / "label-free-selector" / "data-do-not-redistribute"
    R, ink = load_labels(L); ink &= R; H, W = R.shape
    cols = np.nonzero(R)[1]; med = int(np.median(cols)); colmap = np.arange(W)[None, :]
    A = np.broadcast_to(colmap < med, R.shape); Bh = np.broadcast_to(colmap >= med, R.shape)
    blk = (np.arange(H)[:, None] // BLK) * ((W + BLK - 1) // BLK) + (np.arange(W)[None, :] // BLK)
    out = {"grid": [H, W], "R_px": int(R.sum()), "ink_px": int(ink.sum()), "median_col": med, "preds": {}}
    names = {"P1": "500p2a_canonical_030726_forward_070326.tif", "P2": "ps48_640_640_smooth_0.1_500p2a_ckpt_130000_forward_210326.tif",
             "P3": "ps512_ema_0.9995_500p2a_ckpt_080000_forward_230326.tif", "P4": "ps512_ema_0.9995_500p2a_ckpt_080000_reverse_230326.tif"}
    for k, f in names.items():
        Q = pool_sum(tifffile.imread(D / "preds" / f)); assert Q.shape == (H, W)
        T = select(Q, R, ink, A); ev = evaluate(Q, R, ink, Bh, blk, T)
        out["preds"][k] = {"file": f, "T_star": T, "eval_half_B": ev, "verdict": verdict_for(T, ev)}
        print(k, json.dumps({kk: T[kk] for kk in ("orientation", "dy", "dx", "sep")}), json.dumps(ev), out["preds"][k]["verdict"], flush=True)
        del Q
    p1 = out["preds"]["P1"]; out["verdict"] = p1["verdict"]
    out["replication"] = {k: {"same_verdict": v["verdict"] == p1["verdict"],
                              "T_within_8px_same_orientation": v["T_star"]["orientation"] == p1["T_star"]["orientation"] and
                              max(abs(v["T_star"]["dy"] - p1["T_star"]["dy"]), abs(v["T_star"]["dx"] - p1["T_star"]["dx"])) <= NEAR}
                          for k, v in out["preds"].items() if k != "P1"}
    # exploratory: IR photo (255 - luminance) over all of R
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    img = Image.open(D / "PHerc.500_ACass.28M1050IR_017_aligned.png"); Wi, Hi = img.size
    lum = np.empty((Hi, Wi), np.uint8)
    for y in range(0, Hi, 1024):  # row bands keep memory low
        band = np.asarray(img.crop((0, y, Wi, min(Hi, y + 1024))).convert("RGBA"))[..., :3].astype(np.float32)
        lum[y:y + band.shape[0]] = np.rint(0.299 * band[..., 0] + 0.587 * band[..., 1] + 0.114 * band[..., 2]).astype(np.uint8)
    del img
    Qir = pool_sum(255 - lum); del lum
    allR = np.ones_like(R)
    ex = {}
    for lbl, T in (("identity", {"orientation": "identity", "dy": 0, "dx": 0}), ("T_star_P1", p1["T_star"])):
        v, lab, _ = paired(Qir, R, ink, allR, blk, T["orientation"], T["dy"], T["dx"])
        ex[lbl] = auc_hist(np.bincount(v[lab], minlength=1021), np.bincount(v[~lab], minlength=1021))
    out["exploratory_IR_auc_all_R"] = ex; print("IR", ex)
    out["prereg_sha256"] = (root / "docs" / "preregistration.sha256").read_text().split()[0]
    (root / "results").mkdir(exist_ok=True); json.dump(out, open(root / "results" / "metrics.json", "w"), indent=1)

if __name__ == "__main__":
    main()
