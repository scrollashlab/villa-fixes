"""Negative controls for stage 2 (no new fetches): (1) canvas predicted from every OTHER published transformed mesh of the
same segment (same render params) -- how often would a wrong mesh also match? (2) canvas from the segment's
tifxyz_normalized grid at the catalog render scale (no regrid) -- should not match where the mesh was regridded."""
import json, math, collections
import numpy as np
S2 = json.load(open("out/stage2-all-2026-10-07.json"))["rows"]
xf = [json.loads(l) for l in open("/workspace/vesuvius-lab/experiments/cross-frame-toolkit/out/full-verify-2026-10-07.jsonl")]
bymesh = {r["mesh"].rstrip("/"): r for r in xf}
byseg = collections.defaultdict(list)
for r in xf: byseg[(r["sample"], r["segment"])].append(r)
lr = lambda x: max(1, int(math.floor(x + 0.5)))
def canvas(hw, sc, rs):
    sx, sy = (sc if isinstance(sc, list) else [sc, sc])[:2]
    return [lr(hw[1] * (rs / float(np.float32(sx)))), lr(hw[0] * (rs / float(np.float32(sy))))]
wrong_total = wrong_match = 0; vols_with_wrong_match = 0
for v in S2:
    if v["derived_type"] != "tifxyz-transformed": continue
    rs = float(v["scale"]) * 2.0 ** (-int(v["group_idx"]))
    cs = [int(v["canvas_size"][0]), int(v["canvas_size"][1])]
    any_m = False
    for m in byseg[(v["sample"], v["segment"])]:
        if m["mesh"].rstrip("/") == v["mesh"]: continue
        wrong_total += 1
        if canvas(m["published_shape"], m["published_scale"], rs) == cs: wrong_match += 1; any_m = True
    vols_with_wrong_match += any_m
print(f"wrong-mesh control: {wrong_match}/{wrong_total} (other mesh, same segment) also match; volumes with any such match: {vols_with_wrong_match}/688")
# copies are byte-identical to the normalized mesh, so those wrong-mesh matches are expected; split them
cm = collections.Counter()
for v in S2:
    if v["derived_type"] != "tifxyz-transformed": continue
    rs = float(v["scale"]) * 2.0 ** (-int(v["group_idx"])); cs = [int(v["canvas_size"][0]), int(v["canvas_size"][1])]
    for m in byseg[(v["sample"], v["segment"])]:
        if m["mesh"].rstrip("/") == v["mesh"]: continue
        if canvas(m["published_shape"], m["published_scale"], rs) == cs:
            cm[(bymesh[v["mesh"]]["kind"], m["kind"], m["regrid_factors"] is None, bymesh[v["mesh"]]["regrid_factors"] is None)] += 1
print("wrong-mesh matches by (named kind, other kind, other unregridded, named unregridded):", dict(cm))
