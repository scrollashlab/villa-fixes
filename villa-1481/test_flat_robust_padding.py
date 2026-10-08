"""Regression tests for villa #1481: robust flat norm must exclude reader padding."""

from __future__ import annotations

import numpy as np
import zarr

from vesuvius.image_proc.intensity.normalization import normalize_robust
from vesuvius.ink_detection.inference.infer import (
    Block,
    FlatBlockDataset,
    FlatPatchReader,
    select_layer_indices,
)


def _short_depth_zarr(tmp_path, name: str = "short-depth.zarr"):
    source_ZYX = np.arange(100, 100 + 3 * 4 * 4, dtype=np.uint8).reshape(3, 4, 4)
    path = tmp_path / name
    array = zarr.open(
        path,
        mode="w",
        shape=source_ZYX.shape,
        chunks=source_ZYX.shape,
        dtype="u1",
        zarr_format=2,
    )
    array[:] = source_ZYX
    return path, source_ZYX


def test_flat_robust_normalization_excludes_reader_padding(tmp_path):
    """Training normalizes only source voxels; padding stays zero (#1481)."""
    path, source_ZYX = _short_depth_zarr(tmp_path)
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
    np.testing.assert_array_equal(got[0], np.zeros((4, 4), dtype=np.float32))
    np.testing.assert_array_equal(got[4], np.zeros((4, 4), dtype=np.float32))
    np.testing.assert_allclose(got, expected, rtol=0, atol=1e-6)


def test_flat_divide_255_is_unchanged_by_the_padding_rule(tmp_path):
    path, source_ZYX = _short_depth_zarr(tmp_path, "divide.zarr")
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


def test_flat_robust_normalization_uses_source_placement_not_origin(tmp_path):
    """Blocks starting before the array place source at source_y0 - y0, not 0."""
    path, source_ZYX = _short_depth_zarr(tmp_path, "neg-origin.zarr")
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
        blocks=[Block(y0=-2, x0=0, valid_h=2, valid_w=4)],
        patch_size=4,
        preprocessing="tifxyz_robust",
    )
    got = dataset[0][0].numpy()[0]
    assert np.all(got[:, 0:2, :] == 0)
    expected_real = normalize_robust(source_ZYX[:, 0:2, :].astype(np.float32))
    np.testing.assert_allclose(got[1:4, 2:4, :], expected_real, rtol=0, atol=1e-6)
