"""Generated owner exception rulings against the ready door, at one tree.

Run from a tree's root, with this file and specs/excepted-exact/probe.py in place:
    PROBE_OUT=<file> PROBE_TMP=<scratch folder> pytest -q -p no:cacheprovider <this file copied into tests/>

Classes: ruling PR spelling x head x gap text (variants and parts of the printed gap and of its gates, from the
excepted-exact probe) x approved, through three ready routes (gh, REST, MCP). Oracle, written apart from the code:
a route passes exactly when the ruling is approved, names the PR the door reads as <repo>#<number>, its head is a
non-empty prefix of the PR head, and its gap names the printed gap. Every ready and create route of the corpus then
runs under the one exact ruling (ready passes, create stays shut) and under real bash with a stub gh on PATH, to
count the routes that really run the door program. A hole is a case whose verdict differs from the oracle.
"""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

from conftest import HEAD, fake, make_pr, root, write_plan  # noqa: F401  the fixtures, outside tests/
from test_guards import ROUTES, branch, door_reached, mcp
from wuwei import guards, ws

spec = importlib.util.spec_from_file_location('xprobe', Path(__file__).parents[1] / 'specs' / 'excepted-exact' / 'probe.py')
xprobe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xprobe)

GAP = 'gates missing at head aaaaaaa: quality'
PRS = ('o/r#7', 'O/R#7', 'o/r#07', 'https://github.com/o/r/pull/7', 'o/r#7 ', 'r#7', '#7', 'o/r#8', 'o/r#5', 'other/x#7')
HEADS = ('aaaaaaa', HEAD, 'aaaa', '', 'bbbbbbb', 'AAAAAAA', 'aaaaaaab')
GAPS = sorted(xprobe.same(GAP) | xprobe.same('quality') | xprobe.partial(GAP) | {'e', 'goal', 'security', 'quality, security'})
APPROVED = (True, False, None)
CALLS = {'gh pr ready 7': lambda root: guards.bash(root, 'gh pr ready 7', '/repo', 's1'),
         'REST ready_for_review': lambda root: guards.bash(root, 'gh api -X POST repos/o/r/pulls/7/ccr/ready_for_review', '/repo', 's1'),
         'MCP update draft false': lambda root: guards.pre_tool(root, mcp('update_pull_request', pullNumber=7, draft=False))}


def setup(root, fake, monkeypatch):
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'o/r')
    monkeypatch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'light'}])
    fake.prs['5'] = make_pr(number=5)
    fake.prs['7'] = {**make_pr(number=7), 'isDraft': True}
    branch(fake)
    rows = ws.rows
    case = {}
    monkeypatch.setattr(ws, 'rows', lambda root, kind: [{'data': case}] if kind == 'ruling' and case else rows(root, kind))
    return case


def oracle(pr, head, gap, approved, ref='o/r#7'):
    return bool(approved) and pr == ref and bool(head) and HEAD.startswith(head) and xprobe.names(gap, GAP)


def test_rulings(root, fake, monkeypatch):
    case, out = setup(root, fake, monkeypatch), {'cases': 0, 'passed': 0, 'holes': []}
    for pr in PRS:
        for head in HEADS:
            for gap in GAPS:
                for approved in APPROVED:
                    case.clear()
                    case.update(kind='exception', pr=pr, head=head, gap=gap, approved=approved)
                    for name, call in CALLS.items():
                        got = door_reached(call(root))
                        out['cases'] += 1
                        out['passed'] += got == 'pass'
                        if (got == 'pass') != oracle(pr, head, gap, approved):
                            out['holes'].append([name, pr, head, gap, approved, got])
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as f:
        f.write(json.dumps({'rulings': {**out, 'holes': out['holes'][:50], 'hole_count': len(out['holes'])}}) + '\n')


def test_corpus_routes(root, fake, monkeypatch):
    case, rows = setup(root, fake, monkeypatch), []
    stub = Path(os.environ['PROBE_TMP']) / 'stub'
    (stub / 'sub').mkdir(parents=True, exist_ok=True)  # the cd sub and env -C sub routes
    (stub / 'gh').write_text('#!/bin/sh\necho ran >> "$STUB_LOG"\n')
    (stub / 'gh').chmod(0o755)
    for route in (r for r in ROUTES if r['verdict'] in ('ready', 'create')):
        ref = 'other/x#7' if 'other/x' in route['command'] else 'o/r#7'
        case.clear()
        before = door_reached(guards.bash(root, route['command'], '/repo', 's1'))
        case.update(kind='exception', pr=ref, head='aaaaaaa', gap=GAP, approved=True)
        after = door_reached(guards.bash(root, route['command'], '/repo', 's1'))
        log = stub / 'log'
        log.unlink(missing_ok=True)
        subprocess.run(['bash', '-c', route['command']], cwd=stub, env={**os.environ, 'PATH': f'{stub}:/usr/bin:/bin',
                       'STUB_LOG': str(log)}, capture_output=True, timeout=10)
        want = 'pass' if route['verdict'] == 'ready' else route['verdict']
        rows.append({'route': route['command'], 'door': route['verdict'], 'before': before, 'after': after,
                     'ran_door_program': log.is_file(), 'hole': before != route['verdict'] or after != want})
    (stub / 'gh').unlink()
    (stub / 'log').unlink(missing_ok=True)
    (stub / 'sub').rmdir()
    stub.rmdir()
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as f:
        f.write(json.dumps({'routes': rows}) + '\n')
