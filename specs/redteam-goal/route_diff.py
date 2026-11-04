"""The main-versus-head route differential for redteam-goal (AGENTS.md "Testing the guards" and "Mutants").

Every route in the route corpus goes through guards.bash under eight code hosts, stubbed as tests/test_guards.py stubs
it (repository o/r, branch i-1-change, PR 5 and PR 7 a draft, a base sha and a merge base known). Each host records an
approved PASS for quality, security and arch at the head on both PRs, so the only gate a door can still name is goal:
- standard: a standard item, a plain 5-line change to src/app.py;
- full: a full item, the same change (its goal still owed at both trees);
- clear: a smart item classified clear, the same change;
- complicated: a smart item classified complicated, the same change;
- doubt: a smart item classified clear with its promise in doubt (goal owed at both trees);
- complex: a smart item classified complex, the same change;
- owner: a smart item classified clear changing src/core/rules.py, an owner path;
- risky: a smart item classified clear changing src/token.py, a risky path.
Both trees read the fake host from one tests folder, so only the runtime moves.

    python3 -I route_diff.py <tree> <tests folder> <scratch folder for case roots> > <out>.json
    python3 -I route_diff.py compare <main>.json <head>.json
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HOSTS = ('standard', 'full', 'clear', 'complicated', 'doubt', 'complex', 'owner', 'risky')
if sys.argv[1] == 'compare':
    main, head = (json.loads(Path(name).read_text(encoding='utf-8')) for name in sys.argv[2:4])
    moved = sorted(key for key in main['cases'] if main['cases'][key] != head['cases'].get(key))
    print(f"corpus sha256 {main['corpus_sha256']} (main) {head['corpus_sha256']} (head); {main['routes']} routes; "
          f"{len(main['cases'])} cases; {len(moved)} moved")
    for host in HOSTS:
        print(f"{host}: {sum(1 for k in main['cases'] if k.startswith(host + ' '))} cases, "
              f"{sum(1 for k in moved if k.startswith(host + ' '))} moved")
    gaps = lambda case: '; '.join(case['reason'].split('\n- ')[1:]) or 'no gap'  # noqa: E731
    for key in moved:
        print(f"- {key}: main {main['cases'][key]['door']} ({gaps(main['cases'][key])}), "
              f"head {head['cases'][key]['door']} ({gaps(head['cases'][key])})")
    sys.exit(0)
tree, tests = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(tree / 'cli'), str(tests)]

from wuwei import gh, guards, ws  # noqa: E402  (before conftest, which puts its own tree's cli first on the path)
from conftest import FakeGh, HEAD, make_pr  # noqa: E402
from test_evidence import attest  # noqa: E402
from test_guards import door_reached  # noqa: E402

assert Path(guards.__file__).is_relative_to(tree), guards.__file__

BASE = 'c' * 40
PLAIN = '@@ -1,4 +1,6 @@ def run(x):\n     if x == 0:\n+    if x == 9:\n+        return 9\n     return 0'
TESTS = '@@ -1,2 +1,3 @@\n+def test_run():\n+    assert run(9) == 9'
SOURCE = {'owner': 'src/core/rules.py', 'risky': 'src/token.py'}
DOMAIN = {'complicated': 'complicated: two modules and a rule', 'complex': 'complex: a new protocol nobody has run'}


def branchy(n):
    return 'def run(x):\n' + ''.join(f'    if x == {i}:\n        return {i}\n' for i in range(n)) + '    return -1\n'


def run(host, command):
    with tempfile.TemporaryDirectory(dir=sys.argv[3]) as folder:
        root = Path(folder)
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['src/core/*']})
        tier = host if host in ('standard', 'full') else 'smart'
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
            {'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'o/r', 'tier': tier, 'domain': DOMAIN.get(host, 'clear: one known fix'),
             'in_doubt': host == 'doubt'}]}))
        fake = FakeGh()
        gh.run = fake
        source = SOURCE.get(host, 'src/app.py')
        files = {source: PLAIN, 'tests/test_app.py': TESTS}
        for number in ('5', '7'):
            pr = make_pr(number=int(number), files=tuple(files))
            pr.update(baseRefOid=BASE, isDraft=number == '7')
            for f in pr['files']:
                f['patch'] = files[f['path']]
            fake.prs[number] = pr
        fake.branches['i-1-change'], fake.merge_base = HEAD, BASE
        fake.deltas[('main', 'i-1-change')] = [{'path': p, 'additions': 5, 'deletions': 0, 'patch': t} for p, t in files.items()]
        fake.files.update({f'{source}@{BASE}': branchy(3), f'{source}@{HEAD}': branchy(4)})
        for pr in ('o/r#5', 'o/r#7'):
            for gate in ('quality', 'security', 'arch'):
                attest(root, gate, HEAD, pr=pr, name=f'{gate}-{pr[-1]}.md')
        decision = guards.bash(root, command, '/repo', 's1')
        return {'door': door_reached(decision), 'reason': (decision or {}).get('reason', '').replace(str(root), '<root>')}


guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
corpus = tests / 'fixtures' / 'routes.json'
routes = json.loads(corpus.read_text(encoding='utf-8'))['routes']
cases = {f'{host} {route["command"]}': run(host, route['command']) for host in HOSTS for route in routes}
print(json.dumps({'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(), 'routes': len(routes), 'cases': cases},
                 sort_keys=True, indent=1))
