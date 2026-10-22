"""Normalisation probe: one name per path class, a linked entry, a linked cache folder, a linked workspace folder; get, put, prune each."""
import itertools
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from wuwei import ws  # noqa: E402

base = Path(sys.argv[2])
NAMES = {'//': 'a//..//..//esc', '%xx': '%2e%2e%2f%2e%2e%2fesc', '/./': 'a/./../.././esc', '/../': '../esc'}
LINKS = ('entry', 'folder', 'wsdir')
OLD = time.time() - 10 ** 6


def plant(path):
    path.write_text(json.dumps('secret'))
    os.utime(path, (OLD, OLD))


holes, ran = [], 0
for (label, kind), op in itertools.product([(k, 'name') for k in NAMES] + [(k, 'link') for k in LINKS], ('get', 'put', 'prune')):
    case = base / f'{kind}-{label.strip("/").replace("/", "_").replace("%", "pct")}-{op}'
    shutil.rmtree(case, ignore_errors=True)
    root, outside = case / 'ws', case / 'outside'
    outside.mkdir(parents=True)
    plant(outside / 'esc.json')
    if label == 'wsdir':
        (outside / 'cache').mkdir()
        plant(outside / 'cache' / 'esc.json')
        root.mkdir()
        (root / ws.DIR).symlink_to(outside, target_is_directory=True)
    else:
        (root / ws.DIR).mkdir(parents=True)
    if label == 'folder':
        (root / ws.DIR / 'cache').symlink_to(outside, target_is_directory=True)
    elif label == 'entry':
        (root / ws.DIR / 'cache').mkdir()
        (root / ws.DIR / 'cache' / 'esc.json').symlink_to(outside / 'esc.json')
    elif kind == 'name':
        (root / ws.DIR / 'cache').mkdir()
        plant(root / ws.DIR / 'esc.json')
    name = NAMES.get(label, 'esc')
    before = {p: p.read_text() for p in case.rglob('esc.json') if p.is_file()}
    ran += 1
    try:
        got = {'get': lambda: ws.cache_get(root, name, float('inf')), 'put': lambda: ws.cache_put(root, name, 'planted'),
               'prune': lambda: ws.cache_prune(root, -1, name)}[op]()
    except Exception as error:
        got = f'raised {type(error).__name__}'
    after = {p: p.read_text() for p in case.rglob('esc.json') if p.is_file()}
    leaked = op == 'get' and got == 'secret'
    changed = [str(p.relative_to(case)) for p in before if after.get(p) != before[p]]
    added = [str(p.relative_to(case)) for p in after if p not in before]
    if leaked or changed or added:
        holes.append(f'{kind}:{label}:{op} leaked={leaked} changed={changed} added={added}')
    print(f'{kind:5} {label:6} {op:6} -> {got!r:24} changed={changed} added={added}')
    shutil.rmtree(case)
print(f'generated {ran}, ran {ran}, holes {len(holes)}')
for hole in holes:
    print('HOLE', hole)
