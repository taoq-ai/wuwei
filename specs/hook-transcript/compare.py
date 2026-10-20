"""Print what moved between two probe_differential.py outputs: python3 -I compare.py <main.json> <head.json>."""

import json
import sys


def kind(found):
    return 'pass' if found is None or found[0] == 'note' else found[0]


main, head = (json.load(open(path, encoding='utf-8')) for path in sys.argv[1:3])
for section in ('routes', 'checks'):
    old, new = main[section].get('rows', main[section]), head[section].get('rows', head[section])
    moved = [(k, old.get(k), new[k]) for k in new if old.get(k) != new[k]]
    print(f'{section}: {len(new)} read at both trees, {len(moved)} moved' + (
        f" (corpus sha256 {head[section]['sha256']})" if 'sha256' in head[section] else ''))
    for key, before, after in moved:
        print(f'  {key!r}: {before if section == "checks" else {k: kind(v) for k, v in before.items()}} -> '
              f'{after if section == "checks" else {k: kind(v) for k, v in after.items()}}')
