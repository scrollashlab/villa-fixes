"""Tests for tifxyz-audit checks and CLI exit codes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile

from tifxyz_audit.checks import audit_paths, discover_tifxyz_dirs
from tifxyz_audit.cli import main
from tifxyz_audit.report import exit_code


ROOT = Path(__file__).resolve().parents[1]


def _write_tifxyz(
    path: Path,
    *,
    scale=(0.05, 0.05),
    voxel_size_um=None,
    shape=(8, 10),
    bbox=None,
    fill: float = 10.0,
    invalid_frac: float = 0.0,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    meta = {
        "uuid": path.name,
        "scale": list(scale),
        "type": "seg",
        "format": "tifxyz",
    }
    if voxel_size_um is not None:
        meta["voxel_size_um"] = voxel_size_um
    if bbox is not None:
        meta["bbox"] = bbox
    (path / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    h, w = shape
    z = np.full((h, w), fill, dtype=np.float32)
    n_inv = int(h * w * invalid_frac)
    if n_inv:
        z.ravel()[:n_inv] = -1.0
    for name in ("x.tif", "y.tif", "z.tif"):
        tifffile.imwrite(path / name, z if name == "z.tif" else np.zeros_like(z))
    return path


def test_discover_segment_mesh_layout(tmp_path: Path):
    seg = tmp_path / "seg"
    mesh = seg / "mesh"
    a = _write_tifxyz(mesh / "a-1.129um.tifxyz")
    b = _write_tifxyz(mesh / "b-2.4um.tifxyz")
    found = discover_tifxyz_dirs([seg])
    assert set(found) == {a.resolve(), b.resolve()}


def test_meta_missing_is_error(tmp_path: Path):
    d = tmp_path / "empty"
    d.mkdir()
    # not a tifxyz; parent scan finds nothing
    dirs, findings = audit_paths([tmp_path], skip_tiff=True)
    assert any(f.code == "no_tifxyz_found" for f in findings)
    assert exit_code(findings) == 2


def test_meta_unparseable(tmp_path: Path):
    d = tmp_path / "bad.tifxyz"
    d.mkdir()
    (d / "meta.json").write_text("{not-json")
    dirs, findings = audit_paths([d], skip_tiff=True)
    assert any(f.code == "meta_unparseable" and f.severity == "error" for f in findings)
    assert exit_code(findings) == 2


def test_scale_missing(tmp_path: Path):
    d = tmp_path / "noscale.tifxyz"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"uuid": "x"}) + "\n")
    for n in ("x.tif", "y.tif", "z.tif"):
        tifffile.imwrite(d / n, np.zeros((4, 4), dtype=np.float32))
    _, findings = audit_paths([d])
    assert any(f.code == "scale_missing" for f in findings)


def test_voxel_size_inferable_warning(tmp_path: Path):
    d = _write_tifxyz(tmp_path / "mesh-7.91um.tifxyz")
    _, findings = audit_paths([d], skip_tiff=True)
    assert any(f.code == "voxel_size_um_inferable" and f.severity == "warning" for f in findings)


def test_scale_frame_ambiguity(tmp_path: Path):
    mesh = tmp_path / "mesh"
    for name, um in [
        ("-on-1.129um.tifxyz", 1.129),
        ("-on-2.4um.tifxyz", 2.4),
        ("-on-7.91um.tifxyz", 7.91),
        ("-on-45.532um.tifxyz", 45.532),
    ]:
        _write_tifxyz(mesh / name, scale=(0.05, 0.05))
    _, findings = audit_paths([mesh], skip_tiff=True)
    amb = [f for f in findings if f.code == "scale_frame_ambiguity"]
    assert len(amb) == 1
    assert amb[0].data["spread_ratio"] == pytest.approx(45.532 / 1.129, rel=1e-6)
    # ambiguity is warning (internally valid files)
    assert exit_code(findings) == 0
    assert exit_code(findings, strict=True) == 1


def test_tiff_shape_mismatch(tmp_path: Path):
    d = _write_tifxyz(tmp_path / "m.tifxyz", shape=(8, 8))
    tifffile.imwrite(d / "y.tif", np.zeros((8, 9), dtype=np.float32))
    _, findings = audit_paths([d], sample_invalid=False)
    assert any(f.code == "tiff_shape_mismatch" for f in findings)
    assert exit_code(findings) == 2


def test_tiff_missing(tmp_path: Path):
    d = tmp_path / "partial.tifxyz"
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"uuid": "p", "scale": [0.05, 0.05]}) + "\n")
    tifffile.imwrite(d / "x.tif", np.zeros((4, 4), dtype=np.float32))
    _, findings = audit_paths([d])
    assert any(f.code == "tiff_missing" for f in findings)


def test_bbox_outside_volume(tmp_path: Path):
    d = _write_tifxyz(
        tmp_path / "b.tifxyz",
        bbox=[[0, 0, 0], [100, 100, 100]],
    )
    _, findings = audit_paths([d], volume_shape=(50, 50, 50), skip_tiff=True)
    assert any(f.code == "bbox_outside_volume" for f in findings)
    assert exit_code(findings) == 2


def test_bbox_inside_volume(tmp_path: Path):
    d = _write_tifxyz(
        tmp_path / "b.tifxyz",
        bbox=[[1, 2, 3], [10, 20, 30]],
    )
    _, findings = audit_paths([d], volume_shape=(100, 100, 100), skip_tiff=True)
    assert any(f.code == "bbox_inside_volume" for f in findings)


def test_cli_fix_meta_requires_flag_subprocess(tmp_path: Path):
    d = _write_tifxyz(tmp_path / "seg-2.4um.tifxyz")
    proc = subprocess.run(
        [sys.executable, "-m", "tifxyz_audit", str(d), "--fix-meta", "--skip-tiff"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "requires --in-place or --output-dir" in (proc.stderr + proc.stdout)


def test_cli_fix_meta_output_dir(tmp_path: Path):
    d = _write_tifxyz(tmp_path / "seg-2.4um.tifxyz")
    out = tmp_path / "out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tifxyz_audit",
            str(d),
            "--fix-meta",
            "--output-dir",
            str(out),
            "--skip-tiff",
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    meta = json.loads((out / d.name / "meta.json").read_text())
    assert meta["voxel_size_um"] == pytest.approx(2.4)
    # original untouched
    assert "voxel_size_um" not in json.loads((d / "meta.json").read_text())


def test_cli_json_and_exit_codes(tmp_path: Path):
    good = _write_tifxyz(tmp_path / "ok.tifxyz", voxel_size_um=7.91)
    proc = subprocess.run(
        [sys.executable, "-m", "tifxyz_audit", str(good), "--json", "--skip-tiff"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert "summary" in payload and "findings" in payload

    bad = tmp_path / "bad.tifxyz"
    bad.mkdir()
    (bad / "meta.json").write_text("{")
    proc2 = subprocess.run(
        [sys.executable, "-m", "tifxyz_audit", str(bad), "--skip-tiff"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc2.returncode == 2


def test_invalid_point_stats(tmp_path: Path):
    d = _write_tifxyz(tmp_path / "inv.tifxyz", invalid_frac=0.25)
    _, findings = audit_paths([d])
    stats = [f for f in findings if f.code == "invalid_point_stats"]
    assert stats
    assert stats[0].data["sentinel_neg1_fraction"] == pytest.approx(0.25, abs=0.05)


def test_scale_frame_ambiguity_float_noise(tmp_path: Path):
    mesh = tmp_path / "mesh"
    _write_tifxyz(mesh / "a-1.129um.tifxyz", scale=(0.05, 0.05))
    _write_tifxyz(mesh / "b-45.532um.tifxyz", scale=(0.05000000074505806, 0.05000000074505806))
    _, findings = audit_paths([mesh], skip_tiff=True)
    amb = [f for f in findings if f.code == "scale_frame_ambiguity"]
    assert len(amb) == 1
    assert amb[0].data["spread_ratio"] == pytest.approx(45.532 / 1.129, rel=1e-6)
