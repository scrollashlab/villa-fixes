import sys, hashlib, warnings, json
warnings.filterwarnings("ignore")
from vesuvius.ink_detection.volume_io import open_volume_root
URL = "s3://vesuvius-challenge-open-data/PHercParis4/volumes/20260411134726-2.400um-0.2m-78keV-masked.zarr"
cached = open_volume_root(URL, cache_dir=sys.argv[1], cache_max_gb=0.03)["3"]
direct = open_volume_root(URL)["3"]
C=128; zc,yc,xc=[s//2//C for s in cached.shape]
same=0; n=0
for z0 in (0,4,8):
  for dz in range(4):
    for dy in range(5):
      z=(zc+z0+dz)*C; y=(yc+dy)*C; x=xc*C
      a=cached[z:z+C,y:y+C,x:x+C]; b=direct[z:z+C,y:y+C,x:x+C]
      n+=1; same+=int(hashlib.sha256(a.tobytes()).digest()==hashlib.sha256(b.tobytes()).digest())
print(json.dumps({"blocks":n,"byte_identical":same}))
