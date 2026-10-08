"""Regression tests for villa #1481 against the patched FlatBlockDataset."""

from __future__ import annotations

import numpy as np
import pytest
import zarr

from vesuvius.image_proc.intensity.normalization import normalize_robust
from vesuvius.ink_detection.inference.infer import (
    Block,
    FlatBlockDataset,
    FlatPatchReader,
    select_layer_indices,
)


@pytest.fixture()
def short_depth_zarr(tmp_path):
    source_ZYX = np.arange(100, 100 + 3 * 4 * 4, dtype=np.uint8).reshape(3, 4, 4)
    path = tmp_path / "short-depth.zarr"
    array = zarr.open(
        str(path),
        mode="w",
        shape=source_ZYX.shape,
        chunks=source_ZYX.shape,
        dtype="u1",
        zarr_format=2,
    )
    array[:] = source_ZYX
    return path, source_ZYX


def test_issue_1481_bug_numbers_still_match_pad_then_normalize():
    """Sanity: the published pad-then-normalize mismatch is still the bug."""
    source = np.arange(100, 100 + 3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
    train = np.zeros((5, 4, 4), dtype=np.float32)
    train[1:4] = normalize_robust(source.copy())
    padded = np.zeros((5, 4, 4), dtype=np.float32)
    padded[1:4] = source
    buggy = normalize_robust(padded.copy())
    assert abs(float(buggy[0, 0, 0]) - (-2.2658675)) < 1e-4
    assert abs(float(np.abs(train[1:4] - buggy[1:4]).mean()) - 0.48813486) < 1e-4


def test_flat_robust_excludes_padding(short_depth_zarr):
    path, source_ZYX = short_depth_zarr
    layers = select_layer_indices(
        3, layer_start=None, layer_end=None, output_depth=5, direction="forward"
    )
    reader = FlatPatchReader(
        input_path=path,
        resolution="0",
        depth_axis_first=True,
        height=4,
        width=4,
        layer_indices=layers,
        output_depth=5,
        preprocessing="tifxyz_robust",
    )
    dataset = FlatBlockDataset(
        reader=reader,
        blocks=[Block(y0=0, x0=0, valid_h=4, valid_w=4)],
        patch_size=4,
        preprocessing="tifxyz_robust",
    )
    got = dataset[0][0].numpy()[0]
    expected = np.zeros((5, 4, 4), dtype=np.float32)
    expected[1:4] = normalize_robust(source_ZYX.astype(np.float32))
    np.testing.assert_array_equal(got[0], 0)
    np.testing.assert_array_equal(got[4], 0)
    np.testing.assert_allclose(got, expected, rtol=0, atol=1e-6)


def test_divide_255_unchanged(short_depth_zarr):
    path, source_ZYX = short_depth_zarr
    layers = select_layer_indices(
        3, layer_start=None, layer_end=None, output_depth=5, direction="forward"
    )
    reader = FlatPatchReader(
        input_path=path,
        resolution="0",
        depth_axis_first=True,
        height=4,
        width=4,
        layer_indices=layers,
        output_depth=5,
        preprocessing="divide_255",
    )
    dataset = FlatBlockDataset(
        reader=reader,
        blocks=[Block(y0=0, x0=0, valid_h=4, valid_w=4)],
        patch_size=4,
        preprocessing="divide_255",
    )
    got = dataset[0][0].numpy()[0]
    expected = np.zeros((5, 4, 4), dtype=np.float32)
    expected[1:4] = source_ZYX.astype(np.float32) / 255.0
    np.testing.assert_allclose(got, expected, rtol=0, atol=1e-7)
