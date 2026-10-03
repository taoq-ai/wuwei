"""Measure the four memory graph hypotheses (spike #444) and print the conclusion.

python3 scripts/poc/memory-graph/run.py [--days N] [--no-fts]. Throwaway PoC code.
"""

import argparse
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'cli'))
from wuwei.memory import estimated_tokens  # noqa: E402

import corpus  # noqa: E402
import graph  # noqa: E402

MB = 2 ** 20
TYPES = corpus.TYPES


def read(root, path):
    return (Path(root) / path).read_text(encoding='utf-8')


def grep_baseline(root, words):
    """The planner today: grep -rni over .wuwei, files ranked by hits, the top 5 read in full."""
    root, output, hits = Path(root), [], {}
    needles = [w.lower() for w in words]
    for file in sorted(p for p in (root / '.wuwei').rglob('*') if p.is_file()):
        path = str(file.relative_to(root))
        for number, text in enumerate(file.read_text(encoding='utf-8').splitlines(), 1):
            if any(n in text.lower() for n in needles):
                output.append(f'{path}:{number}:{text}')
                hits[path] = hits.get(path, 0) + 1
    top = sorted(hits, key=lambda p: (-hits[p], p))[:5]
    # ponytail: the 100-line cap stands for a planner narrowing a long grep.
    return top, estimated_tokens('\n'.join(output[:100])) + sum(estimated_tokens(read(root, p)) for p in top)


def query(conn, form):
    if form[0] == 'ask':
        return graph.ask(conn, form[1])
    _, node, types, hops = form
    return graph.around(conn, node, hops, types)[:5]


def h1(root, conn, golden):
    """Rows per type and in total, plus (base rate, graph rate, base tokens, graph tokens).

    Two baselines: word-level grep (any question word) and key grep (the one most specific
    key a planner would search). The stronger of the two is the one H1 is judged against.
    """
    sums = {kind: [0] * 11 for kind in (*TYPES, 'total')}
    for q in golden:
        expected = {path for path, _ in q['expected']}
        start = time.perf_counter()
        top, base_tokens = grep_baseline(root, q['words'])
        base_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        key_top, key_tokens = grep_baseline(root, [q['key']])
        key_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        rows = query(conn, q['form'])
        graph_ms = (time.perf_counter() - start) * 1000
        printed = estimated_tokens('\n'.join(f'{r[1]} {r[2]} {r[3]}:{r[4]} {r[5]}' for r in rows))
        # ponytail: conservative; the graph pays to read its top records in full, like grep.
        graph_tokens = printed + sum(estimated_tokens(read(root, p)) for p in dict.fromkeys(r[3] for r in rows))
        values = (1, expected <= set(top), expected <= set(key_top), expected <= {r[3] for r in rows},
                  base_tokens, key_tokens, graph_tokens, printed, base_ms, key_ms, graph_ms)
        for kind in (q['type'], 'total'):
            sums[kind] = [a + b for a, b in zip(sums[kind], values)]
    lines = ['| Type | Questions | Word grep answered % | Key grep answered % | Graph answered % '
             '| Word grep tokens | Key grep tokens | Graph tokens | Graph excerpts-only tokens '
             '| Word grep ms | Key grep ms | Graph ms |', '|' + ' --- |' * 12]
    for kind, (count, *rest) in sums.items():
        lines.append(f'| {kind} | {count} | '
                     + ' | '.join(f'{v / count:.1f}' if i > 6 else f'{(100 if i < 3 else 1) * v / count:.0f}'
                                  for i, v in enumerate(rest)) + ' |')
    count, word_ok, key_ok, graph_ok, word_tokens, key_tokens, graph_tokens = sums['total'][:7]
    # Stronger baseline: more answered, then fewer tokens.
    base_ok, base_tokens = max((word_ok, -word_tokens), (key_ok, -key_tokens))
    return lines, (100 * base_ok / count, 100 * graph_ok / count, -base_tokens, graph_tokens)


def h2(root, conn, golden):
    """Brief length with and without the around subgraph for 10 fixture items."""
    root = Path(root)
    chosen = [q['form'][1][5:] for q in golden if q['type'] == 'reversed']
    decided = sorted({row[0][5:] for row in conn.execute(
        "select dst from edges where type = 'decided_in'")} - set(chosen))
    lines = ['| Item | Brief tokens | With subgraph tokens | Ratio | Prior decisions | Visible without '
             '| Visible with | Asks | Re-decisions |', '|' + ' --- |' * 9]
    ratios = []
    for item in chosen + decided[:10 - len(chosen)]:
        base = read(root, next(p.relative_to(root) for p in root.glob(f'.wuwei/days/*/briefs/{item}-builder.md')))
        cut = max(1, len(base.splitlines()) // 5)
        sub = [f'{r[1]} {r[2]} {r[3]}:{r[4]}' for r in graph.around(conn, f'item:{item}', 2)][:cut]
        with_ = base + 'Around:\n' + ''.join(line + '\n' for line in sub)
        prior = [r[3] for r in graph.around(conn, f'item:{item}', 1, ['decided_in'])]
        ratio = estimated_tokens(with_) / estimated_tokens(base)
        ratios.append(ratio)
        lines.append(f'| {item} | {estimated_tokens(base)} | {estimated_tokens(with_)} | {ratio:.2f} | '
                     f'{len(prior)} | {sum(p in base for p in prior)} | {sum(p in with_ for p in prior)} '
                     '| unmeasured | unmeasured |')
    within = max(ratios) <= 1.2
    lines.append(f'\nBrief length within 20 percent for every item: {"yes" if within else "no"}.')
    return lines


def h3(days, fts):
    """Build cost on a corpus of 4 * days, and whether a rebuild from scratch is identical."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        corpus.generate(tmp, 4 * days)
        start = time.perf_counter()
        conn = graph.build(tmp, tmp / 'one.db', fts)
        seconds = time.perf_counter() - start
        index = (tmp / 'one.db').stat().st_size
        largest = max(p.stat().st_size for p in tmp.glob('.wuwei/days/*/events.jsonl'))
        nodes, edges = (conn.execute(f'select count(*) from {t}').fetchone()[0] for t in ('nodes', 'edges'))
        again = graph.build(tmp, tmp / 'two.db', fts)
        identical = graph.dump_hash(conn) == graph.dump_hash(again)
        conn.close()
        again.close()
    lines = ['| Days | Build s | Largest events.jsonl bytes | Index bytes | Nodes | Edges | Rebuild identical |',
             '|' + ' --- |' * 7,
             f'| {4 * days} | {seconds:.2f} | {largest} | {index} | {nodes} | {edges} | '
             f'{"yes" if identical else "no"} |']
    return lines, h3_verdict(seconds, largest, index, identical)


def export(root):
    """Simulated #443 export: charter rule lines plus a digest of the last 7 days, no paths."""
    # ponytail: #443 is not on main; this follows the shape it specifies.
    root, out = Path(root), []
    for charter in sorted((root / '.wuwei/charters').glob('*.md')):
        out += [line for line in read(root, charter.relative_to(root)).splitlines() if line.startswith('- ')]
    for day in sorted((root / '.wuwei/days').iterdir())[-7:]:
        for record in sorted(day.glob('decisions/D-*.md')):
            out += [line for line in record.read_text(encoding='utf-8').splitlines()
                    if line.startswith(('Question:', 'Context:', 'Outcome:'))]
        for retro in sorted(day.glob('retro/*.json')):
            out.append(json.loads(retro.read_text(encoding='utf-8'))['fields']['Change'])
        for incident in sorted(day.glob('incidents/INC-*.md')):
            out += [line for line in incident.read_text(encoding='utf-8').splitlines() if line.startswith('Title:')]
    return '\n'.join(out)


def h4(root, golden):
    text = export(root).lower()
    counts = {kind: [0, 0] for kind in (*TYPES, 'total')}
    for q in golden:
        for kind in (q['type'], 'total'):
            counts[kind][0] += 1
            counts[kind][1] += q['answer'].lower() in text
    lines = [f'Export size: {estimated_tokens(text)} tokens.', '',
             '| Type | Questions | Answered by export | Fraction |', '|' + ' --- |' * 4]
    lines += [f'| {kind} | {n} | {k} | {k / n:.2f} |' for kind, (n, k) in counts.items()]
    total, answered = counts['total']
    return lines, answered / total


def h1_verdict(base_rate, graph_rate, base_tokens, graph_tokens):
    """Answer rate up by 25 points, or tokens down by half."""
    return 'supported' if graph_rate - base_rate >= 25 or graph_tokens <= base_tokens / 2 else 'unsupported'


def h3_verdict(seconds, largest_events_bytes, index_bytes, identical):
    """The design 5.13 consolidate budget (10 s, 20 MB per events.jsonl), index under 50 MB."""
    ok = seconds <= 10 and largest_events_bytes <= 20 * MB and index_bytes < 50 * MB and identical
    return 'supported' if ok else 'unsupported'


def h4_verdict(fraction):
    """Supported means the export already answers more than half the questions."""
    return 'supported' if fraction > 0.5 else 'unsupported'


def conclude(h1, h3, h4):
    """Fixed before any measurement; H2 only decides whether briefs are part of a build."""
    if h1 != 'supported':
        return 'drop'
    return 'park' if h3 != 'supported' or h4 == 'supported' else 'build'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=90)
    parser.add_argument('--no-fts', action='store_true')
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            golden = corpus.generate(tmp, args.days)
            fts = not args.no_fts and graph.fts_available()
            conn = graph.build(tmp, Path(tmp) / 'memory.db', fts)
            out = [f'Search: {"fts5" if fts else "like"} (Python {platform.python_version()}, '
                   f'SQLite {sqlite3.sqlite_version}), corpus {args.days} days, {len(golden)} questions', '']
            rows, (base_rate, graph_rate, base_tokens, graph_tokens) = h1(tmp, conn, golden)
            v1 = h1_verdict(base_rate, graph_rate, base_tokens, graph_tokens)
            out += ['### H1 answers', '', *rows, '',
                    f'Verdict H1: {v1} (against the stronger grep: answer rate up 25 points '
                    'or tokens down by half)', '']
            out += ['### H2 briefs', '', *h2(tmp, conn, golden), '',
                    'Verdict H2: unmeasured (asks and re-decisions need a live seat; counted unsupported)', '']
            conn.close()
            rows, v3 = h3(args.days, fts)
            out += ['### H3 cost', '', *rows, '',
                    f'Verdict H3: {v3} (build at most 10 s, events.jsonl at most 20 MB, '
                    'index under 50 MB, identical rebuild)', '']
            rows, fraction = h4(tmp, golden)
            v4 = h4_verdict(fraction)
            out += ['### H4 overlap', '', *rows, '',
                    f'Verdict H4: {v4} (supported when the export answers more than half)', '',
                    f'Conclusion: {conclude(v1, v3, v4)}']
    except (OSError, ValueError, KeyError, StopIteration, sqlite3.Error) as exc:
        print(f'memory-graph poc unmeasured: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
