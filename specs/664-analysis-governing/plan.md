# Implementation Plan: the analysis step checks each assumption against the governing document

**Branch**: `664-analysis-governing` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

One shared spot, `cli/wuwei/specmode.py`, learns the item's governing reference
(`governing`), the table check (`governed`) and the builder brief block (`brief_block`).
Three callers use it: `brief.write` appends the block to a builder brief,
`specmode.brief_line` names the reference on a gate brief, and `wuwei spec analysis`
(`commands/spec.py write`) refuses a governed report without the table. `plan.py` lets the
lead's candidate carry `governed_by` and copies it like `tier`. Charters, agents and docs
say the rest.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. No new import at hook time: `specmode` is
imported by the hooks, so the new functions use only `re` and `Path` (already imported) and
import `docs._sections` lazily inside `governed`, which only `wuwei spec analysis` calls.

## Constitution Check

- I (stdlib): `re` and `pathlib` only.
- II (exits, fail closed): a reference that does not resolve raises `ValueError` with the
  reason; `wuwei spec analysis` and `wuwei brief` already map `ValueError` to exit 2.
- III (one behaviour, one function): resolve (`governing`), check (`governed`), render
  (`brief_block`); each has its own test.
- IV (test first): every behaviour has its test task before its implementation task.
- V (ponytail): no new command, no config, no setter; `governed_by` rides the existing
  candidate-to-item copy; the report section reader is the existing `docs._sections`.
- VII (security): the reference is resolved inside the worktree and refused when absolute
  or escaping it, as `commands/spec.py` already does for the spec directory. The field only
  adds a requirement, so a seat-written `Governing:` line cannot lower anything; the plan
  item's value wins over the spec line.
- Design spec: 5.10 gains a "Governing document (#664)" paragraph (owner issue amends it, as
  #614 and #633 did for theirs).

## Design

### `cli/wuwei/specmode.py` (the shared spot)

Constants next to `BOX`:

```python
# #664: the item's governing document: governed_by on the plan item, else this line in spec.md.
GOVERNING = re.compile(r'^Governing:[ \t]*(\S[^\n]*?)[ \t]*$', re.M)
VERDICTS = ('agrees', 'conflicts', 'not covered')
```

`governing(tree, row, location=None)` returns `None` when the item names no governing
document, else `(reference, first, last, text)` with 1-based inclusive line numbers.

- `reference = row.get('governed_by')`; when falsy and `location` is not None and
  `tree/location/spec.md` is a file, the first `GOVERNING` match in it.
- `name, _, heading = reference.partition('#')`. Refuse (`ValueError`) when `name` is empty
  or absolute, when `(tree / name).resolve()` is not relative to `Path(tree).resolve()`, or
  when it is not a file: `governing document {reference} is not a file in the worktree`.
- Without a heading: the whole file. With one: the first line matching
  `^(#{1,6})[ \t]+(.*?)[ \t]*$` whose text equals `heading` or starts with `heading + ' '`;
  the section ends before the next heading line with the same or fewer `#`, or at the end of
  the file. No match: `ValueError(f'no heading {heading} in {name}')`.
  `# ponytail: a '#' line inside a fenced code block reads as a heading; parse fences if a
  governing document ever has one.`
- Read with `_read` (UTF-8); `OSError` and `UnicodeError` propagate (callers map them to
  exit 2).

`governed(report, spec_text)` returns `None` when the report has the table, else the gap:

- `table = _sections(report, ('Governing',))` and
  `assumptions = _sections(spec_text, ('Assumptions',))`, with
  `from wuwei.docs import _sections` inside the function.
- A row is a line starting with `|` whose cells (split as `_clean` does) number at least
  three, whose second cell lowercased is in `VERDICTS` and whose third cell matches
  `\S+:\d+`. The header and separator rows never match.
- `needed = max(1, len(re.findall(r'^[-*] ', assumptions, re.M)))`.
- Gap texts: no section: `the report has no ## Governing table`; too few rows:
  `the ## Governing table has {rows} valid rows for {needed} assumptions`.

`brief_block(config, item, row, tree)` returns `''` unless `mode(config) != 'off'`,
`config['spec']['engine'] == 'speckit'`, `skip(config, row)` is None and
`governing(tree, row)` is not None (at brief time the spec may not exist, so only the row
counts). Otherwise:

```text

## Governing document

{reference} (lines {first}-{last}) governs this item. Give the text below to /speckit.analyze
with the spec, and end the report with a ## Governing table: | Assumption | Verdict | Line |,
one row per assumption in spec.md, the verdict agrees, conflicts or not covered, the line
cited as <path>:<n>. bin/wuwei spec analysis refuses a report without it.

{text}
```

`brief_line`, gate branch only: when `governing(tree, row, location)` is not None, append
`; governed by {reference} (lines {first}-{last}): check the ## Governing table in
analysis.md` to the `Spec: {engine} artifacts: {location}` text (spec-kit only; other
engines keep today's line). The builder branch does not change: the block carries the
instruction.

### `cli/wuwei/brief.py` `write`

Where the body is joined (`text = '\n'.join(header) + '\n\n' + body + '\n'`), append
`specmode.brief_block(config, item, current, tree)` when `role == 'builder'` and `tree` is
set. The block goes after the body, never in the header: the header is cut at the first
blank line by `launch_prompt` (line 19) and by the second-opinion rewrite in
`dispatch.py:745`, and the section text has blank lines. Computing it before the state
lock's `update` keeps the refusal (bad reference) before anything is written.

### `cli/wuwei/commands/spec.py` `write`

After the empty-report check (line 51), before `atomic_write`:

```python
found = specmode.governing(tree, items[name], location)
if found:
    gap = specmode.governed(text, (directory / 'spec.md').read_text(encoding='utf-8'))
    if gap:
        reference, first, last, _ = found
        raise ValueError(f'{name} is governed by {reference} (lines {first}-{last}) and {gap}; '
                         'add one row per assumption: | <assumption> | agrees, conflicts or '
                         'not covered | <path>:<line> |, then run this again')
```

`run_analysis` already prints `wuwei spec analysis: <reason>` and returns 2 for `ValueError`,
`OSError` and `UnicodeError`.

### `cli/wuwei/plan.py`

- `_proposal`, next to the `paths` check (line 101): when `'governed_by' in item` and it is
  not a non-empty string, `ValueError(f'{name}: governed_by must be a path or path#heading;
  {PLAN_JSON}')`.
- `approve` (line 386) and `add` (line 489): the copied keys become `('tier',
  'governed_by')`.

### Charters and agents

- `charters/builder.md` step 1: after "Read the governing requirement ...", add: name a
  governing document in `spec.md` as `Governing: <path>#<heading>`; when the brief or the
  spec names one, give its text to `/speckit.analyze` and end the report with a
  `## Governing` table, one row per assumption with `agrees`, `conflicts` or `not covered`
  and the cited `<path>:<line>`; `wuwei spec analysis` refuses the report without it.
- `charters/sentinel-goal.md` step 1: when the brief's `Spec:` line names a governing
  document, check each row of the `## Governing` table in `analysis.md` against the cited
  line; a `conflicts` row, a wrong citation or an assumption without a row is a violated
  requirement (`blocks: yes`) unless a recorded decision rules on it.
- `charters/lead.md` step 4 (candidate fields, next to `paths`): when a document section
  governs the item (a pre-registration, a design section), name it as `governed_by`,
  `<path>` or `<path>#<heading>` relative to the repository.
- Run `bin/wuwei agents build`; `agents/builder.md`, `agents/sentinel-goal.md`,
  `agents/lead.md` change. Each new charter sentence must be unique across charters
  (`test_charter_sentences_have_one_home`) and use none of the banned or blocking patterns.

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 5.10, after the spec-kit step table: a
  "Governing document (owner, 2026-10-10, #664)" paragraph stating FR-001 to FR-006 in
  prose.
- `docs/site/reference.md` line 71 (`bin/wuwei spec`): add "a governed item's report without
  the `## Governing` table" to the exit-2 list.
- `docs/site/configuration.md` line 119: one sentence on the governed table.

## Reused, not re-implemented

`docs._sections` (report and spec sections), `_clean`'s cell split, `specmode._read`,
`specmode._location` (already called by `commands/spec.write`), the worktree containment
check pattern of `commands/spec.write`, the candidate-to-item key copy in `approve` and
`add`, `run_analysis`'s exit mapping, `bin/wuwei agents build`.

## Must not change

- `STEPS`, `_clean`, `status`, `check`, `record`, `named`: the hooks and the build loop read
  the same artifacts and rules as today.
- The builder `Spec:` line and every brief of an ungoverned item, byte for byte.
- `wuwei spec analysis` for an ungoverned item: same refusals, same output.
- OpenSpec and superpowers paths.
- `state.py` reserved keys: item fields are producer-owned by default, so `governed_by`
  needs no new entry to be protected.

## Files

| File | Change |
|---|---|
| `cli/wuwei/specmode.py` | `GOVERNING`, `VERDICTS`, `governing`, `governed`, `brief_block`; gate branch of `brief_line` |
| `cli/wuwei/brief.py` | `write` appends `specmode.brief_block` to builder briefs |
| `cli/wuwei/commands/spec.py` | `write` refuses a governed report without the table |
| `cli/wuwei/plan.py` | `_proposal` validates `governed_by`; `approve` and `add` copy it |
| `charters/builder.md`, `charters/sentinel-goal.md`, `charters/lead.md` | one sentence each |
| `agents/builder.md`, `agents/sentinel-goal.md`, `agents/lead.md` | regenerated |
| `docs/specs/2026-09-24-wuwei-design.md` | 5.10 paragraph |
| `docs/site/reference.md`, `docs/site/configuration.md` | the refusal and the table |
| `tests/test_spec_mode.py` | `governing`, `governed`, gate line, `spec analysis` refusals and acceptance |
| `tests/test_brief.py` | builder brief block present, absent, and refused on a bad reference |
| `tests/test_plan.py` | `governed_by` validated and copied |
| `tests/test_charters.py` | the three charter anchors |
