"""#522: the plain tone rule, its lint and the budget every text class keeps."""

import ast
import functools
import re

from test_plan import root  # noqa: F401 (fixture)
from test_protect_state import payload, workspace  # noqa: F401 (fixture)
from test_reasons import ROOT, _sources, _text, all_reasons
from wuwei.__main__ import main

# #838: the measure the CI budget uses; the wuwei lint tone command is gone.
AVERAGE, LONGEST = 20, 35
# ponytail: a suffix heuristic with false hits ("comment", "decision"); compare rates over
# time, and move to a word list if the rate misleads.
NOMINAL = re.compile(r'\b(?=[a-z]{7})[a-z]*(?:tion|sion|ment|ance|ence|ness|ity)s?\b', re.I)
_DROP = re.compile(r'\A---\n.*?\n---\n|```.*?```|<!--.*?-->', re.S)
_ITEM = re.compile(r'\s*(?:[-*]|\d+\.)\s')


def _blocks(text):
    """The prose of one text as blocks; a sentence never crosses a block."""
    text = _DROP.sub('\n', text)
    text = re.sub(r'`[^`\n]*`', 'code', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    blocks, current = [], []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or (set(stripped) <= set('|:- ') and '-' in stripped):
            blocks.append(current)
            current = []
        elif stripped.startswith('|'):
            blocks.append(current)
            blocks.extend([cell] for cell in stripped.split('|'))
            current = []
        elif _ITEM.match(line):
            blocks.append(current)
            current = [line[_ITEM.match(line).end():]]
        else:
            current.append(line)
    blocks.append(current)
    return [' '.join(' '.join(block).split()) for block in blocks if block]


def _lengths(block):
    for piece in re.split(r'(?<=[.!?])\s+', block):
        words = sum(1 for token in piece.split() if re.search(r'[\w{]', token))
        if words:
            yield words


def sentences(text):
    """The length in words of each sentence of one text. A semicolon is not a boundary."""
    return [n for block in _blocks(text) for n in _lengths(block)]


def measure(*texts):
    lengths = [n for text in texts for n in sentences(text)]
    words = sum(lengths)
    return {'sentences': len(lengths), 'words': words,
            'average': words / len(lengths) if lengths else 0.0,
            'longest': max(lengths, default=0), 'over': sum(n > LONGEST for n in lengths),
            'nominalisations': sum(len(NOMINAL.findall(block)) for text in texts for block in _blocks(text))}


def at_rule(m):
    return m['average'] < AVERAGE and m['over'] == 0


def line(name, m):
    rate = 100 * m['nominalisations'] / m['words'] if m['words'] else 0.0
    return (f"{name}: average {m['average']:.1f} words, longest {m['longest']}, {m['over']} over {LONGEST}, "
            f"{m['sentences']} sentences, {m['nominalisations']} nominalisations ({rate:.1f} per 100 words), "
            f"{'at' if at_rule(m) else 'over'} the rule")

# #522: per class, the sentences over 35 words it may keep and its nominalisations per 100
# words (the after-pass rate rounded up to one decimal). docs keeps the 75 long sentences of
# the pages outside the pass (research.md), plus the two hero image lines (#574), whose alt is one sentence.
BUDGETS = {'reasons': (0, 3.1), 'cards': (0, 3.1), 'skills': (0, 2.9), 'charters': (0, 4.3), 'docs': (77, 3.0)}


def _cards():
    """The literal question and option descriptions of every widget( call."""
    for _, source in _sources():
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call) and node.args
                    and getattr(node.func, 'attr', getattr(node.func, 'id', None)) == 'widget'):
                yield from (text for text, _ in _text(node.args[0]))
                if len(node.args) > 2 and isinstance(node.args[2], (ast.List, ast.Tuple)):
                    for elt in node.args[2].elts:
                        if isinstance(elt, ast.Tuple) and len(elt.elts) == 2:
                            yield from (text for text, _ in _text(elt.elts[1]))


@functools.cache
def _classes():
    return {'reasons': tuple(text for _, _, text, _, _ in all_reasons()),
            'cards': tuple(_cards()),
            'skills': tuple(p.read_text() for p in sorted(ROOT.glob('skills/*/SKILL.md'))),
            'charters': tuple(p.read_text() for p in sorted(ROOT.glob('charters/*.md'))),
            'docs': tuple(p.read_text() for p in [*sorted(ROOT.glob('docs/site/*.md')), ROOT / 'README.md'])}


def classes():
    """{class: [texts]}: the five text classes the plain tone budget holds, a fresh copy per call (#685)."""
    return {name: list(texts) for name, texts in _classes().items()}


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


def test_fixture_cards_read_at_the_rule(root, monkeypatch):
    import os
    from test_plan import proposal
    from wuwei import plan
    from wuwei.commands import close
    from wuwei.guards import agent_launch
    monkeypatch.setattr(agent_launch, 'free_memory', lambda config, root: 8 * 1024**3)
    monkeypatch.setattr(os, 'cpu_count', lambda: 4)
    plan.propose(proposal(), root)
    cards = [plan.gate_widget(root), close.widget(root, 'A', {'status': 'building', 'phase': 'build'})]
    for card in cards:
        _at_rule([card['question'], *(option['description'] for option in card['options'])], owner_ok=False)
