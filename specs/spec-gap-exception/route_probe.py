"""The route corpus through the guards at one tree, set up as tests/test_guards.py reads it.

Run from a tree's root: PROBE_OUT=<file> pytest -q -p no:cacheprovider <this file>
Each line of PROBE_OUT is a JSON [route, the door it reaches, the reason]. Run it at main and at the head and compare the
files: a line that differs is a route whose verdict or reason moves.
"""

import json
import os
import re

import pytest

from conftest import fake, make_pr, projects, root  # noqa: F401  the fixtures, outside tests/
from test_guards import ROUTES, branch, door_reached, memory  # noqa: F401
from wuwei import guards


@pytest.mark.parametrize('route', ROUTES, ids=[r['command'] for r in ROUTES])
def test_route(root, fake, monkeypatch, memory, route):
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'o/r')
    monkeypatch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    fake.prs['5'] = make_pr(number=5, files=('src/app.py',))
    fake.prs['7'] = {**make_pr(number=7, files=('src/app.py',)), 'isDraft': True}
    branch(fake, ('src/app.py',))
    decision = guards.pre_tool(root, {'tool_name': 'Bash', 'tool_input': {'command': route['command']}, 'cwd': '/repo', 'session_id': 's1'})
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as out:
        out.write(json.dumps([route['command'], door_reached(decision), re.sub(r'/tmp/pytest-of-[^/]+/pytest-[0-9]+/', '<tmp>/', str((decision or {}).get('reason')))]) + '\n')
