"""Shared constants and helpers for the catalog QA audit."""
import hashlib, json, os
LAB = "/workspace/vesuvius-lab"
CAT = os.environ.get("CQA_CATALOG") or f"{LAB}/experiments/cross-frame-toolkit/data/cache/metadata-2026-10-07.json"
XFRAME_SRC = os.environ.get("XFRAME_SRC") or f"{LAB}/handoff/xframe/src"
BUCKET = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com"
CANON = "https://data.aws.ash2txt.org/samples"
MESH_TYPES = ("tifxyz", "tifxyz-normalized", "tifxyz-transformed", "tifxyz-flattened")
SALT = "catalog-qa-audit-2026-10-07/"


def holdout(sample: str, ident: str) -> bool:
    """Pre-registered split: held out iff int(sha256(salt+sample/id)[:8],16) % 10 < 3."""
    h = hashlib.sha256(f"{SALT}{sample}/{ident}".encode()).hexdigest()
    return int(h[:8], 16) % 10 < 3


def load_catalog():
    return json.load(open(CAT))


def url_of(origin: dict) -> str:
    root = origin["access_roots"][0]["url"]
    if root.startswith("s3://vesuvius-challenge-open-data"):
        return f"{BUCKET}/{origin['path']}"
    if root.startswith("https://data.aws.ash2txt.org"):
        return f"{root.rstrip('/')}/{origin['path']}"
    raise ValueError(root)
