"""Tests for tifxyz frame / voxel_size_um helpers (villa #1522)."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

# Avoid pulling OpenCV via vesuvius.tifxyz.__init__ -> reader on light CPU boxes.
_HERE = Path(__file__).resolve()
_SRC_META = (
    _HERE.parents[2] / "src" / "vesuvius" / "tifxyz" / "meta_frames.py"
)
if not _SRC_META.is_file():
    # Installed / editable layout
    import vesuvius

    _SRC_META = (
        Path(vesuvius.__file__).resolve().parent / "tifxyz" / "meta_frames.py"
    )


def _load_meta_frames():
    spec = importlib.util.spec_from_file_location(
        "vesuvius_tifxyz_meta_frames_under_test", _SRC_META
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


meta_frames = _load_meta_frames()
VOXEL_SIZE_UM_KEY = meta_frames.VOXEL_SIZE_UM_KEY
SCALE_RTOL = meta_frames.SCALE_RTOL
annotate_meta_voxel_size_um = meta_frames.annotate_meta_voxel_size_um
find_ambiguous_scale_frames = meta_frames.find_ambiguous_scale_frames
frames_comparable = meta_frames.frames_comparable
parse_voxel_size_um_from_name = meta_frames.parse_voxel_size_um_from_name
scale_pairs_close = meta_frames.scale_pairs_close

# Exact floats observed in public open-data meta.json (2026-10-05 HST):
# JSON literal 0.05 vs float64 expansion of float32(0.05).
SCALE_JSON_0_05 = (0.05, 0.05)
SCALE_F32_0_05 = (0.05000000074505806, 0.05000000074505806)


def _write_mesh(root: Path, name: str, *, scale, voxel_size_um=None) -> Path:
    path = root / name
    path.mkdir(parents=True)
    meta = {"uuid": name, "scale": list(scale), "type": "seg", "format": "tifxyz"}
    if voxel_size_um is not None:
        meta[VOXEL_SIZE_UM_KEY] = voxel_size_um
    (path / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return path


@pytest.mark.parametrize(
    "name,expected",
    [
        ("-on-20260608103018-1.129um.tifxyz", 1.129),
        ("-on-20230205180739-7.91um.tifxyz", 7.91),
        ("-on-20260310170716-45.532um.tifxyz", 45.532),
        ("plain-no-um.tifxyz", None),
    ],
)
def test_parse_voxel_size_um_from_name(name, expected):
    got = parse_voxel_size_um_from_name(name)
    if expected is None:
        assert got is None
    else:
        assert got == pytest.approx(expected)


def test_annotate_meta_from_dirname(tmp_path: Path):
    mesh = _write_mesh(tmp_path, "-on-20260411134726-2.4um.tifxyz", scale=(0.05, 0.05))
    assert annotate_meta_voxel_size_um(mesh) == pytest.approx(2.4)
    meta = json.loads((mesh / "meta.json").read_text())
    assert meta[VOXEL_SIZE_UM_KEY] == pytest.approx(2.4)
    assert annotate_meta_voxel_size_um(mesh, voxel_size_um=9.0) == pytest.approx(2.4)
    assert annotate_meta_voxel_size_um(mesh, voxel_size_um=9.0, overwrite=True) == pytest.approx(9.0)


def test_find_ambiguous_scale_frames_matches_issue_example(tmp_path: Path):
    mesh_root = tmp_path / "mesh"
    mesh_root.mkdir()
    for name in [
        "-on-20260608103018-1.129um.tifxyz",
        "-on-20260411134726-2.4um.tifxyz",
        "-on-20230205180739-7.91um.tifxyz",
        "-on-20260310170716-45.532um.tifxyz",
    ]:
        _write_mesh(mesh_root, name, scale=(0.05, 0.05))

    ambiguous = find_ambiguous_scale_frames(mesh_root)
    assert len(ambiguous) == 1
    group = ambiguous[0]
    assert group.scale == (0.05, 0.05)
    assert group.voxel_sizes_um == (1.129, 2.4, 7.91, 45.532)
    assert group.spread_ratio == pytest.approx(45.532 / 1.129, rel=1e-6)


def test_find_ambiguous_scale_frames_clear_when_voxel_sizes_match(tmp_path: Path):
    mesh_root = tmp_path / "mesh"
    mesh_root.mkdir()
    _write_mesh(mesh_root, "a-7.91um.tifxyz", scale=(0.05, 0.05), voxel_size_um=7.91)
    _write_mesh(mesh_root, "b-7.91um.tifxyz", scale=(0.05, 0.05), voxel_size_um=7.91)
    assert find_ambiguous_scale_frames(mesh_root) == []


def test_frames_comparable_requires_voxel_size():
    a = {"scale": [0.05, 0.05]}
    b = {"scale": [0.05, 0.05]}
    assert frames_comparable([a, b]) is False
    a[VOXEL_SIZE_UM_KEY] = 7.91
    b[VOXEL_SIZE_UM_KEY] = 7.91
    assert frames_comparable([a, b]) is True
    b[VOXEL_SIZE_UM_KEY] = 1.129
    assert frames_comparable([a, b]) is False


def test_scale_pairs_close_covers_float32_roundtrip():
    """Real open-data pair: JSON 0.05 vs float32(0.05) as float64."""
    assert SCALE_RTOL == 1e-6
    assert scale_pairs_close(SCALE_JSON_0_05, SCALE_F32_0_05) is True
    # Sanity: intentional different scales stay apart
    assert scale_pairs_close((0.05, 0.05), (0.1, 0.1)) is False
    rel = abs(SCALE_JSON_0_05[0] - SCALE_F32_0_05[0]) / SCALE_F32_0_05[0]
    assert rel < SCALE_RTOL
    assert math.isclose(
        SCALE_JSON_0_05[0], SCALE_F32_0_05[0], rel_tol=SCALE_RTOL, abs_tol=0.0
    )


def test_find_ambiguous_merges_float32_and_json_scale_paris4_pattern(tmp_path: Path):
    """Paris4 footgun: 7.91 meta uses 0.05; siblings use float32 expansion.

    Without tolerance the 7.91 mesh was dropped (3 of 4). Must list all four.
    """
    mesh_root = tmp_path / "mesh"
    mesh_root.mkdir()
    _write_mesh(
        mesh_root,
        "20230702185753-on-20230205180739-7.91um.tifxyz",
        scale=SCALE_JSON_0_05,
    )
    _write_mesh(
        mesh_root,
        "20230702185753-on-20260310170716-45.532um.tifxyz",
        scale=SCALE_F32_0_05,
    )
    _write_mesh(
        mesh_root,
        "20230702185753-on-20260411134726-2.4um.tifxyz",
        scale=SCALE_F32_0_05,
    )
    _write_mesh(
        mesh_root,
        "20230702185753-on-20260608103018-1.129um.tifxyz",
        scale=SCALE_F32_0_05,
    )
    ambiguous = find_ambiguous_scale_frames(mesh_root)
    assert len(ambiguous) == 1
    group = ambiguous[0]
    assert len(group.records) == 4
    assert group.voxel_sizes_um == (1.129, 2.4, 7.91, 45.532)
    assert group.spread_ratio == pytest.approx(45.532 / 1.129, rel=1e-6)


def test_frames_comparable_same_um_twins_with_scale_jitter():
    """PHerc0172 twins: same 7.91um, scales 0.05 vs float32 expansion."""
    a = {"scale": list(SCALE_JSON_0_05), VOXEL_SIZE_UM_KEY: 7.91}
    b = {"scale": list(SCALE_F32_0_05), VOXEL_SIZE_UM_KEY: 7.91}
    assert frames_comparable([a, b]) is True
    # Cross-µm must stay False even with matching float32 scales
    c = {"scale": list(SCALE_F32_0_05), VOXEL_SIZE_UM_KEY: 1.129}
    assert frames_comparable([b, c]) is False


def test_reader_known_keys_include_voxel_size_um():
    """Contract: reader promotes voxel_size_um out of extra (#1522)."""
    reader_py = _SRC_META.with_name("reader.py")
    src = reader_py.read_text(encoding="utf-8")
    assert 'known_keys = {"uuid", "scale", "bbox", "area", "voxel_size_um"}' in src
    assert '"voxel_size_um": voxel_size_um' in src
