"""The card helpers decision.py keeps, the reserved outcome records, and VALID, the D-n record
shape other tests write as a past day's record."""

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


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    return root


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


def test_widget_shape():
    from wuwei.decision import widget
    built = widget('Q?', 'Head', [('a', 'one'), ('b', 'two')], 'wuwei x <label>')
    assert built == {'question': 'Q?', 'header': 'Head', 'multiSelect': False, 'record': 'wuwei x <label>',
                     'options': [{'label': 'a', 'description': 'one'}, {'label': 'b', 'description': 'two'}]}
    for header, options in (('x' * 13, [('a', '1'), ('b', '2')]), ('H', [('a', '1')]),
                            ('H', [(str(n), 'd') for n in range(5)])):
        with pytest.raises(ValueError):
            widget('Q?', header, options, 'r')
