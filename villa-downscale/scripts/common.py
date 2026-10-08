import os
# Defaults are the lab box paths used for the 2026-10-07 run; override with environment variables.
CAT = os.environ.get("VDS_CATALOG") or "/workspace/vesuvius-lab/experiments/cross-frame-toolkit/data/cache/metadata-2026-10-07.json"   # local copy of the bucket metadata.json
CACHE = os.environ.get("VDS_CACHE") or "/workspace/vesuvius-lab/experiments/villa-downscale/data/cache"   # CC BY-NC, local only
BASE = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com"
# pre-registered (docs/preregistration.md): smallest + median normalized-mesh bytes per scroll
SEGMENTS = [("PHerc0139", "20260422000000"), ("PHerc0139", "20250108000002"),
            ("PHercParis4", "20260602204401"), ("PHercParis4", "20260623153216"),
            ("PHerc0500P2", "20250825181939"), ("PHerc0500P2", "20250825181917")]
