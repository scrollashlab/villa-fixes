"""PHerc0800 ensemble run (see docs/preregistration.md).
usage: python run.py <work_dir> <stage> [items]
stages: fetch | arms | infer | score | all ; items: comma list of C1,T1..T6 (default all, C1 first)
Env: VILLA_SRC (villa vesuvius/src on PYTHONPATH), HECATE_DIR (hecate.py + hecate_9.6um.pth), CKPT_DIR, NUM_WORKERS (default 0)."""
import json, os, sys, subprocess, time, hashlib, urllib.request
from pathlib import Path
import numpy as np, zarr, tifffile, cv2
HERE = Path(__file__).resolve().parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE / "vendor"))
from textscore2 import score2
S3 = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com/"
UM = 8.64
SEGS = json.load(open(ROOT / "meta" / "segments.json"))
ITEMS = {"C1": "PHerc0009B/segments/20250919125754-auto_grown_20250919055754487_inp_hr/surface-volumes/8.64um-1.2m-116keV-volume-20250521125136.zarr/"}
for i, s in enumerate(SEGS, 1): ITEMS[f"T{i}"] = s["path"]
MODELS = {"m1": "ink_9um/hybrid_3d2d-seed42/step-075000.pth", "m2": "ink_9um/hybrid_3d2d-seed43/step-075000.pth",
          "m4": "reader-v2/reader-v2-step040000.pth", "m5": "dense_native/dense_native_016000.pth"}
DIRS = ("forward", "reverse")

def log(w, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"; print(line, flush=True)
    with open(Path(w) / "run.log", "a") as f: f.write(line + "\n")

def fetch(w, it):
    out = Path(w) / it / "sv.zarr"
    if (out / ".done").exists(): return out
    meta = json.loads(urllib.request.urlopen(S3 + ITEMS[it] + "0/.zarray", timeout=60).read())
    assert meta["dtype"] == "|u1"
    zs = zarr.open_array(str(out / "0"), mode="w", shape=meta["shape"], chunks=meta["chunks"], dtype=np.uint8, zarr_format=2, fill_value=0)
    src = zarr.open_array(S3 + ITEMS[it] + "0", mode="r")
    for y in range(0, meta["shape"][1], 512):
        zs[:, y:y + 512] = src[:, y:y + 512]
    (out / ".done").write_text(json.dumps(meta)); log(w, f"FETCH {it} {meta['shape']}"); return out

def centred(D, n):  # villa center_crop_layer_indices: start = D // 2 - n // 2
    if D <= n: return slice(0, D)
    s = D // 2 - n // 2; return slice(s, s + n)

def arms(w, it):
    sv = Path(w) / it / "sv.zarr"; vol = zarr.open_array(str(sv / "0"), mode="r")
    a = {"A": sv}
    b = Path(w) / it / "svB.zarr"
    if not (b / ".done").exists():
        sys.path.insert(0, str(HERE / "vendor")); from depth_sharpen_9um import sharpen
        sl = centred(vol.shape[0], 21); out = zarr.open_array(str(b / "0"), mode="w", shape=(21,) + vol.shape[1:], chunks=(21, 128, 128), dtype=np.uint8, zarr_format=2, fill_value=0)
        for y in range(0, vol.shape[1], 256):
            out[:, y:y + 256] = sharpen(np.asarray(vol[sl, y:y + 256]), UM, use_map=False)
        (b / ".done").write_text(json.dumps({"slice": [sl.start, sl.stop]})); log(w, f"ARM_B {it} layers {sl.start}:{sl.stop}")
    a["B"] = b; return a

def resample_96(vol, um):  # verbatim from reader-v2 scripts/infer_with_hecate.py
    f = um / 9.6
    nz, ny, nx = vol.shape
    oy, ox, oz = int(round(ny * f)), int(round(nx * f)), int(round(nz * f))
    xy = np.stack([cv2.resize(np.asarray(vol[k]), (ox, oy), interpolation=cv2.INTER_AREA) for k in range(nz)])
    zs = (np.arange(oz) + 0.5) / f - 0.5
    z0 = np.clip(np.floor(zs).astype(int), 0, nz - 1); z1 = np.clip(z0 + 1, 0, nz - 1); w = np.clip(zs - z0, 0, 1)
    return np.stack([np.round((1 - w[k]) * xy[z0[k]] + w[k] * xy[z1[k]]).astype(np.uint8) for k in range(oz)])

def infer(w, it):
    ck = Path(os.environ["CKPT_DIR"]); nw = os.environ.get("NUM_WORKERS", "0"); env = dict(os.environ)
    env["PYTHONPATH"] = os.environ["VILLA_SRC"] + os.pathsep + env.get("PYTHONPATH", "")
    for arm, z in arms(w, it).items():
        od = Path(w) / it / arm; od.mkdir(parents=True, exist_ok=True)
        for m, rel in MODELS.items():
            if (od / f"{m}_reverse.tif").exists(): continue
            t = time.time()
            cmd = [sys.executable, "-B", "-m", "vesuvius.ink_detection.inference.infer", str(z), str(ck / rel), str(od / f"{m}.tif"),
                   "--overlap", "0.5", "--blend-mode", "hann", "--direction", "both", "--num-workers", nw, "--batch-size", os.environ.get("BATCH", "8"), "--no-compile"]
            r = subprocess.run(cmd, env=env, capture_output=True, text=True)
            (od / f"{m}.log").write_text(r.stdout[-20000:] + r.stderr[-20000:])
            log(w, f"INFER {it} {arm} {m} exit={r.returncode} {time.time()-t:.1f}s"); assert r.returncode == 0, f"{m} failed"
        if not (od / "m3_reverse.png").exists():
            vol = zarr.open_array(str(z / "0"), mode="r"); npy = od / "sv96.npy"; np.save(npy, resample_96(vol, UM))
            hd = Path(os.environ["HECATE_DIR"])
            for d in DIRS:
                t = time.time(); outp = od / ("m3.png" if d == "forward" else "m3_reverse.png")
                cmd = [sys.executable, "-B", str(hd / "hecate.py"), "--checkpoint", str(hd / "hecate_9.6um.pth"), "--input", str(npy), "--spacing-um", "9.6",
                       "--output", str(outp), "--batch-size", os.environ.get("HBATCH", "4")] + (["--reverse"] if d == "reverse" else []) + (["--precision", os.environ["HPREC"]] if os.environ.get("HPREC") else [])
                r = subprocess.run(cmd, env=env, capture_output=True, text=True); (od / f"m3_{d}.log").write_text(r.stdout[-20000:] + r.stderr[-20000:])
                log(w, f"INFER {it} {arm} m3 {d} exit={r.returncode} {time.time()-t:.1f}s"); assert r.returncode == 0, "hecate failed"
            npy.unlink()

def load_map(od, m, d, shape):
    if m == "m3":
        h = cv2.imread(str(od / ("m3.png" if d == "forward" else "m3_reverse.png")), cv2.IMREAD_UNCHANGED)
        h = (h[..., 0] if h.ndim == 3 else h).astype(np.float32)
        return cv2.resize(h, (shape[1], shape[0]), interpolation=cv2.INTER_LINEAR) / 255.0
    a = np.asarray(tifffile.imread(str(od / (f"{m}.tif" if d == "forward" else f"{m}_reverse.tif")))).astype(np.float32)
    return a / 255.0 if a.max() > 1.5 else a

def score(w, it):
    res = {}
    for arm, z in arms(w, it).items():
        od = Path(w) / it / arm; vol = zarr.open_array(str(z / "0"), mode="r"); ct = np.asarray(vol[vol.shape[0] // 2]); sh = ct.shape
        maps = {m: {d: load_map(od, m, d, sh) for d in DIRS} for m in ["m1", "m2", "m3", "m4", "m5"]}
        E = {d: np.mean([maps[m][d] for m in maps], axis=0) for d in DIRS}
        for d in DIRS: tifffile.imwrite(str(od / f"E_{d}.tif"), np.round(E[d] * 255).clip(0, 255).astype(np.uint8), compression="zlib")
        def s1(f, r):
            pf, pr = np.round(f * 255), np.round(r * 255); valid = (ct > 0) & (pf > 0)
            return score2(pf, pr, ct, valid, hi=(180,))[180]
        rec = {"E": {"s1_fwd": s1(E["forward"], E["reverse"]), "s1_rev": s1(E["reverse"], E["forward"])}, "models": {}}
        for m in maps: rec["models"][m] = {"s1_fwd": s1(maps[m]["forward"], maps[m]["reverse"]), "s1_rev": s1(maps[m]["reverse"], maps[m]["forward"])}
        rec["E"]["S1"] = max(rec["E"]["s1_fwd"], rec["E"]["s1_rev"]); best = "forward" if rec["E"]["s1_fwd"] >= rec["E"]["s1_rev"] else "reverse"
        rs = subprocess.run([sys.executable, "-B", str(HERE / "vendor" / "rowscore.py"), str(od / f"E_{best}.tif"), str(UM), str(z)], capture_output=True, text=True)
        rec["E"]["S2"] = json.loads(rs.stdout.strip().splitlines()[-1]) if rs.returncode == 0 else {"error": rs.stderr[-500:]}
        rec["E"]["best_direction"] = best
        rec["sha256"] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(od.glob("*.tif")) + sorted(od.glob("*.png"))}
        res[arm] = rec
    out = ROOT / "results" / "scores.jsonl"
    with open(out, "a") as f: f.write(json.dumps({"item": it, "path": ITEMS[it], **res}) + "\n")
    log(w, f"SCORE {it} A.S1={res['A']['E']['S1']} B.S1={res['B']['E']['S1']}"); return res

if __name__ == "__main__":
    w, stage = sys.argv[1], sys.argv[2]; Path(w).mkdir(parents=True, exist_ok=True)
    items = sys.argv[3].split(",") if len(sys.argv) > 3 else list(ITEMS)
    for it in items:
        if stage in ("fetch", "all"): fetch(w, it)
        if stage in ("arms", "all"): arms(w, it)
        if stage in ("infer", "all"): infer(w, it)
        if stage in ("score", "all"): score(w, it)
