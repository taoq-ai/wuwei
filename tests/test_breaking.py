"""A breaking change to an outward surface needs an announcement and the owner's confirmation."""

import hashlib

import pytest

from conftest import HEAD, answered, make_pr, verdict_text, write_plan
from wuwei import evidence, guards, hook, verdict, ws


def standard(root):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard'}])


def attest(root, gate, breaking='no', pr='acme/app#42', head=HEAD):
    path = root / ws.DIR / 'verdicts' / 'I-1' / f'{gate}-{pr.replace("/", "_")}-{head[:7]}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict_text(gate=gate, breaking=breaking, pr=pr, head=head))
    ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'item': 'I-1', 'gate': gate,
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})


def texts(root):
    return [g['text'] for g in evidence.blocking(evidence.gaps(root, 'acme/app', 42))]


def gates(root, breaking='no'):
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate, breaking)


def test_a_declared_breaking_change_needs_an_announcement_then_the_owner(root, fake):
    standard(root)
    pr = make_pr(body='WUWEI-Item: I-1')
    pr['title'] = 'feat!: drop the v1 export endpoint'
    fake.prs['42'] = pr
    gates(root)
    assert texts(root) == ['breaking change without an announcement: add "Announcement: <http(s) URL of the '
                           'published client communication, release note or migration guide>", the URL alone on '
                           'its line, without brackets']
    pr['body'] = 'WUWEI-Item: I-1\nAnnouncement: https://status.acme.test/2026-10-15-export-v1-retired'
    assert texts(root) == ['breaking change needs the owner\'s confirmation: ask "breaking: acme/app#42 at aaaaaaa: '
                           '<what breaks>. Announced at <link>. Proceed?"']
    ws.record(root, 'ruling', {'kind': 'breaking', 'pr': 'acme/app#42', 'head': 'aaaaaaa', 'approved': True})
    assert texts(root) == []


def test_the_arch_gate_finds_an_undeclared_break(root, fake):
    standard(root)
    fake.prs['42'] = make_pr()
    gates(root, breaking='yes: removes the --format flag from the export command')
    assert texts(root)[0].startswith('breaking change without an announcement')


@pytest.mark.parametrize('pr, found', [
    ('acme/app#41', []),  # an earlier, squash-merged PR of the item: its yes is not this PR's (#1292)
    ('acme/app#42', ['breaking change without an announcement']),  # this PR's own yes holds
    ('acme/app', ['breaking change without an announcement']),  # a verdict naming only the repository holds
])
def test_a_breaking_yes_holds_only_the_pr_it_names(root, fake, pr, found):
    standard(root)
    fake.prs['42'] = make_pr()
    attest(root, 'arch', 'yes: removes the --format flag', pr=pr, head='c' * 40)  # off this PR's line, as after a squash
    gates(root)  # this PR's own arch verdict says no at its head
    assert [t[:39] for t in texts(root) if t.startswith('breaking')] == found


def test_a_confirmation_does_not_survive_a_moved_head(root, fake):
    standard(root)
    pr = make_pr(body='WUWEI-Item: I-1\nBREAKING CHANGE: v1 export removed\nAnnouncement: https://acme.test/v2')
    fake.prs['42'] = pr
    gates(root)
    ws.record(root, 'ruling', {'kind': 'breaking', 'pr': 'acme/app#42', 'head': 'bbbbbbb', 'approved': True})
    assert texts(root)[0].startswith('breaking change needs the owner\'s confirmation')


def test_a_contract_file_calls_the_arch_gate_at_any_tier(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(files=('api/openapi.yaml', 'tests/test_api.py'))
    attest(root, 'quality')
    assert texts(root) == ['gates missing at head aaaaaaa: arch']


def test_an_arch_verdict_must_say_whether_it_breaks():
    text = verdict_text(gate='arch', breaking=None)
    assert any('Breaking' in e for e in verdict.parse(text, strict=True)['errors'])
    assert verdict.parse(text)['errors'] == []  # verdicts attested before the rule still count
    parsed = verdict.parse(text.replace('Confidence: high\n', 'Confidence: high\nBreaking: yes: drops field x\n'))
    assert parsed['errors'] == [] and parsed['breaking'] == 'drops field x'
    assert verdict.parse(text.replace('Confidence: high\n', 'Confidence: high\nBreaking: no (internal only)\n'))['breaking'] == ''


def test_the_breaking_question_reaches_the_owner_and_is_recorded(root):
    question = 'breaking: acme/app#42 at aaaaaaa: drops v1 export. Announced at https://x.test/a. Proceed?'
    payload = {'tool_name': 'AskUserQuestion', 'cwd': str(root), 'session_id': 's1',
               'tool_input': {'questions': [{'question': question}]}}
    assert guards.pre_tool(root, payload) is None
    hook.handle(root, 'PostToolUse', answered(root, [question], {question: 'Yes, proceed'}))
    assert ws.rows(root, 'ruling')[-1]['data'] == {'kind': 'breaking', 'pr': 'acme/app#42', 'head': 'aaaaaaa',
                                                   'approved': True, 'question': question, 'answer': 'Yes, proceed'}



@pytest.mark.parametrize('answer, approved', [('Proceed', True), ('proceed.', True), ('Do not proceed', False),
                                              ('No', False)])
def test_a_proceed_answer_to_the_breaking_question_approves(root, answer, approved):
    question = 'breaking: acme/app#42 at aaaaaaa: drops v1 export. Announced at https://x.test/a. Proceed?'
    payload = {'tool_name': 'AskUserQuestion', 'cwd': str(root), 'session_id': 's1',
               'tool_input': {'questions': [{'question': question}]}}
    hook.handle(root, 'PostToolUse', answered(root, [question], {question: answer}))
    assert ws.rows(root, 'ruling')[-1]['data']['approved'] is approved

def test_a_breaking_question_without_its_pr_is_refused(root):
    payload = {'tool_name': 'AskUserQuestion', 'cwd': str(root), 'session_id': 's1',
               'tool_input': {'questions': [{'question': 'breaking: we drop v1. Proceed?'}]}}
    assert 'owner/repo#n at <sha7>' in guards.pre_tool(root, payload)['reason']


CLASSIFY = 'breaking: acme/app#42 at aaaaaaa: drops v1 export. Treat as breaking?'
PROCEED = 'breaking: acme/app#42 at aaaaaaa: drops v1 export. Announced at https://x.test/a. Proceed?'


def test_the_classification_question_passes_and_the_hint_names_it(root):
    ask = lambda q: guards.pre_tool(root, {'tool_name': 'AskUserQuestion', 'cwd': str(root), 'session_id': 's1',
                                           'tool_input': {'questions': [{'question': q}]}})
    assert ask(CLASSIFY) is None
    reason = ask('breaking: is v1 export breaking?')['reason']
    assert '"breaking: owner/repo#n at <sha7>: <what changes>. Treat as breaking?"' in reason and 'Proceed?' in reason


def test_a_classification_yes_never_stands_in_for_the_proceed(root, fake):
    standard(root)
    pr = make_pr(body='WUWEI-Item: I-1\nAnnouncement: https://status.acme.test/v1-retired')
    fake.prs['42'] = pr
    gates(root)
    hook.handle(root, 'PostToolUse', answered(root, [CLASSIFY], {CLASSIFY: 'Yes, it is breaking'}))
    assert ws.rows(root, 'ruling')[-1]['data'] == {'kind': 'breaking', 'breaking': True, 'pr': 'acme/app#42', 'head': 'aaaaaaa',
                                                   'approved': False, 'question': CLASSIFY, 'answer': 'Yes, it is breaking'}
    assert texts(root)[0].startswith('breaking change needs the owner\'s confirmation')  # the yes made it breaking
    hook.handle(root, 'PostToolUse', answered(root, [PROCEED], {PROCEED: 'Proceed'}))
    assert texts(root) == []


@pytest.mark.parametrize('title, head, found', [
    ('feat: change 42', HEAD, []),  # the owner's no clears the arch yes at this head
    ('feat: change 42', 'c' * 40, ['breaking change without an announcement']),  # a new head: the arch yes holds again
    ('feat!: change 42', HEAD, ['breaking change without an announcement']),  # the PR declares its own break
])
def test_a_classification_no_clears_the_breaking_gap_at_its_head(root, fake, title, head, found):
    standard(root)
    pr = make_pr(head=head)
    pr['title'] = title
    fake.prs['42'] = pr
    attest(root, 'arch', 'yes: removes the --format flag', head=head)
    attest(root, 'quality', head=head)
    attest(root, 'security', head=head)
    hook.handle(root, 'PostToolUse', answered(root, [CLASSIFY], {CLASSIFY: 'No'}))
    assert [t[:39] for t in texts(root) if t.startswith('breaking')] == found
