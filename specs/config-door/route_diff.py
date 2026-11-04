"""The main-versus-head route differential for config-door (AGENTS.md "Testing the guards").

Every route in tests/fixtures/routes.json goes through guards.pre_tool twice, as the owner's session (no agent_type) and
as a builder seat (agent_type wuwei:builder), with the code host stubbed as test_every_route_reads_as_recorded stubs it:
repository o/r, branch i-1-change, PR 5 with a safety gap, PR 7 a draft. Both trees read one corpus and one fake host
from one tests folder, so only the runtime moves. Case folders are made and removed under <base>.

    python3 -I route_diff.py <tree> <tests folder> <base> > <out>.json
    python3 -I route_diff.py compare <main>.json <head>.json
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

if sys.argv[1] == 'compare':
    main, head = (json.loads(Path(name).read_text(encoding='utf-8')) for name in sys.argv[2:4])
    moved = sorted(key for key in main['cases'] if main['cases'][key] != head['cases'].get(key))
    print(f"corpus sha256 {main['corpus_sha256']}; {main['routes']} routes; {len(main['cases'])} cases; {len(moved)} moved")
    for who in ('owner', 'seat'):
        print(f"{who}: {sum(k.startswith(who + ' ') for k in main['cases'])} cases, {sum(k.startswith(who + ' ') for k in moved)} moved")
    doors = [k for k in moved if main['cases'][k]['door'] != head['cases'][k]['door']]
    print(f"verdict moved: {len(doors)}; reason only (same verdict, the refusal text gains the owner line): {len(moved) - len(doors)}")
    for key in moved:
        print(f"- {key}: main {main['cases'][key]['door']}, head {head['cases'][key]['door']}"
              + ('' if key in doors else ' (reason only)'))
    sys.exit(0)
tree, tests, base = (Path(arg).resolve() for arg in sys.argv[1:4])
sys.path[:0] = [str(tree / 'cli'), str(tests)]

from wuwei import gh, guards, ws  # noqa: E402  (before conftest, which puts its own tree's cli first on the path)
from conftest import FakeGh, make_pr  # noqa: E402
from test_guards import branch, door_reached  # noqa: E402

assert Path(guards.__file__).is_relative_to(tree), guards.__file__
guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'


def run(who, command):
    case = base / 'case'
    shutil.rmtree(case, ignore_errors=True)
    root, home = case / 'ws', case / 'home'
    (root / ws.DIR).mkdir(parents=True)
    (home / '.claude' / 'projects' / '-repo' / 'memory').mkdir(parents=True)
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
    ws.PROJECTS = home / '.claude' / 'projects'
    os.environ['HOME'] = str(home)
    fake = FakeGh()
    gh.run = fake
    fake.prs['5'] = make_pr(number=5, files=('src/app.py',))
    fake.prs['7'] = {**make_pr(number=7, files=('src/app.py',)), 'isDraft': True}
    branch(fake, ('src/app.py',))
    payload = {'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': '/repo', 'session_id': 's1',
               **({'agent_type': 'wuwei:builder'} if who == 'seat' else {})}
    found = guards.pre_tool(root, payload)
    shutil.rmtree(case)
    return {'door': door_reached(found), 'reason': str((found or {}).get('reason', '')).replace(str(case), '<case>')}


corpus = tests / 'fixtures' / 'routes.json'
routes = json.loads(corpus.read_text(encoding='utf-8'))['routes']
cases = {f'{who} {route["command"]}': run(who, route['command']) for who in ('owner', 'seat') for route in routes}
print(json.dumps({'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(), 'routes': len(routes), 'cases': cases},
                 sort_keys=True, indent=1))
