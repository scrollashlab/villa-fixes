# Independent re-check: numpy/scikit-image/PIL only; does not import run.py, textscore2, cv2 or scipy.ndimage.
import json, hashlib, numpy as np, tifffile, zarr
from PIL import Image
from skimage.measure import label
W = r"C:\vc-gpu\data-do-not-redistribute\work"
def resize_linear(a, H, Wd):  # half-pixel-centre bilinear with edge clamp
    h, w = a.shape
    ys = np.clip((np.arange(H) + 0.5) * h / H - 0.5, 0, h - 1); xs = np.clip((np.arange(Wd) + 0.5) * w / Wd - 0.5, 0, w - 1)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int); y1 = np.minimum(y0 + 1, h - 1); x1 = np.minimum(x0 + 1, w - 1)
    fy = (ys - y0)[:, None]; fx = (xs - x0)[None, :]
    a = a.astype(np.float64)
    return (a[y0][:, x0] * (1 - fy) * (1 - fx) + a[y0][:, x1] * (1 - fy) * fx + a[y1][:, x0] * fy * (1 - fx) + a[y1][:, x1] * fy * fx)
def screen(pf, pr, ct):
    valid = (ct > 0) & (pf > 0)
    if not valid.any(): return 0.0
    thr = np.percentile(ct[valid], 15)
    m = valid & (pf >= 180) & (pr <= 110) & (ct >= thr)
    lab = label(m, connectivity=1); sizes = np.bincount(lab.ravel()); sizes[0] = 0
    ok = (sizes >= 200) & (sizes <= 20000); ok[0] = False
    return round(float(ok[lab].sum() / valid.sum()), 5)
def load(od, m, d, shape):
    if m == "m3":
        im = np.array(Image.open(od + ("\\m3.png" if d == "f" else "\\m3_reverse.png")))
        im = im[..., 0] if im.ndim == 3 else im
        return resize_linear(im.astype(np.float32), *shape).astype(np.float32) / 255.0
    a = tifffile.imread(od + ("\\%s.tif" % m if d == "f" else "\\%s_reverse.tif" % m)).astype(np.float32)
    return a / 255.0 if a.max() > 1.5 else a
rows = [json.loads(l) for l in open(r"C:\vc-gpu\exp\results\scores.jsonl")]
maxdiff = 0.0; hashbad = 0; out = []
for r in rows:
    it = r["item"]
    for arm in "AB":
        od = W + "\\%s\\%s" % (it, arm); z = W + "\\%s\\%s" % (it, "sv.zarr" if arm == "A" else "svB.zarr")
        v = zarr.open_array(z + "\\0", mode="r"); ct = np.asarray(v[v.shape[0] // 2])
        for name, h in r[arm]["sha256"].items():
            if name.startswith("E_") or name.startswith("m"):
                hh = hashlib.sha256(open(od + "\\" + name, "rb").read()).hexdigest()
                if hh != h: hashbad += 1; print("HASH MISMATCH", it, arm, name)
        maps = {m: {d: load(od, m, d, ct.shape) for d in "fr"} for m in ["m1", "m2", "m3", "m4", "m5"]}
        E = {d: sum(maps[m][d] for m in maps) / 5.0 for d in "fr"}
        def s1(f, rr): return screen(np.round(f * 255), np.round(rr * 255), ct)
        mine = {"E": (s1(E["f"], E["r"]), s1(E["r"], E["f"]))}
        for m in maps: mine[m] = (s1(maps[m]["f"], maps[m]["r"]), s1(maps[m]["r"], maps[m]["f"]))
        rec = r[arm]
        theirs = {"E": (rec["E"]["s1_fwd"], rec["E"]["s1_rev"])}; theirs.update({m: (rec["models"][m]["s1_fwd"], rec["models"][m]["s1_rev"]) for m in maps})
        for k in mine:
            for a_, b_ in zip(mine[k], theirs[k]): maxdiff = max(maxdiff, abs(a_ - b_))
        out.append({"item": it, "arm": arm, "recheck": mine, "original": theirs})
        print(it, arm, "E", mine["E"], theirs["E"], flush=True)
json.dump({"max_abs_diff": maxdiff, "hash_mismatches": hashbad, "rows": out}, open(r"C:\vc-gpu\exp\results\recheck.json", "w"), indent=1)
print("MAXDIFF", maxdiff, "HASHBAD", hashbad)
