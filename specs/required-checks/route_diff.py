"""The main-versus-head differential for required-checks (AGENTS.md, "Testing the guards").

Every route in the route corpus goes through hook.handle as a PreToolUse Bash call under six code hosts,
stubbed as tests/test_guards.py stubs it (repository o/r, branch i-1-change, PR 5 with its quality gate
passed at its head and one green check `test`, PR 7 a draft): `none`, where main has no protection;
`required`, where main's protection requires `test (3.11)`; `blocked`, where GitHub reports PR 5 blocked;
`running`, where its `test` is in progress; and `blocked_running` and `required_running`, each of those with
`test` in progress. It prints one JSON object: the corpus sha256 and, per case, the hook's output and the
ledger rows it wrote (kind and sorted data keys).

Run it once per tree, with the same corpus for both, under a Python that has pytest (conftest imports it),
then compare the two outputs:
    python -I specs/required-checks/route_diff.py <tree> <corpus dir> > <out>.json
    python -I specs/required-checks/route_diff.py compare <main>.json <head>.json
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HOSTS = ('none', 'required', 'blocked', 'blocked_running', 'running', 'required_running')

if sys.argv[1] == 'compare':
    main, head = (json.loads(Path(name).read_text(encoding='utf-8')) for name in sys.argv[2:4])
    moved = sorted(key for key in main['cases'] if main['cases'][key] != head['cases'].get(key))
    print(f"corpus sha256 {main['corpus_sha256']} (main) {head['corpus_sha256']} (head); {main['routes']} routes; "
          f"{len(main['cases'])} cases; {len(moved)} moved")
    for host in HOSTS:
        print(f"{host}: {sum(1 for key in moved if key.startswith(host + ' '))} moved")
    for key in moved:
        print(f"- {key}\n  main: {json.dumps(main['cases'][key])}\n  head: {json.dumps(head['cases'][key])}")
    sys.exit(0)
tree, corpus = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(tree / 'cli'), str(tree / 'tests')]

from conftest import FakeGh, HEAD, make_pr  # noqa: E402
from test_evidence import attest  # noqa: E402
from wuwei import gh, guards, hook, ws  # noqa: E402


def run(payload, host):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
            {'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard', 'status': 'open', 'score': 1}]}))
        fake = FakeGh()
        gh.run = fake
        fake.prs['5'] = make_pr(number=5)
        fake.prs['7'] = {**make_pr(number=7), 'isDraft': True}
        fake.branches['i-1-change'] = HEAD
        fake.deltas[('main', 'i-1-change')] = [{'path': 'src/app.py', 'additions': 5, 'deletions': 0}]
        if host.startswith('required'):
            fake.protection = {'main': ['test (3.11)']}
        if host.startswith('blocked'):
            fake.prs['5']['mergeableState'] = 'blocked'
        if host.endswith('running'):
            fake.prs['5']['statusCheckRollup'] = [{'name': 'test', 'conclusion': None, 'status': 'IN_PROGRESS'}]
        attest(root, 'quality', pr='o/r#5')
        rows_before = len(ws.ledger(root))
        out = hook.handle(root, 'PreToolUse', payload)
        rows = [[row['kind'], sorted(row['data'])] for row in ws.ledger(root)[rows_before:]]
        return {'out': out, 'rows': rows}


guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
routes = json.loads((corpus / 'routes.json').read_text(encoding='utf-8'))['routes']
cases = {}
for host in HOSTS:
    for route in routes:
        cases[f'{host} ' + route['command']] = run({'session_id': 's1', 'tool_name': 'Bash', 'cwd': '/repo',
                                                    'tool_input': {'command': route['command']}}, host)
print(json.dumps({'corpus_sha256': hashlib.sha256((corpus / 'routes.json').read_bytes()).hexdigest(),
                  'routes': len(routes), 'cases': cases}, sort_keys=True, indent=1))
