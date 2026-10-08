import gzip, json
import numpy as np
import pytest
from xframe import geom
from xframe.tifxyz import write_tifxyz

A, B, C = "20240101000000", "20240202000000", "20240303000000"
M_AB = [[0.4, 0.01, 0.0, 12.5], [-0.01, 0.4, 0.002, -7.0], [0.0, -0.002, 0.4, 30.0]]   # ~0.4x (coarser target)
M_AC = [[2.0, 0.0, 0.03, -100.0], [0.0, 2.0, 0.0, 50.0], [-0.03, 0.0, 2.0, 5.0]]      # ~2x (finer target)


def curved_surface(rows=40, cols=50, step=20.0, invalid_frac=0.1, seed=0):
    rng = np.random.default_rng(seed)
    v, u = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    x = 500 + u * step; z = 300 + v * step
    y = 800 + 40 * np.sin(u / 7.0) + 25 * np.cos(v / 5.0)
    P = np.stack([x, y, z], -1).astype(np.float32)
    P[rng.random((rows, cols)) < invalid_frac] = -1
    P[:3, :] = -1  # invalid border band like real meshes
    return P


@pytest.fixture
def fake_bucket(tmp_path):
    """A bucket-shaped directory: metadata.json.gz + one segment with normalized source (downscale 4),
    derived meshes built with xframe.geom (self-consistency only; VC fidelity is tested against the real bucket),
    a byte copy, and one deliberately shifted derived mesh (negative control)."""
    root = tmp_path / "bucket"
    seg = "20240505000000"
    base = f"S1/segments/{seg}-test/mesh"
    P = curved_surface()
    write_tifxyz(root / f"{base}/intermediate/tifxyz_normalized", P, {"format": "tifxyz", "scale": [0.05, 0.05], "type": "seg"})
    Qb, _ = geom.transform_surface(P, np.array(M_AB), 4.0)
    write_tifxyz(root / f"{base}/{seg}-on-{B}-9.0um.tifxyz", Qb, {"format": "tifxyz", "scale": [0.05, 0.05]})
    Qc, _ = geom.transform_surface(P, np.array(M_AC), 4.0)
    Qc_bad = Qc.copy(); ok = geom.valid_mask(Qc_bad); Qc_bad[ok] += np.float32(3.0)   # 3-voxel shift on every axis
    write_tifxyz(root / f"{base}/{seg}-on-{C}-1.8um.tifxyz", Qc_bad, {"format": "tifxyz", "scale": [0.05, 0.05]})
    write_tifxyz(root / f"{base}/{seg}-copy.tifxyz", P, {"format": "tifxyz", "scale": [0.05, 0.05]})

    def tr(key, target, proc="transform-tifxyz-normalized"):
        return {"type": "tifxyz-transformed", "origins": [{"path": key + "/"}], "parameters": {"target_volume": target},
                "creation_info": {"process": proc}}
    md = {"samples": {"S1": {
        "sample": {"id": "S1", "properties": {"volume_transforms": [
            {"from_volume_id": A, "transforms": [{"to_volume_id": B, "matrix": M_AB, "derivation_path": f"{A}-{B}"},
                                                 {"to_volume_id": C, "matrix": M_AC, "derivation_path": f"{A}-{C}"}]}]}},
        "volumes": {A: {"properties": {"pixel_size_um": 3.6}}, B: {"properties": {"pixel_size_um": 9.0}},
                    C: {"properties": {"pixel_size_um": 1.8}}},
        "segments": {seg: {"long_id": f"{seg}-test", "original_volume_id": A, "properties": {"original_volume_downscale": 4},
                           "data": [{"type": "tifxyz-normalized", "origins": [{"path": f"{base}/intermediate/tifxyz_normalized/"}]},
                                    tr(f"{base}/{seg}-on-{B}-9.0um.tifxyz", B), tr(f"{base}/{seg}-on-{C}-1.8um.tifxyz", C),
                                    tr(f"{base}/{seg}-copy.tifxyz", A, "copy-normalized-for-original")]}}}}}
    (root / "metadata.json").write_bytes(gzip.compress(json.dumps(md).encode()))
    return dict(root=root, seg=seg, base=base, P=P, Qb=Qb, Qc=Qc)
