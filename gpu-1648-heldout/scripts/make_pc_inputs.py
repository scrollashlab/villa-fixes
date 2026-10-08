"""Box side: build the PC phase-2 inputs from the prepared crops.

Writes (all under data-do-not-redistribute/pc-transfer, CC BY-NC derived, never published):
  masks/<case>_L2_mask.tif, masks/<case>_L0_mask.tif  (validation mask on the run grid; L0 = nearest x4)
  parts/prepared-partNN.zip                            (stored zips of the prepared zarr files, each <= 90 MiB)
and a metadata-only manifest pc/phase2/inputs-manifest.json (decoded-array sha256 per prepared input,
crop boxes, mask sha256s) that the PC verifies before running.
"""
import hashlib, json, sys, zipfile
from pathlib import Path
import numpy as np, tifffile, zarr

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data-do-not-redistribute"
CASES = ["pherc0814-46527", "pherc0139-w016", "pherc1667-w029"]
LIMIT = 36 * 1024 * 1024

def main():
    crops = json.load(open(ROOT / "meta" / "crops.json"))
    out = DATA / "pc-transfer"; (out / "masks").mkdir(parents=True, exist_ok=True); (out / "parts").mkdir(parents=True, exist_ok=True)
    for p in (out / "parts").glob("*.zip"): p.unlink()
    man = {"cases": {}, "parts": []}
    for case in CASES:
        y0, y1, x0, x1 = crops[case]["crop_l2_yx"]
        M = zarr.open_array(str(DATA / "labels" / f"{case}_validation_mask.zarr" / "0"), mode="r", zarr_format=2)[10][y0:y1, x0:x1] > 0
        rec = {"crop_l2_yx": [y0, y1, x0, x1], "levels": {}}
        for lv, s in (("L2", 1), ("L0", 4)):
            m = M if s == 1 else np.repeat(np.repeat(M, s, 0), s, 1)
            m8 = m.astype(np.uint8) * 255
            mp = out / "masks" / f"{case}_{lv}_mask.tif"
            tifffile.imwrite(mp, m8, compression="zlib")
            a = zarr.open_array(str(DATA / "prepared" / f"{case}_{lv}.zarr" / "0"), mode="r")[:]
            assert a.shape == (21, (y1 - y0) * s, (x1 - x0) * s), (case, lv, a.shape)
            rec["levels"][lv] = {"prepared_shape": list(a.shape), "prepared_sha256": hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest(),
                                 "mask_sha256": hashlib.sha256(np.ascontiguousarray(m8).tobytes()).hexdigest(), "mask_px": int(m.sum())}
            print(case, lv, a.shape, int(m.sum()), flush=True)
        man["cases"][case] = rec
    # split the prepared zarr files into stored zips <= LIMIT
    files = sorted(p for p in (DATA / "prepared").rglob("*") if p.is_file())
    part, size, zf = 0, 0, None
    for f in files:
        n = f.stat().st_size
        if zf is None or size + n > LIMIT:
            if zf: zf.close()
            part += 1; size = 0
            zf = zipfile.ZipFile(out / "parts" / f"prep-a{part:02d}.zip", "w", zipfile.ZIP_STORED)
        zf.write(f, f.relative_to(DATA / "prepared").as_posix()); size += n
    zf.close()
    for p in sorted((out / "parts").glob("*.zip")):
        man["parts"].append({"name": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    json.dump(man, open(ROOT / "pc" / "phase2" / "inputs-manifest.json", "w"), indent=1)
    print(json.dumps(man["parts"], indent=1))

if __name__ == "__main__":
    main()
