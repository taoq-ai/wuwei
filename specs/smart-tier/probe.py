"""The lowering probe for smart-tier: no recorded domain, however written, lowers what a measured signal owes.

Domains (7 spellings, as a lead or a seat could write the plan field) x signals (10 diffs) run through evidence.gaps
against the fake host of tests/conftest.py, each case in its own folder under <scratch>. A hole is a case that owes
less than its signal demands, or less than the same diff under the clear domain, or less than the plain diff under
the same domain.

    python3 -I probe.py <tree> <tests folder> <scratch folder>
"""
import json
import shutil
import sys
from pathlib import Path

tree, tests, scratch = (Path(arg).resolve() for arg in sys.argv[1:4])
sys.path[:0] = [str(tree / 'cli'), str(tests)]
from wuwei import evidence, gh, ws  # noqa: E402  (before conftest, which puts its own tree's cli first on the path)
from conftest import FakeGh, HEAD, make_pr  # noqa: E402

assert Path(evidence.__file__).is_relative_to(tree), evidence.__file__
BASE = 'c' * 40
PLAIN = '@@ -1,4 +1,6 @@ def run(x):\n     if x == 0:\n+    if x == 9:\n+        return 9\n     return 0'
TESTS = '@@ -1,2 +1,3 @@\n+def test_run():\n+    assert run(9) == 9'
DOMAINS = ['clear: a known fix', 'complicated: two modules', 'complex: a new protocol', '', 'Clear: shouted', 'clear', None]
# signal: (path, patch, decision nodes at the base and the head, lines, in doubt, the gates it must owe)
SIGNALS = {'plain': ('src/app.py', PLAIN, 3, 4, 5, False, {'quality'}),
           'owner': ('infra/app.py', PLAIN, 3, 4, 5, False, {'quality', 'security'}),
           'risky': ('src/token.py', PLAIN, 3, 4, 5, False, {'quality', 'security'}),
           'trust': ('src/session.py', PLAIN, 3, 4, 5, False, {'quality', 'security'}),
           'guard': ('src/app.py', '@@ -1,3 +1,3 @@ def door(cmd):\n-    return deny(cmd)\n+    return None', 3, 3, 5, False, {'quality', 'arch'}),
           'rise': ('src/app.py', PLAIN, 9, 10, 5, False, {'quality', 'security'}),
           'nopatch': ('src/app.py', None, 3, 4, 5, False, {'quality', 'arch'}),
           'contract': ('src/api.proto', '@@ -1 +1,2 @@\n message A {}\n+message B {}', 0, 0, 5, False, {'quality', 'arch'}),
           'wide': ('src/app.py', PLAIN, 3, 4, 300, False, {'quality', 'arch'}),
           'doubt': ('src/app.py', PLAIN, 3, 4, 5, True, {'quality', 'goal'})}


def branchy(n):
    return 'def run(x):\n' + ''.join(f'    if x == {i}:\n        return {i}\n' for i in range(n)) + '    return -1\n'


def owed(n, domain, signal):
    path, patch, was, now, size, doubt, _ = SIGNALS[signal]
    root = scratch / f'case-{n}'
    shutil.rmtree(root, ignore_errors=True)
    (root / ws.DIR).mkdir(parents=True)
    try:
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app'], 'owner_paths': ['infra/**']})
        ws.atomic_write(root / ws.DIR / 'plan.json', json.dumps({'items': [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app',
                                                                         'tier': 'smart', 'domain': domain, 'in_doubt': doubt}]}))
        fake = FakeGh()
        gh.run = fake
        pr = make_pr(files=(path, 'tests/test_app.py'), lines=size)
        pr['baseRefOid'] = BASE
        pr['files'][0]['patch'], pr['files'][1]['patch'] = patch, TESTS
        fake.prs['42'] = pr
        fake.files.update({f'{path}@{BASE}': branchy(was), f'{path}@{HEAD}': branchy(now)})
        found = [g['text'] for g in evidence.gaps(root, 'acme/app', 42) if g['text'].startswith('gates missing')]
        return set(found[0].split(': ', 1)[1].split(', ')) if found else set()
    finally:
        shutil.rmtree(root, ignore_errors=True)


cases = [(d, s) for d in DOMAINS for s in SIGNALS]
gates = {case: owed(n, *case) for n, case in enumerate(cases)}
holes = [f'{d!r} x {s}: owes {sorted(g)}' for (d, s), g in gates.items()
         if not SIGNALS[s][-1] <= g or not gates[(DOMAINS[0], s)] <= g or not gates[(d, 'plain')] <= g]
print(f'generated {len(cases)}; ran through evidence.gaps {len(gates)}; holes {len(holes)}')
for (d, s), g in gates.items():
    print(f'{d!r:28} {s:9} {", ".join(sorted(g))}')
print('\n'.join(holes))
