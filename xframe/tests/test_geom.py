import math
import numpy as np
import pytest
from xframe import geom
from conftest import curved_surface


def ref_resample(P, H, W):
    """Independent per-pixel transcription of villa resamplePointsLinearPreservingInvalids."""
    rows, cols = P.shape[:2]
    out = np.full((H, W, 3), -1, np.float32)
    xs = np.float32(cols) / np.float32(W); ys = np.float32(rows) / np.float32(H)
    ok = lambda p: not (p == -1).any() and np.isfinite(p).all()
    for dy in range(H):
        sy = min(max((np.float32(dy) + np.float32(0.5)) * ys - np.float32(0.5), np.float32(0)), np.float32(rows - 1))
        y0 = int(math.floor(sy)); y1 = min(y0 + 1, rows - 1); fy = np.float32(sy - np.float32(y0))
        for dx in range(W):
            sx = min(max((np.float32(dx) + np.float32(0.5)) * xs - np.float32(0.5), np.float32(0)), np.float32(cols - 1))
            x0 = int(math.floor(sx)); x1 = min(x0 + 1, cols - 1); fx = np.float32(sx - np.float32(x0))
            p00, p01, p10, p11 = P[y0, x0], P[y0, x1], P[y1, x0], P[y1, x1]
            if not (ok(p00) and ok(p01) and ok(p10) and ok(p11)): continue
            top = p00 * (np.float32(1) - fx) + p01 * fx; bot = p10 * (np.float32(1) - fx) + p11 * fx
            out[dy, dx] = top * (np.float32(1) - fy) + bot * fy
    return out


@pytest.mark.parametrize("H,W", [(37, 23), (80, 100), (13, 11)])
def test_resample_matches_reference(H, W):
    P = curved_surface(20, 25, invalid_frac=0.15, seed=H)
    np.testing.assert_array_equal(geom.resample_linear_preserving_invalids(P, H, W), ref_resample(P, H, W))


def test_resample_row_blocks_equal_full():
    P = curved_surface(30, 30, seed=3)
    full = geom.resample_linear_preserving_invalids(P, 97, 61)
    parts = [geom.resample_linear_preserving_invalids(P, 97, 61, (a, min(97, a + 10))) for a in range(0, 97, 10)]
    np.testing.assert_array_equal(np.concatenate(parts), full)


def test_vc_median():
    assert geom._vc_median(np.array([3.0, 1.0, 2.0])) == 2.0
    assert geom._vc_median(np.array([4.0, 1.0, 3.0, 2.0])) == 2.5
    assert math.isnan(geom._vc_median(np.array([])))


def test_measure_spacing_plane_grid():
    v, u = np.meshgrid(np.arange(60), np.arange(70), indexing="ij")
    P = np.stack([u * 20.0, v * 15.0, np.zeros_like(u, float)], -1).astype(np.float32)
    hx, nx, vy, ny = geom.measure_grid_axis_spacing(P)
    assert hx == pytest.approx(20.0) and vy == pytest.approx(15.0) and nx > 0 and ny > 0


def test_transform_surface_prescale_only_upsamples_4x():
    P = curved_surface(40, 50, invalid_frac=0.0)
    Q, info = geom.transform_surface(P, None, 4.0)
    assert info["shape"] == [160, 200]
    # bilinear resample of a 4x-scaled grid == 4 x bilinear resample of the source (affine commutes with lerp)
    R = geom.resample_linear_preserving_invalids(P, 160, 200)
    ok = geom.valid_mask(R) & geom.valid_mask(Q)
    assert ok.sum() > 0.8 * ok.size
    np.testing.assert_allclose(Q[ok], 4 * R[ok], rtol=0, atol=1e-2)


def test_transform_surface_downscale_by_matrix():
    P = curved_surface(40, 50, invalid_frac=0.0)
    M = np.array([[0.5, 0, 0, 10], [0, 0.5, 0, 20], [0, 0, 0.5, 30]])
    Q, info = geom.transform_surface(P, M, 1.0)
    r, c = info["shape"]
    assert abs(r - 20) <= 2 and abs(c - 25) <= 2      # spacing-measured factor ~0.5 on a curved sheet


def test_no_regrid_for_identity():
    P = curved_surface()
    Q, info = geom.transform_surface(P, None, 1.0)
    assert info["regrid_factors"] is None
    np.testing.assert_array_equal(Q[geom.valid_mask(P)], P[geom.valid_mask(P)])


def test_invert_and_uniform_scale():
    M = np.array([[0.4, 0.01, 0.0, 12.5], [-0.01, 0.4, 0.002, -7.0], [0.0, -0.002, 0.4, 30.0]])
    p = np.array([[100.0, 200.0, 300.0], [5.0, -3.0, 1e4]])
    np.testing.assert_allclose(geom.apply_affine(geom.apply_affine(p, M), geom.invert_affine(M)), p, atol=1e-9)
    assert geom.uniform_scale_factor(np.diag([2.0, 2.0, 2.0])) == pytest.approx(2.0)
    assert geom.uniform_scale_factor(np.array([[1, 0.5, 0], [0, 1, 0], [0, 0, 1.0]])) is None
