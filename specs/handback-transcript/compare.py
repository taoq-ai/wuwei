"""Print what moved between two route_diff.py outputs: python3 -I compare.py <main.json> <head.json>."""

import json
import sys


def kind(found):
    return 'pass' if found is None or found[0] == 'note' else found[0]


main, head = (json.load(open(path, encoding='utf-8')) for path in sys.argv[1:3])
old, new = main['routes']['rows'], head['routes']['rows']
moved = [k for k in new if old.get(k) != new[k]]
print(f"routes: {len(new)} read at both trees through guards.bash, the planner's PreToolUse and a sentinel seat's PreToolUse, "
      f"{len(moved)} moved (corpus sha256 {head['routes']['sha256']}; main read the same corpus: {main['routes']['sha256'] == head['routes']['sha256']})")
for key in moved:
    print(f'  {key!r}: {({k: kind(v) for k, v in old[key].items()})} -> {({k: kind(v) for k, v in new[key].items()})}')
old, new = main['handbacks'], head['handbacks']
print(f'handbacks: {len(new)} cases, {sum(old.get(k) != new[k] for k in new)} moved')
for key in new:
    print(f"  {'MOVED ' if old.get(key) != new[key] else ''}{key}: main {old.get(key)} -> head {new[key]}")
