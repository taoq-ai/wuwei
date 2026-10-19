"""Compare two path_probe.py outputs: python3 compare.py <main.json> <head.json>. Prints every case and each one that moved."""

import json
import sys

main, head = (json.load(open(path, encoding='utf-8')) for path in sys.argv[1:3])
print(f'python main {main["python"]} head {head["python"]}: {len(head["rows"])} cases at head, {len(main["rows"])} at main')
moved = [case for case in head['rows'] if main['rows'].get(case) != head['rows'][case]]
for case, row in head['rows'].items():
    print(f'  {case:30} {"MOVED " + json.dumps(main["rows"].get(case)) + " -> " if case in moved else ""}{json.dumps(row)}')
holes = [case for case, row in head['rows'].items() if row['ledger_rewritten'] or row['outside_changed'] or not row['chain_ok']
         or row['outcome'] == 'hook.error']
print(f'moved: {len(moved)}; head holes (ledger rewritten, outside changed, chain broken or hook.error): {len(holes)}', holes)
