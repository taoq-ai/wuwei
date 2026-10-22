"""Generated question probe: gap kinds x tiers x question tails, end to end through the question guard, the hook and
wuwei evidence at one tree.

Run from a tree's root: PROBE_OUT=<file> pytest -q -p no:cacheprovider <this file>
Each case builds a PR whose evidence prints the kind's gap, reads that printed text from wuwei evidence (never typed),
asks "exception: acme/app#42 at aaaaaaa: <printed><tail>", answers Yes through the hook when the guard passes it, and
reads the evidence again. Each line of PROBE_OUT is a JSON [kind, tier, tail, guard verdict, outcome]. The oracle:
a spec or safety kind reaches the owner, a process kind (template, size, age) is sent back; a passed question drops
exactly the printed gap and keeps every other gap. Any other outcome is a hole.
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
LONG = '| A10 | Inconsistency | HIGH | spec.md:L1 | ' + 'Spec says X. ' * 10 + '|\n'  # printed cut at 100 characters
KINDS = {  # kind: (what the fixture changes, a part of the printed gap that picks it, process)
    'tasks unchecked': ({f'{SPEC}/tasks.md': '- [ ] T1\n' * 17}, 'tasks.md has 17 unchecked items', False),
    'tasks without boxes': ({f'{SPEC}/tasks.md': 'nothing yet\n'}, 'tasks.md has no checklist items', False),
    'plan missing': ({f'{SPEC}/plan.md': None}, 'plan.md missing', False),
    'no clarifications': ({f'{SPEC}/spec.md': '# Spec\n'}, 'Clarifications', False),
    'checklist unchecked': ({f'{SPEC}/checklists/requirements.md': '- [ ] testable\n'}, 'checklists/', False),
    'row with a break': ({f'{SPEC}/analysis.md': TABLE + '| A08 | HIGH | Spec says X. Plan says Y |\n'}, 'A08', False),
    'row with a question mark': ({f'{SPEC}/analysis.md': TABLE + '| A09 | CRITICAL | Is X needed? Plan says Y. |\n'}, 'A09', False),
    'long row cut': ({f'{SPEC}/analysis.md': TABLE + LONG}, 'A10', False),
    'no spec in the diff': ('nospec', 'no spec in the diff', False),
    'openspec tasks': ('openspec', 'tasks.md has 1 unchecked item', False),
    'no test': ('notest', 'no test in the diff', False),
    'template': ('template', "template's sections", True),
    'size': ('size', 'changed lines', True),
    'age': ('age', 'open 5 days', True),
}
TIERS = ('light', 'standard', 'full')
TAILS = ('. Accept?', '. I recommend accepting it. Accept?', '.', '', '? Accept', '. Accept (yes or no)?')


def build(root, fake, kind, tier):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': tier}])
    change, _, _ = KINDS[kind]
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


def printed(root, fake, kind):
    """The kind's gap as wuwei evidence prints it at full tier, read from the evidence."""
    build(root, fake, kind, 'full')
    found = [g['text'] for g in evidence.gaps(root, 'acme/app', 42) if KINDS[kind][1] in g['text']]
    assert len(found) == 1, (kind, found)
    return found[0]


@pytest.mark.parametrize('tail', TAILS)
@pytest.mark.parametrize('tier', TIERS)
@pytest.mark.parametrize('kind', KINDS)
def test_case(root, fake, kind, tier, tail):
    gap = printed(root, fake, kind)
    build(root, fake, kind, tier)
    before = [g['text'] for g in evidence.gaps(root, 'acme/app', 42)]
    question = f'exception: acme/app#42 at aaaaaaa: {gap}{tail}'
    decision = guards.pre_tool(root, {'tool_name': 'AskUserQuestion', 'cwd': '/w', 'session_id': 's1',
                                      'tool_input': {'questions': [{'question': question}]}})
    verdict = 'sent back' if decision else 'owner'
    outcome = ''
    if decision is None:
        hook.handle(root, 'PostToolUse', answered(root, [question], {question: 'Yes'}))
        after = [g['text'] for g in evidence.gaps(root, 'acme/app', 42)]
        outcome = 'waived' if after == [t for t in before if t != gap] else f'after the yes: {after}'
    hole = verdict != ('sent back' if KINDS[kind][2] else 'owner') or (verdict == 'owner' and outcome != 'waived')
    with open(os.environ['PROBE_OUT'], 'a', encoding='utf-8') as out:
        out.write(json.dumps([kind, tier, tail, verdict, outcome, 'HOLE' if hole else 'ok']) + '\n')
