import json, sys, collections, numpy as np
rows = [json.loads(l) for l in open(sys.argv[1])]
S = dict(n_rows=len(rows), n_segments=len({(r['sample'], r['segment']) for r in rows}))
S['by_kind_class'] = {f"{k}|{c}": v for (k, c), v in sorted(collections.Counter((r.get('kind'), r['class']) for r in rows).items())}
S['by_process_kind'] = dict(collections.Counter(r.get('kind') for r in rows))
by = collections.defaultdict(collections.Counter)
for r in rows: by[f"{r['sample']}|ds{(r.get('downscale') or 1):g}"][r['class']] += 1
S['by_sample_downscale'] = {k: dict(v) for k, v in sorted(by.items())}
ok = [r for r in rows if r['class'] not in ('ERROR', 'NOT_COMPARABLE')]
S['shape_match'] = dict(collections.Counter(bool(r.get('shape_match')) for r in rows if 'shape_match' in r))
S['validity_mismatch_cells_total'] = int(sum((r.get('valid_only_predicted') or 0) + (r.get('valid_only_published') or 0) for r in ok))
S['n_cells_compared_total'] = int(sum(r.get('n_compared') or 0 for r in ok))
for kind in ('derived', 'copy'):
    rr = [r for r in ok if r['kind'] == kind]
    if rr:
        S[f'{kind}_worst'] = dict(max_vox=max(r['max_vox'] for r in rr), max_um=max((r.get('max_um') or 0) for r in rr),
                                  p99_vox_max=max(r['p99_vox'] for r in rr), worst_mesh=max(rr, key=lambda r: r['max_vox'])['mesh'],
                                  n_gt_10_vox_total=int(sum(r.get('n_gt_10_vox') or 0 for r in rr)),
                                  max_frac_gt_0_5_vox=max(r.get('frac_gt_0_5_vox') or 0 for r in rr))
S['non_consistent'] = [{k: r.get(k) for k in ('sample', 'segment', 'mesh', 'class', 'error', 'median_vox', 'p99_vox', 'max_vox', 'published_shape', 'predicted_shape', 'frac_gt_0_5_vox')} for r in rows if r['class'] != 'CONSISTENT']
S['downscale_meshes'] = dict(collections.Counter(f"{r['sample']}|ds{r['downscale']:g}|{r['class']}" for r in rows if (r.get('downscale') or 1) != 1))
S['regrid'] = dict(collections.Counter('none' if r.get('regrid_factors') is None else ('up' if r['regrid_factors'][0] > 1 else 'down') for r in ok))
S['seconds_total'] = round(sum(r.get('elapsed_s') or 0 for r in rows), 1)
print(json.dumps(S, indent=1))
