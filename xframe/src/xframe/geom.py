"""Geometry primitives ported from villa volume-cartographer (core/src/AffineTransform.cpp,
core/src/QuadSurface.cpp @ e0bbb8b4) so Python reproduces vc_transform_geom exactly.

Points are float32 arrays of shape (rows, cols, 3) holding (x, y, z); invalid = x == -1 or non-finite.
"""
from __future__ import annotations
import math
import numpy as np

INVALID = np.float32(-1.0)


def valid_mask(P: np.ndarray) -> np.ndarray:
    """isValidPointSample: no component == -1 and all finite (the stricter of VC's two checks)."""
    return np.isfinite(P).all(-1) & ~(P == -1).any(-1)


def _vc_surface_valid(P: np.ndarray) -> np.ndarray:
    """isValidSurfacePoint: x != -1 and all finite (used by VC spacing measurement)."""
    return (P[..., 0] != -1) & np.isfinite(P).all(-1)


def _vc_median(v: np.ndarray) -> float:
    """medianValue: upper-middle element; for even n the mean of it and the max of the lower half."""
    n = len(v)
    if n == 0:
        return math.nan
    s = np.sort(v)
    mid = s[n // 2]
    if n % 2 == 0:
        return 0.5 * (mid + s[n // 2 - 1])
    return float(mid)


def measure_grid_axis_spacing(P: np.ndarray):
    """Port of measureGridAxisSpacing. Returns (x_spacing, x_count, y_spacing, y_count).
    x = distance to left neighbour (along columns), y = distance to upper neighbour (along rows)."""
    rows, cols = P.shape[:2]
    if rows < 2 or cols < 2:
        return math.nan, 0, math.nan, 0
    if rows < 20 or cols < 20:
        r0, r1, c0, c1, step = 1, rows, 1, cols, 1
    else:
        r0 = max(1, int(rows * 0.1)); r1 = int(rows * 0.9)
        c0 = max(1, int(cols * 0.1)); c1 = int(cols * 0.9)
        r1 = max(r0 + 1, r1); c1 = max(c0 + 1, c1); step = 4
    ri = np.arange(r0, r1, step); ci = np.arange(c0, c1, step)
    V = _vc_surface_valid(P)
    Pd = P.astype(np.float64)
    R, C = np.meshgrid(ri, ci, indexing="ij")
    here = V[R, C]
    out = []
    for dr, dc in ((0, -1), (-1, 0)):
        nb = V[R + dr, C + dc] & here
        d = np.linalg.norm(Pd[R, C] - Pd[R + dr, C + dc], axis=-1)[nb]
        d = d[np.isfinite(d) & (d > 0)]
        out.append((_vc_median(d), len(d)))
    (hx, nx), (vy, ny) = out
    return hx, nx, vy, ny


def uniform_scale_factor(M: np.ndarray):
    """affineUniformScaleFactor: mean singular value if all within 1e-4 relative, else None."""
    s = np.linalg.svd(np.asarray(M, float)[:3, :3], compute_uv=False)
    if not np.all(np.isfinite(s)) or np.any(s <= 0):
        return None
    m = s.mean()
    return float(m) if np.max(np.abs(s - m)) / m <= 1e-4 else None


def mean_linear_scale(M: np.ndarray) -> float:
    """Mean singular value of the linear part (descriptive; used by `explain`)."""
    return float(np.linalg.svd(np.asarray(M, float)[:3, :3], compute_uv=False).mean())


def invert_affine(M: np.ndarray) -> np.ndarray:
    M = np.asarray(M, float)
    A = np.linalg.inv(M[:3, :3])
    return np.hstack([A, (-A @ M[:3, 3])[:, None]])


def apply_affine(points: np.ndarray, M: np.ndarray, prescale: float = 1.0) -> np.ndarray:
    """Apply x' = M[:, :3] @ (prescale * x) + M[:, 3] to (..., 3) points in float64."""
    M = np.asarray(M, float)
    p = np.asarray(points, np.float64) * prescale
    return p @ M[:, :3].T + M[:, 3]


def _resample_coords(n_src: int, n_dst: int):
    scale = np.float32(n_src) / np.float32(n_dst)
    s = (np.arange(n_dst, dtype=np.float32) + np.float32(0.5)) * scale - np.float32(0.5)
    s = np.clip(s, np.float32(0), np.float32(n_src - 1)).astype(np.float32)
    i0 = np.floor(s).astype(np.int64)
    i1 = np.minimum(i0 + 1, n_src - 1)
    f = (s - i0.astype(np.float32)).astype(np.float32)
    return i0, i1, f


def resample_linear_preserving_invalids(P: np.ndarray, new_rows: int, new_cols: int,
                                        row_range: tuple | None = None) -> np.ndarray:
    """Port of resamplePointsLinearPreservingInvalids (half-pixel bilinear in float32; a destination
    cell is invalid (-1,-1,-1) if any of its 4 source corners is invalid).
    `row_range=(a, b)` returns only destination rows a..b-1 (for bounded-memory block processing)."""
    rows, cols = P.shape[:2]
    a, b = row_range if row_range else (0, new_rows)
    y0, y1, fy = _resample_coords(rows, new_rows)
    x0, x1, fx = _resample_coords(cols, new_cols)
    y0, y1, fy = y0[a:b], y1[a:b], fy[a:b]
    P = P.astype(np.float32, copy=False)
    V = valid_mask(P)
    ok = V[y0][:, x0] & V[y0][:, x1] & V[y1][:, x0] & V[y1][:, x1]
    FX = fx[None, :, None]; FY = fy[:, None, None]
    top = P[y0][:, x0] * (np.float32(1) - FX) + P[y0][:, x1] * FX
    bot = P[y1][:, x0] * (np.float32(1) - FX) + P[y1][:, x1] * FX
    R = top * (np.float32(1) - FY) + bot * FY
    R[~ok] = INVALID
    return R


def regrid_factors(P_before: np.ndarray, P_after: np.ndarray, prescale: float, M) -> tuple:
    """transformSurfacePoints regrid decision. Returns (factor_x, factor_y) as float32, or None if VC would not resample."""
    bx, bnx, by, bny = measure_grid_axis_spacing(P_before)
    tx, tnx, ty, tny = measure_grid_axis_spacing(P_after)
    sx = tx / bx if (bnx > 0 and tnx > 0 and math.isfinite(bx) and bx > 0 and math.isfinite(tx) and tx > 0) else math.nan
    sy = ty / by if (bny > 0 and tny > 0 and math.isfinite(by) and by > 0 and math.isfinite(ty) and ty > 0) else math.nan
    usf = uniform_scale_factor(M) if M is not None else None
    fallback = prescale * (usf if usf is not None else 1.0)
    if not (math.isfinite(sx) and sx > 0): sx = fallback
    if not (math.isfinite(sy) and sy > 0): sy = fallback
    if not (abs(sx - 1.0) > 1e-4 or abs(sy - 1.0) > 1e-4):
        return None
    fx, fy = np.float32(sx), np.float32(sy)
    if abs(fx - 1.0) < 0.001 and abs(fy - 1.0) < 0.001:   # QuadSurface::resample early return
        return None
    return float(fx), float(fy)


def regrid_shape(rows: int, cols: int, factors) -> tuple:
    if factors is None:
        return rows, cols
    fx, fy = np.float32(factors[0]), np.float32(factors[1])
    return max(1, int(round(float(np.float32(rows) * fy)))), max(1, int(round(float(np.float32(cols) * fx))))


def transform_surface(P: np.ndarray, M=None, prescale: float = 1.0):
    """Full vc_transform_geom tifxyz path: prescale, affine, VC spacing-based regrid.
    Returns (points float32 (r,c,3), info dict)."""
    Q, fac, (r, c) = transform_points_only(P, M, prescale)
    if fac is not None:
        Q = resample_linear_preserving_invalids(Q, r, c)
    return Q, {"regrid_factors": fac, "shape": [r, c]}


def transform_points_only(P: np.ndarray, M=None, prescale: float = 1.0):
    """Prescale + affine without regrid. Returns (Q float32, regrid factors, predicted shape)."""
    P = np.asarray(P, np.float32)
    V = valid_mask(P)
    Mx = np.hstack([np.eye(3), np.zeros((3, 1))]) if M is None else np.asarray(M, float)
    Q = np.full(P.shape, INVALID, np.float32)
    Q[V] = apply_affine(P[V], Mx, prescale).astype(np.float32)
    Q[~valid_mask(Q)] = INVALID
    fac = regrid_factors(P, Q, prescale, None if M is None else Mx)
    return Q, fac, regrid_shape(P.shape[0], P.shape[1], fac)


def predict_shape(P: np.ndarray, M=None, prescale: float = 1.0):
    """Grid shape vc_transform_geom would produce (needs only the source mesh)."""
    _, fac, shape = transform_points_only(P, M, prescale)
    return shape, fac
