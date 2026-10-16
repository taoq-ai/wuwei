import pytest

from conftest import HEAD, verdict_text
from wuwei import verdict


def test_a_clean_pass_parses():
    parsed = verdict.parse(verdict_text())
    assert parsed['errors'] == []
    assert (parsed['verdict'], parsed['gate'], parsed['head'], parsed['repo'], parsed['pr']) == (
        'PASS', 'quality', HEAD, 'acme/app', 42)


def test_findings_parse_with_their_block_flag():
    text = verdict_text(verdict='FIX', findings=(
        '- [high] src/app.py:12 blocks: yes. Failure: an empty list returns None and the caller crashes.\n'
        '- [low] src/app.py:40 blocks: no. Failure: a log line repeats the token prefix.'))
    parsed = verdict.parse(text)
    assert parsed['errors'] == []
    assert [f['blocks'] for f in parsed['findings']] == [True, False]


@pytest.mark.parametrize('text, error', [
    (verdict_text(verdict='MAYBE'), 'Verdict'),
    (verdict_text(head='abc'), 'Head'),
    (verdict_text(gate='vibes'), 'Gate'),
    (verdict_text(pr='app#x'), 'PR'),
    (verdict_text(findings='- src/app.py blocks: yes'), 'finding'),
    (verdict_text(findings='- [high] src/app.py:3 blocks: yes. Failure: it breaks.'), 'PASS'),
    ('Verdict: PASS\n', 'Findings'),
])
def test_lint_names_what_is_wrong(text, error):
    assert any(error in message for message in verdict.parse(text)['errors'])


def test_confidence_is_part_of_the_verdict():
    assert verdict.parse(verdict_text())['confidence'] == 'high'
    text = verdict_text().replace('Confidence: high\n', '')
    assert any('Confidence' in e for e in verdict.parse(text)['errors'])


def test_the_charter_template_wording_parses():
    text = verdict_text(findings='- [medium] src/app.py:12-14 blocks: no. Note: the poll interval above 60 stops backfill.')
    text = text.replace('Confidence: high', 'Confidence: medium (both guards killed by mutants)')
    parsed = verdict.parse(text)
    assert parsed['errors'] == [] and parsed['confidence'] == 'medium'
    assert parsed['findings'][0]['blocks'] is False


def test_a_note_needs_no_file_line_but_a_blocking_finding_does():
    parsed = verdict.parse(verdict_text(findings='- [low] blocks: no. a note on the design'))
    assert parsed['errors'] == [] and parsed['findings'][0]['blocks'] is False
    errors = verdict.parse(verdict_text(verdict='FIX', findings='- [high] blocks: yes. Failure: x'))['errors']
    assert any('file>:<line>' in e for e in errors)


def test_a_blocking_finding_still_needs_its_failure_scenario():
    text = verdict_text(verdict='FIX', findings='- [HIGH] src/app.py:3 blocks: yes. Note: looks off')
    assert any('Failure:' in e for e in verdict.parse(text)['errors'])


def test_a_verdict_written_before_the_pr_opens_names_only_the_repository():
    parsed = verdict.parse(verdict_text(pr='acme/app'))
    assert parsed['errors'] == [] and parsed['repo'] == 'acme/app' and parsed['pr'] is None
