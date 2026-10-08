"""Real-data probe for villa #1586: does cache_max_gb bound the on-disk cache across reopens?"""
import os, sys, json, warnings
warnings.filterwarnings("ignore")
from vesuvius.ink_detection.volume_io import open_volume_root, disk_cache_subdir
from pathlib import Path
URL = "s3://vesuvius-challenge-open-data/PHercParis4/volumes/20260411134726-2.400um-0.2m-78keV-masked.zarr"
cache_dir, budget_gb, z0 = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
root = open_volume_root(URL, cache_dir=cache_dir, cache_max_gb=budget_gb)
a = root["3"]
C = 128
zc, yc, xc = a.shape[0]//2, a.shape[1]//2, a.shape[2]//2
nonzero = 0
# 4 z-chunks x 5 y-chunks x 1 x-chunk = 20 chunks per run, distinct per z0 offset
for dz in range(4):
    for dy in range(5):
        z = (zc//C + z0 + dz) * C; y = (yc//C + dy) * C; x = (xc//C) * C
        blk = a[z:z+C, y:y+C, x:x+C]
        nonzero += int((blk != 0).any())
sub = disk_cache_subdir(URL, Path(cache_dir))
total = sum(p.stat().st_size for p in sub.rglob("*") if p.is_file())
print(json.dumps({"z0": z0, "chunks_read": 20, "nonempty_chunks": nonzero,
                  "cache_bytes": total, "budget_bytes": int(budget_gb*1e9),
                  "ratio": round(total/(budget_gb*1e9), 3)}))
