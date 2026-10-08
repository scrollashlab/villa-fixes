"""Full streamed corpus verify with the installed xframe package (nothing persisted except result JSONL).
Usage: python full_verify.py CATALOG OUT_JSONL [WORKERS]"""
import json, sys, time, os
from concurrent.futures import ProcessPoolExecutor, as_completed
from xframe import __version__
from xframe.catalog import Catalog
from xframe.tifxyz import Source
from xframe.verify import verify_segment

CAT, OUT = sys.argv[1], sys.argv[2]
WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 3


def work(args):
    sample, seg_id = args
    cat = Catalog.load(CAT); src = Source()          # anonymous HTTPS, no cache_dir -> streamed
    seg = cat.segment(sample, seg_id)
    t0 = time.time()
    rows = verify_segment(cat, seg, src, block_rows=256, include_copies=True)
    for r in rows: r["xframe_version"] = __version__
    return sample, seg_id, rows, time.time() - t0


def main():
    cat = Catalog.load(CAT)
    todo = [(s.sample, s.id) for s in cat.segments() if any(m.kind in ("derived", "copy") for m in s.meshes)]
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            r = json.loads(line); done.add((r["sample"], r["segment"]))
    todo = [t for t in todo if t not in done]
    # big PHercParis4 segments first is not needed; interleave by sample for steady memory
    print(f"segments to verify: {len(todo)} (already done {len(done)})", flush=True)
    t0 = time.time(); n = 0
    with ProcessPoolExecutor(WORKERS) as ex, open(OUT, "a") as f:
        futs = {ex.submit(work, t): t for t in todo}
        for fu in as_completed(futs):
            s, g = futs[fu]
            try:
                _, _, rows, dt = fu.result()
            except Exception as e:
                rows, dt = [{"sample": s, "segment": g, "class": "ERROR", "error": f"worker: {e!r}"}], 0
            for r in rows: f.write(json.dumps(r) + "\n")
            f.flush(); n += 1
            cls = {}
            for r in rows: cls[r["class"]] = cls.get(r["class"], 0) + 1
            print(f"[{n}/{len(todo)} {time.time()-t0:.0f}s] {s} {g} {dt:.0f}s {cls}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
