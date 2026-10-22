"""The route corpus through the guards at one tree, set up as tests/test_guards.py reads it.

Run from a tree's root: PROBE_OUT=<file> [ROUTE_MODE=<mode>] pytest -q -p no:cacheprovider <this file>
Each line of PROBE_OUT is a JSON [route, the door it reaches, the reason]. Run it at main and at the head and compare the
files: a line that differs is a route whose verdict or reason moves. The modes:
- plain: as tests/test_guards.py reads the corpus.
- excepted: an approved exception at the head for every gap that holds #5 and #7 (the PRs the doors read), so
  evidence.excepted is on the path of every door.
- spec-all: #5 is a full-tier spec PR whose analysis.md holds two open rows (A1, A2) and whose checklists/ holds two
  files with unchecked boxes (a.md, security.md); every gap that holds #5 and #7 is accepted.
- spec-first: as spec-all, but the gaps naming A2 or security.md are never accepted, so the door must hold on them.
"""

import json
import os
import re

import pytest

from conftest import fake, make_pr, projects, root, write_plan  # noqa: F401  the fixtures, outside tests/
from test_evidence import SPEC, speckit
from test_guards import ROUTES, branch, door_reached, memory  # noqa: F401
from wuwei import evidence, guards, ws

MODE = os.environ.get('ROUTE_MODE', 'plain')
TWO = {f'{SPEC}/analysis.md': '| ID | Severity | Summary |\n|---|---|---|\n| A1 | HIGH | wording nit |\n| A2 | CRITICAL | auth bypass |\n',
       f'{SPEC}/checklists/a.md': '- [ ] testable\n', f'{SPEC}/checklists/security.md': '- [ ] threat model\n' * 5}


@pytest.mark.parametrize('route', ROUTES, ids=[r['command'] for r in ROUTES])
def test_route(root, fake, monkeypatch, memory, route):
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'o/r')
    monkeypatch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    fake.prs['5'] = make_pr(number=5, files=('src/app.py',))
    fake.prs['7'] = {**make_pr(number=7, files=('src/app.py',)), 'isDraft': True}
    branch(fake, ('src/app.py',))
    if MODE.startswith('spec'):
        write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'full'}])
        fake.prs['5'] = make_pr(number=5, files=speckit(fake, **TWO))
    if MODE != 'plain':
        for number in (5, 7):
            for gap in evidence.blocking(evidence.gaps(root, 'o/r', number)):
                if MODE != 'spec-first' or not re.search(r'A2 \||security\.md', gap['text']):
                    ws.record(root, 'ruling', {'kind': 'exception', 'pr': f'o/r#{number}', 'head': 'aaaaaaa',
                                               'gap': gap['text'], 'approved': True})
    decision = guards.pre_tool(root, {'tool_name': 'Bash', 'tool_input': {'command': route['command']}, 'cwd': '/repo', 'session_id': 's1'})
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as out:
        out.write(json.dumps([route['command'], door_reached(decision), re.sub(r'/tmp/pytest-of-[^/]+/pytest-[0-9]+/', '<tmp>/', str((decision or {}).get('reason')))]) + '\n')
