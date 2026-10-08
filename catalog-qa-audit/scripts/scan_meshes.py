"""Per-mesh point statistics for every published tifxyz mesh (pre-registered audit).
Streams x/y/z.tif + meta.json anonymously, decodes with raw tifffile, writes metadata-only JSONL.
Usage: python scan_meshes.py OUT_JSONL WORKERS MIN_BYTES MAX_BYTES   (byte bounds on compressed x+y+z size)"""
import io, json, math, sys, time, urllib.request, urllib.error
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote
import numpy as np, tifffile
sys.path.insert(0, str(Path(__file__).parent))
from common import BUCKET, MESH_TYPES, XFRAME_SRC, load_catalog, holdout
sys.path.insert(0, XFRAME_SRC)
from xframe.catalog import Catalog   # catalog matrices only (sample-level volume_transforms)

HERE = Path(__file__).resolve().parent
SHAPES = {(r["sample"], r["volume"]): r.get("zarray_shape") for r in json.load(open(HERE.parent / "out" / "volume-shapes-2026-10-07.json"))}
LISTING = {r["path"]: r for r in json.load(open(HERE.parent / "out" / "mesh-listing-2026-10-07.json"))}
# spacing median via log histogram: relative bin width 1e-4 (the pre-registered rule is a factor-sqrt(2) band)
SP_EDGES = np.exp(np.arange(math.log(1e-4), math.log(1e7), math.log(1.0001)))
import os
MEMMAP = os.environ.get("SCAN_MEMMAP") == "1"   # decode huge meshes to disk memmaps under data/cache/mm (local, never redistributed)
MM_ROOT = str(HERE.parent / "data" / "cache" / "mm")
BLOCK = 128   # rows per block; bounds peak memory (results are block-size independent, see tests)
_cat = None


def get(key, tries=5):
    url = f"{BUCKET}/{quote(key, safe='/')}"
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): raise
            last = e
        except Exception as e:
            last = e
        time.sleep(3 * (i + 1))
    raise last


class RowStack:
    """(H, W, 3) view over three per-channel arrays; row slices are stacked on demand (bounds RAM for huge meshes)."""
    def __init__(self, X, Y, Z):
        self.ch = (X, Y, Z); self.shape = X.shape + (3,)
    def __getitem__(self, sl):
        return np.stack([c[sl] for c in self.ch], -1).astype(np.float32, copy=False)


def read_mesh(path, mm_dir=None):
    """Decode x/y/z.tif. With mm_dir, each channel is decoded into a disk memmap (local scratch, deleted after use)."""
    ch = []
    for c in "xyz":
        buf = get(path + f"{c}.tif")
        if mm_dir is None:
            a = tifffile.imread(io.BytesIO(buf))
        else:
            a = tifffile.imread(io.BytesIO(buf), out=str(Path(mm_dir) / f"{c}.mm"))
        del buf
        if ch and a.shape != ch[0].shape:
            raise ValueError(f"shape mismatch {c}.tif {a.shape} vs {ch[0].shape}")
        ch.append(a)
    meta = json.loads(get(path + "meta.json"))
    if mm_dir is not None:
        return RowStack(*ch), meta
    P = np.empty(ch[0].shape + (3,), np.float32)
    for i in range(3):
        P[..., i] = ch[i]
    return P, meta


def masks(B):
    fin = np.isfinite(B).all(-1)
    vc = fin & (B[..., 0] != -1)                    # VC isValidSurfacePoint
    strict = fin & ~(B == -1).any(-1)                # xframe isValidPointSample
    return vc, strict


def bbox_upd(bb, Q):
    if Q.shape[0] == 0: return bb
    lo, hi = Q.min(0).astype(np.float64), Q.max(0).astype(np.float64)
    if bb is None: return [lo, hi]
    return [np.minimum(bb[0], lo), np.maximum(bb[1], hi)]


def tri_area(a, b, c, ok):
    u = (b - a).astype(np.float64); v = (c - a).astype(np.float64)
    cr = np.cross(u, v)
    ar = 0.5 * np.sqrt((cr * cr).sum(-1))
    return float(ar[ok].sum())


def point_stats(P):
    H, W = P.shape[:2]
    st = {"rows": H, "cols": W, "n_valid_vc": 0, "n_valid_strict": 0}
    bb = {"vc": None, "strict": None}
    hist = np.zeros(len(SP_EDGES) + 1, np.int64); npairs = 0; area = 0.0
    for a in range(0, H, BLOCK):
        b = min(H, a + BLOCK + 1)                 # one-row overlap for vertical pairs / quads
        B = P[a:b]; vc, strict = masks(B)
        own = slice(0, min(BLOCK, b - a)) if b < H else slice(0, b - a)
        st["n_valid_vc"] += int(vc[own].sum()); st["n_valid_strict"] += int(strict[own].sum())
        bb["vc"] = bbox_upd(bb["vc"], B[own][vc[own]]); bb["strict"] = bbox_upd(bb["strict"], B[own][strict[own]])
        # 4-neighbour spacing (VC validity on both endpoints)
        h_ok = vc[own, 1:] & vc[own, :-1]
        d = np.linalg.norm(B[own, 1:][h_ok].astype(np.float64) - B[own, :-1][h_ok], axis=1)
        if b - a > 1:
            v_ok = vc[1:] & vc[:-1]
            d = np.concatenate([d, np.linalg.norm(B[1:][v_ok].astype(np.float64) - B[:-1][v_ok], axis=1)])
        npairs += d.size
        hist += np.bincount(np.searchsorted(SP_EDGES, d), minlength=len(SP_EDGES) + 1)
        # VC computeSurfaceAreaVox2: two triangles per quad, triangles touching a sentinel (-1,-1,-1) or non-finite vertex add 0
        if b - a > 1:
            fin = np.isfinite(B).all(-1); sen = (B == -1).all(-1); good = fin & ~sen
            p00, p10, p01, p11 = B[:-1, :-1], B[:-1, 1:], B[1:, :-1], B[1:, 1:]
            g00, g10, g01, g11 = good[:-1, :-1], good[:-1, 1:], good[1:, :-1], good[1:, 1:]
            area += tri_area(p00, p10, p11, g00 & g10 & g11) + tri_area(p00, p11, p01, g00 & g11 & g01)
    st["bbox_vc"] = [list(map(float, x)) for x in bb["vc"]] if bb["vc"] is not None else None
    st["bbox_strict"] = [list(map(float, x)) for x in bb["strict"]] if bb["strict"] is not None else None
    st["n_pairs"] = int(npairs)
    if npairs:
        i = int(np.searchsorted(np.cumsum(hist), 0.5 * npairs))
        st["spacing_median"] = float(SP_EDGES[min(i, len(SP_EDGES) - 1)])
    st["area_vx2_computed"] = area
    return st


def coverage(P, sample, seg, cat):
    """volume_coverage recomputed from these vertices for every key in the segment's volume_coverage."""
    s = float(seg["properties"].get("original_volume_downscale") or 1)
    ov = seg["original_volume_id"]
    out = {}
    H = P.shape[0]
    for V in (seg["properties"].get("volume_coverage") or {}):
        r = {}
        try:
            M, prov = cat.matrix(sample, ov, V); M = np.asarray(M, float); r["matrix_how"] = prov["how"]
        except KeyError:
            r["no_transform"] = True; out[V] = r; continue
        shp = SHAPES.get((sample, V))
        R, t = M[:, :3], M[:, 3]
        sig = float(np.linalg.svd(R, compute_uv=False)[0]); r["sigma_max"] = sig
        acc = {k: {"bb": None, "n": 0, "inside": 0, "band": 0} for k in ("vc", "strict")}
        for a in range(0, H, BLOCK):
            B = P[a:a + BLOCK]; vc, strict = masks(B)
            for k, m in (("vc", vc), ("strict", strict)):
                Q = (B[m].astype(np.float64) * s) @ R.T + t
                A = acc[k]; A["n"] += Q.shape[0]; A["bb"] = bbox_upd(A["bb"], Q)
                if shp is not None and Q.shape[0]:
                    ext = np.array([shp[2], shp[1], shp[0]], float) - 1.0     # x, y, z max index
                    inside = ((Q >= 0) & (Q <= ext)).all(1)
                    din = np.minimum(Q, ext - Q).min(1)                         # inside: distance to nearest face
                    dout = np.maximum(np.maximum(-Q, Q - ext), 0).max(1)        # outside: Chebyshev distance to box
                    dist = np.where(inside, din, dout)
                    A["inside"] += int(inside.sum()); A["band_d"] = A.get("band_d", []) + [dist.astype(np.float32)]
        for k in acc:
            A = acc[k]
            r[k] = {"n": A["n"], "bbox": [list(map(float, x)) for x in A["bb"]] if A["bb"] is not None else None}
            if shp is not None and A["n"]:
                r[k]["inside_frac"] = A["inside"] / A["n"]
                r[k]["_dist"] = np.concatenate(A["band_d"]) if A.get("band_d") else np.zeros(0, np.float32)
        r["shape_zyx"] = shp
        out[V] = r
    return out, s


def work(task):
    global _cat
    if _cat is None:
        from common import CAT; _cat = Catalog.load(CAT)
    t0 = time.time()
    sample, gid, typ, path = task
    seg = _cat.samples[sample]["segments"][gid]
    row = {"sample": sample, "segment": gid, "type": typ, "path": path, "holdout": holdout(sample, gid)}
    mm_dir = None
    if MEMMAP:
        import tempfile; mm_dir = tempfile.mkdtemp(dir=MM_ROOT)
    try:
        P, meta = read_mesh(path, mm_dir)
        row["meta"] = {k: meta.get(k) for k in ("bbox", "scale", "area_vx2", "area_cm2", "format", "type")}
        row["meta_keys"] = sorted(meta.keys())
        row.update(point_stats(P))
        if typ in ("tifxyz", "tifxyz-normalized"):
            cov, s = coverage(P, sample, seg, _cat)
            g = max(1.0 / meta["scale"][0], 1.0 / meta["scale"][1]) if meta.get("scale") else None
            row["grid_step_own"] = g
            for V, r in cov.items():
                for k in ("vc", "strict"):
                    if k in r and "_dist" in r[k]:
                        gV = g * s * r["sigma_max"] if g else None
                        dist = r[k].pop("_dist")
                        r[k]["f_band"] = float((dist <= gV).mean()) if (gV and dist.size) else None
                        r[k]["grid_step_V"] = gV
            row["coverage"] = cov; row["downscale"] = s
        del P
    except Exception as e:
        row["error"] = repr(e)[:500]
    finally:
        if mm_dir is not None:
            import shutil; P = None; shutil.rmtree(mm_dir, ignore_errors=True)
    row["elapsed_s"] = round(time.time() - t0, 2)
    return row


def main():
    out, workers, lo, hi = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    md = load_catalog()
    done = set()
    if Path(out).exists():
        done = {json.loads(l)["path"] for l in open(out) if '"error"' not in l}
    tasks = []
    for s, e in md["samples"].items():
        for g, seg in e["segments"].items():
            for d in seg.get("data", []):
                if d["type"] in MESH_TYPES:
                    p = d["origins"][0]["path"]
                    nb = sum(LISTING[p]["files"][f]["bytes"] for f in ("x.tif", "y.tif", "z.tif"))
                    if lo <= nb < hi and p not in done:
                        tasks.append((nb, (s, g, d["type"], p)))
    tasks.sort(key=lambda x: -x[0])
    print(f"{len(tasks)} meshes to scan ({sum(t[0] for t in tasks)/1e9:.1f} GB compressed), {len(done)} already done", flush=True)
    n = 0
    with ProcessPoolExecutor(workers) as ex, open(out, "a") as f:
        futs = [ex.submit(work, t) for _, t in tasks]
        for fu in as_completed(futs):
            r = fu.result(); f.write(json.dumps(r) + "\n"); f.flush(); n += 1
            if n % 25 == 0 or "error" in r:
                print(n, r["type"], r["path"][-70:], r.get("error", ""), r["elapsed_s"], flush=True)
    print("done", n, flush=True)


if __name__ == "__main__":
    main()
