"""CPU numerical reproduction of villa #1481 (pad-then-robust vs train semantics)."""
from __future__ import annotations

import numpy as np
from vesuvius.image_proc.intensity.normalization import normalize_robust


def main() -> None:
    source = np.arange(100, 100 + 3 * 4 * 4, dtype=np.float32).reshape(3, 4, 4)
    train = np.zeros((5, 4, 4), dtype=np.float32)
    train[1:4] = normalize_robust(source.copy())
    padded = np.zeros((5, 4, 4), dtype=np.float32)
    padded[1:4] = source
    inference_buggy = normalize_robust(padded.copy())
    mae = float(np.abs(train[1:4] - inference_buggy[1:4]).mean())
    maxae = float(np.abs(train[1:4] - inference_buggy[1:4]).max())
    print(f"padded zeros become ~ {inference_buggy[0, 0, 0]:.4f} (train keeps 0)")
    print(f"real-voxel MAE={mae:.4f} maxAE={maxae:.4f}")
    assert mae > 0.4 and maxae > 1.0


if __name__ == "__main__":
    main()
