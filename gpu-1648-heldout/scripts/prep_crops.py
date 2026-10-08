"""Build the L2 and L0 prepared inputs for each held-out case, fetching only the source chunks
near its validation mask, then run villa's own prepare_9um_isotropic_input on the local source crop.

Per case (labels/masks from the HF aligned-21slice set, channel 10):
  crop (L2 px) = validation-mask bbox +/- 128, clipped to the L2 shape; L0 crop = same region x4.
  L2 source chunks fetched: those intersecting the mask dilated by 128 L2 px (one model patch at L2).
  L0 source chunks fetched: those intersecting the mask dilated by 32 L2 px = 128 L0 px (one patch at L0).
  Unfetched chunks inside the crop stay 0 (fill); no model patch covering a mask pixel reaches them.
  prepare: villa prepare_isotropic_input (centered 84 of 109 planes = [13, 97], rounded mean of 4, uint8).
"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, zarr
from numcodecs import Blosc
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data-do-not-redistribute"
CASES = ["pherc0139-w016", "pherc0814-46527", "pherc1667-w029"]
CH = 10; MARGIN_CROP = 128; MARGIN = {2: 128, 0: 32}; SCALE = {2: 1, 0: 4}; CHUNK = 128

def get_bytes(url):
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gpu-1648-heldout"}), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            if attempt == 5: raise
        except Exception:
            if attempt == 5: raise
        time.sleep(2 * (attempt + 1))

def main():
    sys.path.insert(0, sys.argv[1])  # villa vesuvius/src
    from vesuvius.ink_detection.preprocessing.prepare_9um_isotropic_input import prepare_isotropic_input
    out = {}
    for case in CASES:
        attrs = json.load(open(ROOT / "meta" / f"{case}_validation_mask.zattrs.json"))
        base = attrs["source_surface_volume"].replace("s3.amazonaws.com", "s3.us-east-1.amazonaws.com")
        assert attrs["source_surface_volume_level"] == 2 and attrs["source_z_slice"] == [13, 97]
        M = zarr.open_array(str(DATA / "labels" / f"{case}_validation_mask.zarr" / "0"), mode="r", zarr_format=2)[CH] > 0
        H, W = M.shape
        ys, xs = np.nonzero(M)
        y0, y1 = int(max(0, ys.min() - MARGIN_CROP)), int(min(H, ys.max() + 1 + MARGIN_CROP))
        x0, x1 = int(max(0, xs.min() - MARGIN_CROP)), int(min(W, xs.max() + 1 + MARGIN_CROP))
        rec = {"crop_l2_yx": [int(y0), int(y1), int(x0), int(x1)], "source_surface_volume": attrs["source_surface_volume"], "levels": {}}
        for level in (2, 0):
            s = SCALE[level]
            za = json.loads(get_bytes(f"{base}/{level}/.zarray"))
            assert za["dtype"] == "|u1" and za["chunks"][1:] == [CHUNK, CHUNK] and za["shape"][0] == 109
            assert za["shape"][1] == H * s and za["shape"][2] == W * s, (za["shape"], H, W, s)
            D = ndimage.binary_dilation(M, structure=np.ones((3, 3), bool), iterations=MARGIN[level])
            dy, dx = np.nonzero(D)
            cpx = CHUNK // s  # one source chunk spans cpx L2 px
            cells = sorted(set(zip((dy // cpx).tolist(), (dx // cpx).tolist())))
            sep = za.get("dimension_separator", ".")
            cdir = DATA / "s3cache" / case / str(level); cdir.mkdir(parents=True, exist_ok=True)
            def fetch(cell):
                cy, cx = cell; f = cdir / f"{cy}_{cx}.raw"
                if f.exists(): return f.stat().st_size, True
                b = get_bytes(f"{base}/{level}/0{sep}{cy}{sep}{cx}")
                if b is None: return 0, False
                f.write_bytes(b); return len(b), True
            with ThreadPoolExecutor(16) as ex: res = list(ex.map(fetch, cells))
            nbytes = sum(r[0] for r in res); present = sum(1 for r in res if r[1])
            # local bare source crop at this level
            Y0, Y1, X0, X1 = y0 * s, y1 * s, x0 * s, x1 * s
            src_path = DATA / "work" / f"{case}_L{level}_source.zarr"
            if src_path.exists(): import shutil; shutil.rmtree(src_path)
            src = zarr.open_array(str(src_path), mode="w", shape=(109, Y1 - Y0, X1 - X0), chunks=(109, CHUNK, CHUNK), dtype=np.uint8,
                                  fill_value=0, zarr_format=2, compressor=Blosc(cname="zstd", clevel=3, shuffle=Blosc.BITSHUFFLE))
            for (cy, cx), (n, ok) in zip(cells, res):
                f = cdir / f"{cy}_{cx}.raw"
                if not ok or not f.exists(): continue
                buf = np.frombuffer(f.read_bytes(), dtype=np.uint8)
                assert za["compressor"] is None and buf.size == 109 * CHUNK * CHUNK, buf.size
                blk = buf.reshape(109, CHUNK, CHUNK)
                gy0, gx0 = cy * CHUNK, cx * CHUNK
                ly0, ly1 = max(gy0, Y0), min(gy0 + CHUNK, Y1); lx0, lx1 = max(gx0, X0), min(gx0 + CHUNK, X1)
                if ly1 <= ly0 or lx1 <= lx0: continue
                src[:, ly0 - Y0:ly1 - Y0, lx0 - X0:lx1 - X0] = blk[:, ly0 - gy0:ly1 - gy0, lx0 - gx0:lx1 - gx0]
            prep = DATA / "prepared" / f"{case}_L{level}.zarr"
            if prep.exists(): import shutil; shutil.rmtree(prep)
            prep.parent.mkdir(parents=True, exist_ok=True)
            prepare_isotropic_input(str(src_path), prep, level="0", workers=8)
            import shutil; shutil.rmtree(src_path)
            rec["levels"][f"L{level}"] = {"source_shape": za["shape"], "chunks_requested": len(cells), "chunks_present": present,
                                          "bytes_downloaded": nbytes, "prepared_shape": [21, Y1 - Y0, X1 - X0]}
            print(case, level, rec["levels"][f"L{level}"], flush=True)
        out[case] = rec
    json.dump(out, open(ROOT / "meta" / "crops.json", "w"), indent=1)

if __name__ == "__main__":
    main()
