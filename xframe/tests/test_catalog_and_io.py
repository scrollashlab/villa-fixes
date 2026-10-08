import numpy as np
import pytest
from xframe.catalog import Catalog
from xframe.tifxyz import Source, read_tifxyz, write_tifxyz
from conftest import A, B, C, M_AB


def test_catalog_lookup(fake_bucket):
    cat = Catalog.load(str(fake_bucket["root"] / "metadata.json"))
    M, prov = cat.matrix("S1", A, B)
    np.testing.assert_allclose(M, M_AB); assert prov["how"] == "catalog"
    Mi, prov_i = cat.matrix("S1", B, A); assert prov_i["how"] == "inverted catalog"
    p = np.array([10.0, 20.0, 30.0]); np.testing.assert_allclose(Mi[:, :3] @ (M[:, :3] @ p + M[:, 3]) + Mi[:, 3], p, atol=1e-9)
    assert cat.matrix("S1", A, A)[1]["how"] == "identity"
    with pytest.raises(KeyError): cat.matrix("S1", B, C)
    seg = cat.segment("S1", fake_bucket["seg"])
    assert seg.downscale == 4 and seg.normalized is not None
    assert sorted(m.kind for m in seg.meshes) == ["copy", "derived", "derived", "normalized"]
    assert cat.segment("S1", f"{fake_bucket['seg']}-test").id == fake_bucket["seg"]
    assert cat.voxel_um("S1", C) == 1.8


def test_tifxyz_roundtrip(tmp_path):
    P = np.random.default_rng(1).random((7, 9, 3)).astype(np.float32); P[0, 0] = -1
    write_tifxyz(tmp_path / "m", P, {"scale": [0.05, 0.05]})
    Q, meta = read_tifxyz(None, str(tmp_path / "m"))
    np.testing.assert_array_equal(P, Q); assert meta["scale"] == [0.05, 0.05]
    Q2, _ = read_tifxyz(Source(root=str(tmp_path)), "m")
    np.testing.assert_array_equal(P, Q2)
