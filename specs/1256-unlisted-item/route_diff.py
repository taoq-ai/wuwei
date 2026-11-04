"""The main-versus-head route differential for issue 1256 (AGENTS.md "Testing the guards", "Mutants").

Every route in the route corpus goes through guards.bash under three plans, stubbed as tests/test_guards.py stubs it
(repository o/r, branch i-1-change, PR 5 and PR 7 a draft, both at one head with green checks). Each records an
approved PASS for quality and security at the head on both PRs, under the item the PR's footer names:
- linked: the footer names I-1 and the plan holds I-1;
- unlisted: the footer names X-9 and the plan holds only I-1;
- added: as unlisted, then X-9 added to the plan with both PRs (wuwei plan add X-9 ... --pr o/r#5).
Both trees read the fake host from one tests folder, so only the runtime moves.

    python3 -I route_diff.py <tree> <tests folder> <scratch folder for case roots> > <out>.json
    python3 -I route_diff.py compare <main>.json <head>.json
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HOSTS = ('linked', 'unlisted', 'added')
if sys.argv[1] == 'compare':
    main, head = (json.loads(Path(name).read_text(encoding='utf-8')) for name in sys.argv[2:4])
    moved = sorted(key for key in main['cases'] if main['cases'][key] != head['cases'].get(key))
    print(f"corpus sha256 {main['corpus_sha256']} (main) {head['corpus_sha256']} (head); {main['routes']} routes; "
          f"{len(main['cases'])} cases; {len(moved)} moved")
    for host in HOSTS:
        print(f"{host}: {sum(1 for k in main['cases'] if k.startswith(host + ' '))} cases, "
              f"{sum(1 for k in moved if k.startswith(host + ' '))} moved")
    for key in moved:
        was, now = main['cases'][key], head['cases'][key]
        note = ' [same verdict, reason text moved]' if was['door'] == now['door'] else ''
        print(f"- {key}: main {was['door']} ({was['reason']!r}), head {now['door']} ({now['reason']!r}){note}")
    sys.exit(0)
tree, tests = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(tree / 'cli'), str(tests)]

from wuwei import gh, guards, ws  # noqa: E402  (before conftest, which puts its own tree's cli first on the path)
from conftest import FakeGh, HEAD, footer, make_pr  # noqa: E402
from test_evidence import attest  # noqa: E402
from test_guards import door_reached  # noqa: E402

assert Path(guards.__file__).is_relative_to(tree), guards.__file__


def run(host, command):
    item = 'I-1' if host == 'linked' else 'X-9'
    with tempfile.TemporaryDirectory(dir=sys.argv[3]) as folder:
        root = Path(folder)
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
        items = [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard'}]
        if host == 'added':
            items.append({'id': 'X-9', 'title': 'change', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'standard', 'prs': ['o/r#5', 'o/r#7']})
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': items}))
        fake = FakeGh()
        gh.run = fake
        for number in ('5', '7'):
            fake.prs[number] = {**make_pr(number=int(number), files=('src/app.py', 'tests/test_app.py'), body=footer(item)),
                                'isDraft': number == '7'}
        fake.branches['i-1-change'] = HEAD
        fake.deltas[('main', 'i-1-change')] = [{'path': p, 'additions': 5, 'deletions': 0} for p in ('src/app.py', 'tests/test_app.py')]
        for pr in ('o/r#5', 'o/r#7'):
            for gate in ('quality', 'security'):
                attest(root, gate, HEAD, item=item, pr=pr, name=f'{gate}-{pr[-1]}.md')
        decision = guards.bash(root, command, '/repo', 's1')
        return {'door': door_reached(decision), 'reason': (decision or {}).get('reason', '').replace(str(root), '<root>')}


guards.origin = lambda cwd: 'o/r'
guards.current_branch = lambda cwd: 'i-1-change'
corpus = tests / 'fixtures' / 'routes.json'
routes = json.loads(corpus.read_text(encoding='utf-8'))['routes']
cases = {f'{host} {route["command"]}': run(host, route['command']) for host in HOSTS for route in routes}
print(json.dumps({'corpus_sha256': hashlib.sha256(corpus.read_bytes()).hexdigest(), 'routes': len(routes), 'cases': cases},
                 sort_keys=True, indent=1))
