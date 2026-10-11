"""The decision record library the learning and MCP cards still use (part 14 keeps it)."""

from pathlib import Path
import re

import pytest


VALID = '''Question: Which fix?
Class: design
Context: tests/test_example.py records the failure.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| A | Implement fix | Passes every must and scores 8 on Correctness. It costs a little Speed. | The failure is fixed today. |
| B | Defer until tomorrow | Passes every must but scores 2 on Correctness. | Nothing changes until tomorrow. |
Lenses:
| Lens | A | B |
| --- | --- | --- |
| SOLID | Keeps single responsibility. | No change. |
| twelve-factor | No new config. | No change. |
| YAGNI | Builds only the fix. | Builds nothing. |
| ponytail | Smallest diff that works. | Simplest: nothing. |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Correctness | 10 | 8 | 2 |
| Speed | 2 | 3 | 5 |
Recommendation: A
Reasoning: Correctness decided it. A risky fix would flip it to B.
Confidence: high
Reversibility: two-way
Blast radius: own branch
Pre-mortem: Regression returns.
Revisit: Regression returns.
Decided-by: seat
Outcome: pending
'''
B_ROW = '| B | Defer until tomorrow | Passes every must but scores 2 on Correctness. | Nothing changes until tomorrow. |'
LENS_BLOCK = VALID[VALID.index('Lenses:'):VALID.index('Musts:')]
# A record written before #475: description column, no Class, no Reasoning.
LEGACY = '''Question: Which fix?
Context: tests/test_example.py records the failure.
Options:
| Option | Description |
| --- | --- |
| A | Implement fix |
| B | Defer until tomorrow |
Musts:
| Criterion | A | B |
| --- | --- | --- |
| Safe | pass | pass |
Wants:
| Criterion | Weight | A | B |
| --- | --- | --- | --- |
| Correctness | 10 | 8 | 2 |
| Speed | 2 | 3 | 5 |
Recommendation: A
Confidence: high
Reversibility: two-way
Blast radius: own branch
Pre-mortem: Regression returns.
Revisit: Regression returns.
Decided-by: seat
Outcome: pending
'''


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    return root


def save(root, text=VALID, name='D-3.md'):
    from wuwei.workspace import day_dir
    path = day_dir(root) / 'decisions' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        path.write_text(text)
    return path


def lint(text):
    """(code, message) of the new-record check write() applies, with the default lenses."""
    from wuwei import decision
    try:
        decision.evaluate(text, decision.LENSES, write=True)
    except ValueError as exc:
        return 1, str(exc)
    return 0, 'OK'


@pytest.mark.parametrize('old,new,reason', [
    ('Recommendation: A', 'Recommendation: B', 'B (30)'),
    ('Recommendation: A', 'Recommendation: C', 'Recommendation'),
    ('| Safe | pass | pass |', '| Safe | fail | pass |', 'must'),
    ('| Safe | pass | pass |', '| Safe | fail | fail |', 'passing'),
    ('| Safe | pass | pass |', '| Safe | yes | pass |', 'pass/fail'),
    (B_ROW + '\n', '', 'two options'),
    ('Defer until tomorrow', 'Another fix', 'Do nothing, Defer or Keep'),
    ('| B | Defer until tomorrow |', '| A | Defer until tomorrow |', 'duplicate'),
    ('| 10 | 8 | 2 |', '| 11 | 8 | 2 |', 'weight'),
    ('| 10 | 8 | 2 |', '| 0 | 8 | 2 |', 'weight'),
    ('| 10 | 8 | 2 |', '| 10 | 11 | 2 |', 'score'),
    ('| 10 | 8 | 2 |', '| 10 | -1 | 2 |', 'score'),
    ('| 10 | 8 | 2 |', '| 10 | NaN | 2 |', 'score'),
    ('| 10 | 8 | 2 |', '| 10 | 8 | |', 'cell'),
    ('| Criterion | A | B |', '| Criterion | A | C |', 'columns'),
    ('Confidence: high', 'Confidence: certain', 'Confidence'),
    ('Decided-by: seat', 'Decided-by: anybody', 'Decided-by'),
    ('Reversibility: two-way', 'Reversibility: maybe', 'Reversibility'),
    ('Outcome: pending', 'Outcome: pending\nOutcome: done', 'duplicate'),
])
def test_lint_findings(old, new, reason):
    code, message = lint(VALID.replace(old, new))
    assert code == 1
    assert reason in message
    if new == 'Recommendation: B':
        assert 'A (86)' in message


@pytest.mark.parametrize('field', ['Question', 'Context', 'Options', 'Musts', 'Wants',
    'Recommendation', 'Confidence', 'Reversibility', 'Blast radius', 'Pre-mortem',
    'Revisit', 'Decided-by', 'Outcome'])
def test_missing_fields(field):
    code, message = lint(VALID.replace(field + ':', 'Omitted:'))
    assert code == 1 and field in message


@pytest.mark.parametrize('text', [VALID, VALID.replace('Defer until tomorrow', 'Do nothing'),
    VALID.replace('| 8 | 2 |', '| 2 | 2 |').replace('| 3 | 5 |', '| 5 | 5 |'),
    VALID.replace('| Safe | pass | pass |', '| Safe | fail | pass |').replace('Recommendation: A', 'Recommendation: B'),
    VALID.replace('Question:', '**Question:**'), VALID.replace('Reversibility: two-way', 'Reversibility: unsure')])
def test_valid_evaluation(text):
    assert lint(text)[0] == 0


@pytest.mark.parametrize('wrap', [lambda s: '```\n' + s + '```',
    lambda s: '<!--\n' + s + '-->', lambda s: '\n'.join('> ' + line for line in s.splitlines())])
def test_examples_do_not_supply_fields(wrap):
    assert lint(wrap(VALID))[0] == 1


@pytest.mark.parametrize('path,value', [('decision_outcomes', {}),
    ('decision_outcomes.D-3', {}), ('items.x.decision_outcomes', {}),
    ('items.x', {'decision_outcomes': {}})])
def test_reserved_outcomes(ws, path, value):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state(path, value, ws)


def test_reserved_callback(ws):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.write_state(lambda data: data.update(decision_outcomes={'D-3': {}}), ws)


def test_reserved_outcomes_inside_list(ws):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('metadata', [{'decision_outcomes': {'D-3': {}}}], ws)


def test_reserved_outcomes_inside_tuple_callback(ws):
    from wuwei import state
    with pytest.raises(state.StateError, match='reserved'):
        state.write_state(lambda data: data.update(
            metadata=({'decision_outcomes': {'D-3': {}}},)), ws)


@pytest.mark.parametrize('kind', ['decision.decided', 'decision.rejected', 'decision.future'])
def test_generic_event_reserves_all_decision_kinds(ws, monkeypatch, capsys, kind):
    from wuwei.__main__ import main
    from wuwei.workspace import day_dir
    monkeypatch.chdir(ws)
    assert main(['event', kind, '{}']) == 1
    assert not (day_dir(ws) / 'events.jsonl').exists()


@pytest.mark.parametrize('field', ['Context', 'Blast radius', 'Pre-mortem', 'Revisit', 'Outcome'])
def test_prose_fields_allow_continuation(field):
    lines = VALID.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(field + ':'))
    lines.insert(index + 1, 'More evidence and explanation.')
    assert lint('\n'.join(lines))[0] == 0


@pytest.mark.parametrize('field', ['Question', 'Recommendation', 'Confidence', 'Reversibility', 'Decided-by'])
def test_scalar_fields_reject_continuation(field):
    lines = VALID.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith(field + ':'))
    lines.insert(index + 1, 'Another value')
    assert lint('\n'.join(lines))[0] == 1


@pytest.mark.parametrize('suffix', ['\n## Consequences\nA longer explanation.\n## Notes\nEvidence.',
                                    '\nConsequences: A longer explanation.\nNotes: Evidence.'])
def test_trailing_madr_sections(suffix):
    assert lint(VALID + suffix)[0] == 0
    assert lint(VALID.replace('Outcome: pending', '') + suffix)[0] == 1


@pytest.mark.parametrize('outer_pipes', [True, False])
def test_markdown_tables_and_case_insensitive_musts(outer_pipes):
    from wuwei.decision import evaluate
    text = VALID.replace('| Safe | pass | pass |', '| Safe | FAIL | Pass |').replace('Recommendation: A', 'Recommendation: B')
    if not outer_pipes:
        text = '\n'.join(line.strip('|') if line.startswith('|') else line for line in text.splitlines())
    assert evaluate(text)[1]['B'] == 30


@pytest.mark.parametrize('data,expected', [
    ({}, None),
    ({'decision_outcomes': {}}, None),
    ({'decision_outcomes': {'D-1': {}}}, None),
    ({'decision_outcomes': {'D-1': {'option': 'A', 'decided_by': 'seat'}}}, None),
    ({'decision_outcomes': {'D-1': 'defer'}}, None),
    ({'decision_outcomes': {'D-1': {'option': 'defer', 'decided_by': 'owner'}}}, 'defer'),
])
def test_answered_reads_only_owner_outcomes(data, expected):
    from wuwei import decision
    assert decision.answered(data, 'D-1') == expected


def test_classes_are_the_fixed_list():
    from wuwei import decision
    assert decision.CLASSES == ('approach', 'retry', 'park', 'accept-residual', 'defer', 'scope-cut', 're-plan',
                                'dependency-bump', 'design', 'boundary', 'refactor', 'merge', 'message', 'other')


def test_cruise_decided_by_reads_as_mandate_and_is_refused_on_write():
    # #814: a record written before the upgrade reads as mandate; a new write refuses cruise.
    from wuwei import decision
    text = VALID.replace('Decided-by: seat', 'Decided-by: cruise park@L2')
    assert decision.evaluate(text)[0]['Decided-by'] == 'mandate'
    code, message = lint(text)
    assert code == 1 and message.startswith('Decided-by'), message


def test_role_is_an_optional_validated_field():
    from wuwei import decision
    with_role = lambda role: VALID.replace('Class: design', f'Class: design\nRole: {role}')
    assert lint(with_role('builder'))[0] == 0
    code, message = lint(with_role('wizard'))
    assert code == 1 and message.startswith('Role:')
    assert lint(with_role('builder\nreviewer'))[0] == 1
    assert decision.evaluate(with_role('builder'))[0]['Role'] == 'builder'


@pytest.mark.parametrize('old,new,named', [
    ('Class: design\n', '', 'Class'),
    ('| Option | Title |', '| Option | Name |', 'Options'),
    ('Passes every must but scores 2 on Correctness.', '', 'Options'),
    ('Nothing changes until tomorrow.', '', 'Options'),
    ('Reasoning: Correctness decided it. A risky fix would flip it to B.\n', '', 'Reasoning'),
    ('flip it to B.\n', 'flip it to B.\nAnd more.\n', 'Reasoning'),
    (LENS_BLOCK, '', 'Lenses'),
    ('| YAGNI | Builds only the fix. | Builds nothing. |\n', '', 'YAGNI'),
    ('| No new config. |', '|  |', 'Lenses'),
    ('Musts:', '| Speed | Fast. | Slow. |\nMusts:', 'Speed'),
    ('| A | Implement fix |', '| A | defer until Tomorrow |', 'title Defer until tomorrow'),
    ('| A | Implement fix |', '| A | ' + 'x' * 41 + ' |', 'x' * 41),
    ('| A | Implement fix |', '| A | Implement "fix" |', 'Implement "fix"'),
    ('| A | Implement fix |', '| A | Implement $fix |', 'Implement $fix'),
])
def test_explained_record_fields(old, new, named):
    assert old in VALID
    code, message = lint(VALID.replace(old, new))
    assert code == 1 and named in message, message


def test_legacy_record_still_evaluates(ws):
    from wuwei import decision
    assert decision.evaluate(LEGACY)[1]['A'] == 86
    code, message = lint(LEGACY)
    assert code == 1 and ('Options' in message or 'Class' in message)
    with pytest.raises(ValueError):
        decision.write(LEGACY, ws)


def test_prioritisation_record_needs_no_lens():
    assert lint(VALID.replace('Class: design', 'Class: re-plan').replace(LENS_BLOCK, '')) == (0, 'OK')


def test_class_after_question_is_its_own_field():
    from wuwei import decision
    text = VALID.replace('Class: design', 'Class: re-plan')
    assert decision.evaluate(text)[0]['Class'] == 're-plan'
    with pytest.raises(ValueError, match='Class'):
        decision.evaluate(text.replace('Class: re-plan', 'Class: desing'))


def test_widget_shape():
    from wuwei.decision import widget
    built = widget('Q?', 'Head', [('a', 'one'), ('b', 'two')], 'wuwei x <label>')
    assert built == {'question': 'Q?', 'header': 'Head', 'multiSelect': False, 'record': 'wuwei x <label>',
                     'options': [{'label': 'a', 'description': 'one'}, {'label': 'b', 'description': 'two'}]}
    for header, options in (('x' * 13, [('a', '1'), ('b', '2')]), ('H', [('a', '1')]),
                            ('H', [(str(n), 'd') for n in range(5)])):
        with pytest.raises(ValueError):
            widget('Q?', header, options, 'r')


FIVE = '''Question: Which fix?
Class: other
Context: tests/test_example.py records the failure.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| A | Fix one | Scores 5. | One changes. |
| B | Defer until tomorrow | Scores 2. | Nothing changes. |
| C | Fix three | Scores 9. | Three changes. |
| D | Fix four | Scores 4. | Four changes. |
| E | Fix five | Scores 3. | Five changes. |
Musts:
| Criterion | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| Safe | pass | pass | pass | pass | pass |
Wants:
| Criterion | Weight | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- | --- |
| Correctness | 10 | 5 | 2 | 9 | 4 | 3 |
Recommendation: C
Reasoning: Correctness decided it.
Confidence: high
Reversibility: two-way
Blast radius: own branch
Pre-mortem: Regression returns.
Revisit: Regression returns.
Decided-by: seat
Outcome: pending
'''


def test_record_widget(ws):
    from wuwei import decision
    from wuwei.commands.outbound import RECORD
    from wuwei.workspace import owner_cli
    save(ws)
    built = decision.record_widget('D-3', decision.evaluate(VALID)[0], RECORD, root=ws)
    assert built['question'] == 'D-3: Which fix? Correctness decided it.' and built['header'] == 'D-3'
    assert [o['label'] for o in built['options']] == ['Implement fix (Recommended)', 'Defer until tomorrow']
    assert built['multiSelect'] is False
    assert built['options'][0]['description'].splitlines() == [
        'Passes every must and scores 8 on Correctness.', 'The failure is fixed today.',
        'SOLID: Keeps single responsibility.', 'twelve-factor: No new config.',
        'YAGNI: Builds only the fix.', 'ponytail: Smallest diff that works.']
    fields = decision.evaluate(VALID)[0]
    assert built['record'] == f'{owner_cli(ws)} outbound answer D-3 "<label>" --card {decision.card_hash("D-3", fields)}'
    swapped = VALID.replace('| 10 | 8 | 2 |', '| 10 | 2 | 8 |').replace('Recommendation: A', 'Recommendation: B')
    built = decision.record_widget('D-3', decision.evaluate(swapped)[0], RECORD, root=ws)
    assert [o['label'] for o in built['options']] == ['Defer until tomorrow (Recommended)', 'Implement fix']
    save(ws, FIVE)
    built = decision.record_widget('D-3', decision.evaluate(FIVE)[0], RECORD, root=ws)
    assert [o['label'] for o in built['options']] == [
        'Fix three (Recommended)', 'Fix one', 'Defer until tomorrow', 'Fix four']
    assert built['options'][0]['description'] == 'Scores 9.\nThree changes.'


def test_card_hash_names_question_and_options():
    # #599: the record command carries the card the owner saw: its Question and Options.
    from wuwei import decision
    fields = decision.evaluate(VALID)[0]
    found = decision.card_hash('D-3', fields)
    assert re.fullmatch(r'[0-9a-f]{12}', found) and found == decision.card_hash('D-3', dict(fields))
    for key in ('Question', 'Options'):
        assert decision.card_hash('D-3', {**fields, key: fields[key] + ' changed'}) != found
    for old, new in (('Outcome: pending', 'Outcome: A'), ('Decided-by: seat', 'Decided-by: owner')):
        assert decision.card_hash('D-3', decision.evaluate(VALID.replace(old, new))[0]) == found
    assert decision.card_hash('D-3', decision.evaluate(VALID + 'Notes: later.\n')[0]) == found


def test_widget_trims_by_verbosity():
    from wuwei import decision
    fields = decision.evaluate(VALID)[0]
    brief = decision.record_widget('D-3', fields, 'r', root=Path('/w'))['options'][0]['description'].splitlines()[0]
    full = decision.record_widget('D-3', fields, 'r', level='full', root=Path('/w'))['options'][0]['description'].splitlines()[0]
    assert brief == 'Passes every must and scores 8 on Correctness.'
    assert full == 'Passes every must and scores 8 on Correctness. It costs a little Speed.'
    assert decision.record_widget('D-3', fields, 'r', level='full', root=Path('/w'))['question'] == (
        'D-3: Which fix? Correctness decided it.')


def test_set_outcome_rewrites_first_outcome():
    from wuwei import decision
    text = 'Question: Q?\n## Outcome: pending\nNotes: kept\nOutcome: pending\n'
    assert decision.set_outcome(text, 'proceed') == 'Question: Q?\n## Outcome: proceed\nNotes: kept\nOutcome: pending\n'


def test_owner_record_writes_outcome_owner_and_notes(ws):
    from wuwei import decision
    text = decision.owner_record(VALID, 'B', 'at the host terminal', 'phone answer')
    fields, _ = decision.evaluate(text)
    assert fields['Outcome'] == 'B' and fields['Decided-by'] == 'owner'
    assert text.endswith('\nNotes: Decided at 2026-09-28T12:00:00+00:00 at the host terminal. phone answer\n')
    assert decision.owner_record(VALID, 'A', 'at the host terminal').endswith(
        '\nNotes: Decided at 2026-09-28T12:00:00+00:00 at the host terminal.\n')


def test_keep_is_a_status_quo_title():
    assert lint(VALID.replace('Defer until tomorrow', 'Keep owner-only'))[0] == 0
