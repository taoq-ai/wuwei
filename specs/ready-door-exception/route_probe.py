"""The route corpus through the doors under one owner exception ruling per form, at one tree.

Run from a tree's root: PROBE_OUT=<file> pytest -q -p no:cacheprovider <this file>
Each line of PROBE_OUT is a JSON [route, ruling form, the door the route reaches]. Run it at main and
at the head and compare the files: a line that differs is a route whose verdict moves. Draft o/r#7 and
ready o/r#5 sit at head aaaaaaa with no gate passed; the plan item is light, so the gap is
"gates missing at head aaaaaaa: quality". The +stray forms add an unattested verdict file for the item.
"""

import json
import os

import pytest

from conftest import fake, make_pr, root, verdict_text, write_plan  # noqa: F401  the fixtures, outside tests/
from test_guards import ROUTES, branch, door_reached
from wuwei import guards, ws

GAP = 'gates missing at head aaaaaaa: quality'
FORMS = {  # form: (pr, head, gap, approved, stray verdict file)
    'none': None,
    'o/r#7 text': ('o/r#7', 'aaaaaaa', GAP, True, False),
    'o/r#7 gates': ('o/r#7', 'aaaaaaa', 'quality', True, False),
    'o/r#7 text +stray': ('o/r#7', 'aaaaaaa', GAP, True, True),
    'o/r#7 other head': ('o/r#7', 'bbbbbbb', GAP, True, False),
    'o/r#7 not approved': ('o/r#7', 'aaaaaaa', GAP, False, False),
    'o/r#7 part': ('o/r#7', 'aaaaaaa', 'qualit', True, False),
    'o/r#8 text': ('o/r#8', 'aaaaaaa', GAP, True, False),
    'other/x#7 text': ('other/x#7', 'aaaaaaa', GAP, True, False),
    'o/r#5 text': ('o/r#5', 'aaaaaaa', GAP, True, False),
    'o/r#5 text +stray': ('o/r#5', 'aaaaaaa', GAP, True, True),
}


@pytest.mark.parametrize('form', FORMS)
@pytest.mark.parametrize('route', ROUTES, ids=[r['command'] for r in ROUTES])
def test_route(root, fake, monkeypatch, route, form):
    monkeypatch.setattr(guards, 'origin', lambda cwd: 'o/r')
    monkeypatch.setattr(guards, 'current_branch', lambda cwd: 'i-1-change')
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'o/r', 'tier': 'light'}])
    fake.prs['5'] = make_pr(number=5)  # clean but for its gate: the ruling decides the door
    fake.prs['7'] = {**make_pr(number=7), 'isDraft': True}
    branch(fake)
    if FORMS[form]:
        pr, head, gap, approved, stray = FORMS[form]
        ws.record(root, 'ruling', {'kind': 'exception', 'pr': pr, 'head': head, 'gap': gap, 'approved': approved})
        if stray:
            path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality-aaaaaaa.md'
            path.parent.mkdir(parents=True)
            path.write_text(verdict_text(gate='quality', head='a' * 40, pr=pr))
    found = door_reached(guards.bash(root, route['command'], '/repo', 's1'))
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as out:
        out.write(json.dumps([route['command'], form, found]) + '\n')
