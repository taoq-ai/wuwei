"""Generated question probe: gap kinds x tiers x question tails, end to end through the question guard, the hook,
wuwei evidence and the merge door at one tree.

Run from a tree's root: PROBE_OUT=<file> pytest -q -p no:cacheprovider <this file>
Each case builds a PR whose evidence prints the kind's gap, reads that printed text from wuwei evidence (never typed),
asks "exception: acme/app#42 at aaaaaaa: <printed><tail>", answers Yes through the hook when the guard passes it, and
reads the evidence again. Each line of PROBE_OUT is a JSON object: kind, tier, tail, question, printed, recorded (the gap
hook.exception_refs reads), verdict, outcome, door and hole. The oracle: a spec or safety kind reaches the owner, a
process kind (template, size, age) is sent back; a passed question drops exactly the printed gap and keeps every other
gap. A kind with a second open row or checklist (rest) must print it before and after the first yes (light tier reads
no spec); at full tier the merge door must hold on it until a second question names it, then open. Any other outcome is
a hole.
"""

import datetime
import json
import os

import pytest

from conftest import answered, fake, footer, make_pr, projects, root, write_plan  # noqa: F401  the fixtures, outside tests/
from test_evidence import SPEC, full_gates, speckit
from wuwei import evidence, guards, hook, ws

CHANGE = 'openspec/changes/add-rate-limits'
TABLE = '| ID | Severity | Summary |\n|---|---|---|\n'


def rows(*lines):
    return {f'{SPEC}/analysis.md': TABLE + ''.join(line + '\n' for line in lines)}


KINDS = {  # kind: (what the fixture changes, a part of the printed gap that picks it, process, a gap that must stay)
    'tasks unchecked': ({f'{SPEC}/tasks.md': '- [ ] T1\n' * 17}, 'tasks.md has 17 unchecked items', False, None),
    'tasks without boxes': ({f'{SPEC}/tasks.md': 'nothing yet\n'}, 'tasks.md has no checklist items', False, None),
    'plan missing': ({f'{SPEC}/plan.md': None}, 'plan.md missing', False, None),
    'no clarifications': ({f'{SPEC}/spec.md': '# Spec\n'}, 'Clarifications', False, None),
    'checklist unchecked': ({f'{SPEC}/checklists/requirements.md': '- [ ] testable\n'}, 'checklists/', False, None),
    'row with a break': (rows('| A08 | HIGH | Spec says X. Plan says Y |'), 'A08', False, None),
    'row with a question mark': (rows('| A09 | CRITICAL | Is X needed? Plan says Y. |'), 'A09', False, None),
    'long row cut': (rows('| A10 | Inconsistency | HIGH | spec.md:L1 | ' + 'Spec says X. ' * 10 + '|'), 'A10', False, None),
    'long row break before last bar': (rows('| A12 | HIGH | Spec says X. Plan says Y | ' + 'z' * 80 + ' |'), 'A12', False, None),
    'long row question in cut': (rows('| A13 | HIGH | spec.md | Is X needed? ' + 'w' * 80 + ' |'), 'A13', False, None),
    'long row no break in cut': (rows('| A14 | HIGH | spec.md | ' + 'v' * 100 + ' |'), 'A14', False, None),
    'row break at end of cell': (rows('| A15 | HIGH | Spec says X. | Plan says Y? |'), 'A15', False, None),
    'row without trailing bar': (rows('| A11 | HIGH | Spec says X. Plan says Y'), 'A11', False, None),
    'two rows': (rows('| A1 | HIGH | wording nit |', '| A2 | CRITICAL | auth bypass in login |'), 'A1 |', False, 'A2 |'),
    'two checklists': ({f'{SPEC}/checklists/a.md': '- [ ] testable\n', f'{SPEC}/checklists/security.md': '- [ ] threat\n' * 5},
                       'checklists/a.md', False, 'checklists/security.md'),
    'no spec in the diff': ('nospec', 'no spec in the diff', False, None),
    'openspec tasks': ('openspec', 'tasks.md has 1 unchecked item', False, None),
    'no test': ('notest', 'no test in the diff', False, None),
    'template': ('template', "template's sections", True, None),
    'size': ('size', 'changed lines', True, None),
    'age': ('age', 'open 5 days', True, None),
}
TIERS = ('light', 'standard', 'full')
TAILS = ('. Accept?', '. I recommend accepting it. Accept?', '.', '', '? Accept', '. Accept (yes or no)?',
         '. Accept (yes|no)?', ' | Accept?', '. Accept? 1. yes 2. no', '. Accept? 1. yes | 2. no', '.\nAccept?')


def build(root, fake, kind, tier):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': tier}])
    change = KINDS[kind][0]
    body, extra = footer() + '\nRollback: revert', {}
    if change == 'nospec':
        fake.paths.add('.specify')
        files = ['src/app.py', 'tests/test_app.py']
    elif change == 'openspec':
        fake.paths.add('openspec')
        fake.files.update({f'{CHANGE}/proposal.md': '# Why\n', f'{CHANGE}/tasks.md': '- [ ] T1\n',
                           f'{CHANGE}/specs/limits/spec.md': '## ADDED Requirements\n'})
        files = [f'{CHANGE}/proposal.md', f'{CHANGE}/tasks.md', f'{CHANGE}/specs/limits/spec.md']
    elif change == 'notest':
        files = ['src/app.py']
    elif isinstance(change, dict):
        files = speckit(fake, **change)
    else:
        files = speckit(fake)
        if change == 'template':
            fake.files['.github/pull_request_template.md'] = '## Summary\n\n## Testing\n'
        extra = {'size': {'lines': 300}, 'age': {'created': (ws.now() - datetime.timedelta(days=5)).isoformat(timespec='seconds')}
                 }.get(change, {})
    fake.prs['42'] = make_pr(files=files, body=body, reviews=(('alice', 'APPROVED'),), **extra)
    full_gates(root)


def texts(root):
    return [g['text'] for g in evidence.gaps(root, 'acme/app', 42)]


def printed(root, fake, kind):
    """The kind's gap as wuwei evidence prints it at full tier, read from the evidence."""
    build(root, fake, kind, 'full')
    found = [t for t in texts(root) if KINDS[kind][1] in t]
    assert len(found) == 1, (kind, found)
    return found[0]


def accept(root, gap, tail):
    """Ask the exception; answer Yes through the hook when the guard passes it. The guard's verdict."""
    question = f'exception: acme/app#42 at aaaaaaa: {gap}{tail}'
    decision = guards.pre_tool(root, {'tool_name': 'AskUserQuestion', 'cwd': '/w', 'session_id': 's1',
                                      'tool_input': {'questions': [{'question': question}]}})
    if decision is None:
        hook.handle(root, 'PostToolUse', answered(root, [question], {question: 'Yes'}))
    return question, 'sent back' if decision else 'owner'


@pytest.mark.parametrize('tail', TAILS)
@pytest.mark.parametrize('tier', TIERS)
@pytest.mark.parametrize('kind', KINDS)
def test_case(root, fake, kind, tier, tail):
    gap, rest = printed(root, fake, kind), KINDS[kind][3]
    build(root, fake, kind, tier)
    before = texts(root)
    question, verdict = accept(root, gap, tail)
    outcome, door = '', ''
    if verdict == 'owner':
        after = texts(root)
        outcome = 'waived' if after == [t for t in before if t != gap] else f'after the yes: {after}'
        if rest and tier != 'light' and not (any(rest in t for t in before) and any(rest in t for t in after)):
            outcome = 'masked: the rest is not printed before or after the first yes'
        elif rest and tier == 'full' and outcome == 'waived':
            held = guards.merge_door(root, 'acme/app', 42)
            second = next(t for t in after if rest in t)
            accept(root, second, tail)
            door = 'held on the rest, then open' if held and f'- {second}' in held['reason'].splitlines() and \
                guards.merge_door(root, 'acme/app', 42) is None else f'held {bool(held)}, then {guards.merge_door(root, "acme/app", 42)}'
            outcome = 'waived' if door == 'held on the rest, then open' else f'door: {door}'
    hole = verdict != ('sent back' if KINDS[kind][2] else 'owner') or (verdict == 'owner' and outcome != 'waived')
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as out:
        out.write(json.dumps({'kind': kind, 'tier': tier, 'tail': tail, 'question': question, 'printed': gap,
                              'recorded': hook.exception_refs(question)[1], 'verdict': verdict, 'outcome': outcome,
                              'door': door, 'hole': hole}) + '\n')
