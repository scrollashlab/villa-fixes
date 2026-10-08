"""Access to the open-data catalog (`metadata.json`): volumes, voxel sizes, sample-level transforms, segment meshes."""
from __future__ import annotations
import gzip, json
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from .tifxyz import Source


@dataclass
class Mesh:
    key: str                 # bucket key of the tifxyz directory
    kind: str                # 'normalized' | 'derived' | 'copy' | 'original' | 'flattened'
    target_volume: str | None
    process: str | None


@dataclass
class Segment:
    sample: str
    id: str
    long_id: str
    original_volume: str | None
    downscale: float
    meshes: list = field(default_factory=list)

    @property
    def normalized(self):
        return next((m for m in self.meshes if m.kind == "normalized"), None)


class Catalog:
    def __init__(self, data: dict):
        self.data = data
        self.samples = data.get("samples", {})

    @classmethod
    def load(cls, path_or_none: str | None = None, src: Source | None = None) -> "Catalog":
        if path_or_none and Path(path_or_none).exists():
            raw = Path(path_or_none).read_bytes()
        else:
            raw = (src or Source()).get("metadata.json")
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return cls(json.loads(raw))

    # volumes -------------------------------------------------------------
    def volume(self, sample: str, vol: str) -> dict:
        return self.samples[sample]["volumes"].get(vol) or {}

    def voxel_um(self, sample: str, vol: str):
        return (self.volume(sample, vol).get("properties") or {}).get("pixel_size_um")

    # transforms ----------------------------------------------------------
    def _sample_transforms(self, sample: str) -> dict:
        out = {}
        props = self.samples[sample]["sample"].get("properties") or {}
        for blk in props.get("volume_transforms") or []:
            for t in blk.get("transforms") or []:
                out[(blk["from_volume_id"], t["to_volume_id"])] = t
        return out

    def matrix(self, sample: str, src_vol: str, dst_vol: str):
        """Return (3x4 matrix, provenance dict). Identity if src == dst. Uses the sample-level
        `volume_transforms` list (what the publishing pipeline used); falls back to inverting dst->src."""
        if src_vol == dst_vol:
            return np.hstack([np.eye(3), np.zeros((3, 1))]), {"how": "identity"}
        T = self._sample_transforms(sample)
        if (src_vol, dst_vol) in T:
            t = T[(src_vol, dst_vol)]
            return np.array(t["matrix"], float), {"how": "catalog", "derivation_path": t.get("derivation_path")}
        if (dst_vol, src_vol) in T:
            from .geom import invert_affine
            t = T[(dst_vol, src_vol)]
            return invert_affine(np.array(t["matrix"], float)), {"how": "inverted catalog", "derivation_path": t.get("derivation_path")}
        avail = sorted({f"{a}->{b}" for a, b in T})
        raise KeyError(f"no catalog transform {src_vol}->{dst_vol} in {sample}; available: {avail}")

    # segments ------------------------------------------------------------
    def segment(self, sample: str, seg: str) -> Segment:
        segs = self.samples[sample]["segments"]
        if seg not in segs:  # allow long_id
            hits = [k for k, g in segs.items() if g.get("long_id") == seg or (g.get("long_id") or "").startswith(seg)]
            if len(hits) != 1:
                raise KeyError(f"segment {seg!r} not found (or ambiguous) in {sample}")
            seg = hits[0]
        g = segs[seg]
        s = Segment(sample=sample, id=seg, long_id=g.get("long_id") or seg, original_volume=g.get("original_volume_id"),
                    downscale=float((g.get("properties") or {}).get("original_volume_downscale") or 1))
        for e in g.get("data", []):
            t = e.get("type"); key = e["origins"][0]["path"]
            ci = e.get("creation_info") or {}
            if t == "tifxyz-normalized":
                s.meshes.append(Mesh(key, "normalized", s.original_volume, ci.get("process")))
            elif t == "tifxyz-transformed":
                proc = ci.get("process")
                kind = "copy" if proc == "copy-normalized-for-original" else "derived"
                s.meshes.append(Mesh(key, kind, (e.get("parameters") or {}).get("target_volume"), proc))
            elif t == "tifxyz":
                s.meshes.append(Mesh(key, "original", None, ci.get("process")))
            elif t == "tifxyz-flattened":
                s.meshes.append(Mesh(key, "flattened", None, ci.get("process")))
        return s

    def segments(self, samples=None):
        for sid in sorted(self.samples):
            if samples and sid not in samples:
                continue
            for gid in sorted(self.samples[sid]["segments"]):
                yield self.segment(sid, gid)
