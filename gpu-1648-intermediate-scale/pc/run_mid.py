"""PC runner: #1648 in-plane-scale test at 4.681 um (S4) vs 9.362 um (S9) on PHerc0841 x3 (docs/preregistration.md).

usage: python -B run_mid.py <ROOT> <cmd> [--segs a,b] [--num-workers N]
  prep    fetch the planned level-0 chunks (mask-box only) and build S9 crops + S4 tiles (+ masks), band by band (low RAM)
  probe   step 0b: one S4 tile of w00, seed42@75k, run with --num-workers 0, 2, 0; byte identity, peak RSS, GPU util
  run     all arms: 3 segments x {S9, S4 tiles} x {seed42, seed43}@75k x both directions (resumable)
  reduce  per-64x64-block label histograms on the level-1 crop grid (S9: 256 bins; S4 2x2 sums: 1021 bins)
Everything stays under ROOT/data-do-not-redistribute and ROOT/outputs/mid (CC BY-NC derived; local only).
"""
import argparse, hashlib, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SEGS = ["pherc0841-w00", "pherc0841-ag144", "pherc0841-ag174"]
CKPTS = ["seed42", "seed43"]
CORE, MARGIN, BATCH = 4096, 256, 32

def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()

def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mid-scale"}), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if i == tries - 1: raise
        except Exception:
            if i == tries - 1: raise
        time.sleep(2 * (i + 1))

def D(R): return R / "data-do-not-redistribute" / "mid"
def O(R): return R / "outputs" / "mid"
def ckpt(R, s): return R / "ckpt" / f"hybrid_3d2d-{s}-step-075000.pth"

def tiles_for(P):
    y0, y1, x0, x1 = P["crop_yx"]; H0, W0 = 2 * (y1 - y0), 2 * (x1 - x0); out = []
    for ty in range(0, H0, CORE):
        for tx in range(0, W0, CORE):
            cy0, cy1, cx0, cx1 = ty, min(ty + CORE, H0), tx, min(tx + CORE, W0)
            py0, py1, px0, px1 = max(0, cy0 - MARGIN), min(H0, cy1 + MARGIN), max(0, cx0 - MARGIN), min(W0, cx1 + MARGIN)
            out.append({"name": f"t{ty // CORE}_{tx // CORE}", "core": [cy0, cy1, cx0, cx1], "pad": [py0, py1, px0, px1]})
    return out

class L0Reader:
    """Reads level-0 (65,y,x) regions in L0-crop coordinates from the chunk cache; unfetched chunks read as 0."""
    def __init__(self, R, seg, P):
        import numpy as np
        self.np = np; self.cache = D(R) / "chunks" / seg; y0, _, x0, _ = P["crop_yx"]; self.Y0, self.X0 = 2 * y0, 2 * x0
    def read(self, ly0, ly1, lx0, lx1):
        np = self.np; gy0, gy1, gx0, gx1 = ly0 + self.Y0, ly1 + self.Y0, lx0 + self.X0, lx1 + self.X0
        out = np.zeros((65, gy1 - gy0, gx1 - gx0), np.uint8)
        for cy in range(gy0 // 128, (gy1 - 1) // 128 + 1):
            for cx in range(gx0 // 128, (gx1 - 1) // 128 + 1):
                f = self.cache / f"{cy}_{cx}.bin"
                if not f.exists(): continue
                blk = np.frombuffer(f.read_bytes(), np.uint8).reshape(65, 128, 128)
                a0, a1 = max(gy0, cy * 128), min(gy1, cy * 128 + 128); b0, b1 = max(gx0, cx * 128), min(gx1, cx * 128 + 128)
                out[:, a0 - gy0:a1 - gy0, b0 - gx0:b1 - gx0] = blk[:, a0 - cy * 128:a1 - cy * 128, b0 - cx * 128:b1 - cx * 128]
        return out

def zpool(np, a):  # (65,y,x) -> (33,y,x): pairs (0,1)..(62,63) half-up mean, plane 64 alone
    s = a[:64].astype(np.uint16).reshape(32, 2, *a.shape[1:]).sum(axis=1)
    return np.concatenate([((s + 1) // 2).astype(np.uint8), a[64:65]], 0)

def s9pool(np, a):  # (65,2y,2x) -> (33,y,x): 2x2x2 half-up mean; plane 64: 2x2 half-up mean
    Y, X = a.shape[1] // 2, a.shape[2] // 2
    s = a[:64].astype(np.uint16).reshape(32, 2, Y, 2, X, 2).sum(axis=(1, 3, 5))
    last = a[64].astype(np.uint16).reshape(Y, 2, X, 2).sum(axis=(1, 3))
    return np.concatenate([((s + 4) // 8).astype(np.uint8), ((last + 2) // 4).astype(np.uint8)[None]], 0)

def new_zarr(path, shape):
    import zarr
    from numcodecs import Blosc
    g = zarr.open_group(str(path), mode="w", zarr_format=2)
    return g.create_array("0", shape=shape, chunks=(33, 128, 128), dtype="uint8", fill_value=0,
                          compressors=Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE), overwrite=True)

def cmd_prep(R, plan, a):
    import numpy as np, tifffile
    log = {}
    for seg in a.segs:
        P = plan[seg]; base0 = P["render_level1"][:-1] + "0"; cache = D(R) / "chunks" / seg; cache.mkdir(parents=True, exist_ok=True)
        cells0 = sorted({(2 * cy + dy, 2 * cx + dx) for cy, cx in P["cells"] for dy in (0, 1) for dx in (0, 1)})
        def fetch(c):
            f = cache / f"{c[0]}_{c[1]}.bin"
            if f.exists() and f.stat().st_size == 65 * 128 * 128: return f.stat().st_size, True
            b = get(f"{base0}/0.{c[0]}.{c[1]}")
            if b is None: return 0, False
            assert len(b) == 65 * 128 * 128, (seg, c, len(b))
            f.write_bytes(b); return len(b), True
        with ThreadPoolExecutor(8) as ex: res = list(ex.map(fetch, cells0))
        rd = L0Reader(R, seg, P); y0, y1, x0, x1 = P["crop_yx"]; h, w = y1 - y0, x1 - x0
        mask1 = tifffile.imread(R / "data-do-not-redistribute" / "lfs" / "masks" / f"{seg}_region_mask.tif") > 0
        assert mask1.shape == (h, w), (seg, mask1.shape, h, w)
        # S9: one crop on the level-1 crop grid, built in bands of 64 level-1 rows
        sd = D(R) / "inputs" / seg; sd.mkdir(parents=True, exist_ok=True)
        z9 = new_zarr(sd / "S9.zarr", (33, h, w)); hs = hashlib.sha256()
        for r in range(0, h, 64):
            band = s9pool(np, rd.read(2 * r, 2 * min(r + 64, h), 0, 2 * w)); z9[:, r:r + band.shape[1], :] = band; hs.update(band.tobytes())
        tifffile.imwrite(sd / "S9_mask.tif", (mask1 * 255).astype(np.uint8))
        tl = []
        for t in tiles_for(P):
            py0, py1, px0, px1 = t["pad"]; zt = new_zarr(sd / f"S4_{t['name']}.zarr", (33, py1 - py0, px1 - px0)); ht = hashlib.sha256()
            for r in range(py0, py1, 128):
                band = zpool(np, rd.read(r, min(r + 128, py1), px0, px1)); zt[:, r - py0:r - py0 + band.shape[1], :] = band; ht.update(band.tobytes())
            m = np.repeat(np.repeat(mask1, 2, 0), 2, 1)[py0:py1, px0:px1]
            tifffile.imwrite(sd / f"S4_{t['name']}_mask.tif", (m * 255).astype(np.uint8))
            tl.append({**t, "mask_px": int(m.sum()), "decoded_sha256": ht.hexdigest()})
        log[seg] = {"l0_chunks": len(cells0), "present": sum(1 for r in res if r[1]), "bytes_downloaded": sum(r[0] for r in res),
                    "S9_shape": [33, h, w], "S9_decoded_sha256": hs.hexdigest(), "S4_tiles": tl}
        print("prepared", seg, json.dumps({k: v for k, v in log[seg].items() if k != "S4_tiles"}), "tiles", len(tl), flush=True)
    O(R).mkdir(parents=True, exist_ok=True)
    old = json.load(open(O(R) / "prep-log.json")) if (O(R) / "prep-log.json").exists() else {}
    old.update(log); json.dump(old, open(O(R) / "prep-log.json", "w"), indent=1)

class Monitor:
    """Peak RSS of this process + all descendants, and GPU utilization samples (nvidia-smi, no window)."""
    def __init__(self):
        import psutil, subprocess
        self.ps, self.sp = psutil, subprocess; self.peak = 0; self.util = []; self.stop = False
        self.t = threading.Thread(target=self.loop, daemon=True); self.t.start()
    def loop(self):
        me = self.ps.Process(); k = 0
        while not self.stop:
            try:
                rss = me.memory_info().rss + sum(c.memory_info().rss for c in me.children(recursive=True))
                self.peak = max(self.peak, rss)
            except Exception: pass
            if k % 5 == 0:
                try:
                    o = self.sp.run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True,
                                    text=True, timeout=10, creationflags=getattr(self.sp, "CREATE_NO_WINDOW", 0)).stdout.strip()
                    self.util.append(int(o.splitlines()[0]))
                except Exception: pass
            k += 1; time.sleep(0.2)
    def done(self):
        self.stop = True; self.t.join(); u = self.util
        return {"peak_rss_mib": round(self.peak / 2**20, 1), "gpu_util_mean": round(sum(u) / len(u), 1) if u else None,
                "gpu_util_max": max(u) if u else None, "gpu_util_samples": len(u)}

def infer_one(R, inp, mask, ck, out_tif, nw):
    import torch
    sys.path.insert(0, str(R / "villa-8b63a2652" / "vesuvius" / "src"))
    from vesuvius.ink_detection.inference import infer
    t0 = time.perf_counter()
    infer.main([str(inp), str(ckpt(R, ck)), str(out_tif), "--direction", "both", "--mask-path", str(mask), "--no-compile",
                "--num-workers", str(nw), "--batch-size", str(BATCH), "--amp-dtype", "auto"])
    if torch.cuda.is_available(): torch.cuda.synchronize()
    return time.perf_counter() - t0

def cmd_probe(R, plan, a):
    seg = "pherc0841-w00"; sd = D(R) / "inputs" / seg; t = tiles_for(plan[seg])[0]["name"]
    od = O(R) / "probe-preds-do-not-redistribute"; od.mkdir(parents=True, exist_ok=True); res = []
    for i, nw in enumerate([0, 2, 0]):
        out = od / f"run{i}_nw{nw}.tif"; m = Monitor()
        dt = infer_one(R, sd / f"S4_{t}.zarr", sd / f"S4_{t}_mask.tif", "seed42", out, nw); st = m.done()
        res.append({"run": i, "num_workers": nw, "seconds": round(dt, 1), **st,
                    "sha_forward": sha_file(out), "sha_reverse": sha_file(out.with_name(out.stem + "_reverse.tif"))})
        print("PROBE", json.dumps(res[-1]), flush=True)
    ident = res[1]["sha_forward"] == res[0]["sha_forward"] and res[1]["sha_reverse"] == res[0]["sha_reverse"]
    repeat = res[2]["sha_forward"] == res[0]["sha_forward"] and res[2]["sha_reverse"] == res[0]["sha_reverse"]
    keep2 = ident and res[1]["peak_rss_mib"] < 2048
    out = {"tile": t, "runs": res, "nw2_identical_to_nw0": ident, "nw0_repeat_identical": repeat, "keep_num_workers_2": keep2}
    json.dump(out, open(O(R) / "probe.json", "w"), indent=1); print("PROBE_RESULT", json.dumps(out), flush=True)

def cmd_run(R, plan, a):
    import torch
    logp = O(R) / "run-log.json"; log = json.load(open(logp)) if logp.exists() else {"runs": {}}
    log["env"] = {"python": sys.version.split()[0], "torch": torch.__version__, "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
                  "villa": "8b63a2652", "batch_size": BATCH, "num_workers": a.num_workers}
    for seg in a.segs:
        sd = D(R) / "inputs" / seg; od = O(R) / "preds-do-not-redistribute" / seg; od.mkdir(parents=True, exist_ok=True)
        units = [("S9", sd / "S9.zarr", sd / "S9_mask.tif")] + [(f"S4_{t['name']}", sd / f"S4_{t['name']}.zarr", sd / f"S4_{t['name']}_mask.tif") for t in tiles_for(plan[seg])]
        for ck in CKPTS:
            for name, inp, mask in units:
                key = f"{seg}|{ck}|{name}"
                if log["runs"].get(key, {}).get("done"): continue
                out = od / f"{ck}_{name}.tif"; m = Monitor(); dt = infer_one(R, inp, mask, ck, out, a.num_workers); st = m.done()
                log["runs"][key] = {"done": True, "seconds": round(dt, 2), **st, "sha_forward": sha_file(out),
                                    "sha_reverse": sha_file(out.with_name(out.stem + "_reverse.tif"))}
                json.dump(log, open(logp, "w"), indent=1); print("done", key, round(dt, 1), json.dumps(st), flush=True)
    print("RUN_DONE", flush=True)

def cmd_reduce(R, plan, a):
    import numpy as np, tifffile
    S = O(R) / "stats"; S.mkdir(parents=True, exist_ok=True)
    for seg in a.segs:
        P = plan[seg]; y0, y1, x0, x1 = P["crop_yx"]; h, w = y1 - y0, x1 - x0
        z = np.load(R / "data-do-not-redistribute" / "lfs" / "labels" / f"{seg}.npz"); shp = tuple(z["shape"]); assert shp == (h, w)
        reg = np.unpackbits(z["region"])[: h * w].reshape(shp).astype(bool); ink = np.unpackbits(z["ink"])[: h * w].reshape(shp).astype(bool)
        nbx = (w + 63) // 64; blk = ((np.arange(h)[:, None] // 64) * nbx + (np.arange(w)[None, :] // 64))[reg]
        ub, binv = np.unique(blk, return_inverse=True); lab = ink[reg]; nb = len(ub)
        od = O(R) / "preds-do-not-redistribute" / seg; out = {"blocks": ub, "n": int(reg.sum()), "n_pos": int(lab.sum())}; shas = {}
        for ck in CKPTS:
            for d, suf in (("forward", ""), ("reverse", "_reverse")):
                f9 = od / f"{ck}_S9{suf}.tif"; m9 = tifffile.imread(f9); assert m9.shape == (h, w); shas[f"{ck}|S9|{d}"] = sha_file(f9)
                full = np.zeros((2 * h, 2 * w), np.uint8)
                for t in tiles_for(P):
                    ft = od / f"{ck}_S4_{t['name']}{suf}.tif"; mt = tifffile.imread(ft); shas[f"{ck}|S4_{t['name']}|{d}"] = sha_file(ft)
                    cy0, cy1, cx0, cx1 = t["core"]; py0, _, px0, _ = t["pad"]
                    full[cy0:cy1, cx0:cx1] = mt[cy0 - py0:cy1 - py0, cx0 - px0:cx1 - px0]
                s4 = full.reshape(h, 2, w, 2).astype(np.uint16).sum(axis=(1, 3)); del full
                for arm, v, nbins in (("S9", m9[reg].astype(np.int64), 256), ("S4", s4[reg].astype(np.int64), 1021)):
                    key = binv * nbins + v
                    pos = np.bincount(key[lab], minlength=nb * nbins).reshape(nb, nbins).astype(np.uint32)
                    neg = np.bincount(key[~lab], minlength=nb * nbins).reshape(nb, nbins).astype(np.uint32)
                    out[f"{ck}|{arm}|{d}|pos"] = pos; out[f"{ck}|{arm}|{d}|neg"] = neg
                print("reduced", seg, ck, d, flush=True)
        out["tif_sha256"] = np.array(json.dumps(shas))
        np.savez_compressed(S / f"{seg}.npz", **out); print("REDUCED", seg, out["n"], out["n_pos"], nb, flush=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("root", type=Path); ap.add_argument("cmd")
    ap.add_argument("--segs", default=",".join(SEGS)); ap.add_argument("--num-workers", type=int, default=0)
    a = ap.parse_args(); R = a.root; a.segs = a.segs.split(",")
    (R / "tmp").mkdir(exist_ok=True); os.environ["TEMP"] = os.environ["TMP"] = str(R / "tmp")
    import tempfile; tempfile.tempdir = str(R / "tmp")
    plan = json.load(open(R / "mid" / "heldout-plan.json"))
    {"prep": cmd_prep, "probe": cmd_probe, "run": cmd_run, "reduce": cmd_reduce}[a.cmd](R, plan, a)

if __name__ == "__main__":
    main()
