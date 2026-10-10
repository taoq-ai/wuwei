# Implementation Plan: generated and data lines never count, and an analysis-only change gets one reviewer

**Branch**: `657-generated-lines` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One new function at the shared spot, `merge.uncounted`, beside `merge.matched` and the #615
size rule it replaces. `dispatch.tier` and `merge.check` both call it, so the tier and the
size cap count the same lines. `dispatch.tier` uses its result three ways: the line count,
the binary rule, and the existing #622 docs-only decision (`_docs_role`), which now also
accepts notebooks and data files. One config key, `repos.gates.data_paths`. No new module,
event kind, state key, port operation or adapter allowlist entry.

## Technical Context

Python 3.11+ stdlib only (constitution I); pytest dev-only. `.gitattributes` is read with
`Path.read_text` from the configured repository checkout, no git subprocess.

## Constitution Check

- I stdlib: nothing new imported (`re` and `Path` are already in `merge.py`).
- II exits: an unreadable `.gitattributes` raises `OSError` or `UnicodeDecodeError`; inside
  `tier()` the existing `except` records `diff unmeasured: ...` at standard, inside `check()`
  the existing `ERRORS` handler exits 2. A missing file excludes nothing.
- III one behaviour one function: what counts is decided once, in `merge.uncounted`.
- IV test first: tasks.md orders every test before its code.
- V simplicity: a fixed lockfile list, a fixed data suffix list and a fixed 200-line
  threshold, one `ponytail:` comment naming the heuristic; no code-paths setting.
- VII security: a generated file never makes a diff docs-only; trust, never-auto and
  FULL-pattern rules still run on every path; a diff that edits `.gitattributes` gets no
  linguist exclusion. Invariants I34 (widened) and I42 (new) hold it.
- Workflow: a changed decision rule adds its 9.2 row and `tests/test_invariants.py` check.

## Design

### cli/wuwei/merge.py

Beside `matched()`:

```python
# #657: what never counts toward the tier or max_changed_lines. ponytail: lockfiles by name and
# data by suffix over DATA_LINES changed lines; linguist-generated globs from the root
# .gitattributes are matched like every path glob here, not with full gitattributes semantics.
LOCKFILES = ('*.lock', 'bun.lock*', 'package-lock.json', 'npm-shrinkwrap.json', 'pnpm-lock.yaml', 'go.sum')
DATA_SUFFIXES = ('*.json', '*.jsonl', '*.csv', '*.parquet')
DATA_LINES = 200


def uncounted(root, repo, files):
    """#657: {path: 'data' | 'generated'} for each changed file whose every named path is data
    (repos.gates.data_paths, or a data suffix with a binary change or over DATA_LINES lines)
    or generated (a lockfile, repos.merge.size_exclude, a linguist-generated glob in the
    repository's root .gitattributes, ignored when the diff changes that file)."""
```

Body, in this order:

1. `named = [(f['path'], f.get('previous_path')) for f in files]` (diff stat rows have no
   `previous_path`; host rows do).
2. linguist globs: empty when any `named` pair contains `'.gitattributes'`; else read
   `root / Path(repo['path']).expanduser() / '.gitattributes'` (`FileNotFoundError` gives
   `''`, any other error propagates). For each line split on whitespace, skip blank and `#`
   lines, keep `parts[0]` when `{'linguist-generated', 'linguist-generated=true'}` meets
   `parts[1:]`, with a leading `/` or `**/` removed.
3. `data = tuple(p + '*' if p.endswith('/') else p for p in repo['gates']['data_paths'])`;
   `generated = (*LOCKFILES, *repo['merge']['size_exclude'], *linguist)`.
4. Per file: `big = additions is None or deletions is None or additions + deletions >
   DATA_LINES`; the kind of each non-None named path is `'data'` when it matches `data`, or
   `big` and it matches `DATA_SUFFIXES`; else `'generated'` when it matches `generated`;
   else `None`. The file is in the result when no kind is `None`: `'data'` when every kind is
   data, else `'generated'`.

`check()` lines 269-273 become:

```python
# #615, #657: a file counts toward the size rule unless merge.uncounted names it.
skip = uncounted(root, settings, files)
changed = sum(file['additions'] + file['deletions'] for file in files if file['path'] not in skip)
excluded = additions + deletions - changed
require(granted or changed <= policy['max_changed_lines'],
        f'diff exceeds max changed lines: {changed} count over {policy["max_changed_lines"]}'
        + (f' ({excluded} generated or data excluded)' if excluded else ''))
```

(`additions` and `deletions` are the totals already summed and checked above.) Nothing else
in `check()` changes; the never-auto loop still runs on every path before this.

### cli/wuwei/dispatch.py

- `DOC_SUFFIXES = ('.md', '.rst', '.ipynb')` with the comment extended: `#657: a notebook is
  analysis`.
- `_docs_role(paths, data=())`: a path qualifies when `path in data`, or today's document test
  holds; the `AGENT_DOCS` exclusion and the role choice (`SPEC_DOCS` gives `quality`, else
  `goal`) are unchanged and apply to data paths too.
- `tier()`, in the measured `try`: after `_changes`, `skip = merge.uncounted(root, repo,
  changes)` (inside the `try`, so an unreadable `.gitattributes` is `diff unmeasured`), then
  `total` as today and `excluded = sum((c['additions'] or 0) + (c['deletions'] or 0) for c in
  changes if c['path'] in skip)`.
- the binary rule: `if (... is None or ... is None) and path not in skip:`.
- `docs = _docs_role([...paths...], [p for p, kind in skip.items() if kind == 'data']) if
  computed == 'light' else None`.
- the size rule:

```python
counted = total - excluded
lines = f'{total} changed lines' + (
    f', {excluded} generated or data excluded, {counted} count,' if excluded else '')
if counted > gates['light_max_lines'] and not docs:
    rise('standard', f'{lines} over light_max_lines {gates["light_max_lines"]}')
elif not docs:
    reasons.append(f'{lines} within light_max_lines {gates["light_max_lines"]}')
```

The `elif` drops `computed == 'light'` (spec FR-007), so a standard or full item also shows
its count. With nothing excluded the text is byte-identical to today's.

### cli/wuwei/workspace.py

`SCHEMA['repos'][0]['gates']` gains `"data_paths": [(str, None)]` with a `#657` comment, the
same shape as `size_exclude` (default empty list).

### Documents

- `docs/site/configuration.md`: a `repos.gates.data_paths` row after `trust_paths`; the
  `repos.merge.size_exclude` row says it also stops counting toward the tier; the
  `repos.gates.light_max_lines` row says generated and data lines do not count and the
  reason names the totals.
- `docs/site/concepts.md` (Review tiers): one paragraph: what never counts, the reason text,
  and that a diff of documents, notebooks and data gets the docs-only reviewer.
- `docs/specs/2026-09-24-wuwei-design.md` 9.2: widen the I34 row text to documents,
  notebooks and data; add row I42 (below).

### Invariants (`tests/test_invariants.py`)

- `i34`: add one plain case whose changes are the document plus
  `{'path': 'study/results/scores.csv', 'additions': 600, 'deletions': 0}`, expecting
  `['goal']`; the raising cases are unchanged.
- `i42` (new, `READS['I42'] = ()`, memoized like `i34`, stubbing `dispatch._changes` the same
  way, floor `light`), with `dist/* linguist-generated` written to the fixture checkout's
  `.gitattributes`:
  - `[src/app.py 80, pilot/manifest.json 4800]` and `[src/app.py 80, dist/app.js 4800]`:
    `tier()` records light with a reason ending `80 count, within light_max_lines 100`, and
    `merge.uncounted` on the same rows names exactly the large file;
  - `[src/app.py 80, .gitattributes 1, dist/app.js 4800]`: `merge.uncounted` returns `{}`
    and `tier()` is raised by size.
  The checkout is `rules.root / config['repos'][0]['path']`; remove the `.gitattributes` in a
  `finally` so no other invariant reads it. Row text: "Generated and data lines never count toward the tier or the size cap, and both
  read the same count from `merge.uncounted`; a diff that changes `.gitattributes` gets no
  linguist-generated exclusion".

## What must not change

- Every rule that raises the tier for a path (trust, never-auto, FULL-pattern), for a lead
  flag, track FULL, a `full` floor and pace careful; their reason texts.
- The docs-only reason text and roles, `gate_set`, the brief and report code.
- The never-auto refusal in `merge.check`, which runs on every path including uncounted ones.
- `#615` semantics: a rename counts unless both of its paths are uncounted.
- The reason text for a diff with nothing excluded.

## Tests that change on purpose

- `tests/test_merge.py::test_size_exclude_counts_only_the_files_it_does_not_match`: cases 2
  and 4 use `results/run.json`/`src/run.json` at 1000 lines, which are now data. Move both to
  `.txt` (`results/run.txt`, `src/run.txt` from `results/run.txt`, setting
  `size_exclude = ["results/*.txt"]` for case 4) so they keep testing #615.

## Project Structure

Files changed: `cli/wuwei/merge.py`, `cli/wuwei/dispatch.py`, `cli/wuwei/workspace.py`,
`tests/test_merge.py`, `tests/test_dispatch.py`, `tests/test_invariants.py`,
`docs/site/configuration.md`, `docs/site/concepts.md`, `docs/specs/2026-09-24-wuwei-design.md`.
