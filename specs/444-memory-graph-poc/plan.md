# Implementation Plan: Memory graph proof of concept

**Branch**: `444-memory-graph-poc` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

A time-boxed spike with throwaway code. Three scripts under `scripts/poc/memory-graph/`
generate a seeded corpus with a golden set, build a SQLite graph from it, and measure four
hypotheses against a simulated grep baseline and a simulated #443 export. One test file
keeps the PoC runnable. The builder runs the 90-day measurement and writes
`docs/specs/2026-10-03-memory-graph-poc.md` with the printed tables, the threats, the
conclusion the pre-registered rule gives and a decision record. Nothing under `cli/`
changes.

## Technical Context

- Python 3.11+, stdlib only: `sqlite3` (FTS5 when the build has it, `LIKE` otherwise),
  `random` (fixed seed 444), `json`, `re`, `time.perf_counter`, `hashlib`, `tempfile`,
  `argparse`. pytest for the test only.
- Record shapes and the graph schema: [data-model.md](data-model.md).
- The PoC imports two things from `cli/wuwei` (run.py puts `<repo>/cli` on `sys.path`,
  built from `Path(__file__)`, never an absolute path):
  - `wuwei.memory.estimated_tokens` for every token count (the product's estimator, so
    the numbers match what SessionStart reports);
  - `wuwei.decision.evaluate` in the test, to prove planted decision records and the
    document's decision record have the real shape.
- The last corpus day is `2026-09-29` (the fixture day in `scripts/headless_e2e.py`);
  the corpus covers the N days ending there.

## Constitution Check

- I (stdlib): the PoC is stdlib; it is not under `cli/` or `adapters/`, so
  `tests/test_stdlib.py` does not scan it, and it imports nothing outside the stdlib
  and `wuwei`.
- II (exits): `run.py` exits 0 after printing, 2 with the reason on `OSError`,
  `ValueError`, `KeyError` or `sqlite3.Error`. An unmeasured hypothesis prints
  `unmeasured` and counts unsupported; it is never shown as supported.
- III and IV: each behaviour has one function and is covered by a test written first
  (tasks.md orders them).
- V (ponytail): three scripts and one test file; no package, no config, no CLI command,
  no `path` query, no live seat runner. Shortcuts carry `ponytail:` comments (grep cap,
  conservative token model, simulated export).
- VII (security): no network, no subprocess, no real workspace touched; everything is
  written under a temporary directory and deleted.

## Files

| File | Status | Holds |
|---|---|---|
| `scripts/poc/memory-graph/corpus.py` | new | `LAST_DAY`, `generate(root, days=90, seed=444) -> list[dict]` (writes the corpus, returns the golden set) |
| `scripts/poc/memory-graph/graph.py` | new | `fts_available()`, `build(root, db, fts) -> sqlite3.Connection`, `ask(conn, words, limit=5)`, `around(conn, node, hops=2, types=None)`, `dump_hash(conn)` |
| `scripts/poc/memory-graph/run.py` | new | `grep_baseline(root, words)`, `export(root)`, `h1(...)`, `h2(...)`, `h3(...)`, `h4(...)`, `h1_verdict`, `h3_verdict`, `h4_verdict`, `conclude`, `main(argv=None)` |
| `tests/test_memory_graph_poc.py` | new | the six tests in tasks.md |
| `docs/specs/2026-10-03-memory-graph-poc.md` | new | the spike document |
| `specs/444-memory-graph-poc/` | new | spec-kit artifacts |

The directory name has a hyphen, so the scripts import each other as siblings (`import
corpus`, `import graph`): running `run.py` puts its directory first on `sys.path`. The test
loads `run.py` the way `tests/test_headless_e2e.py:load` loads `scripts/headless_e2e.py`
(`importlib.util.spec_from_file_location` with the directory on `sys.path` while it
executes); reuse that pattern, do not invent another.

## Functions

### corpus.py

`generate(root, days=90, seed=444)` writes `root/.wuwei/` (data-model.md, "Corpus") and
returns the golden set (data-model.md, "Golden set"). One `random.Random(seed)`; files
walked and written in sorted order so the output is byte-identical for the same arguments.
Noise volumes scale with `days / 90` (rounded, at least 1); the 30 planted facts are always
written, spread over the range (planted fact `i` on day index `i * days // 30`, clamped so a
reversal's second decision lands on a later day when `days > 1`). The generator raises
`ValueError` if a planted answer phrase also appears in a noise record (it checks before
returning).

### graph.py

- `fts_available()`: try `create virtual table t using fts5(x)` on a `:memory:`
  connection; `True` or `False`.
- `build(root, db, fts)`: delete `db` if present, create the schema (data-model.md,
  "Graph"), walk the records in sorted path order and run the extractors, insert nodes
  first-sighting-wins, commit, return the open connection. One extractor per record kind
  as small private functions in this file; no registry.
- `ask(conn, words, limit=5)`: FTS5 `MATCH` with the words quoted and joined by `OR`,
  ordered by `bm25(search), id`; fallback ranks by the number of words found with `LIKE`
  in `title || ' ' || excerpt`, then `id`. Returns rows `(id, type, title, path, line,
  excerpt)`.
- `around(conn, node, hops=2, types=None)`: breadth-first over edges in both
  directions, restricted to `types` when given; returns the reached nodes (not the start)
  ordered by `(hop, type, id)` with the same row shape as `ask`.
- `dump_hash(conn)`: `sha256` over `'\n'.join(conn.iterdump())`.

The search mode is a parameter of `build` (and stored in a one-row `meta` table that
`ask` reads), so the test and `--no-fts` force the fallback without monkeypatching.

### run.py

- `grep_baseline(root, words)`: walk every file under `root/.wuwei` in sorted order;
  a line hits when any word occurs in it case-insensitively (the `grep -rni -e w1 -e w2`
  equivalent, done in Python with no subprocess); output lines are `path:line:text`
  (path relative to `root`); files ranked by hit count descending, then path; returns
  `(top5_paths, tokens)` where tokens is `estimated_tokens` of the first 100 output
  lines plus the full text of the top 5 files.
  `# ponytail: 100-line cap stands for a planner narrowing a long grep`.
- Graph cost per question: `estimated_tokens` of the printed hits (one line each:
  `type title path:line excerpt`) plus the full text of the distinct records among the
  top 5 (conservative); the excerpts-only number is kept as the optimistic column.
- `h1(root, conn, golden)`: per question run the baseline and the graph query named by
  its form, time both with `perf_counter`, mark answered when every expected path is in
  the top 5 paths; aggregate per type and in total. Returns the table rows and the
  totals the verdict needs.
- `h2(root, conn, golden)`: the 10 fixture items (the six items of the "reversed"
  questions, then the first four other items in id order that have at least one
  decision); for each, the base brief is the item's `briefs/<item>-builder.md`; the
  subgraph is `around(item, hops=2)` rendered one line per node and cut to
  `max(1, base_lines // 5)` lines; report base tokens, with tokens, ratio, prior
  decisions on the item, decision ids visible without and with, and `unmeasured` for
  asks and re-decisions. Verdict is always `unmeasured`.
- `h3(days)`: `corpus.generate` into a fresh temporary directory with `4 * days`; time
  `graph.build` once; record the index file size, the largest `events.jsonl`, node and
  edge counts; build again into a second file and compare `dump_hash`.
- `export(root)`: the simulated #443 export (data-model.md, "Export").
- `h4(root, golden)`: per type and in total, the fraction of questions whose answer
  phrase occurs (case-insensitive) in `export(root)`.
- `h1_verdict(base_rate, graph_rate, base_tokens, graph_tokens)`: `'supported'` when
  `graph_rate - base_rate >= 25` (percentage points) or `graph_tokens <= base_tokens / 2`,
  else `'unsupported'`.
- `h3_verdict(seconds, largest_events_bytes, index_bytes, identical)`: `'supported'`
  when `seconds <= 10`, `largest_events_bytes <= 20 * 2**20`, `index_bytes < 50 * 2**20`
  and `identical`, else `'unsupported'`.
- `h4_verdict(fraction)`: `'supported'` (the export already answers most questions) when
  `fraction > 0.5`, else `'unsupported'`.
- `conclude(h1, h3, h4)`: `'drop'` when `h1 != 'supported'`; `'park'` when
  `h3 != 'supported'` or `h4 == 'supported'`; else `'build'`. H2 is not an input.
- `main(argv=None)`: `--days N` (default 90), `--no-fts`. Generates into a temporary
  directory, builds, prints `Search: fts5|like (Python x.y.z, SQLite a.b.c)`, then the
  four tables as Markdown (`### H1 answers` and so on), each followed by
  `Verdict H<n>: <verdict> (<threshold in words>)`, then `Conclusion: <build|park|drop>`.
  Returns 0. On the errors listed under Constitution Check prints
  `memory-graph poc unmeasured: <reason>` to stderr and returns 2, with no verdict lines.

## Measurement notes for the document

- Rerun command: `python3 scripts/poc/memory-graph/run.py` (and `--no-fts` for the
  fallback numbers if they differ).
- Threats to validity the document must list: synthetic corpus and golden set written by
  the graph's author; the three synthetic record extensions and which question types use
  them (touched, revert); simulated baseline (grep in Python, a 100-line cap, a planner
  who would refine); `wuwei why` not measured although it serves the reversed type; the
  simulated export; H2 behaviour unmeasured; one machine's wall times.
- What build would be, if concluded: `ask` (and `around` only if the around-type rows
  beat the baseline), built by `consolidate` within the 5.13 budget, plus recording PR
  files, reverts and incidents as records; the brief integration only if H2 is supported.
  Anything not supported by a table is left out and named.

## Must not change

Everything outside the files table: `cli/`, `adapters/`, `hooks/`, `skills/`, `agents/`,
`charters/`, `templates/`, `scripts/*.py`, `docs/site/`, `README.md`, the design spec and
the constitution. No new dependency, no `pyproject.toml` change.

## Builder's job

Follow tasks.md in order: the corpus test and the corpus first, then the graph, then the
runner, then the document from a real 90-day run. Paste the tables as printed; do not
round or edit numbers. If the rule says build, write the follow-up issue text in the
document; the builder files nothing.
