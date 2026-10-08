"""Read/write tifxyz directories from a local path or the public open-data bucket (anonymous HTTPS)."""
from __future__ import annotations
import io, json, os, time, urllib.error, urllib.request
from pathlib import Path
from urllib.parse import quote
import numpy as np
import tifffile

BUCKET_HTTPS = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com"


class Source:
    """Where mesh/catalog bytes come from.
    - remote (default): anonymous HTTPS to the open-data bucket; nothing is written to disk unless cache_dir is set.
    - root: a local directory laid out like the bucket (offline use / tests)."""

    def __init__(self, root: str | None = None, cache_dir: str | None = None, base_url: str = BUCKET_HTTPS):
        self.root = Path(root) if root else None
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.base_url = base_url.rstrip("/")

    def get(self, key: str, retries: int = 4) -> bytes:
        key = key.lstrip("/")
        if self.root is not None:
            return (self.root / key).read_bytes()
        if self.cache_dir is not None and (self.cache_dir / key).exists():
            return (self.cache_dir / key).read_bytes()
        url = f"{self.base_url}/{quote(key, safe='/')}"
        last = None
        for i in range(retries):
            try:
                with urllib.request.urlopen(url, timeout=300) as r:
                    data = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code in (403, 404):
                    raise FileNotFoundError(f"{url}: HTTP {e.code}") from e
                last = e
            except Exception as e:  # network hiccup
                last = e
            time.sleep(2 * (i + 1))
        else:
            raise last
        if self.cache_dir is not None:
            out = self.cache_dir / key
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        return data


def is_local_dir(path: str) -> bool:
    return os.path.isdir(path)


def read_meta(src: Source | None, key_or_dir: str) -> dict:
    if src is None or is_local_dir(key_or_dir):
        return json.loads((Path(key_or_dir) / "meta.json").read_text())
    return json.loads(src.get(key_or_dir.rstrip("/") + "/meta.json"))


def read_tifxyz(src: Source | None, key_or_dir: str):
    """Return (points float32 (rows, cols, 3), meta dict). Invalid cells keep their stored values.
    Channels are decoded one at a time into a preallocated array to bound peak memory on very large meshes."""
    P = None
    for i, c in enumerate("xyz"):
        if src is None or is_local_dir(key_or_dir):
            a = tifffile.imread(str(Path(key_or_dir) / f"{c}.tif"))
        else:
            b = src.get(key_or_dir.rstrip("/") + f"/{c}.tif")
            a = tifffile.imread(io.BytesIO(b)); del b
        if P is None:
            P = np.empty(a.shape + (3,), np.float32)
        elif a.shape != P.shape[:2]:
            raise ValueError(f"x/y/z.tif shapes differ: {P.shape[:2]} vs {c}.tif {a.shape}")
        P[..., i] = a; del a
    return P, read_meta(src, key_or_dir)


def write_tifxyz(out_dir: str, P: np.ndarray, meta: dict) -> None:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate("xyz"):
        tifffile.imwrite(str(out / f"{c}.tif"), np.ascontiguousarray(P[..., i], dtype=np.float32))
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
