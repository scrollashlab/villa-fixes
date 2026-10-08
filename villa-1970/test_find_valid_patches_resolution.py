"""Regression tests for villa #1970: plain zarr + valid_patch_find_resolution.

When a label volume is a plain zarr Array (not an OME-Zarr multiscale group),
requesting valid_patch_find_resolution >= 1 used to treat the full-resolution
array as already downsampled and multiply patch starts by 2**level, writing
out-of-bounds positions into the patch cache. Multiscale groups that lack the
requested level already fell back to full resolution; plain arrays should too.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import List

import numpy as np
import pytest
import zarr


def _load_find_valid_patches():
    """Load the module without importing the heavy datasets package __init__."""
    try:
        from vesuvius.models.datasets.find_valid_patches import find_valid_patches

        return find_valid_patches
    except Exception:
        pass

    candidates = []
    try:
        import vesuvius

        candidates.append(
            Path(vesuvius.__file__).resolve().parent
            / "models"
            / "datasets"
            / "find_valid_patches.py"
        )
    except Exception:
        pass

    # Source-tree layout: tests/models/datasets/ -> ../../.. = vesuvius package root
    here = Path(__file__).resolve()
    candidates.append(
        here.parents[3] / "src" / "vesuvius" / "models" / "datasets" / "find_valid_patches.py"
    )
    candidates.append(
        here.parents[2] / "src" / "vesuvius" / "models" / "datasets" / "find_valid_patches.py"
    )

    for path in candidates:
        if path.is_file():
            spec = importlib.util.spec_from_file_location(
                "vesuvius_find_valid_patches_under_test", path
            )
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod.find_valid_patches

    raise ImportError("Could not locate find_valid_patches.py")


find_valid_patches = _load_find_valid_patches()

PATCH = (128, 128, 128)
SHAPE = (221, 132, 132)  # same shape class as PHerc0500P2 level-5 open-data crop


def _start_positions(result) -> List[List[int]]:
    return [list(p["start_pos"]) for p in result["fg_patches"]]


def _oob(positions, shape=SHAPE, patch=PATCH) -> List[List[int]]:
    shape_t = np.asarray(shape)
    patch_t = np.asarray(patch)
    bad = []
    for pos in positions:
        end = np.asarray(pos) + patch_t
        if np.any(end > shape_t) or np.any(np.asarray(pos) < 0):
            bad.append(list(pos))
    return bad


@pytest.fixture()
def plain_label_array(tmp_path: Path):
    """Plain zarr Array with a labeled blob in the first 128^3 corner."""
    path = tmp_path / "plain_label.zarr"
    arr = np.zeros(SHAPE, dtype=np.uint8)
    arr[10:90, 10:90, 10:90] = 1
    store = zarr.open(str(path), mode="w", shape=SHAPE, chunks=(64, 64, 64), dtype="u1")
    store[:] = arr
    opened = zarr.open(str(path), mode="r")
    assert not hasattr(opened, "keys")
    return opened


@pytest.fixture()
def ome_label_group(tmp_path: Path, plain_label_array):
    """OME-style group with real level-1 downsample of the same voxels."""
    path = tmp_path / "ome_label.zarr"
    full = np.asarray(plain_label_array)
    g = zarr.open_group(str(path), mode="w")
    g.create_dataset("0", data=full, chunks=(64, 64, 64))
    g.create_dataset("1", data=full[::2, ::2, ::2], chunks=(32, 32, 32))
    g.attrs["multiscales"] = [{"datasets": [{"path": "0"}, {"path": "1"}]}]
    return zarr.open(str(path), mode="r")


@pytest.fixture()
def ome_level0_only_group(tmp_path: Path, plain_label_array):
    """Group that only has level 0 — should fall back when level 1 is requested."""
    path = tmp_path / "ome_level0_only.zarr"
    full = np.asarray(plain_label_array)
    g = zarr.open_group(str(path), mode="w")
    g.create_dataset("0", data=full, chunks=(64, 64, 64))
    return zarr.open(str(path), mode="r")


def _run(label, level: int):
    return find_valid_patches(
        [label],
        ["synthetic"],
        PATCH,
        bbox_threshold=0.15,
        label_threshold=0.01,
        num_workers=1,
        valid_patch_find_resolution=level,
    )


def test_plain_array_level0_finds_in_bounds_patch(plain_label_array):
    pos = _start_positions(_run(plain_label_array, 0))
    assert pos == [[0, 0, 0]]
    assert _oob(pos) == []


def test_plain_array_level1_falls_back_to_full_resolution(plain_label_array):
    """#1970: must not scale positions by 2 when the array has no level 1."""
    pos = _start_positions(_run(plain_label_array, 1))
    assert pos == [[0, 0, 0]], f"expected single in-bounds patch, got {pos}"
    assert _oob(pos) == []


def test_plain_array_level2_falls_back_to_full_resolution(plain_label_array):
    pos = _start_positions(_run(plain_label_array, 2))
    assert pos == [[0, 0, 0]]
    assert _oob(pos) == []


def test_ome_group_level1_still_uses_downsampled_level(ome_label_group):
    """Control: a real multiscale level 1 must still be used (in-bounds after scale-up)."""
    pos = _start_positions(_run(ome_label_group, 1))
    assert pos  # at least one patch
    assert _oob(pos) == [], f"OME level-1 patches out of bounds: {pos}"


def test_ome_group_missing_level_falls_back(ome_level0_only_group):
    pos = _start_positions(_run(ome_level0_only_group, 1))
    assert pos == [[0, 0, 0]]
    assert _oob(pos) == []
