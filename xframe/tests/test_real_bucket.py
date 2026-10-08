"""Live checks against the public open-data bucket (CC BY-NC 4.0; only pytest's temporary directory is written).
Opt-in: XFRAME_REAL=1 pytest tests/test_real_bucket.py"""
import os
import numpy as np
import pytest
from xframe import geom
from xframe.catalog import Catalog
from xframe.convert import convert_tifxyz, resolve
from xframe.tifxyz import Source, read_tifxyz
from xframe.verify import verify_segment

pytestmark = pytest.mark.skipif(os.environ.get("XFRAME_REAL") != "1", reason="set XFRAME_REAL=1 for live bucket tests")
SAMPLE, SEG = "PHerc0139", "20250108000004"          # w029: downscale 4, five derived meshes (9.362 .. 1.129 um)


@pytest.fixture(scope="module")
def ctx():
    src = Source(); return Catalog.load(None, src), src


def test_real_verify_downscale_segment(ctx):
    cat, src = ctx
    rows = verify_segment(cat, cat.segment(SAMPLE, SEG), src)
    assert len(rows) == 5
    for r in rows:
        assert r["class"] == "CONSISTENT", r
        assert r["shape_match"] and r["valid_only_predicted"] == 0 and r["valid_only_published"] == 0


def test_real_wrong_prescale_is_caught(ctx):
    cat, src = ctx
    seg = cat.segment(SAMPLE, SEG); seg.downscale = 1.0           # negative control: ignore the downscale
    rows = [r for r in verify_segment(cat, seg, src) if "9.362um" in r["mesh"]]
    assert rows and rows[0]["class"] in ("NOT_COMPARABLE", "DRIFT")


def test_real_convert_matches_published(ctx, tmp_path):
    cat, src = ctx
    seg = cat.segment(SAMPLE, SEG)
    tgt = [m for m in seg.meshes if m.kind == "derived" and "9.362um" in m.key][0]
    M, prov = resolve(cat, SAMPLE, None, tgt.target_volume, SEG, None)
    convert_tifxyz(src, seg.normalized.key, str(tmp_path / "out"), M, prov)
    Q, _ = read_tifxyz(None, str(tmp_path / "out")); Pp, _ = read_tifxyz(src, tgt.key)
    assert Q.shape == Pp.shape
    ok = geom.valid_mask(Q) & geom.valid_mask(Pp)
    assert np.percentile(np.linalg.norm(Q[ok].astype(float) - Pp[ok], axis=1), 99) < 0.5
