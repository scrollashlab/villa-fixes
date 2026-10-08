"""Apply the pre-registered checks (docs/preregistration.md) to the catalog + mesh scan; write metadata-only results.
Usage: python analyze.py SCAN_JSONL VOLUME_SHAPES_JSON OUT_JSON"""
import json, math, re, sys, datetime, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import load_catalog, holdout, XFRAME_SRC
sys.path.insert(0, XFRAME_SRC)
from xframe.catalog import Catalog

SQ2 = math.sqrt(2.0)
REAL = ["B", "O", "F", "S", "W", "A1", "A2", "N1", "N2", "N3", "D1", "D2", "D3", "D4", "P1", "K1", "K2", "V1", "C1"]
PRIOR = {"F-marker": "#1618", "B-marker": "#1734", "V1": "#1211/#1617/#1503/#1516", "C1": "#1730"}


def fisher_two_sided(a, b, c, d):
    """2x2 [[a,b],[c,d]] two-sided Fisher exact p (sum of tables with p <= p_obs)."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
    def p(x): return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)
    lo, hi = max(0, c1 - r2), min(r1, c1); po = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= po * (1 + 1e-9)))


def px_ok(px_str, pixel_um, long_id, level=0):
    """Pre-registered: px equals pixel_size_um rounded to printed decimals, or the px token of the volume long_id
    (for renders also the effective size pixel*2^level)."""
    dec = len(px_str.split(".")[1]) if "." in px_str else 0
    v = float(px_str); cands = []
    if pixel_um is not None:
        cands += [round(pixel_um * 2 ** L, dec) for L in {0, level}]
    m = re.search(r"-([0-9.]+)um", long_id or "")
    if m:
        cands += [round(float(m.group(1)) * 2 ** L, dec) for L in {0, level}]
    match_pix = pixel_um is not None and any(abs(v - round(pixel_um * 2 ** L, dec)) < 1e-9 for L in {0, level})
    return any(abs(v - c) < 1e-9 for c in cands), match_pix


def parse_date(s):
    if not s: return None
    t = s.replace("Z", "+00:00") if not s.endswith("+00:00Z") else s[:-1]
    try:
        d = datetime.datetime.fromisoformat(t)
        return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def main():
    scan_path, shapes_path, out_path = sys.argv[1:4]
    md = load_catalog(); cat = Catalog.load(None) if False else Catalog(md)
    scan = {}
    for l in open(scan_path):
        r = json.loads(l); scan[r["path"]] = r
    shapes = {(r["sample"], r["volume"]): r for r in json.load(open(shapes_path))}
    rows = collections.defaultdict(list)   # class -> list of {split, defect, ...}
    quirks = collections.Counter(); notcomp = collections.Counter()

    def add(cls, sample, ident, defect, info, split_id=None):
        rows[cls].append({"holdout": holdout(sample, split_id or ident), "defect": bool(defect), "sample": sample, "id": ident, **info})

    # index of artifacts by canonical source path (copy_info.source_path) and by bucket path
    by_src = {}; by_path = {}
    for s, e in md["samples"].items():
        for g, seg in e["segments"].items():
            for d in seg.get("data", []):
                for o in d["origins"]:
                    rec = (s, g, d["type"], d["origins"][0]["path"], json.dumps(d.get("parameters") or {}, sort_keys=True))
                    by_path[o["path"]] = rec
                    ci = o.get("copy_info") or {}
                    if ci.get("source_path"): by_src[ci["source_path"]] = rec

    def resolve(sp):
        if not sp: return None
        if sp in by_src: return by_src[sp]
        m = re.match(r"s3://vesuvius-challenge/(.*)$", sp)
        return by_path.get(m.group(1)) if m else None

    edges = {}
    for s, e in md["samples"].items():
        vols = e.get("volumes") or {}
        T = {}
        for blk in (e["sample"].get("properties") or {}).get("volume_transforms") or []:
            for t in blk.get("transforms") or []:
                T.setdefault(blk["from_volume_id"], set()).add(t["to_volume_id"])
        for g, seg in e["segments"].items():
            ov = seg.get("original_volume_id"); props = seg.get("properties") or {}; cov = props.get("volume_coverage") or {}
            s_ds = float(props.get("original_volume_downscale") or 1)
            ents = seg.get("data", [])
            meshes = {d["type"]: d for d in ents if d["type"] in ("tifxyz", "tifxyz-normalized")}
            # ---------- D1
            df = (seg.get("creation") or {}).get("derived_from") or {}
            if df.get("type") == "volume":
                add("D1", s, g, df.get("id") != ov, {"declared": df.get("id"), "original_volume_id": ov})
            # ---------- C1 (prior art #1730)
            vol = vols.get(ov); sd = parse_date((seg.get("creation") or {}).get("date"))
            scan_d = parse_date(((e.get("scans") or {}).get((vol or {}).get("scan_id")) or {}).get("creation", {}).get("date")) if vol else None
            if sd and scan_d:
                add("C1", s, g, sd < scan_d, {"segment_date": str(sd), "scan_date": str(scan_d)})
            else:
                quirks["C1_unparseable_or_unresolvable_date"] += 1
            # ---------- K1 / K2
            for V in cov:
                if V != ov:
                    try: cat.matrix(s, ov, V); ok = True
                    except KeyError: ok = False
                    add("K1", s, g, not ok, {"volume": V})
            reach = T.get(ov, set())
            for V in sorted(reach):
                add("K2", s, g, V not in cov, {"volume": V})
            # ---------- N3, N1, D4, P1, N2, D2
            for d in ents:
                p = d["origins"][0]["path"]; t = d["type"]
                if t in ("tifxyz", "tifxyz-normalized", "tifxyz-transformed", "tifxyz-flattened", "layers-zarr"):
                    add("N3", s, g, not p.startswith(f"{s}/segments/{seg['long_id']}/"), {"path": p})
                src = resolve(((d.get("creation_info") or {}).get("derived_from") or {}).get("source_path"))
                if src: edges[(s, g, p)] = (src[0], src[1], src[3])
                elif (d.get("creation_info") or {}).get("derived_from"):
                    quirks[f"derived_from_unresolved:{t}"] += 1
                if t == "tifxyz-transformed":
                    V = (d.get("parameters") or {}).get("target_volume")
                    m = re.search(r"/mesh/(\d+)-on-(\d+)-([0-9.]+)um\.tifxyz/$", p)
                    if not m:
                        add("N1", s, g, True, {"path": p, "why": "unparseable"}); continue
                    vv = vols.get(V)
                    okpx, matchpix = px_ok(m.group(3), ((vv or {}).get("properties") or {}).get("pixel_size_um"), (vv or {}).get("long_id")) if vv else (True, None)
                    if vv is None: quirks["N1_target_volume_not_in_catalog"] += 1
                    elif okpx and not matchpix: quirks["N1_px_matches_long_id_only"] += 1
                    add("N1", s, g, (m.group(1) != g) or (m.group(2) != V) or not okpx,
                        {"path": p, "segid_in_path": m.group(1), "volume_in_path": m.group(2), "target_volume": V, "px": m.group(3),
                         "pixel_size_um": ((vv or {}).get("properties") or {}).get("pixel_size_um")})
                    dfi = ((d.get("creation_info") or {}).get("derived_from") or {})
                    add("D4", s, g, not (src and src[1] == g and src[2] == "tifxyz-normalized"), {"path": p, "resolved_type": src and src[2], "resolved_segment": src and src[1]})
                    if V != ov:
                        dec = (cov.get(V) or {}).get("overlap_ratio")
                        add("P1", s, g, dec is None or dec <= 0.3, {"path": p, "declared_overlap": dec})
                if t == "layers-zarr":
                    V = (d.get("parameters") or {}).get("target_volume"); L = int((d.get("parameters") or {}).get("render_level") or 0)
                    m = re.search(r"surface-volumes/([0-9.]+)um-.*?volume-(\d+)(?:-L(\d+))?\.zarr/$", p)
                    vv = vols.get(V)
                    if not m:
                        add("N2", s, g, True, {"path": p, "why": "unparseable"})
                    else:
                        okpx = px_ok(m.group(1), ((vv or {}).get("properties") or {}).get("pixel_size_um"), (vv or {}).get("long_id"), L)[0] if vv else True
                        add("N2", s, g, m.group(2) != V or not okpx, {"path": p, "volume_in_path": m.group(2), "target_volume": V, "px": m.group(1), "render_level": L,
                                                                    "path_level": int(m.group(3) or 0)})
                        if int(m.group(3) or 0) != L: quirks["N2_exploratory_render_level_token_mismatch"] += 1
                    if src:
                        stype, sseg, spath = src[2], src[1], src[3]
                        if stype in ("tifxyz-transformed",):
                            sp = json.loads(src[4]).get("target_volume")
                            bad = sp != V
                        elif stype in ("tifxyz-normalized", "tifxyz"):
                            bad = (V != ov) or s_ds != 1
                        else:
                            bad = None
                        if bad is not None:
                            add("D2", s, g, bad, {"path": p, "target_volume": V, "source_type": stype, "source_path": spath, "original_volume_id": ov, "downscale": s_ds})
                        else:
                            quirks[f"D2_source_not_a_mesh:{stype}"] += 1
            # ---------- W (needs scan of the tifxyz original)
            if "tifxyz" in meshes:
                r = scan.get(meshes["tifxyz"]["origins"][0]["path"])
                if r and "error" not in r and r["meta"].get("scale"):
                    su, sv = r["meta"]["scale"][0], r["meta"]["scale"][1]
                    wexp, hexp = r["cols"] / su, r["rows"] / sv
                    w, h = props.get("width"), props.get("height")
                    ok = abs(w - wexp) < 1 and abs(h - hexp) < 1
                    swap = abs(w - r["rows"] / sv) < 1 and abs(h - r["cols"] / su) < 1
                    add("W", s, g, not ok, {"path": r["path"], "declared_wh": [w, h], "computed_wh": [wexp, hexp], "swap": (not ok) and swap,
                                            "grid_rows_cols": [r["rows"], r["cols"]], "scale": [su, sv]})
                else:
                    notcomp["W_no_scan_or_scale"] += 1
            # ---------- B / O (reference = tifxyz original if present, else normalized)
            ref = None
            for typ in ("tifxyz", "tifxyz-normalized"):
                if typ in meshes:
                    r = scan.get(meshes[typ]["origins"][0]["path"])
                    if r and "error" not in r and "coverage" in r:
                        ref = r; break
            if ref is None:
                notcomp["BO_no_reference_mesh"] += len(cov); continue
            cm = (seg.get("creation") or {}).get("metadata") or {}
            marker = bool(cm.get("bbox")) and any(float(v) == -1 for c in cm["bbox"] for v in c)
            for V, dv in cov.items():
                c = ref["coverage"].get(V) or {}
                if c.get("no_transform"):
                    notcomp["BO_no_transform"] += 1; continue
                gV = None
                for k in ("vc", "strict"):
                    if k in c and c[k].get("grid_step_V"): gV = c[k]["grid_step_V"]
                if gV is None and ref.get("grid_step_own"):
                    gV = ref["grid_step_own"] * ref["downscale"] * c["sigma_max"]
                tol = (gV or 0) + 0.01
                db = dv.get("bbox_transformed")
                if db is not None and c.get("vc", {}).get("bbox"):
                    res = {}
                    for k in ("vc", "strict"):
                        cb = c[k]["bbox"]
                        if cb is None: continue
                        diffs = [db[i][j] - cb[i][j] for i in range(2) for j in range(3)]
                        short = any(cb[0][j] < db[0][j] - tol or cb[1][j] > db[1][j] + tol for j in range(3))
                        loose = (not short) and any(abs(x) > tol for x in diffs)
                        res[k] = {"computed": cb, "max_abs_diff": max(abs(x) for x in diffs), "short": short, "loose": loose}
                    fail = all((res[k]["short"] or res[k]["loose"]) for k in res)
                    sub = None
                    if fail:
                        sub = "B-marker" if marker else ("B-short" if res["vc"]["short"] else "B-loose")
                    add("B", s, g, fail, {"volume": V, "reference": ref["type"], "reference_path": ref["path"], "declared": db,
                                          "computed_vc": res["vc"]["computed"], "max_abs_diff_vc": res["vc"]["max_abs_diff"],
                                          "max_abs_diff_strict": res.get("strict", {}).get("max_abs_diff"), "tol": tol, "sub": sub,
                                          "stored_bbox_has_marker": marker, "matrix": c.get("matrix_how")})
                else:
                    notcomp["B_no_declared_or_computed"] += 1
                do = dv.get("overlap_ratio")
                if do is not None and "inside_frac" in c.get("vc", {}):
                    res = {}
                    for k in ("vc", "strict"):
                        if "inside_frac" not in c.get(k, {}): continue
                        fb = c[k].get("f_band") or 0.0
                        res[k] = {"computed": c[k]["inside_frac"], "f_band": fb, "fail": abs(do - c[k]["inside_frac"]) > 0.01 + fb}
                    fail = all(res[k]["fail"] for k in res)
                    add("O", s, g, fail, {"volume": V, "reference": ref["type"], "reference_path": ref["path"], "declared": do,
                                          "computed_vc": res["vc"]["computed"], "f_band_vc": res["vc"]["f_band"],
                                          "computed_strict": res.get("strict", {}).get("computed"), "stored_bbox_has_marker": marker})
                else:
                    notcomp["O_no_declared_or_shape"] += 1

    # ---------- D3 cycles
    G = collections.defaultdict(list)
    for (s, g, p), (s2, g2, p2) in edges.items(): G[p].append(p2)
    color = {}; cycles = 0
    def dfs(u):
        nonlocal cycles
        color[u] = 1
        for v in G.get(u, []):
            if color.get(v) == 1: cycles += 1
            elif color.get(v) is None: dfs(v)
        color[u] = 2
    sys.setrecursionlimit(100000)
    for u in list(G):
        if color.get(u) is None: dfs(u)
    for (s, g, p) in edges:
        pass
    rows["D3"].append({"holdout": False, "defect": cycles > 0, "sample": "*", "id": "graph", "edges": len(edges), "cycles": cycles})

    # ---------- per-mesh: F, S, A1, A2
    for p, r in scan.items():
        if "error" in r: notcomp["mesh_scan_error"] += 1; continue
        m = r["meta"]; s, g = r["sample"], r["segment"]
        sc = m.get("scale")
        gstep = max(1 / sc[0], 1 / sc[1]) if sc else None
        if m.get("bbox") and gstep and r.get("bbox_vc"):
            tol = gstep + 0.01; fails = {}
            for k in ("vc", "strict"):
                cb = r.get(f"bbox_{k}")
                if cb is None: continue
                diffs = [m["bbox"][i][j] - cb[i][j] for i in range(2) for j in range(3)]
                fails[k] = (max(abs(x) for x in diffs), any(abs(x) > tol for x in diffs))
            fail = all(v[1] for v in fails.values())
            marker = any(float(v) == -1 for c in m["bbox"] for v in c)
            add("F", s, g, fail, {"path": p, "type": r["type"], "declared": m["bbox"], "computed_vc": r["bbox_vc"], "computed_strict": r.get("bbox_strict"),
                                  "max_abs_diff_vc": fails.get("vc", (None,))[0], "max_abs_diff_strict": fails.get("strict", (None,))[0], "tol": tol,
                                  "sub": ("F-marker" if marker else "F-other") if fail else None})
        else:
            quirks[f"F_not_computable:{'no_bbox' if not m.get('bbox') else 'no_scale'}:{r['type']}"] += 1
        if sc and r.get("n_pairs", 0) >= 100:
            ratio = math.sqrt(sc[0] * sc[1]) * r["spacing_median"]
            add("S", s, g, not (1 / SQ2 <= ratio <= SQ2), {"path": p, "type": r["type"], "scale": sc, "spacing_median": r["spacing_median"], "ratio": ratio})
        if m.get("area_vx2") is not None:
            comp = r["area_vx2_computed"]
            rel = (m["area_vx2"] / comp - 1) if comp else None
            add("A1", s, g, rel is None or abs(rel) > 0.25, {"path": p, "type": r["type"], "declared": m["area_vx2"], "computed": comp, "rel": rel})
            if m.get("area_cm2") is not None and m["area_vx2"]:
                seg = md["samples"][s]["segments"][g]; ov = seg["original_volume_id"]
                if r["type"] == "tifxyz-transformed":
                    V = re.search(r"-on-(\d+)-", p).group(1); fv = ((md["samples"][s]["volumes"].get(V) or {}).get("properties") or {}).get("pixel_size_um")
                else:
                    pv = ((md["samples"][s]["volumes"].get(ov) or {}).get("properties") or {}).get("pixel_size_um")
                    fv = pv * float(seg["properties"].get("original_volume_downscale") or 1) if pv else None
                if fv:
                    implied = math.sqrt(m["area_cm2"] * 1e8 / m["area_vx2"])
                    add("A2", s, g, abs(implied / fv - 1) > 0.02, {"path": p, "type": r["type"], "implied_voxel_um": implied, "frame_voxel_um": fv})
                else:
                    notcomp["A2_frame_voxel_unknown"] += 1
        else:
            quirks[f"meta_without_area_vx2:{r['type']}"] += 1

    # ---------- V1 (volume level)
    for (s, v), r in shapes.items():
        if r.get("catalog_shape") is None:
            quirks["V1_catalog_shape_null"] += 1; continue
        if r.get("zarray_shape") is None:
            notcomp["V1_no_zarray"] += 1; continue
        add("V1", s, v, list(r["catalog_shape"]) != list(r["zarray_shape"]), {"catalog_shape": r["catalog_shape"], "zarray_shape": r["zarray_shape"]}, split_id=v)

    # ---------- summarise
    summary = {}
    for cls in REAL:
        R = rows.get(cls, [])
        dd = [x for x in R if not x["holdout"]]; hh = [x for x in R if x["holdout"]]
        a, b = sum(x["defect"] for x in dd), len(dd) - sum(x["defect"] for x in dd)
        c, d = sum(x["defect"] for x in hh), len(hh) - sum(x["defect"] for x in hh)
        ent = {"denominator": len(R), "defects": a + c, "discovery": [a, len(dd)], "holdout": [c, len(hh)]}
        if a >= 3:
            exp = a / len(dd) * len(hh) if dd else 0
            if exp < 1: ent["replication"] = "not testable (expected hold-out count < 1)"
            else:
                pf = fisher_two_sided(a, b, c, d)
                ent["fisher_p"] = pf; ent["replication"] = "replicates" if (c >= 1 and pf >= 0.01) else "does not replicate"
        subs = collections.Counter(x.get("sub") for x in R if x["defect"] and x.get("sub"))
        if subs: ent["subclasses"] = dict(subs)
        ent["by_sample"] = dict(collections.Counter(x["sample"] for x in R if x["defect"]))
        summary[cls] = ent
    json.dump({"summary": summary, "quirks": dict(quirks), "not_computable": dict(notcomp),
               "rows": {k: v for k, v in rows.items()}}, open(out_path, "w"), indent=1)
    for k, v in summary.items():
        print(k, v["defects"], "/", v["denominator"], "disc", v["discovery"], "hold", v["holdout"], v.get("replication", ""), v.get("subclasses", ""), v["by_sample"])
    print("quirks", dict(quirks)); print("not computable", dict(notcomp))


if __name__ == "__main__":
    main()
