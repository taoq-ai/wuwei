"""The main-versus-head differential for models-record (AGENTS.md, "Testing the guards").

Every route in the route corpus goes through hook.handle as a PreToolUse Bash call, every fixture payload
through hook.handle under its own event, and a grid of Agent launches through PreToolUse, all with the
code host stubbed as tests/test_guards.py stubs it (repository o/r, branch i-1-change, PR 5 with a safety
gap, PR 7 a draft). It prints one JSON object: the corpus sha256 and, per case, the hook's output and the
ledger rows it wrote (kind and sorted data keys).

Run it once per tree, with the same corpus for both, under a Python that has pytest (conftest imports it),
then compare the two outputs:
    python -I specs/models-record/route_diff.py <tree> <corpus dir> > <out>.json
    python -I specs/models-record/route_diff.py compare <main>.json <head>.json
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
    for kind in ('bash', 'payload', 'agent'):
        print(f"{kind}: {sum(1 for key in main['cases'] if key.startswith(kind + ' '))} cases, "
              f"{sum(1 for key in moved if key.startswith(kind + ' '))} moved")
    decisions = [key for key in head['cases'] if key.startswith('agent ') and 'permissionDecision' in json.dumps(head['cases'][key])]
    print(f"agent launches given a permission decision or updatedInput at the head: "
          f"{len(decisions) + sum(1 for c in head['cases'].values() if 'updatedInput' in json.dumps(c))}")
    for key in moved:
        if not key.startswith('agent '):
            print(f"- {key}\n  main: {json.dumps(main['cases'][key])}\n  head: {json.dumps(head['cases'][key])}")
    sys.exit(0)
tree, corpus = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(tree / 'cli'), str(tree / 'tests')]

from conftest import FakeGh, HEAD, make_pr  # noqa: E402
from wuwei import gh, guards, hook, ws  # noqa: E402

ROLES = ('lead', 'builder', 'shepherd', 'steward', 'sentinel-arch', 'sentinel-quality', 'sentinel-security',
         'sentinel-goal', 'Explore')
MODELS = (None, 'opus', 'sonnet', 'haiku', 'claude-opus-5-5', 'claude-sonnet-5-5')
EFFORTS = (None, 'medium', 'high')


def run(event, payload, tier='standard'):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
            {'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': tier, 'status': 'open', 'score': 1}]}))
        fake = FakeGh()
        gh.run = fake
        fake.prs['5'] = make_pr(number=5, files=('src/app.py',))
        fake.prs['7'] = {**make_pr(number=7, files=('src/app.py',)), 'isDraft': True}
        fake.branches['i-1-change'] = HEAD
        fake.deltas[('main', 'i-1-change')] = [{'path': 'src/app.py', 'additions': 5, 'deletions': 0}]
        out = hook.handle(root, event, {**payload, 'cwd': str(root)} if event != 'PreToolUse' else payload)
        rows = [[row['kind'], sorted(row['data'])] for row in ws.ledger(root)]
        return {'out': out, 'rows': rows}


guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
routes = json.loads((corpus / 'routes.json').read_text(encoding='utf-8'))['routes']
cases = {}
for route in routes:
    cases['bash ' + route['command']] = run('PreToolUse', {'session_id': 's1', 'tool_name': 'Bash', 'cwd': '/repo',
                                                           'tool_input': {'command': route['command']}})
for path in sorted((corpus / 'payloads').glob('*.json')):
    payload = json.loads(path.read_text(encoding='utf-8'))
    cases['payload ' + path.name] = run(payload['hook_event_name'], payload)
for tier in ('light', 'standard', 'full'):
    for role in ROLES:
        for model in MODELS:
            for effort in EFFORTS:
                data = {'subagent_type': role, 'description': role, 'prompt': 'Item: I-1\nGo.',
                        **({'model': model} if model else {}), **({'effort': effort} if effort else {})}
                cases[f'agent {tier} {role} {model} {effort}'] = run(
                    'PreToolUse', {'session_id': 's1', 'tool_name': 'Agent', 'cwd': '/repo', 'tool_input': data}, tier)
print(json.dumps({'corpus_sha256': hashlib.sha256((corpus / 'routes.json').read_bytes()).hexdigest(),
                  'routes': len(routes), 'cases': cases}, sort_keys=True, indent=1))
