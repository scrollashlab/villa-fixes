"""Synthetic unit tests for the audit scanner and analysis predicates (no network, no payloads)."""
import math, sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scan_meshes as sm  # noqa: E402
import analyze as an      # noqa: E402
from common import holdout  # noqa: E402


def grid(H, W, step=1.0, z=0.0):
    v, u = np.mgrid[0:H, 0:W].astype(np.float32)
    return np.stack([u * step, v * step, np.full_like(u, z)], -1).astype(np.float32)


def naive_area(P):
    good = np.isfinite(P).all(-1) & ~(P == -1).all(-1)
    tot = 0.0
    for i in range(P.shape[0] - 1):
        for j in range(P.shape[1] - 1):
            p00, p10, p01, p11 = P[i, j], P[i, j + 1], P[i + 1, j], P[i + 1, j + 1]
            for a, b, c, ok in ((p00, p10, p11, good[i, j] & good[i, j + 1] & good[i + 1, j + 1]),
                                (p00, p11, p01, good[i, j] & good[i + 1, j + 1] & good[i + 1, j])):
                if ok:
                    tot += 0.5 * np.linalg.norm(np.cross((b - a).astype(float), (c - a).astype(float)))
    return tot


def test_masks_vc_vs_strict():
    B = np.array([[[1, 2, 3], [-1, -1, -1], [5, -1, 2], [np.nan, 1, 1], [-1, 4, 4]]], np.float32)
    vc, strict = sm.masks(B)
    assert vc.tolist() == [[True, False, True, False, False]]
    assert strict.tolist() == [[True, False, False, False, False]]


def test_point_stats_flat_grid_across_blocks():
    H, W = 2 * sm.BLOCK + 7, 5          # crosses two block boundaries
    st = sm.point_stats(grid(H, W, 2.0))
    assert st["rows"] == H and st["cols"] == W
    assert st["n_valid_vc"] == st["n_valid_strict"] == H * W
    assert st["bbox_vc"] == [[0.0, 0.0, 0.0], [2.0 * (W - 1), 2.0 * (H - 1), 0.0]]
    assert st["n_pairs"] == H * (W - 1) + (H - 1) * W   # every 4-neighbour pair counted once
    assert abs(st["spacing_median"] / 2.0 - 1) < 2e-4
    assert st["area_vx2_computed"] == pytest.approx(4.0 * (H - 1) * (W - 1), rel=1e-12)


def test_point_stats_sentinels_and_nan_match_naive_area():
    rng = np.random.default_rng(0)
    P = grid(sm.BLOCK + 40, 9, 1.5) + rng.normal(0, 0.2, (sm.BLOCK + 40, 9, 3)).astype(np.float32)
    P[3:6, 2:4] = -1
    P[sm.BLOCK - 1:sm.BLOCK + 2, 5] = np.nan       # straddles the block boundary
    P[100, 7, 1] = -1                              # strict-invalid only
    st = sm.point_stats(P)
    assert st["area_vx2_computed"] == pytest.approx(naive_area(P), rel=1e-9)
    vc, strict = sm.masks(P)
    assert st["n_valid_vc"] == int(vc.sum()) and st["n_valid_strict"] == int(strict.sum())
    assert st["bbox_vc"] == [list(map(float, P[vc].min(0))), list(map(float, P[vc].max(0)))]
    assert st["bbox_strict"] == [list(map(float, P[strict].min(0))), list(map(float, P[strict].max(0)))]


class FakeCat:
    def __init__(self, M): self.M = M
    def matrix(self, sample, src, dst):
        if dst == src: return np.hstack([np.eye(3), np.zeros((3, 1))]), {"how": "identity"}
        if dst == "V2": return self.M, {"how": "forward"}
        raise KeyError(dst)


def test_coverage_inside_fraction_and_transform(monkeypatch):
    P = grid(10, 10, 1.0, z=1.0)                     # x,y in 0..9
    M = np.array([[0, 1, 0, 100.0], [1, 0, 0, 0.0], [0, 0, 1, 0.0]])   # swap x/y, shift x by 100
    monkeypatch.setattr(sm, "SHAPES", {("S", "V1"): [5, 8, 8], ("S", "V2"): [5, 20, 105]})
    seg = {"original_volume_id": "V1",
           "properties": {"original_volume_downscale": 2, "volume_coverage": {"V1": {}, "V2": {}, "V3": {}}}}
    cov, s = sm.coverage(P, "S", seg, FakeCat(M))
    assert s == 2.0
    # V1: points scaled by 2 -> x,y in 0..18 step 2, z=2; bounds x,y<=7, z<=4 -> x,y in {0,2,4,6}: 16/100
    assert cov["V1"]["vc"]["inside_frac"] == pytest.approx(0.16)
    assert cov["V1"]["vc"]["bbox"] == [[0, 0, 2], [18, 18, 2]]
    # V2: x' = 2y + 100 (0..18 -> 100..118), y' = 2x; bounds x'<=104, y'<=19 -> 2y+100<=104 -> y in {0,1,2}: 30/100
    assert cov["V2"]["vc"]["bbox"] == [[100, 0, 2], [118, 18, 2]]
    assert cov["V2"]["vc"]["inside_frac"] == pytest.approx(0.30)
    assert cov["V2"]["sigma_max"] == pytest.approx(1.0)
    assert cov["V3"] == {"no_transform": True}


def test_fisher_matches_known_values():
    # R fisher.test(matrix(c(3,1,1,3),2)) p = 0.4857
    assert an.fisher_two_sided(3, 1, 1, 3) == pytest.approx(0.485714, abs=1e-6)
    assert an.fisher_two_sided(10, 0, 0, 10) == pytest.approx(2 / math.comb(20, 10), rel=1e-9)
    assert an.fisher_two_sided(5, 5, 5, 5) == pytest.approx(1.0)


def test_px_ok_rules():
    assert an.px_ok("7.91", 7.91, "x-7.91um-y") == (True, True)
    assert an.px_ok("7.9", 7.91, "x-7.9um-y") == (True, True)          # rounding to printed decimals
    assert an.px_ok("8.00", 7.91, "x-8.00um-y") == (True, False)       # long_id only -> quirk, not defect
    assert an.px_ok("3.24", 7.91, "x-7.91um-y")[0] is False
    assert an.px_ok("15.82", 7.91, "x-7.91um-y", level=1)[0] is True   # render level effective size


def test_parse_date():
    assert an.parse_date("2024-01-02T03:04:05Z").year == 2024
    assert an.parse_date("2024-01-02").tzinfo is not None
    assert an.parse_date("garbage") is None and an.parse_date(None) is None


def test_holdout_deterministic_and_about_30pct():
    xs = [holdout("S", str(i)) for i in range(5000)]
    assert xs == [holdout("S", str(i)) for i in range(5000)]
    assert 0.27 < sum(xs) / len(xs) < 0.33


def test_memmap_reader_matches_in_memory(tmp_path, monkeypatch):
    import io, json as _json, tifffile
    rng = np.random.default_rng(1)
    P = grid(sm.BLOCK + 13, 11, 3.0) + rng.normal(0, 0.5, (sm.BLOCK + 13, 11, 3)).astype(np.float32)
    P[5:9, 1:3] = -1
    files = {}
    for i, c in enumerate("xyz"):
        b = io.BytesIO(); tifffile.imwrite(b, P[..., i], compression="zlib"); files[f"m/{c}.tif"] = b.getvalue()
    files["m/meta.json"] = _json.dumps({"scale": [0.3, 0.3]}).encode()
    monkeypatch.setattr(sm, "get", lambda key, tries=5: files[key])
    A, _ = sm.read_mesh("m/")
    mm = tmp_path / "mm"; mm.mkdir()
    Bm, meta = sm.read_mesh("m/", str(mm))
    assert isinstance(Bm, sm.RowStack) and Bm.shape == A.shape and meta["scale"] == [0.3, 0.3]
    assert np.array_equal(Bm[0:Bm.shape[0]], A)
    assert sm.point_stats(A) == sm.point_stats(Bm)
