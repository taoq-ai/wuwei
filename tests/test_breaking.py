"""A breaking change to an outward surface needs an announcement and the owner's confirmation."""

import hashlib

import pytest

from conftest import HEAD, make_pr, verdict_text, write_plan
from wuwei import evidence, guards, hook, verdict, ws


def standard(root):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard'}])


def attest(root, gate, breaking='no'):
    path = root / ws.DIR / 'verdicts' / 'I-1' / f'{gate}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(verdict_text(gate=gate, breaking=breaking))
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
    assert texts(root) == ['breaking change without an announcement: add "Announcement: <link to the client '
                           'communication, release note or migration guide>"']
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


def test_a_confirmation_does_not_survive_a_moved_head(root, fake):
    standard(root)
    pr = make_pr(body='WUWEI-Item: I-1\nBREAKING CHANGE: v1 export removed\nAnnouncement: CHANGELOG.md')
    fake.prs['42'] = pr
    gates(root)
    ws.record(root, 'ruling', {'kind': 'breaking', 'pr': 'acme/app#42', 'head': 'bbbbbbb', 'approved': True})
    assert texts(root)[0].startswith('breaking change needs the owner\'s confirmation')


def test_a_contract_file_raises_a_light_item_so_arch_reviews_it(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'c', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light'}])
    fake.prs['42'] = make_pr(files=('api/openapi.yaml', 'tests/test_api.py'))
    attest(root, 'quality')
    assert texts(root) == ['gates missing at head aaaaaaa: arch, security (tier raised to standard: the diff '
                           'changes a published contract)']


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
    hook.handle(root, 'PostToolUse', {**payload, 'tool_response': {'answers': {question: 'Yes, proceed'}}})
    assert ws.rows(root, 'ruling')[-1]['data'] == {'kind': 'breaking', 'pr': 'acme/app#42', 'head': 'aaaaaaa',
                                                   'approved': True, 'question': question, 'answer': 'Yes, proceed'}


def test_a_breaking_question_without_its_pr_is_refused(root):
    payload = {'tool_name': 'AskUserQuestion', 'cwd': str(root), 'session_id': 's1',
               'tool_input': {'questions': [{'question': 'breaking: we drop v1. Proceed?'}]}}
    assert 'owner/repo#n at <sha7>' in guards.pre_tool(root, payload)['reason']
