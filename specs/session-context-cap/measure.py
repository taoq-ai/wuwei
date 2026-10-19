"""Measure hook.session_start's additionalContext for a tree, with the code host stubbed:
    python -I specs/session-context-cap/measure.py <tree> <items> [<goals and standards chars>] [-v]
"""
import json
import re
import sys
import tempfile
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(tree / 'cli'), str(tree / 'tests')]
from conftest import FakeGh, write_plan  # noqa: E402
from wuwei import gh, hook, ws  # noqa: E402

items, filler = int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 0
gh.run = FakeGh()
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / ws.DIR).mkdir()
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
    if items:
        write_plan(root, [{'id': f'item-{n:02d}', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard', 'status': 'open',
                           'score': 50 - n, 'title': f'fix(hook): item {n} keeps the long title a real plan item carries, '
                           'with its promise named in the title the way this plan writes them'} for n in range(items)])
    for name in ('goals.md', 'standards.md') if filler else ():
        (root / ws.DIR / name).write_text('- ' + 'x' * filler + '\n')
    text = hook.handle(root, 'SessionStart', {'session_id': 's1', 'cwd': str(root)})['hookSpecificOutput']['additionalContext']
    shown = len(re.findall(r'^- item-', text, re.M))
    left = re.search(r'(\d+) more items? left out', text)
    print(text) if "-v" in sys.argv else None
    print(json.dumps({'chars': len(text), 'items': items, 'shown': shown, 'left_out': left and int(left[1]),
                      'goals_standards_chars': filler}))
