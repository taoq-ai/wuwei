"""The main-versus-head differential for orchestration-gap (AGENTS.md, "Testing the guards").

Every route in the route corpus goes through guards.bash and through hook.handle as a PreToolUse Bash
call, every fixture payload through hook.handle under its own event, SessionStart for an empty
workspace and one with 40 open items, and Stop for six seat states. The code host is stubbed as
tests/test_guards.py stubs it (repository o/r, branch i-1-change, PR 5, PR 7 a draft). Tree and
workspace paths are replaced by <tree> and <root>, so only behaviour can move. Run it with
CLAUDE_CODE_SESSION_ID unset, so the board knows no session of its own.

Run it once per tree, with the same corpus for both, under a Python that has pytest (conftest imports it):
    python -I specs/orchestration-gap/route_diff.py <tree> <corpus dir> > <out>.json
    python -I specs/orchestration-gap/route_diff.py compare <main>.json <head>.json
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

if sys.argv[1] == 'compare':
    main, head = (json.loads(Path(name).read_text(encoding='utf-8')) for name in sys.argv[2:4])
    moved = sorted(key for key in main['cases'] if main['cases'][key] != head['cases'].get(key))
    print(f"corpus sha256 {main['corpus_sha256']} (main) {head['corpus_sha256']} (head); {main['routes']} routes; "
          f"{len(main['cases'])} cases; {len(moved)} moved")
    for kind in ('guards', 'bash', 'payload', 'session', 'stop'):
        print(f"{kind}: {sum(1 for key in main['cases'] if key.startswith(kind + ' '))} cases, "
              f"{sum(1 for key in moved if key.startswith(kind + ' '))} moved")
    said = lambda case: json.dumps(case['out'])[:400]  # noqa: E731
    for key in moved:
        print(f'- {key}\n  main: {said(main["cases"][key])}\n  head: {said(head["cases"][key])}')
    sys.exit(0)
tree, corpus = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(tree / 'cli'), str(tree / 'tests')]

from conftest import FakeGh, HEAD, make_pr  # noqa: E402
from wuwei import gh, guards, hook, ws  # noqa: E402


def run(event, payload, items=1, seats=()):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
            {'id': f'I-{n}', 'title': f'change {n} with a title as long as a real plan item carries it, promise and all',
             'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard', 'status': 'open', 'score': 50 - n} for n in range(items)]}))
        for kind, role, agent, session in seats:
            ws.record(root, kind, {'role': role, 'agent': agent, 'session': session})
        fake = FakeGh()
        gh.run = fake
        fake.prs['5'] = make_pr(number=5, files=('src/app.py',))
        fake.prs['7'] = {**make_pr(number=7, files=('src/app.py',)), 'isDraft': True}
        fake.prs['9'] = make_pr(number=9, files=('src/app.py',), body='WUWEI-Item: I-2') if items > 2 else None
        fake.prs = {k: v for k, v in fake.prs.items() if v}
        fake.branches['i-1-change'] = HEAD
        fake.deltas[('main', 'i-1-change')] = [{'path': 'src/app.py', 'additions': 5, 'deletions': 0}]
        if event == 'guards':
            out = guards.bash(root, payload['tool_input']['command'], '/repo', 's1')
        else:
            out = hook.handle(root, event, {**payload, 'cwd': str(root)} if event != 'PreToolUse' else payload)
        rows = [[row['kind'], sorted(row['data'])] for row in ws.ledger(root)]
        text = json.dumps({'out': out, 'rows': rows}).replace(str(root.resolve()), '<root>').replace(str(root), '<root>')
        return json.loads(text.replace(str(tree), '<tree>'))


guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
routes = json.loads((corpus / 'routes.json').read_text(encoding='utf-8'))['routes']
cases = {}
for route in routes:
    bash = {'session_id': 's1', 'tool_name': 'Bash', 'cwd': '/repo', 'tool_input': {'command': route['command']}}
    cases['guards ' + route['command']] = run('guards', bash)
    cases['bash ' + route['command']] = run('PreToolUse', bash)
for path in sorted((corpus / 'payloads').glob('*.json')):
    payload = json.loads(path.read_text(encoding='utf-8'))
    cases['payload ' + path.name] = run(payload['hook_event_name'], payload)
for items in (0, 40):
    cases[f'session start {items} items'] = run('SessionStart', {'session_id': 's1', 'hook_event_name': 'SessionStart'}, items)
STOPS = {
    'no seat': (),
    'shepherd and gate seat running in this session': (('seat.started', 'shepherd', 'a1', 's1'), ('seat.started', 'sentinel-quality', 'a2', 's1')),
    'builder running in this session': (('seat.started', 'builder', 'a1', 's1'),),
    'builder stopped in this session': (('seat.started', 'builder', 'a1', 's1'), ('seat.stopped', 'builder', 'a1', 's1')),
    'seat a dead session left running': (('seat.started', 'shepherd', 'a1', 'gone'),),
    'seat this session left unconfirmed': (('seat.started', 'builder', 'a1', 's1'), ('seat.unconfirmed', 'builder', 'a1', 's1')),
}
for name, seats in STOPS.items():
    cases[f'stop {name}'] = run('Stop', {'session_id': 's1', 'hook_event_name': 'Stop', 'stop_hook_active': False}, 3, seats)
print(json.dumps({'corpus_sha256': hashlib.sha256((corpus / 'routes.json').read_bytes()).hexdigest(),
                  'routes': len(routes), 'cases': cases}, sort_keys=True, indent=1))
