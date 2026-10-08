"""Extra per-example evidence for classes S and W (metadata-derived numbers only).
S: per-axis mean 3D step between valid 4-neighbours, computed from villa's read_tifxyz arrays (independent of the
   scanner's histogram), and the level-0 canvas of the segment's published render on its original volume.
W: declared width/height vs read_tifxyz full_resolution_shape, and the level-0 canvas of the render on the original volume.
Usage: PYTHONPATH=<villa main>/vesuvius/src python -B evidence_s_w.py OUT_JSON"""
import json, sys, urllib.request
from pathlib import Path
from urllib.parse import quote
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import BUCKET, load_catalog
from vesuvius.tifxyz import read_tifxyz

XC = Path(__file__).resolve().parent.parent / "data" / "cache" / "xcheck"
S_EX = [("PHerc0814", "20260226113324"), ("PHerc0814", "20250928235954"), ("PHerc0814", "20260225160055")]
W_EX = [("PHerc0500P2", "20250919184432"), ("PHerc0500P2", "20250919184431"), ("PHerc0332", "20240828190516")]


def render_shape(seg, vol):
    for d in seg["data"]:
        if d["type"] == "layers-zarr" and (d.get("parameters") or {}).get("target_volume") == vol and not (d.get("parameters") or {}).get("render_level"):
            p = d["origins"][0]["path"]
            for z in ("0/.zarray", ".zarray"):
                try:
                    with urllib.request.urlopen(f"{BUCKET}/{quote(p + z, safe='/')}", timeout=60) as r:
                        return json.load(r)["shape"]
                except Exception:
                    pass
    return None


def mean_steps(t):
    P = np.stack([t._x, t._y, t._z], -1).astype(np.float64)
    ok = np.isfinite(P).all(-1) & (P[..., 0] != -1)
    du = np.linalg.norm(P[:, 1:] - P[:, :-1], axis=-1)[ok[:, 1:] & ok[:, :-1]]
    dv = np.linalg.norm(P[1:] - P[:-1], axis=-1)[ok[1:] & ok[:-1]]
    return float(du.mean()), float(dv.mean())


def mesh_dir(seg, typ):
    p = next(d for d in seg["data"] if d["type"] == typ)["origins"][0]["path"]
    return XC / p.strip("/").replace("/", "__"), p


def main():
    md = load_catalog(); out = {"S": [], "W": []}
    for s, g in S_EX:
        seg = md["samples"][s]["segments"][g]; ov = seg["original_volume_id"]
        d, p = mesh_dir(seg, "tifxyz-normalized"); t = read_tifxyz(d, load_mask=False)
        su, sv = json.loads((d / "meta.json").read_text())["scale"]
        mu, mv = mean_steps(t)
        out["S"].append({"sample": s, "segment": g, "mesh": p, "meta_scale": [su, sv], "declared_step_vx": [1 / su, 1 / sv],
                         "measured_mean_step_vx_u_v": [mu, mv], "ratio_u_v": [mu * su, mv * sv], "grid_rows_cols": list(t._x.shape),
                         "original_volume": ov, "render_on_original_volume_zyx": render_shape(seg, ov),
                         "declared_width_height": [seg["properties"].get("width"), seg["properties"].get("height")]})
    for s, g in W_EX:
        seg = md["samples"][s]["segments"][g]; ov = seg["original_volume_id"]
        d, p = mesh_dir(seg, "tifxyz"); t = read_tifxyz(d, load_mask=False)
        out["W"].append({"sample": s, "segment": g, "mesh": p, "declared_width_height": [seg["properties"]["width"], seg["properties"]["height"]],
                         "vesuvius_full_resolution_shape_hw": list(t.full_resolution_shape), "grid_rows_cols": list(t._x.shape),
                         "meta_scale": json.loads((d / "meta.json").read_text())["scale"], "original_volume": ov,
                         "original_volume_pixel_size_um": md["samples"][s]["volumes"][ov]["properties"].get("pixel_size_um"),
                         "render_on_original_volume_zyx": render_shape(seg, ov),
                         "creation_metadata_has_dimension_source": "dimension_source" in ((seg.get("creation") or {}).get("metadata") or {})})
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    for k in out:
        for r in out[k]:
            print(k, json.dumps({x: r[x] for x in r if x != "mesh"}))


if __name__ == "__main__":
    main()
