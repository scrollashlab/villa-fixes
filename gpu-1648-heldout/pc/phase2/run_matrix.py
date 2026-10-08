"""PC phase 2: verify inputs, run the pre-registered #1648 held-out matrix with villa's own infer CLI
(in-process, headless), and reduce each output TIFF to the L2 crop grid for scoring on the box.

usage: python -B run_matrix.py <ROOT> [--budget-min 15]
ROOT layout: venv/, villa-8b63a2652/, ckpt/, data-do-not-redistribute/{prepared,masks}/, outputs/
Outputs:
  outputs/preds-do-not-redistribute/<case>_<lv>_<seed>_<dir>.tif   (raw villa output, stays on the PC)
  outputs/reduced-do-not-redistribute/<case>.npz                    (L2 uint8 / L0 4x4 uint16 sums on the L2 crop grid)
  outputs/run-log.json                                               (metadata only: timings, patch counts, hashes)
Runs whose reduced arrays already exist are skipped (resumable). Before each run the projected
elapsed GPU time is checked against --budget-min; if it would be exceeded the script stops cleanly.
"""
import argparse, hashlib, json, os, sys, time
from pathlib import Path

CASES = ["pherc0814-46527", "pherc0139-w016", "pherc1667-w029"]
SEEDS = {"seed42": "hybrid_3d2d-seed42-step-075000.pth", "seed43": "hybrid_3d2d-seed43-step-075000.pth"}
CKPT_SHA = {"seed42": "e635558ae6a1a807a7e5ec1e83adfd45bc3c0ac53883ea43f1d4e085d62a9cab",
            "seed43": "2aeaa85a35ef28d7bc7bf3e848c4a6a91385e9132710927fdba41133c4ecb28f"}
COMMON = ["--no-compile", "--num-workers", "0", "--batch-size", "16", "--amp-dtype", "auto"]

def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""): h.update(b)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("root", type=Path); ap.add_argument("--budget-min", type=float, default=15.0)
    ap.add_argument("--test-subset", action="store_true", help="box smoke test: 46527 L2 seed42 only, CPU ok")
    a = ap.parse_args(); R = a.root
    global CASES, SEEDS
    if a.test_subset:
        CASES = ["pherc0814-46527"]; SEEDS = {"seed42": SEEDS["seed42"]}
    LEVELS = ("L2",) if a.test_subset else ("L2", "L0")
    os.environ["TEMP"] = os.environ["TMP"] = str(R / "tmp"); (R / "tmp").mkdir(exist_ok=True)
    import tempfile; tempfile.tempdir = str(R / "tmp")
    vsrc = R / "villa-8b63a2652" / "vesuvius" / "src"
    sys.path.insert(0, str(vsrc if vsrc.exists() else R / "villa-8b63a2652"))
    import numpy as np, tifffile, zarr, torch
    from vesuvius.ink_detection.inference import infer
    from vesuvius.ink_detection.inference.infer import iter_blocks
    man = json.load(open(R / "phase2" / "inputs-manifest.json"))
    D = R / "data-do-not-redistribute"; O = R / "outputs"
    P = O / "preds-do-not-redistribute"; Q = O / "reduced-do-not-redistribute"; P.mkdir(parents=True, exist_ok=True); Q.mkdir(parents=True, exist_ok=True)
    logp = O / "run-log.json"
    log = json.load(open(logp)) if logp.exists() else {"runs": {}, "checks": {}}
    def save(): json.dump(log, open(logp, "w"), indent=1)
    cuda = torch.cuda.is_available()
    log["env"] = {"python": sys.version.split()[0], "torch": torch.__version__, "cuda": torch.version.cuda,
                  "device": torch.cuda.get_device_name(0) if cuda else "cpu", "villa": "8b63a2652", "args_common": COMMON}
    # --- input verification (decoded arrays, masks, checkpoints)
    for s, f in SEEDS.items():
        h = sha_file(R / "ckpt" / f); assert h == CKPT_SHA[s], (s, h); log["checks"][f"ckpt_{s}"] = h
    counts = {}
    for case in CASES:
        for lv in LEVELS:
            ref = man["cases"][case]["levels"][lv]
            arr = zarr.open_array(str(D / "prepared" / f"{case}_{lv}.zarr" / "0"), mode="r")
            hh = hashlib.sha256(); occ = np.zeros(arr.shape[1:], bool)
            for z in range(arr.shape[0]):  # stream plane by plane: same bytes as the C-order array, low memory
                pl = np.ascontiguousarray(arr[z]); hh.update(pl.tobytes()); occ |= pl != 0
            h = hh.hexdigest(); assert h == ref["prepared_sha256"], (case, lv, h)
            assert list(arr.shape) == ref["prepared_shape"]
            m = tifffile.imread(D / "masks" / f"{case}_{lv}_mask.tif")
            hm = hashlib.sha256(np.ascontiguousarray(m).tobytes()).hexdigest(); assert hm == ref["mask_sha256"], (case, lv, hm)
            counts[(case, lv)] = len(iter_blocks(occ.shape, 128, 64, occ & (m > 0), (1, 1)))
            log["checks"][f"{case}_{lv}"] = {"prepared_sha256_ok": True, "mask_sha256_ok": True, "patches_per_direction": counts[(case, lv)]}
            del occ; print("verified", case, lv, arr.shape, "patches/dir", counts[(case, lv)], flush=True)
    save()
    t_gpu = sum(r.get("seconds", 0) for r in log["runs"].values())
    rate = None  # seconds per patch, measured
    def run(case, lv, seed, masked=True, tag=None):
        nonlocal t_gpu, rate
        tif = P / f"{tag or f'{case}_{lv}_{seed}'}.tif"
        argv = [str(D / "prepared" / f"{case}_{lv}.zarr"), str(R / "ckpt" / SEEDS[seed]), str(tif), "--direction", "both"] + COMMON
        if masked: argv += ["--mask-path", str(D / "masks" / f"{case}_{lv}_mask.tif")]
        t0 = time.perf_counter()
        if cuda: torch.cuda.reset_peak_memory_stats()
        infer.main(argv)
        if cuda: torch.cuda.synchronize()
        dt = time.perf_counter() - t0; t_gpu += dt
        n = 2 * counts[(case, lv)]; rate = dt / n
        outs = {"forward": tif, "reverse": tif.with_name(f"{tif.stem}_reverse{tif.suffix}")}
        return dt, outs, n
    def reduce_(case, lv, path):
        y0, y1, x0, x1 = man["cases"][case]["crop_l2_yx"]; h, w = y1 - y0, x1 - x0
        t = tifffile.imread(path)
        if lv == "L2":
            assert t.shape == (h, w), t.shape; return t.astype(np.uint8)
        assert t.shape == (4 * h, 4 * w), t.shape
        return t.reshape(h, 4, w, 4).astype(np.uint16).sum(axis=(1, 3), dtype=np.uint16)
    budget = a.budget_min * 60
    # --- pre-registered equivalence check: 46527 L2 seed42 masked vs unmasked, exact on mask pixels
    if "equivalence" not in log["checks"]:
        dt_u, outs_u, _ = run("pherc0814-46527", "L2", "seed42", masked=False, tag="equiv_unmasked_pherc0814-46527_L2_seed42")
        dt_m, outs_m, _ = run("pherc0814-46527", "L2", "seed42", masked=True, tag="equiv_masked_pherc0814-46527_L2_seed42")
        m = tifffile.imread(D / "masks" / "pherc0814-46527_L2_mask.tif") > 0
        res = {}
        for d in ("forward", "reverse"):
            u, k = tifffile.imread(outs_u[d]), tifffile.imread(outs_m[d])
            res[d] = {"mask_px": int(m.sum()), "n_diff_in_mask": int((u[m] != k[m]).sum()), "max_abs_diff_in_mask": int(np.abs(u[m].astype(int) - k[m].astype(int)).max())}
        log["checks"]["equivalence"] = {"result": res, "seconds_unmasked": dt_u, "seconds_masked": dt_m,
                                        "exact": all(r["n_diff_in_mask"] == 0 for r in res.values())}
        save(); print("equivalence", json.dumps(log["checks"]["equivalence"]), flush=True)
    use_mask = bool(log["checks"]["equivalence"]["exact"])
    # --- matrix: per case, L2 then L0, seed42 then seed43, both directions per invocation
    for case in CASES:
        red_path = Q / f"{case}.npz"
        red = dict(np.load(red_path)) if red_path.exists() else {}
        for lv in LEVELS:
            for seed in SEEDS:
                key = f"{case}_{lv}_{seed}"
                if f"{lv}_{seed}_forward" in red and f"{lv}_{seed}_reverse" in red: continue
                proj = (rate or 0.05) * 2 * counts[(case, lv)]
                if t_gpu + proj > budget:
                    log["stopped"] = {"at": key, "gpu_seconds_so_far": t_gpu, "projected_next_s": proj, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                    save(); print("BUDGET_STOP", json.dumps(log["stopped"]), flush=True); return 3
                dt, outs, n = run(case, lv, seed, masked=use_mask)
                rec = {"seconds": dt, "patches": n, "s_per_patch": dt / n, "peak_mem_mib": (torch.cuda.max_memory_allocated() / 2**20) if cuda else None, "masked": use_mask}
                for d, p in outs.items():
                    red[f"{lv}_{seed}_{d}"] = reduce_(case, lv, p); rec[f"tif_sha256_{d}"] = sha_file(p)
                log["runs"][key] = rec; np.savez_compressed(red_path, **red); save()
                print("done", key, json.dumps(rec), flush=True)
        log.setdefault("reduced", {})[case] = {"bytes": red_path.stat().st_size, "sha256": sha_file(red_path), "keys": sorted(red)}
        save()
    log.pop("stopped", None); log["gpu_seconds_total"] = t_gpu; save()
    print("MATRIX_DONE gpu_seconds", round(t_gpu, 1), flush=True); return 0

if __name__ == "__main__":
    sys.exit(main())
