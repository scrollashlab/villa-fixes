"""Build the region masks and packed labels that pc/run_mid.py reads, from the public PHerc0841 label TIFFs.

Inputs: meta/from-label-free-selector/heldout-plan.json (crop boxes, level-1 shapes, counts) and the public label
TIFFs (CC BY-NC 4.0; downloaded from the URLs below into <root>/data-do-not-redistribute/labels/ if absent).
Rule (same as the plan): on the render's level-1 grid, region R = all 4 level-0 pixels inside supervision_mask_v2 AND
validation_mask_v2; ink = at least 2 of the 4 level-0 pixels > 0 in inklabels_v2, restricted to R; cropped to crop_yx.
Writes (local only, never redistributed):
  <root>/data-do-not-redistribute/lfs/masks/<seg>_region_mask.tif
  <root>/data-do-not-redistribute/lfs/labels/<seg>.npz
Usage: python -B scripts/make_region_labels.py [<root>]   (default root: this bundle)"""
import json, sys, urllib.request
from pathlib import Path
import numpy as np, tifffile
B = Path(__file__).resolve().parents[1]
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else B
PLAN = json.load(open(B / "meta" / "from-label-free-selector" / "heldout-plan.json"))
URL = "https://huggingface.co/buckets/scrollprize/datasets/resolve/"
SEGS = {"pherc0841-w00": ("ink/841/w00/", "w00"),
        "pherc0841-ag144": ("ink/841/auto_grown_20260220144552896/", "auto_grown_20260220144552896"),
        "pherc0841-ag174": ("ink/841/auto_grown_20260220174252405/", "auto_grown_20260220174252405")}
LAB = ROOT / "data-do-not-redistribute" / "labels"; OUT = ROOT / "data-do-not-redistribute" / "lfs"

def rd(prefix, name):
    f = LAB / f"{name}.tif"
    if not f.exists():
        LAB.mkdir(parents=True, exist_ok=True)
        f.write_bytes(urllib.request.urlopen(urllib.request.Request(URL + prefix + f.name, headers={"User-Agent": "labels"}), timeout=300).read())
    a = tifffile.imread(f)
    if a.ndim == 3: a = a[..., 0] if a.shape[-1] < 5 else a[0]
    return a > 0

def pool4(b, H1, W1, mode):
    H0, W0 = b.shape; P = np.zeros((2 * H1, 2 * W1), bool); P[:min(H0, 2 * H1), :min(W0, 2 * W1)] = b[:2 * H1, :2 * W1]
    s = P.reshape(H1, 2, W1, 2).sum(axis=(1, 3))
    return s == 4 if mode == "all" else s >= 2

def main():
    (OUT / "masks").mkdir(parents=True, exist_ok=True); (OUT / "labels").mkdir(parents=True, exist_ok=True)
    for seg, (prefix, stem) in SEGS.items():
        p = PLAN[seg]; _, H1, W1 = p["level1_shape"]; y0, y1, x0, x1 = p["crop_yx"]
        reg0 = rd(prefix, f"{stem}_supervision_mask_v2") & rd(prefix, f"{stem}_validation_mask_v2")
        R = pool4(reg0, H1, W1, "all"); I = pool4(rd(prefix, f"{stem}_inklabels_v2"), H1, W1, "half") & R
        assert int(R.sum()) == p["region_px"] and int(I.sum()) == p["pos"], (seg, int(R.sum()), int(I.sum()))
        Rc, Ic = R[y0:y1, x0:x1], I[y0:y1, x0:x1]
        tifffile.imwrite(OUT / "masks" / f"{seg}_region_mask.tif", Rc.astype(np.uint8) * 255, compression="zlib")
        np.savez_compressed(OUT / "labels" / f"{seg}.npz", shape=np.array(Rc.shape), region=np.packbits(Rc.ravel()),
                            ink=np.packbits((Ic & Rc).ravel()))
        print(seg, Rc.shape, int(Rc.sum()), int(Ic.sum()), flush=True)

if __name__ == "__main__":
    main()
