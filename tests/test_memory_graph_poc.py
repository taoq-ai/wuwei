"""Keeps the memory graph spike (#444) runnable and honest."""

import importlib.util
from pathlib import Path
import re
import sqlite3
import sys

import pytest

from wuwei import decision

ROOT = Path(__file__).resolve().parents[1]
POC = ROOT / 'scripts' / 'poc' / 'memory-graph'
TYPES = ('why', 'touched', 'lesson', 'revert', 'reversed')


def load(name):
    path = POC / (name + '.py')
    assert path.is_file(), f'{name} is not implemented'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}


def test_golden_set_matches_corpus(tmp_path):
    corpus = load('corpus')
    golden = corpus.generate(tmp_path / 'a', days=6)
    assert len(golden) == 30
    assert sorted(q['type'] for q in golden) == sorted(TYPES * 6)
    root = tmp_path / 'a'
    files = {str(p.relative_to(root)): p.read_text(encoding='utf-8').lower()
             for p in (root / '.wuwei').rglob('*') if p.is_file()}
    for q in golden:
        expected = {path for path, _ in q['expected']}
        lines = []
        for path, line in q['expected']:
            text = (root / path).read_text(encoding='utf-8').splitlines()
            assert 1 <= line <= len(text), (q['id'], path, line)
            lines.append(text[line - 1].lower())
        phrase = q['answer'].lower()
        assert any(phrase in line for line in lines), q['id']
        assert {path for path, text in files.items() if phrase in text} <= expected, q['id']
        for path in expected:
            if '/decisions/' in path:
                decision.evaluate((root / path).read_text(encoding='utf-8'))
    corpus.generate(tmp_path / 'b', days=6)
    assert tree(root) == tree(tmp_path / 'b')


@pytest.mark.parametrize('fts', (True, False))
def test_graph_answers_and_rebuilds_identically(tmp_path, fts):
    corpus, graph = load('corpus'), load('graph')
    if fts and not graph.fts_available():
        pytest.skip('this SQLite build has no FTS5')
    golden = corpus.generate(tmp_path, days=6)
    conn = graph.build(tmp_path, tmp_path / 'one.db', fts)
    assert graph.dump_hash(conn) == graph.dump_hash(graph.build(tmp_path, tmp_path / 'two.db', fts))
    first = {kind: next(q for q in golden if q['type'] == kind) for kind in TYPES}
    hits = graph.ask(conn, first['why']['words'])
    assert tuple(first['why']['expected'][0]) in [(row[3], row[4]) for row in hits]
    _, node, types, hops = first['reversed']['form']
    paths = {row[3] for row in graph.around(conn, node, hops, types)}
    assert {path for path, _ in first['reversed']['expected']} <= paths
    _, node, types, hops = first['touched']['form']
    assert [row[1] for row in graph.around(conn, node, hops, types)] == ['pr'] * 3
    found = {row[0] for row in conn.execute('select distinct type from nodes')}
    assert found == {'item', 'decision', 'pr', 'file', 'lesson', 'retro', 'incident', 'ticket'}


def test_thresholds_and_conclusion():
    run = load('run')
    mb = 2 ** 20
    for args, verdict in (((40, 65, 1000, 900), 'supported'), ((40, 50, 1000, 500), 'supported'),
                          ((40, 64, 1000, 900), 'unsupported'), ((40, 40, 1000, 510), 'unsupported')):
        assert run.h1_verdict(*args) == verdict, args
    assert run.h3_verdict(10, 20 * mb, 50 * mb - 1, True) == 'supported'
    for args in ((10.1, 1, 1, True), (1, 20 * mb + 1, 1, True), (1, 1, 50 * mb, True), (1, 1, 1, False)):
        assert run.h3_verdict(*args) == 'unsupported', args
    assert (run.h4_verdict(0.51), run.h4_verdict(0.5)) == ('supported', 'unsupported')
    for h1, h3, h4, conclusion in (('unsupported', 'supported', 'unsupported', 'drop'),
                                   ('unmeasured', 'supported', 'unsupported', 'drop'),
                                   ('supported', 'unsupported', 'unsupported', 'park'),
                                   ('supported', 'supported', 'supported', 'park'),
                                   ('supported', 'supported', 'unsupported', 'build')):
        assert run.conclude(h1, h3, h4) == conclusion, (h1, h3, h4)


def test_h1_judged_against_the_stronger_grep(tmp_path, capsys):
    corpus, run = load('corpus'), load('run')
    golden = corpus.generate(tmp_path, days=6)
    for q in golden:
        if q['type'] != 'reversed':
            top, _ = run.grep_baseline(tmp_path, [q['key']])
            assert {path for path, _ in q['expected']} <= set(top), q['id']
    assert run.main(['--days', '6', '--no-fts']) == 0
    out = capsys.readouterr().out
    total = re.search(r'^\| total \| 30 \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|', out, re.M)
    word_rate, key_rate, graph_rate, word_tokens, key_tokens, graph_tokens = map(int, total.groups())
    base_rate, base_tokens = max((word_rate, -word_tokens), (key_rate, -key_tokens))
    verdict = re.search(r'^Verdict H1: (\w+) ', out, re.M).group(1)
    assert verdict == run.h1_verdict(base_rate, graph_rate, -base_tokens, graph_tokens)


@pytest.mark.parametrize('args', ([], ['--no-fts']))
def test_runner_prints_four_tables(capsys, args):
    run = load('run')
    if not args and not run.graph.fts_available():
        pytest.skip('this SQLite build has no FTS5')
    assert run.main(['--days', '6', *args]) == 0
    out = capsys.readouterr().out
    assert re.search(r'^Search: ' + ('like' if args else 'fts5') + r' \(', out, re.M)
    verdicts = {}
    for n in '1234':
        assert f'### H{n}' in out
        found = re.findall(rf'^Verdict H{n}: (supported|unsupported|unmeasured) ', out, re.M)
        assert len(found) == 1 and out.index(f'### H{n}') < out.index(f'Verdict H{n}:'), n
        verdicts[n] = found[0]
    assert verdicts['2'] == 'unmeasured'
    assert re.findall(r'^Conclusion: (build|park|drop)$', out, re.M) == [
        run.conclude(verdicts['1'], verdicts['3'], verdicts['4'])]


def test_runner_exits_2_on_error(monkeypatch, capsys):
    run = load('run')

    def broken(*args):
        raise sqlite3.OperationalError('disk I/O error')

    monkeypatch.setattr(run.graph, 'build', broken)
    assert run.main(['--days', '6']) == 2
    out, err = capsys.readouterr()
    assert err.startswith('memory-graph poc unmeasured:') and 'disk I/O error' in err
    assert 'Verdict' not in out and 'Conclusion' not in out


def test_spike_document_decision_record():
    path = ROOT / 'docs' / 'specs' / '2026-10-03-memory-graph-poc.md'
    assert path.is_file(), 'spike document missing'
    text = path.read_text(encoding='utf-8')
    conclusions = re.findall(r'^Conclusion: (build|park|drop)$', text, re.M)
    assert len(conclusions) == 1
    fields, _ = decision.evaluate(text.split('## Decision record', 1)[1])
    assert fields['Decided-by'] == 'owner'
    options = dict(decision.table(fields['Options'], ['Option', 'Description'], 'Options'))
    start = {'build': 'Build', 'park': 'Defer', 'drop': 'Do nothing'}[conclusions[0]]
    assert options[fields['Recommendation']].startswith(start)
    if conclusions[0] == 'build':
        assert '## Follow-up issue' in text
    else:
        assert 'closes with this document linked' in text
    assert '\u2014' not in text
