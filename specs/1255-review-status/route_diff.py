"""The main-versus-head route differential for issue 1255 (AGENTS.md "Testing the guards").

Every route in the route corpus goes through guards.bash under four code hosts, stubbed as tests/test_guards.py stubs
it (repository o/r, branch i-1-change, PR 5 and PR 7 a draft, both at one head). Each host records an approved PASS
for quality and security at the head on both PRs, so the doors read past the gate gaps, and sets the head's checks:
- green: one check, passed;
- running: one check in progress;
- red: one check run failed and one commit status errored;
- excepted: red, with the owner's approved exception for the `CI failing` gap on both PRs at that head.
Four additional hosts use the observed 1067-probe review-status shape: pending review with green CI,
pending review with running CI, failed review, and unreadable classification. Both trees read the
fake host from one tests folder, so only the runtime moves.

    python3 -I route_diff.py <tree> <tests folder> <scratch folder for case roots> > <out>.json
    python3 -I route_diff.py compare <main>.json <head>.json
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HOSTS = ('green', 'running', 'red', 'excepted', 'review-pending', 'review-running', 'review-failed', 'review-unreadable')
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
        was, now = main['cases'][key], head['cases'][key]
        same = (was['door'], gaps(was)) == (now['door'], gaps(now))
        note = ' [same verdict, note text moved: the PR standard (charters/_pr.md)]' if same and \
            now['reason'].startswith('WUWEI PR standard') else ' [same verdict, reason text moved]' if same else ''
        print(f"- {key}: main {was['door']} ({gaps(was)}), head {now['door']} ({gaps(now)}){note}")
    sys.exit(0)
tree, tests = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(tree / 'cli'), str(tests)]

from wuwei import gh, guards, ws  # noqa: E402  (before conftest, which puts its own tree's cli first on the path)
from conftest import FakeGh, HEAD, make_pr  # noqa: E402
from test_evidence import attest  # noqa: E402
from test_guards import door_reached  # noqa: E402

assert Path(guards.__file__).is_relative_to(tree), guards.__file__

CHECKS = {'green': [{'name': 'test', 'conclusion': 'SUCCESS', 'status': 'COMPLETED'}],
          'running': [{'name': 'test', 'conclusion': '', 'status': 'IN_PROGRESS'}],
          'red': [{'name': 'test', 'conclusion': 'FAILURE', 'status': 'COMPLETED'}, {'context': 'ci/build', 'state': 'ERROR'}]}
CHECKS['excepted'] = CHECKS['red']
for host in HOSTS[4:]:
    CHECKS[host] = CHECKS['running' if host == 'review-running' else 'green'] + [
        {'context': 'Review Gate', 'state': 'FAILURE' if host == 'review-failed' else 'PENDING',
         'url': 'https://github.com/o/r/actions/runs/7'}]


def run(host, command):
    with tempfile.TemporaryDirectory(dir=sys.argv[3]) as folder:
        root = Path(folder)
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [
            {'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard'}]}))
        fake = FakeGh()
        gh.run = fake
        if host.startswith('review-'):
            fake.runs = None if host == 'review-unreadable' else {
                '7': ('.github/workflows/review-gate.yml', 'pull_request'),
                '8': ('.github/workflows/review-gate.yml', 'pull_request_review')}
        for number in ('5', '7'):
            fake.prs[number] = {**make_pr(number=int(number), files=('src/app.py', 'tests/test_app.py')),
                                'isDraft': number == '7', 'statusCheckRollup': CHECKS[host]}
        fake.branches['i-1-change'] = HEAD
        fake.deltas[('main', 'i-1-change')] = [{'path': p, 'additions': 5, 'deletions': 0} for p in ('src/app.py', 'tests/test_app.py')]
        for pr in ('o/r#5', 'o/r#7'):
            for gate in ('quality', 'security'):
                attest(root, gate, HEAD, pr=pr, name=f'{gate}-{pr[-1]}.md')
            if host == 'excepted':
                ws.record(root, 'ruling', {'kind': 'exception', 'pr': pr, 'head': HEAD[:7], 'gap': 'CI failing: test, ci/build',
                                           'approved': True})
        decision = guards.bash(root, command, '/repo', 's1')
        return {'door': door_reached(decision), 'reason': (decision or {}).get('reason', '').replace(str(root), '<root>')}


guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
corpus = tests / 'fixtures' / 'routes.json'
routes = json.loads(corpus.read_text(encoding='utf-8'))['routes']
cases = {f'{host} {route["command"]}': run(host, route['command']) for host in HOSTS for route in routes}
print(json.dumps({'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(), 'routes': len(routes), 'cases': cases},
                 sort_keys=True, indent=1))
