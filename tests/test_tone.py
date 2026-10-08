"""#522: the plain tone rule, its lint and the budget every text class keeps."""

import ast

import pytest

from test_plan import root  # noqa: F401 (fixture)
from test_protect_state import payload, workspace  # noqa: F401 (fixture)
from test_reasons import ROOT, _sources, _text, all_reasons
from wuwei import interview
from wuwei.__main__ import main
from wuwei.commands.lint import AVERAGE, LONGEST, line, measure, sentences

# #522: per class, the sentences over 35 words it may keep and its nominalisations per 100
# words (the after-pass rate rounded up to one decimal). docs keeps the 75 long sentences of
# the pages outside the pass (research.md).
BUDGETS = {'reasons': (0, 3.1), 'cards': (0, 3.1), 'skills': (0, 2.9), 'charters': (0, 4.3), 'docs': (75, 3.0)}


def _cards():
    """The literal question and option descriptions of every widget( call, and the interview."""
    for _, source in _sources():
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call) and node.args
                    and getattr(node.func, 'attr', getattr(node.func, 'id', None)) == 'widget'):
                yield from (text for text, _ in _text(node.args[0]))
                if len(node.args) > 2 and isinstance(node.args[2], (ast.List, ast.Tuple)):
                    for elt in node.args[2].elts:
                        if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
                            yield from (text for text, _ in _text(elt.elts[1]))
    for row in interview.QUESTIONS:
        yield row['question']
        yield from (text for _, text, _ in row['choices'])


def classes():
    """{class: [texts]}: the five text classes the plain tone budget holds."""
    return {'reasons': [text for _, _, text, _, _ in all_reasons()],
            'cards': list(_cards()),
            'skills': [p.read_text() for p in sorted(ROOT.glob('skills/*/SKILL.md'))],
            'charters': [p.read_text() for p in sorted(ROOT.glob('charters/*.md'))],
            'docs': [p.read_text() for p in [*sorted(ROOT.glob('docs/site/*.md')), ROOT / 'README.md']]}


def test_sentences_skip_what_is_not_prose():
    text = ('---\nname: x\n---\n# A heading here\n\n```\nnot prose at all here.\n```\n'
            '<!-- a comment here. -->\nOne two `inline code here` three [the link](http://x.y/z).\n')
    assert sentences(text) == [6]


def test_sentences_end_at_list_items_cells_and_marks():
    assert sentences('- one two\n- three four five\n1. six\n') == [2, 3, 1]
    assert sentences('| a b | c |\n| --- | --- |\n| d | e f g |\n') == [2, 1, 1, 3]
    assert sentences('Is it? Yes it is! Then; it goes on.') == [2, 3, 4]
    assert sentences('Name {} here.') == [3]
    assert sentences('one two\nthree four.\n\nfive') == [4, 1]


def test_measure_sums_texts_each_on_its_own():
    m = measure('a b c. d e.', 'f g h i')
    assert (m['sentences'], m['words'], m['average'], m['longest'], m['over']) == (3, 9, 3.0, 4, 0)
    assert measure(' '.join(['word'] * 36) + '.')['over'] == 1
    assert measure('```\ncode\n```\n')['average'] == 0.0
    m = measure('The documentation of measurements shows readiness. Ask and run.\n```\ndocumentation\n```\n')
    assert m['nominalisations'] == 3


def over_budget(texts_by_class):
    found = []
    for name, texts in texts_by_class.items():
        m, (over, rate) = measure(*texts), BUDGETS[name]
        if not (m['average'] < AVERAGE and m['over'] <= over and 100 * m['nominalisations'] <= rate * m['words']):
            found.append(line(name, m))
    return found


def test_every_class_is_within_its_budget():
    assert over_budget(classes()) == []


def test_a_long_charter_sentence_breaks_the_budget():
    texts = classes()
    texts['charters'].append(' '.join(['word'] * 40) + '.')
    assert [found.split(':')[0] for found in over_budget(texts)] == ['charters']


def _line(path, average, longest, over, count, nominal, rate, verdict):
    return (f'{path}: average {average} words, longest {longest}, {over} over 35, {count} sentences, '
            f'{nominal} nominalisations ({rate} per 100 words), {verdict} the rule')


@pytest.fixture
def bare(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_lint_tone_at_and_over_the_rule(bare, capsys):
    good = bare / 'good.md'
    good.write_text(' '.join(['word'] * 12) + '. ' + ' '.join(['word'] * 12) + '.\n')
    assert main(['lint', 'tone', str(good)]) == 0
    assert capsys.readouterr().out == _line(good, '12.0', 12, 0, 2, 0, '0.0', 'at') + '\n'
    bad = bare / 'bad.md'
    bad.write_text(' '.join(['word'] * 36) + '.\n')
    assert main(['lint', 'tone', str(bad)]) == 1
    out = capsys.readouterr().out
    assert '1 over 35' in out and out.endswith('over the rule\n')


def test_lint_tone_measures_a_directory_in_order(bare, capsys):
    (bare / 'docs').mkdir()
    (bare / 'docs/b.md').write_text('Two words.\n')
    (bare / 'docs/a.md').write_text('Three words here.\n')
    (bare / 'docs/c.txt').write_text('Not measured at all.\n')
    assert main(['lint', 'tone', 'docs']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split(':')[0] for line in lines] == ['docs/a.md', 'docs/b.md', 'total']
    assert lines[2] == _line('total', '2.5', 3, 0, 2, 0, '0.0', 'at')


def test_lint_tone_cannot_run(bare, capsys):
    (bare / 'empty').mkdir()
    for path in ('missing.md', 'empty'):
        assert main(['lint', 'tone', path]) == 2
        err = capsys.readouterr().err
        assert path in err and 'pass a markdown file or a directory of them' in err
    (bare / 'bad.md').write_bytes(b'\xff\xfe bad')
    assert main(['lint', 'tone', 'bad.md']) == 2
    assert 'pass a readable UTF-8 file' in capsys.readouterr().err


def _at_rule(texts, owner_ok=True):
    """Each text measured on its own: none over 35, the average under 20 (and no 'the owner')."""
    lengths = [n for text in texts for n in sentences(text)]
    assert lengths and max(lengths) <= LONGEST and sum(lengths) / len(lengths) < AVERAGE, texts
    assert owner_ok or not [text for text in texts if 'the owner' in text.lower()], texts


def test_why_last_refusal_reads_at_the_rule(workspace, monkeypatch, capsys):
    import io
    import json
    import sys
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+00:00')
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(
        payload(workspace, 'Write', file_path='.wuwei/days/2026-09-28/state.json', content='{}'))))
    assert main(['hook', 'PreToolUse']) == 2
    capsys.readouterr()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(workspace))
    assert main(['why', 'last', 'refusal']) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert any('state' in line for line in lines)
    _at_rule(lines)


def test_three_fixture_cards_read_at_the_rule(root, monkeypatch):
    import os
    from test_plan import proposal
    from wuwei import plan
    from wuwei.commands import close
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    monkeypatch.setattr(os, 'cpu_count', lambda: 4)
    plan.propose(proposal(), root)
    cards = [plan.gate_widget(root), close.widget(root, 'A', {'status': 'building', 'phase': 'build'}),
             interview.widgets(root, ['fixture-org/web'])[0]]
    for card in cards:
        _at_rule([card['question'], *(option['description'] for option in card['options'])], owner_ok=False)
