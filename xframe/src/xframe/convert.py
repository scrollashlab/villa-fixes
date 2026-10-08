"""Convert user points (CSV) or a tifxyz mesh between scan frames exactly as the publishing pipeline does."""
from __future__ import annotations
import csv, datetime, json
import numpy as np
from . import __version__, geom
from .catalog import Catalog
from .tifxyz import Source, read_tifxyz, write_tifxyz


def resolve(cat: Catalog, sample: str, from_vol: str | None, to_vol: str, from_normalized_of: str | None, prescale: float | None):
    if from_normalized_of:
        seg = cat.segment(sample, from_normalized_of)
        from_vol = seg.original_volume
        if prescale is None: prescale = seg.downscale
    if not from_vol:
        raise ValueError("need --from VOLUME or --from-normalized-of SEGMENT")
    M, prov = cat.matrix(sample, from_vol, to_vol)
    prov = dict(prov, sample=sample, from_volume=from_vol, to_volume=to_vol, prescale=float(prescale or 1.0),
                from_um=cat.voxel_um(sample, from_vol), to_um=cat.voxel_um(sample, to_vol))
    return M, prov


def convert_csv(in_path: str, out_path: str, M, prov: dict) -> int:
    with open(in_path, newline="") as f:
        rd = csv.DictReader(f); rows = list(rd); fields = list(rd.fieldnames or [])
    for c in ("x", "y", "z"):
        if c not in fields: raise ValueError(f"CSV needs columns x,y,z (got {fields})")
    pts = np.array([[float(r["x"]), float(r["y"]), float(r["z"])] for r in rows], float).reshape(-1, 3)
    out = geom.apply_affine(pts, M, prov["prescale"]) if len(pts) else pts
    um = prov.get("to_um")
    extra = ["x_out", "y_out", "z_out"] + (["x_out_um", "y_out_um", "z_out_um"] if um else [])
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields + extra); w.writeheader()
        for r, p in zip(rows, out):
            r = dict(r); r.update(x_out=repr(float(p[0])), y_out=repr(float(p[1])), z_out=repr(float(p[2])))
            if um: r.update(x_out_um=repr(float(p[0] * um)), y_out_um=repr(float(p[1] * um)), z_out_um=repr(float(p[2] * um)))
            w.writerow(r)
    with open(out_path + ".provenance.json", "w") as f:
        json.dump(dict(prov, matrix=np.asarray(M).tolist(), n_points=len(rows), xframe_version=__version__), f, indent=2)
    return len(rows)


def convert_tifxyz(src: Source | None, in_key_or_dir: str, out_dir: str, M, prov: dict) -> dict:
    P, meta = read_tifxyz(src, in_key_or_dir)
    Q, info = geom.transform_surface(P, None if prov.get("how") == "identity" else M, prov["prescale"])
    V = geom.valid_mask(Q)
    lo = Q[V].min(0).tolist() if V.any() else [-1, -1, -1]; hi = Q[V].max(0).tolist() if V.any() else [-1, -1, -1]
    new_meta = dict(meta)
    new_meta["bbox"] = [lo, hi]                     # scale is kept, as vc_transform_geom does (see villa #1522)
    if prov.get("to_um"): new_meta["voxel_size_um"] = prov["to_um"]
    new_meta["xframe"] = dict(prov, matrix=np.asarray(M).tolist(), regrid_factors=info["regrid_factors"],
                              shape=info["shape"], version=__version__,
                              created=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write_tifxyz(out_dir, Q, new_meta)
    return dict(shape=info["shape"], regrid_factors=info["regrid_factors"], n_valid=int(V.sum()))
