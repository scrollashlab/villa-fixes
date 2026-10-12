# Independent S2 re-check: numpy/scipy/scikit-image only; no cv2, no rowscore.py import.
import json, numpy as np, tifffile, zarr
from scipy.ndimage import binary_erosion
from skimage.measure import label, regionprops
W = r"C:\vc-gpu\data-do-not-redistribute\work"; UM = 8.64; k = 4
def area_weights(n_in, n_out):
    s = n_in / n_out; M = np.zeros((n_out, n_in))
    for i in range(n_out):
        a, b = i * s, (i + 1) * s
        for j in range(int(np.floor(a)), min(int(np.ceil(b)), n_in)):
            M[i, j] = max(0.0, min(b, j + 1) - max(a, j))
    return M / s
def s2(a, mid):
    a = a.astype(np.float32)
    if a.max() > 1.5: a = a / 255.0
    v = np.clip((a - 0.25) / 0.5, 0, 1); valid = mid > 0
    H, Wd = v.shape[0] // k, v.shape[1] // k
    ds = (area_weights(v.shape[0], H) @ v.astype(np.float64) @ area_weights(v.shape[1], Wd).T).astype(np.float32)
    yi = np.minimum((np.arange(H) * v.shape[0] / H).astype(int), v.shape[0] - 1); xi = np.minimum((np.arange(Wd) * v.shape[1] / Wd).astype(int), v.shape[1] - 1)
    vm = valid[yi][:, xi]
    vm = binary_erosion(vm, np.ones((31, 31), bool), border_value=1)
    lab = label(vm, connectivity=2); props = regionprops(lab)
    if len(props) > 1 or len(props) == 1:
        big = max(props, key=lambda p: (p.area, -p.label)); y0, x0, y1, x1 = big.bbox
        vm = (lab == big.label)[y0:y1, x0:x1]; ds = ds[y0:y1, x0:x1]
    if vm.sum() < 5000: return None
    x = ds.copy(); x[~vm] = ds[vm].mean(); x = x - x.mean()
    h, w = x.shape; P = np.abs(np.fft.fftshift(np.fft.fft2(x * np.outer(np.hanning(h), np.hanning(w))))) ** 2
    FY, FX = np.meshgrid(np.fft.fftshift(np.fft.fftfreq(h)), np.fft.fftshift(np.fft.fftfreq(w)), indexing="ij"); fr = np.hypot(FY, FX)
    pm = k * UM * 1e-3; band = (fr > pm / 8.0) & (fr < pm / 2.5)
    bp = P[band]; iy, ix = np.unravel_index(np.argmax(np.where(band, P, 0)), P.shape)
    return {"score": round(float(bp.max() / np.median(bp)), 1), "period_mm": round(float(pm / fr[iy, ix]), 2), "angle_deg": round(float(np.degrees(np.arctan2(FY[iy, ix], FX[iy, ix]))), 1),
            "mean_ink": round(float(v[valid].mean()), 4), "p99": round(float(np.percentile(v[valid], 99)), 3), "frac_gt_0.5": round(float((v[valid] > 0.5).mean()), 4), "valid_px": int(valid.sum())}
rows = [json.loads(l) for l in open(r"C:\vc-gpu\exp\results\scores.jsonl")]; out = []; mism = 0
for r in rows:
    for arm in "AB":
        e = r[arm]["E"]; z = W + "\\%s\\%s\\0" % (r["item"], "sv.zarr" if arm == "A" else "svB.zarr")
        vv = zarr.open_array(z, mode="r"); mid = np.asarray(vv[vv.shape[0] // 2])
        mine = s2(tifffile.imread(W + "\\%s\\%s\\E_%s.tif" % (r["item"], arm, e["best_direction"])), mid)
        diffs = {kk: (mine[kk], e["S2"][kk]) for kk in mine if mine[kk] != e["S2"][kk]}
        mism += len(diffs); out.append({"item": r["item"], "arm": arm, "recheck": mine, "original": e["S2"], "diffs": diffs})
        print(r["item"], arm, mine["score"], e["S2"]["score"], diffs, flush=True)
json.dump({"field_mismatches": mism, "rows": out}, open(r"C:\vc-gpu\exp\results\recheck_s2.json", "w"), indent=1); print("S2_MISMATCHES", mism)
