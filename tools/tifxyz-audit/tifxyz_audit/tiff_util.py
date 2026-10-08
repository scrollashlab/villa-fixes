"""Optional TIFF header / light sampling helpers (requires tifffile + numpy)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def tiff_available() -> bool:
    try:
        import numpy  # noqa: F401
        import tifffile  # noqa: F401

        return True
    except ImportError:
        return False


def read_tiff_shape(path: Path) -> tuple[int, ...]:
    import tifffile

    with tifffile.TiffFile(str(path)) as tf:
        series = tf.series[0]
        return tuple(int(x) for x in series.shape)


def sample_invalid_fraction(
    path: Path,
    *,
    max_values: int = 2_000_000,
) -> dict[str, Any]:
    """Estimate fraction of non-finite and sentinel -1 values.

    For arrays larger than ``max_values``, reads a strided subsample so large
    open-data meshes stay tractable. Returns exact counts when the array is
    fully read.
    """
    import numpy as np
    import tifffile

    arr = tifffile.imread(str(path))
    flat = np.asarray(arr, dtype=np.float64).ravel()
    total = int(flat.size)
    sampled = False
    if total > max_values:
        step = int(np.ceil(total / max_values))
        flat = flat[::step]
        sampled = True
    n = int(flat.size)
    nonfinite = int(np.sum(~np.isfinite(flat)))
    # Invalid-point convention in tifxyz: coordinates marked -1
    sentinel = int(np.sum(flat == -1.0))
    return {
        "path": str(path),
        "total_values": total,
        "values_examined": n,
        "sampled": sampled,
        "nonfinite": nonfinite,
        "sentinel_neg1": sentinel,
        "nonfinite_fraction": (nonfinite / n) if n else 0.0,
        "sentinel_neg1_fraction": (sentinel / n) if n else 0.0,
    }
