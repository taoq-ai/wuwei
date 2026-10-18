"""Compare two probe_differential.py outputs: python3 compare.py <main.json> <head.json>."""

import json
import sys

main, head = (json.load(open(path, encoding='utf-8')) for path in sys.argv[1:3])
print('corpus sha256 main', main['routes']['sha256'], 'head', head['routes']['sha256'])
for part in ('routes', 'payloads', 'handbacks'):
    a, b = (main[part]['rows'], head[part]['rows']) if part == 'routes' else (main[part], head[part])
    moved = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
    print(f'{part}: {len(b)} rows at head, {len(a)} at main, {len(moved)} moved')
    for key in moved if part != 'handbacks' else ():
        print('  moved:', key, a.get(key), '->', b.get(key))
rows = head['handbacks']
named = {k: r for k, r in rows.items() if 'named' in r}
holes = {k: r['next'] for k, r in named.items() if not (r['next']['free_at_root'] and r['next']['attests'])}
print(f'head refusals naming a next file: {len(named)}; that file free and attesting: {len(named) - len(holes)}; holes: {len(holes)}')
for key, why in sorted(holes.items()):
    print('  hole:', key, why)
mrows = main['handbacks']
mnamed = {k: r for k, r in mrows.items() if 'named' in r}
mholes = {k: r['next'] for k, r in mnamed.items() if not (r['next']['free_at_root'] and r['next']['attests'])}
print(f'main refusals naming a next file: {len(mnamed)}; holes: {len(mholes)}')
for key in sorted(mholes):
    print('  main hole:', key, mholes[key])
changed = sorted(k for k in rows if rows[k].get('out') != mrows.get(k, {}).get('out'))
attest_moves = sorted(k for k in rows if rows[k]['attested'] != mrows.get(k, {}).get('attested'))
print(f'handback reasons moved: {len(changed)}; attest counts moved: {len(attest_moves)}')
for key in attest_moves:
    print('  attest moved:', key, mrows.get(key, {}).get('attested'), '->', rows[key]['attested'])
print('outside file changed in any row:', any(r['outside'] != 'outside\n' for r in list(rows.values()) + list(mrows.values())))
