"""Stage-1/2 measurement for docs/preregistration.md (metadata only: catalog, .zattrs, 0/.zarray, meta.json, x.tif IFD via Range).
Usage: python measure.py stage1|stage2 OUT_JSON"""
import json, sys, math, hashlib, struct, time, urllib.request, collections
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import numpy as np

BASE = "https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com"
CAT = "/workspace/vesuvius-lab/experiments/cross-frame-toolkit/data/cache/metadata-2026-10-07.json"
XF = "/workspace/vesuvius-lab/experiments/cross-frame-toolkit/out/full-verify-2026-10-07.jsonl"
GEAL = "/tmp/vcr/audit/pairs.json"
CLS = "out/geal-classes-reconstructed.json"


def req(key, rng=None, method="GET"):
    r = urllib.request.Request(f"{BASE}/{quote(key, safe='/')}", method=method)
    if rng: r.add_header("Range", f"bytes={rng[0]}-{rng[1]}")
    for a in range(4):
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): raise
            time.sleep(2 ** a)
        except Exception:
            time.sleep(2 ** a)
    raise RuntimeError(f"fetch failed {key}")


def tif_hw(key):
    b, _ = req(key, (0, 65535))
    e = "<" if b[:2] == b"II" else ">"
    magic = struct.unpack(e + "H", b[2:4])[0]
    big = magic == 43
    off = struct.unpack(e + "Q", b[8:16])[0] if big else struct.unpack(e + "I", b[4:8])[0]
    need = off + (8 + 20 * 64 if big else 2 + 12 * 64)
    if need > len(b):
        b2, _ = req(key, (off, need)); base = off; buf = b2
    else:
        base = 0; buf = b
    p = off - base
    n = struct.unpack(e + ("Q" if big else "H"), buf[p:p + (8 if big else 2)])[0]; p += 8 if big else 2
    tags = {}
    for i in range(n):
        ent = buf[p:p + (20 if big else 12)]; p += 20 if big else 12
        tag, typ = struct.unpack(e + "HH", ent[:4])
        if tag in (256, 257):
            if big:
                v = struct.unpack(e + ("H" if typ == 3 else "I" if typ == 4 else "Q"), ent[12:12 + (2 if typ == 3 else 4 if typ == 4 else 8)])[0]
            else:
                v = struct.unpack(e + ("H" if typ == 3 else "I"), ent[8:8 + (2 if typ == 3 else 4)])[0]
            tags[tag] = v
    return tags[257], tags[256]   # (H, W)


def lround(x): return max(1, int(math.floor(x + 0.5)))


def strip(p): return p.replace("s3://vesuvius-challenge/", "").replace("s3://vesuvius-challenge-open-data/", "")


def catalog_volumes():
    md = json.load(open(CAT)); out = {}
    for sid, s in md["samples"].items():
        for gid, g in s["segments"].items():
            for e in g["data"]:
                if e["type"] != "layers-zarr": continue
                ci = e.get("creation_info") or {}; prm = ((ci.get("provenance") or {}).get("parameters") or {})
                out[e["origins"][0]["path"].rstrip("/")] = dict(
                    sample=sid, segment=gid, process=ci.get("process"), render_date=ci.get("date"),
                    derived_type=(ci.get("derived_from") or {}).get("data_type"),
                    mesh=strip((ci.get("derived_from") or {}).get("source_path") or "").rstrip("/"),
                    seg_path_param=strip(prm.get("segmentation-path") or "").rstrip("/"),
                    scale=prm.get("scale"), group_idx=prm.get("group-idx"), commit=prm.get("commit"),
                    affine=[prm.get(k) for k in ("affine-transform", "affines", "affine-matrix")],
                    crop=[prm.get(k) for k in ("crop-x", "crop-y", "crop-width", "crop-height")],
                    scale_seg=prm.get("scale-segmentation"), target_volume=(e.get("parameters") or {}).get("target_volume"))
    return out


def measure(path, c):
    r = dict(volume=path, **c)
    try:
        za = json.loads(req(path + "/.zattrs")[0]); r["canvas_size"] = za.get("canvas_size")
        r["zattrs_keys"] = sorted(za.keys())
        try: r["level0_shape"] = json.loads(req(path + "/0/.zarray")[0]).get("shape")
        except Exception as ex: r["level0_error"] = repr(ex)
        mesh = c["mesh"] or c["seg_path_param"]
        meta = json.loads(req(mesh + "/meta.json")[0]); sc = meta.get("scale")
        sx, sy = (sc if isinstance(sc, list) else [sc, sc])[:2]
        h, w = tif_hw(mesh + "/x.tif"); r.update(mesh_scale=[sx, sy], mesh_hw=[h, w])
        _, hd = req(mesh + "/x.tif", method="HEAD"); r["mesh_x_last_modified"] = hd.get("Last-Modified")
        applicable = not any(a for a in c["affine"]) and not c["scale_seg"] and all(v in ("0", None, "") for v in c["crop"])
        r["applicable"] = applicable
        rs = float(c["scale"] or 1) * 2.0 ** (-int(c["group_idx"] or 0))
        W = lround(w * (rs / float(np.float32(sx)))); H = lround(h * (rs / float(np.float32(sy))))
        r["predicted_canvas_WH"] = [W, H]
        cs = r["canvas_size"]
        r["match_canvas"] = bool(cs) and [int(cs[0]), int(cs[1])] == [W, H]
        l0 = r.get("level0_shape")
        r["match_level0"] = bool(l0) and [int(l0[-1]), int(l0[-2])] == [W, H]
        if cs: r["delta_WH"] = [int(cs[0]) - W, int(cs[1]) - H]
    except Exception as ex:
        r["error"] = repr(ex)[:300]
    return r


def main():
    stage, out = sys.argv[1], sys.argv[2]
    cat = catalog_volumes()
    xf = {json.loads(l)["mesh"].rstrip("/"): json.loads(l)["published_shape"] for l in open(XF)}
    if stage == "stage1":
        cls = json.load(open(CLS)); pairs = json.load(open(GEAL))
        scale1 = {(p["seg"], p["sv"]) for p in pairs if p["match_renderer"]}
        h = lambda x: hashlib.sha1((x["seg"] + "|" + x["sv"]).encode()).hexdigest()
        T = []
        for scroll in ["PHercParis4", "PHerc0139", "PHerc0500P2", "PHerc1667", "PHerc0814", "PHerc0343P"]:
            T += sorted([x for x in cls if not x["geal_reproduced"] and x["seg"].startswith(scroll + "/")], key=h)[:5]
        C1 = sorted([x for x in cls if (x["seg"], x["sv"]) in scale1], key=h)[:10]
        C2 = sorted([x for x in cls if x["geal_reproduced"] and (x["seg"], x["sv"]) not in scale1], key=h)[:5]
        todo = [("T", x) for x in T] + [("C1", x) for x in C1] + [("C2", x) for x in C2]
        jobs = []; missing = []
        for grp, x in todo:
            p = f"{x['seg']}/surface-volumes/{x['sv']}"
            if p in cat: jobs.append((grp, p, cat[p]))
            else: missing.append((grp, p))
    else:
        jobs = [("ALL", p, c) for p, c in sorted(cat.items())]; missing = []
    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(lambda j: dict(group=j[0], **measure(j[1], j[2])), jobs))
    for r in res:
        if r.get("mesh") in xf: r["xframe_shape_agrees"] = list(xf[r["mesh"]]) == r.get("mesh_hw")
    summ = collections.defaultdict(collections.Counter)
    for r in res:
        k = "error" if "error" in r else ("not_applicable" if not r["applicable"] else ("match" if r["match_canvas"] and r["match_level0"] else "mismatch"))
        summ[r["group"]][k] += 1
    doc = dict(generated=time.strftime("%Y-%m-%d %H:%M:%S %Z"), stage=stage, catalog=CAT, n=len(res), missing_from_catalog=missing,
               summary={g: dict(v) for g, v in summ.items()}, rows=res)
    json.dump(doc, open(out, "w"), indent=1)
    print(json.dumps({k: doc[k] for k in ("generated", "stage", "n", "missing_from_catalog", "summary")}, indent=1))


if __name__ == "__main__":
    main()
