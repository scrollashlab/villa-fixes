"""Reproduce each published derived mesh of a segment from its normalized source + catalog matrix
(+ original_volume_downscale pre-scale + VC regrid) and measure the point residual, in bounded memory."""
from __future__ import annotations
import gc, math, time
import numpy as np
from . import geom
from .catalog import Catalog, Segment
from .tifxyz import Source, read_tifxyz

# frozen classes (cross-frame-toolkit/docs/protocol-2026-10-07.md), decided from exact exceedance counts:
#   CONSISTENT: <= 1% of compared cells have residual > 0.5 target voxel   (p99 <= 0.5)
#   DRIFT:      >  50% of compared cells have residual > 1 target voxel    (median > 1)
#   PARTIAL:    otherwise;  NOT_COMPARABLE: predicted grid shape != published grid shape
EDGES = np.concatenate([[0.0], np.logspace(-9, 7, 16 * 2000 + 1)])   # quantile bins: ~0.115% relative width


class _Acc:
    def __init__(self):
        self.hist = np.zeros(len(EDGES), np.int64); self.n = 0; self.max = 0.0
        self.gt05 = 0; self.gt1 = 0; self.gt10 = 0; self.sum = 0.0

    def add(self, r: np.ndarray):
        if r.size == 0: return
        self.n += r.size; self.max = max(self.max, float(r.max())); self.sum += float(r.sum())
        self.gt05 += int((r > 0.5).sum()); self.gt1 += int((r > 1).sum()); self.gt10 += int((r > 10).sum())
        idx = np.searchsorted(EDGES, r, side="right") - 1
        self.hist += np.bincount(np.clip(idx, 0, len(EDGES) - 1), minlength=len(EDGES))

    def quantile(self, q: float) -> float:
        if self.n == 0: return math.nan
        c = np.cumsum(self.hist); i = int(np.searchsorted(c, q * self.n, side="left"))
        return float(EDGES[min(i + 1, len(EDGES) - 1)])   # upper edge of the bin holding the quantile


def classify(acc: _Acc) -> str:
    if acc.n == 0: return "NO_OVERLAP"
    if acc.gt05 <= 0.01 * acc.n: return "CONSISTENT"
    if acc.gt1 > 0.5 * acc.n: return "DRIFT"
    return "PARTIAL"


def verify_mesh(cat: Catalog, seg: Segment, mesh, P_src: np.ndarray, src: Source | None, block_rows: int = 256) -> dict:
    t0 = time.time()
    r = dict(sample=seg.sample, segment=seg.id, long_id=seg.long_id, mesh=mesh.key, kind=mesh.kind,
             original_volume=seg.original_volume, target_volume=mesh.target_volume, downscale=seg.downscale,
             target_um=cat.voxel_um(seg.sample, mesh.target_volume) if mesh.target_volume else None)
    try:
        if mesh.kind == "copy":
            M, prov = np.hstack([np.eye(3), np.zeros((3, 1))]), {"how": "identity (byte copy)"}; prescale = 1.0
            Q, fac, pred_shape = P_src.astype(np.float32), None, P_src.shape[:2]
        else:
            M, prov = cat.matrix(seg.sample, seg.original_volume, mesh.target_volume); prescale = seg.downscale
            Q, fac, pred_shape = geom.transform_points_only(P_src, None if prov["how"] == "identity" else M, prescale)
        r.update(matrix=prov, prescale=prescale, regrid_factors=fac, predicted_shape=list(pred_shape))
        Pp, meta = read_tifxyz(src, mesh.key)
        H, W = Pp.shape[:2]
        r.update(published_shape=[H, W], published_scale=meta.get("scale"), shape_match=(H, W) == tuple(pred_shape))
        if not r["shape_match"]:
            r["class"] = "NOT_COMPARABLE"; return r
        acc = _Acc(); only_pred = only_pub = 0
        for a in range(0, H, block_rows):
            b = min(H, a + block_rows)
            R = geom.resample_linear_preserving_invalids(Q, H, W, (a, b)) if fac is not None else Q[a:b]
            vR = geom.valid_mask(R); vP = geom.valid_mask(Pp[a:b]); both = vR & vP
            only_pred += int((vR & ~vP).sum()); only_pub += int((~vR & vP).sum())
            acc.add(np.linalg.norm(R[both].astype(np.float64) - Pp[a:b][both].astype(np.float64), axis=1))
        um = r["target_um"]
        r.update(n_compared=acc.n, valid_only_predicted=only_pred, valid_only_published=only_pub,
                 median_vox=acc.quantile(0.5), p99_vox=acc.quantile(0.99), max_vox=acc.max,
                 frac_gt_0_5_vox=acc.gt05 / acc.n if acc.n else None, frac_gt_1_vox=acc.gt1 / acc.n if acc.n else None,
                 n_gt_10_vox=acc.gt10)
        if um:
            r.update(median_um=r["median_vox"] * um, p99_um=r["p99_vox"] * um, max_um=acc.max * um)
        r["class"] = classify(acc)
        del Pp; gc.collect()
    except FileNotFoundError as e:
        r["class"] = "ERROR"; r["error"] = f"missing: {e}"
    except Exception as e:  # report, never hide
        r["class"] = "ERROR"; r["error"] = repr(e)
    r["elapsed_s"] = round(time.time() - t0, 2)
    return r


def verify_segment(cat: Catalog, seg: Segment, src: Source | None, block_rows: int = 256, include_copies: bool = True) -> list:
    norm = seg.normalized
    targets = [m for m in seg.meshes if m.kind == "derived" or (include_copies and m.kind == "copy")]
    if not targets:
        return []
    if norm is None:
        return [{"sample": seg.sample, "segment": seg.id, "mesh": m.key, "kind": m.kind, "class": "ERROR",
                 "error": "segment has no tifxyz-normalized source"} for m in targets]
    try:
        P_src, _ = read_tifxyz(src, norm.key)
    except Exception as e:
        return [{"sample": seg.sample, "segment": seg.id, "mesh": m.key, "kind": m.kind, "class": "ERROR",
                 "error": f"normalized source unreadable: {e!r}"} for m in targets]
    return [verify_mesh(cat, seg, m, P_src, src, block_rows) for m in sorted(targets, key=lambda m: m.key)]
