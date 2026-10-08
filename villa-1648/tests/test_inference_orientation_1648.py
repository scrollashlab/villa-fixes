"""villa#1648: flat inference reports depth/scale; warns on fine scale only."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pytest
import zarr

from vesuvius.ink_detection.inference.infer import (
    _multiscale_xy_um,
    describe_inference_orientation,
    infer_single_zarr,
    log_inference_orientation,
    parse_args,
)


def test_default_direction_remains_forward():
    args = parse_args(["in.zarr", "ckpt.pth", "out.tif"])
    assert args.direction == "forward"


def test_describe_reports_neutrally_and_does_not_warn_on_forward_alone():
    report = describe_inference_orientation(
        layer_direction="forward",
        resolution="2",
        in_plane_scale_um=9.596,
    )
    assert report["depth_order"] == "forward"
    assert report["in_plane_scale_um"] == pytest.approx(9.596)
    assert report["fine_scale_vs_training"] is False
    assert report["warnings"] == []
    assert any("segment/render-dependent" in n for n in report["notes"])
    assert any("--direction both" in n for n in report["notes"])
    assert "depth_order=forward" in report["summary"]
    # Must not steer users toward reverse:
    blob = " ".join(report["notes"] + report["warnings"]).lower()
    assert "need --direction reverse" not in blob
    assert "often need" not in blob


def test_describe_warns_only_on_fine_in_plane_scale():
    fine = describe_inference_orientation(
        layer_direction="reverse",
        resolution="0",
        in_plane_scale_um=2.399,
    )
    assert fine["fine_scale_vs_training"] is True
    assert len(fine["warnings"]) == 1
    assert "2.399" in fine["warnings"][0]
    assert "underperformed" in fine["warnings"][0].lower() or "finer" in fine["warnings"][0].lower()

    coarse_forward = describe_inference_orientation(
        layer_direction="forward",
        resolution="0",
        in_plane_scale_um=9.596,
    )
    assert coarse_forward["warnings"] == []


def test_log_emits_info_notes_and_scale_warning(caplog):
    report = describe_inference_orientation(
        layer_direction="forward",
        resolution="0",
        in_plane_scale_um=2.399,
    )
    with caplog.at_level(logging.INFO):
        log_inference_orientation(report)
    assert "Ink input orientation:" in caplog.text
    assert "depth_order=forward" in caplog.text
    assert "segment/render-dependent" in caplog.text
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert "2.399" in warnings[0].getMessage()


def test_multiscale_xy_um_reads_ome_and_prepare_attrs(tmp_path):
    root = zarr.open_group(tmp_path / "vol.zarr", mode="w", zarr_format=2)
    root.attrs["multiscales"] = [
        {
            "datasets": [
                {
                    "path": "0",
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [2.399, 2.399, 2.399]}
                    ],
                },
                {
                    "path": "2",
                    "coordinateTransformations": [
                        {"type": "scale", "scale": [2.399, 9.596, 9.596]}
                    ],
                },
            ]
        }
    ]
    assert _multiscale_xy_um(root, "0") == pytest.approx(2.399)
    assert _multiscale_xy_um(root, "2") == pytest.approx(9.596)

    prep = zarr.open_group(tmp_path / "prep.zarr", mode="w", zarr_format=2)
    prep.attrs.update({"format": "level2-zmean4-21slice-v1", "source_level": "0"})
    assert _multiscale_xy_um(prep, "0") == pytest.approx(2.399)


def _write_tiny_prep(path: Path, *, source_level: str, xy_um: float, shape=(21, 64, 64)):
    root = zarr.open_group(str(path), mode="w", zarr_format=2)
    data = np.random.randint(0, 255, size=shape, dtype=np.uint8)
    root.create_array("0", shape=shape, chunks=shape, dtype="u1")
    root["0"][:] = data
    root.attrs.update(
        {
            "format": "level2-zmean4-21slice-v1",
            "source_level": source_level,
            "multiscales": [
                {
                    "datasets": [
                        {
                            "path": "0",
                            "coordinateTransformations": [
                                {"type": "scale", "scale": [xy_um, xy_um, xy_um]}
                            ],
                        }
                    ]
                }
            ],
        }
    )


def test_infer_single_zarr_logs_orientation_and_fine_scale_warning(
    tmp_path, caplog, monkeypatch
):
    """Behavioral path: infer_single_zarr must log report before tiling work."""

    import torch
    from torch import nn

    from vesuvius.ink_detection.inference import infer as infer_mod
    from vesuvius.ink_detection.inference.infer import ConfiguredModel

    prep = tmp_path / "fine.zarr"
    _write_tiny_prep(prep, source_level="0", xy_um=2.399)

    class _Tiny(nn.Module):
        def forward(self, x):
            # x: N,C,Z,Y,X → map to N,1,Y,X
            return x.mean(dim=2)

    configured = ConfiguredModel(
        model=_Tiny().eval(),
        patch_size=64,
        input_depth=17,
        preprocessing="divide_255",
        amp_dtype=None,
    )
    args = parse_args(
        [str(prep), str(tmp_path / "ckpt.pth"), str(tmp_path / "out.tif"), "--no-compile"]
    )
    # Avoid DataLoader / full pipeline hang: stub block iteration to empty after logs.
    monkeypatch.setattr(infer_mod, "iter_blocks", lambda *a, **k: [])
    monkeypatch.setattr(
        infer_mod,
        "build_lowres_block_mask",
        lambda *a, **k: (None, (1, 1), None),
    )
    monkeypatch.setattr(infer_mod, "write_output_tiff", lambda *a, **k: None)
    monkeypatch.setattr(
        infer_mod,
        "open_temp_zarr_array",
        lambda path, shape, chunks: zarr.open_array(
            str(path), mode="w", shape=shape, chunks=chunks, dtype="f4", zarr_format=2
        ),
    )

    with caplog.at_level(logging.INFO):
        infer_single_zarr(
            args=args,
            input_zarr=str(prep),
            configured_model=configured,
            device=torch.device("cpu"),
            output_tiff=tmp_path / "out.tif",
            layer_direction="forward",
        )

    assert "Ink input orientation:" in caplog.text
    assert "depth_order=forward" in caplog.text
    assert "in_plane_scale_um=2.399" in caplog.text
    assert "segment/render-dependent" in caplog.text
    warn_msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("2.399" in m for m in warn_msgs)
    assert not any("need --direction reverse" in m.lower() for m in warn_msgs)
