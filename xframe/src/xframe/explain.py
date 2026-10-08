"""Describe every mesh of a segment: role, frame, voxel size, transform provenance, and what the grid density means."""
from __future__ import annotations
import numpy as np
from . import geom
from .catalog import Catalog, Segment
from .tifxyz import Source, read_meta


def _step_um(meta: dict, um):
    sc = meta.get("scale")
    if not sc or not um: return None
    return float(np.mean([1.0 / float(s) for s in sc])) * um


def explain_segment(cat: Catalog, seg: Segment, src: Source | None, fetch_meta: bool = True) -> dict:
    ov_um = cat.voxel_um(seg.sample, seg.original_volume) if seg.original_volume else None
    out = dict(sample=seg.sample, segment=seg.id, long_id=seg.long_id, traced_volume=seg.original_volume,
               traced_um=ov_um, original_volume_downscale=seg.downscale, meshes=[])
    norm_meta = None
    if seg.normalized is not None and fetch_meta:
        try: norm_meta = read_meta(src, seg.normalized.key)
        except Exception as e: out["normalized_meta_error"] = repr(e)
    src_step = _step_um(norm_meta, (ov_um or 0) * seg.downscale) if norm_meta else None
    out["source_step_um"] = src_step
    if seg.downscale != 1:
        out["warning"] = (f"tifxyz_normalized coordinates are in the 1/{seg.downscale:g} grid of volume {seg.original_volume}; "
                          f"multiply by {seg.downscale:g} before applying any catalog transform (not stated in the mesh's meta.json).")
    for m in sorted(seg.meshes, key=lambda m: (m.kind, m.key)):
        row = dict(kind=m.kind, key=m.key, target_volume=m.target_volume, process=m.process)
        if m.kind in ("derived", "copy") and m.target_volume:
            tum = cat.voxel_um(seg.sample, m.target_volume); row["target_um"] = tum
            if m.kind == "copy":
                row["grid"] = "byte copy of the normalized source (same coordinates)"; row["linear_factor"] = 1.0
            else:
                try:
                    M, prov = cat.matrix(seg.sample, seg.original_volume, m.target_volume)
                    k = geom.mean_linear_scale(M) * seg.downscale
                    row.update(matrix=prov, linear_factor=k, approx_cell_ratio=k * k)
                    if k > 1.05:
                        row["grid"] = f"UP-sampled ~{k:.2f}x per axis (~{k*k:.1f}x cells): bilinear interpolation of the source, no new traced geometry"
                    elif k < 0.95:
                        row["grid"] = f"DOWN-sampled ~{k:.2f}x per axis: decimated from the source (geometry lost)"
                    else:
                        row["grid"] = "about the same density as the source"
                except KeyError as e:
                    row["matrix_error"] = str(e)
            if fetch_meta:
                try:
                    mm = read_meta(src, m.key); row["declared_scale"] = mm.get("scale")
                    row["nominal_step_um"] = _step_um(mm, tum); row["source_step_um"] = src_step
                except Exception as e:
                    row["meta_error"] = repr(e)
        elif m.kind == "normalized":
            row.update(target_volume=seg.original_volume, frame_note=f"volume {seg.original_volume} at 1/{seg.downscale:g} scale" if seg.downscale != 1 else f"volume {seg.original_volume}",
                       source_step_um=src_step, declared_scale=norm_meta.get("scale") if norm_meta else None)
        out["meshes"].append(row)
    return out


def format_explain(d: dict) -> str:
    L = [f"{d['sample']} / {d['long_id']}",
         f"  traced on volume {d['traced_volume']} ({d['traced_um']} um), original_volume_downscale={d['original_volume_downscale']:g}"
         + (f", source grid step ~{d['source_step_um']:.1f} um" if d.get("source_step_um") else "")]
    if d.get("warning"): L.append(f"  WARNING: {d['warning']}")
    for m in d["meshes"]:
        head = f"  [{m['kind']}] {m['key'].rstrip('/').split('/')[-1]}"
        if m["kind"] in ("derived", "copy"):
            head += f"  -> volume {m['target_volume']} ({m.get('target_um')} um)"
            if m.get("nominal_step_um"): head += f", nominal step {m['nominal_step_um']:.1f} um"
            L.append(head)
            if m.get("grid"): L.append(f"      grid: {m['grid']}")
            if m.get("matrix"): L.append(f"      transform: {m['matrix'].get('how')} {m['matrix'].get('derivation_path') or ''}".rstrip())
            for k in ("matrix_error", "meta_error"):
                if m.get(k): L.append(f"      {k}: {m[k]}")
        else:
            L.append(head + (f"  ({m['frame_note']})" if m.get("frame_note") else ""))
    L.append("  note: matrix correctness is not checked here; see villa #1835 / PR #1994 for landmark checks.")
    return "\n".join(L)
