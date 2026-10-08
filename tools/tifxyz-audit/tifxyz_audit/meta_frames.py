"""Frame-aware helpers for tifxyz ``meta.json`` (villa #1522).

``scale`` in ``meta.json`` means grid cells per voxel of *that mesh's own
scan*.  It is correct within one file and does not identify the physical
scan frame.  When a segment ships several meshes (different ``um`` in the
directory name) they often declare the same ``scale`` while voxel sizes
differ by tens of times.  Consumers that compare coordinates across those
meshes using only ``scale`` silently mix frames.

This module:

* documents and standardises an optional ``voxel_size_um`` field (µm per
  voxel, isotropic) so a consumer can tell frames apart without parsing
  directory names;
* parses the conventional ``-<float>um`` token from a tifxyz directory name;
* annotates an existing ``meta.json`` from its directory name;
* reports same-``scale`` / different-``voxel_size_um`` ambiguity across a
  segment ``mesh/`` tree (metadata only; no TIFF reads).

Scale equality uses a relative tolerance (see ``SCALE_RTOL``): open-data
``meta.json`` files mix the JSON literal ``0.05`` with the float64 expansion
of float32 ``0.05`` (``0.05000000074505806``).  Exact float equality falsely
split those siblings and broke ``frames_comparable`` on same-µm twins.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

VOXEL_SIZE_UM_KEY = "voxel_size_um"

# Relative tolerance for comparing meta.scale pairs.
#
# Justification from public open-data metas (PHercParis4 / PHerc0172, 2026-10-05):
# observed pair ``0.05`` vs ``0.05000000074505806`` (= float(np.float32(0.05)))
# has relative difference ≈ 1.49e-8.  ``rel_tol=1e-6`` is ~67× that gap (covers
# float32↔float64 round-trip with margin) while remaining far tighter than any
# intentional scale change (e.g. 0.05 vs 0.1 → rel 1.0).  ``abs_tol=0``: scales
# in this corpus are O(1e-2)–O(1), so relative comparison dominates.
SCALE_RTOL = 1e-6
SCALE_ATOL = 0.0

# Directory names look like:
#   -on-20260608103018-1.129um.tifxyz
#   20230702185753-7.91um
_UM_TOKEN = re.compile(r"(?P<um>\d+(?:\.\d+)?)um(?=$|[^A-Za-z0-9])", re.IGNORECASE)


def parse_voxel_size_um_from_name(name: str | Path) -> float | None:
    """Return µm/voxel parsed from a path or directory name, or None."""
    text = Path(name).name
    matches = list(_UM_TOKEN.finditer(text))
    if not matches:
        return None
    # Prefer the last token (directory names put um near the end).
    return float(matches[-1].group("um"))


def load_meta_dict(meta_path: str | Path) -> dict[str, Any]:
    path = Path(meta_path)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: meta.json root must be an object")
    return data


def write_meta_dict(meta_path: str | Path, meta: Mapping[str, Any]) -> None:
    path = Path(meta_path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(dict(meta), fh, indent=2)
        fh.write("\n")


def get_voxel_size_um(meta: Mapping[str, Any]) -> float | None:
    """Return ``voxel_size_um`` from a meta dict if present and numeric."""
    if VOXEL_SIZE_UM_KEY not in meta:
        return None
    value = meta[VOXEL_SIZE_UM_KEY]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise ValueError(
        f"{VOXEL_SIZE_UM_KEY!r} must be a number when present, got {value!r}"
    )


def scale_pair(meta: Mapping[str, Any]) -> tuple[float, float] | None:
    """Return ``(scale_x, scale_y)`` as stored in meta.json, or None."""
    raw = meta.get("scale")
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return None
    return (float(raw[0]), float(raw[1]))


def scale_pairs_close(
    a: tuple[float, float],
    b: tuple[float, float],
    *,
    rel_tol: float = SCALE_RTOL,
    abs_tol: float = SCALE_ATOL,
) -> bool:
    """Return True if two scale pairs agree within ``rel_tol`` / ``abs_tol``."""
    return math.isclose(a[0], b[0], rel_tol=rel_tol, abs_tol=abs_tol) and math.isclose(
        a[1], b[1], rel_tol=rel_tol, abs_tol=abs_tol
    )


def annotate_meta_voxel_size_um(
    tifxyz_dir: str | Path,
    *,
    voxel_size_um: float | None = None,
    overwrite: bool = False,
) -> float | None:
    """Write ``voxel_size_um`` into ``meta.json`` if missing (or overwrite).

    When ``voxel_size_um`` is omitted, the value is parsed from the directory
    name.  Returns the value written or already present, or None if neither a
    value nor a parseable name was available.
    """
    root = Path(tifxyz_dir)
    meta_path = root / "meta.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"Missing meta.json in {root}")

    meta = load_meta_dict(meta_path)
    existing = None
    if VOXEL_SIZE_UM_KEY in meta:
        existing = get_voxel_size_um(meta)

    resolved = voxel_size_um
    if resolved is None:
        resolved = parse_voxel_size_um_from_name(root)

    if existing is not None and not overwrite:
        return existing
    if resolved is None:
        return existing

    meta[VOXEL_SIZE_UM_KEY] = float(resolved)
    write_meta_dict(meta_path, meta)
    return float(resolved)


@dataclass(frozen=True)
class MeshMetaRecord:
    """One mesh directory's metadata used for frame comparison."""

    path: Path
    scale: tuple[float, float] | None
    voxel_size_um: float | None
    parsed_um_from_name: float | None

    @property
    def effective_voxel_size_um(self) -> float | None:
        if self.voxel_size_um is not None:
            return self.voxel_size_um
        return self.parsed_um_from_name


def iter_mesh_meta_records(mesh_root: str | Path) -> Iterator[MeshMetaRecord]:
    """Yield records for each child directory that contains ``meta.json``."""
    root = Path(mesh_root)
    if not root.is_dir():
        raise NotADirectoryError(root)
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        meta_path = child / "meta.json"
        if not meta_path.is_file():
            continue
        meta = load_meta_dict(meta_path)
        yield MeshMetaRecord(
            path=child,
            scale=scale_pair(meta),
            voxel_size_um=get_voxel_size_um(meta) if VOXEL_SIZE_UM_KEY in meta else None,
            parsed_um_from_name=parse_voxel_size_um_from_name(child),
        )


@dataclass(frozen=True)
class ScaleFrameAmbiguity:
    """Meshes that share ``scale`` but disagree on voxel size."""

    scale: tuple[float, float]
    records: tuple[MeshMetaRecord, ...]
    voxel_sizes_um: tuple[float, ...]

    @property
    def spread_ratio(self) -> float:
        sizes = self.voxel_sizes_um
        return max(sizes) / min(sizes) if sizes else 1.0


def _group_records_by_scale(
    records: Sequence[MeshMetaRecord],
) -> list[tuple[tuple[float, float], list[MeshMetaRecord]]]:
    """Cluster records whose scale pairs are close under ``SCALE_RTOL``."""
    groups: list[tuple[tuple[float, float], list[MeshMetaRecord]]] = []
    for record in records:
        if record.scale is None:
            continue
        placed = False
        for i, (rep_scale, members) in enumerate(groups):
            if scale_pairs_close(record.scale, rep_scale):
                members.append(record)
                placed = True
                break
        if not placed:
            groups.append((record.scale, [record]))
    return groups


def find_ambiguous_scale_frames(
    mesh_root: str | Path,
    *,
    use_dirname_fallback: bool = True,
) -> list[ScaleFrameAmbiguity]:
    """Find groups with matching ``scale`` (within ``SCALE_RTOL``) but differing voxel sizes.

    This is the metadata-only check described in villa #1522.  Voxel size is
    taken from ``voxel_size_um`` when present; if ``use_dirname_fallback`` is
    true, a missing field falls back to the ``um`` token in the directory name.
    Groups where fewer than two members have a known voxel size are skipped.

    Scale matching is tolerant: open-data metas store both ``0.05`` and the
    float32 expansion ``0.05000000074505806`` for the same intended step.
    """
    all_records = list(iter_mesh_meta_records(mesh_root))
    ambiguous: list[ScaleFrameAmbiguity] = []
    for scale, records in _group_records_by_scale(all_records):
        sizes: list[float] = []
        sized_records: list[MeshMetaRecord] = []
        for record in records:
            size = record.voxel_size_um
            if size is None and use_dirname_fallback:
                size = record.parsed_um_from_name
            if size is None:
                continue
            sizes.append(float(size))
            sized_records.append(record)
        if len(sizes) < 2:
            continue
        if max(sizes) / min(sizes) <= 1.0 + 1e-9:
            continue
        # Distinct sizes under one scale → ambiguity.
        unique = tuple(sorted(set(sizes)))
        if len(unique) < 2:
            continue
        ambiguous.append(
            ScaleFrameAmbiguity(
                scale=scale,
                records=tuple(sized_records),
                voxel_sizes_um=unique,
            )
        )
    return ambiguous


def frames_comparable(
    metas: Sequence[Mapping[str, Any]],
) -> bool:
    """Return True only if every meta shares scale *and* voxel_size_um.

    Scale pairs are compared with ``scale_pairs_close`` (``SCALE_RTOL``), not
    exact float equality.  Without ``voxel_size_um``, same ``scale`` is not
    enough to claim a shared frame (#1522).
    """
    if len(metas) < 2:
        return True
    scales = [scale_pair(m) for m in metas]
    voxels = [get_voxel_size_um(m) if VOXEL_SIZE_UM_KEY in m else None for m in metas]
    if any(s is None for s in scales) or any(v is None for v in voxels):
        return False
    assert scales[0] is not None
    if not all(scale_pairs_close(s, scales[0]) for s in scales[1:] if s is not None):
        return False
    # Voxel sizes: exact equality is fine (µm tokens are short decimals).
    return len(set(voxels)) == 1
