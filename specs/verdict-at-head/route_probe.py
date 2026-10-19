"""The route corpus through the doors with one quality PASS attested in each PR form, at one tree.

Run from a tree's root: PROBE_OUT=<file> pytest -q -p no:cacheprovider <this file>
Each line of PROBE_OUT is a JSON [route, verdict PR form, the door the route reaches]. Run it at main
and at the head and compare the files: a line that differs is a route whose verdict moves.
"""

import json
import os

import pytest

from conftest import fake, make_pr, root, write_plan  # noqa: F401  the fixtures, outside tests/
from test_evidence import attest
from test_guards import ROUTES, branch, door_reached
from wuwei import guards

FORMS = ('none', 'o/r#5', 'o/r#7', 'o/r', 'acme/app#42', 'other/x#5')


@pytest.mark.parametrize('form', FORMS)
@pytest.mark.parametrize('route', ROUTES, ids=[r['command'] for r in ROUTES])
def test_route(root, fake, monkeypatch, route, form):
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'o/r')
    monkeypatch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'light'}])
    fake.prs['5'] = make_pr(number=5)  # clean but for its gate: the verdict decides the door
    fake.prs['7'] = {**make_pr(number=7), 'isDraft': True}
    branch(fake)
    if form != 'none':
        attest(root, 'quality', pr=form)
    found = door_reached(guards.bash(root, route['command'], '/repo', 's1'))
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as out:
        out.write(json.dumps([route['command'], form, found]) + '\n')
