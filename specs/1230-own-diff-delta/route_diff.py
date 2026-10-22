"""The main-versus-head route differential for #1230 (AGENTS.md "Testing the guards" and "Mutants").

Every route in the route corpus goes through guards.bash under three code hosts, stubbed as tests/test_guards.py stubs
it (repository o/r, branch i-1-change, PR 5, PR 7 a draft):
- gap: the corpus's own host, PR 5 with a safety gap and no gate passed;
- merge: quality and security PASS on PRs 5 and 7 at an older head, then a base merge that brought main's 300-line
  risky file and left the PR's own diff unchanged (the PR's base sha and the compare's merge base name the base);
- fix: the same passes, then a 4-line fix to src/app.py with no base sha known (today's head-to-head measure);
- generated (fix round 1): the merge host, whose conflict resolution also adds 100 lines to the risky src/session.py in
  the PR's own diff, under a `- Generated (o/r, 2026-10-22): *` standards line, which must not carry it.
Both trees read the fake host from one tests folder, so only the runtime moves.

    python3 -I route_diff.py <tree> <tests folder> > <out>.json
    python3 -I route_diff.py compare <main>.json <head>.json
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HOSTS = ('gap', 'merge', 'fix', 'generated')
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
from conftest import FakeGh, HEAD, OLD, make_pr  # noqa: E402
from test_evidence import attest  # noqa: E402
from test_guards import door_reached  # noqa: E402

assert Path(guards.__file__).is_relative_to(tree), guards.__file__

BASE = 'c' * 40
PATCH = '@@ -10,3 +10,5 @@ def run():\n x = 1\n y = 2\n z = 3\n+def added():\n+    return 1'


def run(host, command):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
            {'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard'}]}))
        fake = FakeGh()
        gh.run = fake
        files = ('src/app.py',) if host == 'gap' else ('src/app.py', 'tests/test_app.py')
        fake.prs['5'] = make_pr(number=5, files=files)
        fake.prs['7'] = {**make_pr(number=7, files=files), 'isDraft': True}
        fake.branches['i-1-change'] = HEAD
        fake.deltas[('main', 'i-1-change')] = [{'path': p, 'additions': 5, 'deletions': 0} for p in files]
        if host != 'gap':
            for pr in ('o/r#5', 'o/r#7'):
                for gate in ('quality', 'security'):
                    attest(root, gate, OLD, pr=pr, name=f'{gate}-{pr[-1]}.md')
            fake.ancestors.add((OLD, HEAD))
        if host in ('merge', 'generated'):
            for pr in fake.prs.values():
                pr['baseRefOid'] = BASE
            fake.merge_base = BASE
            own = [{'path': 'src/app.py', 'additions': 2, 'deletions': 0, 'patch': PATCH}]
            fake.deltas[(BASE, OLD)] = own
            fake.deltas[(BASE, HEAD)] = [dict(own[0], patch=PATCH.replace('-10,3 +10,5', '-52,3 +52,5'))]
            fake.deltas[(OLD, HEAD)] = [{'path': 'src/token.py', 'additions': 300, 'deletions': 0},
                                        {'path': 'src/app.py', 'additions': 12, 'deletions': 0}]
        if host == 'generated':
            (root / ws.DIR / 'standards.md').write_text('- Generated (o/r, 2026-10-22): *\n', encoding='utf-8')
            session = '@@ -5,3 +5,4 @@\n x = 1\n y = 2\n z = 3\n+ttl = 60'
            fake.deltas[(BASE, OLD)].append({'path': 'src/session.py', 'additions': 1, 'deletions': 0, 'patch': session})
            fake.deltas[(BASE, HEAD)].append({'path': 'src/session.py', 'additions': 101, 'deletions': 0,
                                              'patch': session + ''.join(f'\n+ttl_{i} = {i}' for i in range(100))})
            fake.deltas[(OLD, HEAD)].append({'path': 'src/session.py', 'additions': 100, 'deletions': 0})
        if host == 'fix':
            fake.deltas[(OLD, HEAD)] = [{'path': 'src/app.py', 'additions': 4, 'deletions': 0}]
        decision = guards.bash(root, command, '/repo', 's1')
        return {'door': door_reached(decision), 'reason': (decision or {}).get('reason', '').replace(str(root), '<root>')}


guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
corpus = tests / 'fixtures' / 'routes.json'
routes = json.loads(corpus.read_text(encoding='utf-8'))['routes']
cases = {f'{host} {route["command"]}': run(host, route['command']) for host in HOSTS for route in routes}
print(json.dumps({'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(), 'routes': len(routes), 'cases': cases},
                 sort_keys=True, indent=1))
