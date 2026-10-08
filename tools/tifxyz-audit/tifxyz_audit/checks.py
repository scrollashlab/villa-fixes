"""QA checks for one tifxyz directory and for sibling mesh groups."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import meta_frames
from .tiff_util import read_tiff_shape, sample_invalid_fraction, tiff_available

SEVERITIES = ("error", "warning", "info")


@dataclass
class Finding:
    code: str
    severity: str  # error | warning | info
    message: str
    path: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_tifxyz_dir(path: Path) -> bool:
    return path.is_dir() and (path / "meta.json").is_file()


def discover_tifxyz_dirs(inputs: Sequence[Path]) -> list[Path]:
    """Resolve CLI inputs to tifxyz directories (contain meta.json)."""
    found: list[Path] = []
    seen: set[Path] = set()

    def add(p: Path) -> None:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            found.append(rp)

    for raw in inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            continue
        if _is_tifxyz_dir(path):
            add(path)
            continue
        # segment/mesh/ layout
        mesh = path / "mesh"
        if mesh.is_dir():
            for child in sorted(mesh.iterdir()):
                if _is_tifxyz_dir(child):
                    add(child)
            continue
        # parent of many tifxyz dirs
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if _is_tifxyz_dir(child):
                    add(child)
            # also one-level mesh/
            for child in sorted(path.glob("*/mesh")):
                if child.is_dir():
                    for gchild in sorted(child.iterdir()):
                        if _is_tifxyz_dir(gchild):
                            add(gchild)
    return found


def check_meta(path: Path) -> tuple[list[Finding], dict[str, Any] | None]:
    findings: list[Finding] = []
    meta_path = path / "meta.json"
    if not meta_path.is_file():
        findings.append(
            Finding("meta_missing", "error", "meta.json is missing", str(path))
        )
        return findings, None
    try:
        meta = meta_frames.load_meta_dict(meta_path)
    except Exception as exc:  # noqa: BLE001 - report parse failures
        findings.append(
            Finding(
                "meta_unparseable",
                "error",
                f"meta.json could not be parsed: {exc}",
                str(meta_path),
            )
        )
        return findings, None

    scale = meta_frames.scale_pair(meta)
    if scale is None:
        findings.append(
            Finding(
                "scale_missing",
                "error",
                "meta.json has no usable scale [sx, sy]",
                str(meta_path),
            )
        )
    else:
        sx, sy = scale
        if not (math.isfinite(sx) and math.isfinite(sy) and sx > 0 and sy > 0):
            findings.append(
                Finding(
                    "scale_invalid",
                    "error",
                    f"scale must be finite and > 0, got {[sx, sy]}",
                    str(meta_path),
                    {"scale": [sx, sy]},
                )
            )
        else:
            # Common tracer scale is ~0.05; stretch-factor misuse can be tiny (e.g. 0.0005).
            if min(sx, sy) < 1e-4:
                findings.append(
                    Finding(
                        "scale_suspicious_small",
                        "warning",
                        f"scale {[sx, sy]} is unusually small "
                        "(possible stretch-factor misuse; see villa #1319)",
                        str(meta_path),
                        {"scale": [sx, sy]},
                    )
                )
            findings.append(
                Finding(
                    "scale_ok",
                    "info",
                    f"scale={[sx, sy]} (grid cells per voxel of this mesh's scan)",
                    str(meta_path),
                    {"scale": [sx, sy]},
                )
            )

    vox = None
    try:
        vox = (
            meta_frames.get_voxel_size_um(meta)
            if meta_frames.VOXEL_SIZE_UM_KEY in meta
            else None
        )
    except ValueError as exc:
        findings.append(
            Finding("voxel_size_um_invalid", "error", str(exc), str(meta_path))
        )

    parsed = meta_frames.parse_voxel_size_um_from_name(path)
    if vox is not None:
        findings.append(
            Finding(
                "voxel_size_um_present",
                "info",
                f"voxel_size_um={vox}",
                str(meta_path),
                {"voxel_size_um": vox},
            )
        )
        if parsed is not None and abs(parsed - vox) / max(vox, parsed) > 0.01:
            findings.append(
                Finding(
                    "voxel_size_um_dirname_mismatch",
                    "warning",
                    f"voxel_size_um={vox} disagrees with dirname token {parsed}um",
                    str(path),
                    {"voxel_size_um": vox, "parsed_um": parsed},
                )
            )
    elif parsed is not None:
        findings.append(
            Finding(
                "voxel_size_um_inferable",
                "warning",
                f"voxel_size_um missing; dirname implies {parsed}um "
                "(run --fix-meta --in-place or --fix-meta --output-dir ...)",
                str(path),
                {"parsed_um": parsed},
            )
        )
    else:
        findings.append(
            Finding(
                "voxel_size_um_unknown",
                "warning",
                "voxel_size_um missing and not inferable from directory name",
                str(path),
            )
        )

    return findings, meta


def check_tiffs(path: Path, *, sample_invalid: bool = True) -> list[Finding]:
    findings: list[Finding] = []
    names = ("x.tif", "y.tif", "z.tif")
    present = {n: (path / n).is_file() for n in names}
    missing = [n for n, ok in present.items() if not ok]
    if missing:
        findings.append(
            Finding(
                "tiff_missing",
                "error",
                f"missing required TIFF(s): {', '.join(missing)}",
                str(path),
                {"missing": missing},
            )
        )
        return findings

    if not tiff_available():
        findings.append(
            Finding(
                "tiff_checks_skipped",
                "warning",
                "tifffile/numpy not installed; skipped shape and invalid-point checks",
                str(path),
            )
        )
        return findings

    shapes = {}
    for n in names:
        try:
            shapes[n] = read_tiff_shape(path / n)
        except Exception as exc:  # noqa: BLE001
            findings.append(
                Finding(
                    "tiff_header_unreadable",
                    "error",
                    f"{n}: could not read TIFF header: {exc}",
                    str(path / n),
                )
            )
            return findings

    if len(set(shapes.values())) != 1:
        findings.append(
            Finding(
                "tiff_shape_mismatch",
                "error",
                f"x/y/z shapes differ: {shapes}",
                str(path),
                {"shapes": {k: list(v) for k, v in shapes.items()}},
            )
        )
    else:
        shape = shapes["x.tif"]
        findings.append(
            Finding(
                "tiff_shape_ok",
                "info",
                f"x/y/z shape={list(shape)}",
                str(path),
                {"shape": list(shape)},
            )
        )

    if sample_invalid:
        try:
            stats = sample_invalid_fraction(path / "z.tif")
            frac = stats["sentinel_neg1_fraction"]
            sev = "info" if frac < 0.99 else "warning"
            # High -1 fraction can be normal (sparse surface); report as info/warn only.
            findings.append(
                Finding(
                    "invalid_point_stats",
                    sev,
                    (
                        f"z.tif sentinel=-1 fraction={frac:.4f} "
                        f"(nonfinite={stats['nonfinite_fraction']:.4f}; "
                        f"{'sampled' if stats['sampled'] else 'exact'})"
                    ),
                    str(path / "z.tif"),
                    stats,
                )
            )
        except Exception as exc:  # noqa: BLE001
            findings.append(
                Finding(
                    "invalid_point_unreadable",
                    "warning",
                    f"could not sample z.tif for invalid points: {exc}",
                    str(path / "z.tif"),
                )
            )
    return findings


def check_bbox(
    path: Path,
    meta: dict[str, Any] | None,
    volume_shape: tuple[int, int, int] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    if meta is None:
        return findings
    bbox = meta.get("bbox")
    if bbox is None:
        findings.append(
            Finding("bbox_missing", "info", "meta.json has no bbox", str(path))
        )
        return findings
    try:
        mins = [float(x) for x in bbox[0]]
        maxs = [float(x) for x in bbox[1]]
    except Exception:  # noqa: BLE001
        findings.append(
            Finding("bbox_unparseable", "error", f"bbox not usable: {bbox!r}", str(path))
        )
        return findings

    if any(v == -1 for v in mins + maxs):
        findings.append(
            Finding(
                "bbox_missing_marker",
                "warning",
                "bbox contains the -1 missing-point marker (villa #1618 class)",
                str(path / "meta.json"),
                {"bbox": bbox},
            )
        )

    if volume_shape is None:
        findings.append(
            Finding(
                "bbox_volume_unchecked",
                "info",
                "bbox present; pass --volume-shape Z,Y,X to check containment",
                str(path),
                {"bbox": bbox},
            )
        )
        return findings

    # volume_shape is Z,Y,X; bbox is [[min_x,min_y,min_z],[max_x,max_y,max_z]]
    vz, vy, vx = volume_shape
    limits = (vx, vy, vz)
    outside = False
    for i, (lo, hi, lim) in enumerate(zip(mins, maxs, limits)):
        if lo < -1e-3 or hi > lim + 1e-3:
            outside = True
    if outside:
        findings.append(
            Finding(
                "bbox_outside_volume",
                "error",
                f"bbox {bbox} extends outside volume shape ZYX={list(volume_shape)} "
                f"(XYZ limits {list(limits)})",
                str(path),
                {"bbox": bbox, "volume_shape_zyx": list(volume_shape)},
            )
        )
    else:
        findings.append(
            Finding(
                "bbox_inside_volume",
                "info",
                f"bbox inside volume shape ZYX={list(volume_shape)}",
                str(path),
                {"bbox": bbox, "volume_shape_zyx": list(volume_shape)},
            )
        )
    return findings


def check_sibling_ambiguity(dirs: Sequence[Path]) -> list[Finding]:
    """Group by parent and run #1522 same-scale / different-um detection."""
    findings: list[Finding] = []
    by_parent: dict[Path, list[Path]] = {}
    for d in dirs:
        by_parent.setdefault(d.parent, []).append(d)

    for parent, children in sorted(by_parent.items()):
        if len(children) < 2:
            continue
        # find_ambiguous_scale_frames expects a mesh root whose children are tifxyz dirs
        try:
            groups = meta_frames.find_ambiguous_scale_frames(parent)
        except Exception as exc:  # noqa: BLE001
            findings.append(
                Finding(
                    "ambiguity_check_failed",
                    "warning",
                    f"could not run ambiguity check on {parent}: {exc}",
                    str(parent),
                )
            )
            continue
        if not groups:
            findings.append(
                Finding(
                    "scale_frames_ok",
                    "info",
                    f"no same-scale / different-voxel-size ambiguity under {parent}",
                    str(parent),
                )
            )
            continue
        for g in groups:
            findings.append(
                Finding(
                    "scale_frame_ambiguity",
                    "warning",
                    (
                        f"villa #1522: {len(g.records)} meshes share scale={list(g.scale)} "
                        f"but voxel sizes differ: {list(g.voxel_sizes_um)} "
                        f"(spread≈{g.spread_ratio:.2f}x)"
                    ),
                    str(parent),
                    {
                        "scale": list(g.scale),
                        "voxel_sizes_um": list(g.voxel_sizes_um),
                        "spread_ratio": g.spread_ratio,
                        "paths": [str(r.path) for r in g.records],
                    },
                )
            )
    return findings


def audit_paths(
    inputs: Sequence[Path],
    *,
    volume_shape: tuple[int, int, int] | None = None,
    sample_invalid: bool = True,
    skip_tiff: bool = False,
) -> tuple[list[Path], list[Finding]]:
    dirs = discover_tifxyz_dirs(inputs)
    findings: list[Finding] = []
    if not dirs:
        findings.append(
            Finding(
                "no_tifxyz_found",
                "error",
                "no tifxyz directories (with meta.json) found under inputs",
                None,
                {"inputs": [str(p) for p in inputs]},
            )
        )
        return dirs, findings

    metas: dict[Path, dict[str, Any] | None] = {}
    for d in dirs:
        f, meta = check_meta(d)
        findings.extend(f)
        metas[d] = meta
        if not skip_tiff:
            findings.extend(check_tiffs(d, sample_invalid=sample_invalid))
        findings.extend(check_bbox(d, meta, volume_shape))

    findings.extend(check_sibling_ambiguity(dirs))
    return dirs, findings
