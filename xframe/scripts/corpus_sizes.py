"""HEAD-only corpus census of tifxyz mesh storage by derivation (no payload download)."""
import json, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://vesuvius-challenge-open-data.s3.us-east-1.amazonaws.com'
md = json.loads((ROOT / 'data/cache/metadata-2026-10-07.json').read_text())
jobs = []
for sid, s in md['samples'].items():
    vols = s['volumes']
    for gid, g in s['segments'].items():
        ov = g.get('original_volume_id'); ds = g['properties'].get('original_volume_downscale') or 1
        src_um = (vols.get(ov, {}).get('properties') or {}).get('pixel_size_um')
        for e in g['data']:
            if e['type'] not in ('tifxyz-transformed', 'tifxyz-normalized'): continue
            tv = (e.get('parameters') or {}).get('target_volume') if e['type'] == 'tifxyz-transformed' else ov
            tum = (vols.get(tv, {}).get('properties') or {}).get('pixel_size_um')
            jobs.append(dict(sample=sid, segment=gid, type=e['type'], process=(e.get('creation_info') or {}).get('process'),
                             path=e['origins'][0]['path'], src_um=src_um, downscale=ds, target_um=tum))
def head(j):
    tot = 0
    for c in 'xyz':
        req = urllib.request.Request(f"{BASE}/{quote(j['path'].rstrip('/') + '/' + c + '.tif', safe='/')}", method='HEAD')
        try:
            with urllib.request.urlopen(req, timeout=60) as r: tot += int(r.headers['Content-Length'])
        except Exception as ex:
            j['error'] = repr(ex); return j
    j['bytes_xyz'] = tot; return j
with ThreadPoolExecutor(24) as ex: res = list(ex.map(head, jobs))
(ROOT / 'out/corpus-mesh-sizes-2026-10-07.json').write_text(json.dumps(res, indent=1))
agg = collections.defaultdict(lambda: [0, 0])
for j in res:
    if 'bytes_xyz' not in j: continue
    if j['type'] == 'tifxyz-normalized': k = 'normalized (source)'
    elif j['process'] == 'copy-normalized-for-original': k = 'transformed: copy of source'
    else:
        src_eff = j['src_um'] * j['downscale'] if j['src_um'] else None; t = j['target_um']
        if not (src_eff and t): k = 'transformed: unknown um'
        elif t < src_eff / 1.05: k = 'transformed: finer frame (grid bilinear-UPsampled)'
        elif t > src_eff * 1.05: k = 'transformed: coarser frame (grid DOWNsampled)'
        else: k = 'transformed: same-density frame'
    agg[k][0] += 1; agg[k][1] += j['bytes_xyz']
print(json.dumps({k: {'n': v[0], 'GB': round(v[1] / 1e9, 2)} for k, v in sorted(agg.items())}, indent=1))
print('errors', sum('error' in j for j in res), 'total jobs', len(res))
