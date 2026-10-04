# Implementation Plan: config set writes list and table keys in any config.toml layout

**Branch**: `494-config-writer` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

## Summary

The writer every config edit routes through (`calibrate.apply`, fed by `calibrate.settle`)
serializes with `json.dumps` and finds tables with a narrow header regex, so lists of tables
and tables do not parse, multi-line values are refused, and odd headers misplace keys (spec,
Root cause). Fix it once at that shared spot: a small stdlib line model plus a TOML
serializer in one new module, `cli/wuwei/configtext.py`; `calibrate.apply` places through it
and keeps its post-write proof; `calibrate.settle` stops refusing spans; `commands/setup.py`
gains the one entry point `write_value(raw, key, value, mode)` for `config set` and #492, and a
typed refusal for a value that is not TOML; `config check` reports a key set in two tables.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only (`tomllib`, `re`, `json`).
**Testing**: pytest, in process; `tmp_path` workspaces through the `workspace` fixture and
`config_set` helper of `tests/test_setup.py`.
**Constraints**: no TOML library; no new import on the hook path (`configtext` is imported only
by `calibrate`, `commands/setup.py` and, inside `run`, `commands/config.py`; heartbeat imports
`commands/config`, so its import of `configtext` is local);
`CONFIG_CACHE_VERSION` unchanged (the parsed shape does not change).

## Constitution Check

- I Stdlib only: yes. II Exits: `config set` keeps 0/1/2 through `setup._edit`; `config check`
  adds a finding (1). III One behaviour, one function: placement lives only in
  `configtext.place`; every caller reaches it through `calibrate.apply`. IV Test first:
  tasks.md orders every test before its code. V Ponytail: one new module because `calibrate`
  cannot import `commands/setup` (setup imports calibrate) and the line model is not
  calibration; no class, no config, no option beyond the issue's `mode`. VII: the post-write
  proof (parse, every other value unchanged, target equal, schema valid) stays and now names
  the key.

## Changes

### `cli/wuwei/configtext.py` (new, FR-001 to FR-005, FR-009, FR-010)

Module docstring: the config.toml line model and TOML writer (#494); stdlib only.

- Key grammar, one regex each, reused for headers and key lines:
  `PART = r'\s*(?:[A-Za-z0-9_-]+|"(?:[^"\\\n]|\\.)*"|\'[^\'\n]*\')\s*'`,
  `KEYS = rf'{PART}(?:\.{PART})*'`. A header line fullmatches
  `\s*(\[\[?)(KEYS)\]\]?\s*(?:#.*)?` (line ending stripped first); a key line matches
  `\s*(KEYS)=`. `_parts(text)` splits a KEYS match on unquoted dots and decodes a quoted part
  with `tomllib.loads('k = ' + part)['k']`, so `[ outward.max_length ]`, `[owner."verbosity"]`
  and `"pat@example.test" = ...` all resolve.
- `entries(raw)` returns `(lines, items)`: `lines = raw.splitlines(keepends=True)`; `items` is a
  list of `(kind, path, start, end)` with `kind` in `'table'`, `'array'`, `'key'`, line indexes
  `[start, end)`. Walk the lines once; a line inside a key's span is never classified. A key's
  span ends at the first line where `tomllib.loads(''.join(lines[start:j]))` parses
  (`ponytail:` quadratic in a value's line count; config values are short). Paths carry
  array-of-tables indexes: keep `counts = {names: index}`; an `[[a.b]]` header increments
  `counts[('a', 'b')]` (from 0); resolving any header's names appends the current index after
  every prefix found in `counts`, so `[[repos]]` is `('repos', 0)` and a following
  `[repos.merge]` is `('repos', 0, 'merge')`. A key's path is its table's resolved path plus its
  own parts. The root table is `()` with no header line.
- `dumps(value)`: `str` is `json.dumps(value, ensure_ascii=False)` with `\x7f` written as
  `\u007f` (TOML basic strings forbid a raw DEL; `ensure_ascii=False` avoids surrogate pairs);
  `bool` is `true`/`false` (checked before `int`); `int` is `str`; `float` is `repr` (`inf`,
  `nan` are TOML); `dict` is `{k = v, ...}` (`{}` when empty) with `_key(k)` = `k` when it
  fullmatches `[A-Za-z0-9_-]+`, else `json.dumps(k, ensure_ascii=False)`; `list` is `[]` when
  empty, `[a, b]` on one line when every item is a scalar, else `'[\n' + ''.join(f'  {dumps(i)},\n') + ']'`.
  Any other type raises `ValueError` naming the type and "pass a string, number, boolean, list
  or table". The result uses `\n`; `place` converts.
- `place(raw, path, key, value, comment=None)` returns the new text. `target = (*path, key)`,
  `nl = '\r\n' if '\r\n' in raw else '\n'`. First match wins:
  1. a `'key'` item with path `target`: replace `lines[start:end]` with
     `f'{indent}{lhs} = {dumps(value)}'` where `lhs` is the original key text (dotted keys keep
     their form) and `indent` the original leading whitespace;
  2. a `'key'` item whose path is a proper prefix of `target` (an inline table or array): load
     its value (`tomllib.loads` of the span, walked by its own parts), set the remaining path
     inside it (an int part indexes a list; past the end raises the index refusal below), and
     rewrite that span as in 1;
  3. `'array'` items with path prefix `target` (their names equal `target` without indexes):
     `value` must be a list of dicts, else fall through to the post-write refusal; remove every
     block (from each `[[...]]` header to the next header that is not inside that array item)
     and write, at the first block's start, one `[[header]]` block per item, `k = dumps(v)` one
     per line;
  4. a `'table'` item with path `target` and `value` a dict: remove that table's direct key
     spans and write `k = dumps(v)` one per line after its header;
  5. otherwise insert `f'{_key(key)} = {dumps(value)}'` (preceded by `comment` when given) into
     the table `path`: after the end of its last direct `'key'` item, or right after its header
     when it has none (for the root with none, at line 0). When the table `path` has no header
     and is not the root: an int part in `path` whose array item does not exist raises
     `ValueError(f'{dotted}: no entry {i} in {array}; add it first (bin/wuwei config add-repo for a repository)')`;
     otherwise find the nearest existing ancestor header `A` (root when none), and after the
     end of the last header whose path starts with `A` (end of file when `A` is the root) write
     a blank line and one `[header]` line for each missing table from `A` down to `path`,
     parents first (header text is the names without indexes, each through `_key`), then the
     key line.
  Before any insertion, a last line without a line ending gets `nl`. Every written line ends
  with `nl`. `place` does not verify; `calibrate.apply` does.
- `declared(path)`: the `workspace.SCHEMA` node at `path` (an int part steps into a list
  schema's item, a missing name steps into `'*'`), or `None`.
- `describe(node)` returns `(kind, example)` for the refusal: `kind` is `a string`, `an
  integer`, `a number`, `true or false`, `a list of strings`, `a list of integers`, `a list of
  tables`, `a table`; `example` is `dumps(sample(node))` where `sample` gives the first allowed
  value of a constrained string, else the default when not `None`, else `"text"`, `1`, `0.5`,
  `true`; a list gives `[sample(item)]`; a dict gives its first two named keys sampled, or
  `{"name" = sample('*')}` for a wildcard table. For `outward.tool_patterns` that is
  `[{pattern = "text", channel = "text"}]`.
- `misplaced(raw)` returns report lines. For every `'key'` item, `table = path[:-1]`,
  `name = path[-1]`; a placement is *declared* when the schema dict at `table` (via `declared`)
  has `name` as a literal key. Group items by `name`; for a name with at least one declared and
  at least one undeclared placement, emit for each undeclared one:
  `f'{name} is set in [{good}] (line {a}) and [{bad}] (line {b}); [{bad}] does not take it, remove line {b}'`
  (tables printed dotted without indexes; line numbers 1-based from `start`).

### `cli/wuwei/calibrate.py` (FR-006, FR-011)

- `LAYOUT` becomes `'cannot place this value in this config.toml layout; edit by hand, then run bin/wuwei config check'`
  (keeps `edit by hand`, which `tests/test_docs.py` and `tests/test_calibrate.py` match).
- `apply(raw, additions)`: drop the section, serialization and replacement code
  (`calibrate.py:526-554`); for each addition `text = configtext.place(text, path, key, value,
  COMMENT if path not in commented else None)`, add `path` to `commented` only when the key was
  absent before, and after each placement `tomllib.loads(text)` or raise
  `ValueError(f'{dotted}: {LAYOUT}')`. Keep the closing proof unchanged in substance: `before`
  with every addition's present key popped (`(_table(before, path) or {}).pop(key, None)` for
  every addition, replacing the `replaced` list), `_preserves_values(before, parsed)`, each
  target equal, `workspace._validate(parsed, workspace.SCHEMA, (), text)`; a failed proof raises
  `ValueError(f'{dotted}: {LAYOUT}')` with the first failing addition's key.
- `settle(raw, settings)`: a present key that differs is an addition unless its current value
  is a dict and the new one is not (then an edit, as today). Remove the `_assignment` gate and
  the `sections` it needed; delete `_assignment` (no other caller). The deploy keep-rule stays.
- `proposal`, `_labelled`, `_empty_list` and `_table` do not change.

### `cli/wuwei/commands/setup.py` (FR-007, FR-008, FR-009)

- `_parts(key)`: the two key checks now inside `set_value.change` (`KEY` fullmatch, last part
  not an index), returning `[int or str]`; messages unchanged.
- `write_value(raw, key, value, mode='replace')`, docstring "The one config writer entry point
  (#494); #492 passes mode='append' for list keys." Body: `parts = _parts(key)`; `path, name =
  tuple(parts[:-1]), parts[-1]`; `mode` not in `('replace', 'append')` raises
  `ValueError(f'{mode}: unknown mode; use replace or append')`; for `append`, `current =
  (calibrate._table(tomllib.loads(raw), path) or {}).get(name, [])`, a non-list `current` or
  `value` raises `ValueError(f'{key}: append needs a list; use replace')`, and `value =
  [*current, *(v for v in value if v not in current)]`; `return _settle(raw, [(path, name,
  value)])`. Equal values come back as `raw` unchanged (settle skips them, apply returns raw).
- `set_value.change`: `parts = _parts(args.key)`; parse `args.value`; on
  `tomllib.TOMLDecodeError` raise
  `ValueError(f'{args.key}: {args.value!r} is not TOML; {kind} is expected, pass one, for example \'{example}\'')`
  with `kind, example = configtext.describe(configtext.declared(tuple(parts)))`; when
  `declared` is `None`, keep today's "expected one TOML value" text. Then
  `return write_value(raw, args.key, parsed['value'])`. No "the owner" and no "you" in the new
  texts (setup.py is person-facing in `tests/test_reasons.py`).
- `_settle`, `_edit`, `add_repo`, `repo_tables` and the CLI handler name `set_value(args,
  confirm)` do not change.

### `cli/wuwei/commands/config.py` (FR-010)

`run(args)`: `root = workspace.find_workspace()`, `load_config(root, warnings=found)` (same
behaviour as today's no-root call); after `status = CLEAN`, read
`(root / '.wuwei/config.toml').read_text(encoding='utf-8')` and for each
`configtext.misplaced(raw)` line print `wuwei config check: <line>` to stderr and set
`status = FINDINGS`. Nothing else in `run` moves.

### Docs (`docs/site/configuration.md`)

- Line 3: drop "edit the file by hand only for what they refuse, a table or a value that spans
  lines"; say `config set` writes lists and tables and replaces a value that spans lines in
  place, and `config check` names a key set in two tables.
- Line 310: list-of-tables example
  `bin/wuwei config set outward.tool_patterns '[{pattern = "mcp__custom__send", channel = "customer"}]'`;
  keep "a table such as owner.verbosity is set one key at a time" and "a deploy list only grows".
- Line 361 (interview answers): a present key is replaced in place in any layout; only a table
  answered with a single value is listed under "config differs; edit by hand".

### Build notes

- Rules 1 to 3 were built together with rules 4 and 5: the corpus `inline` layout needs rule 2.
- `dumps(value, inline=True)` keeps lists inside an inline table on one line (TOML 1.0) and gives
  `describe` a one-line example.
- `setup._settle` lost its "not a one-line assignment" branch: settle now lists only a table
  answered with a non-table, so that branch was unreachable.

### Tests that change with the new contract

- `tests/test_interview.py::test_settle_turns_other_forms_into_hand_edits`: both forms (a
  multi-line `quiet_hours` and a dotted `merge.auto`) are now replaced in place with
  `edits == []`; rename to `test_settle_replaces_spans_and_dotted_keys`.
- `tests/test_calibrate.py::test_boundary_candidates_and_inline_repos`: the inline
  `repos = [{...}]` now receives `fast_checks` (rule 2) instead of raising.

## What must not change

- `calibrate.proposal` (additive only; a non-empty or multi-line present value stays a hand
  edit), the deploy lists only growing, `COMMENT` once per table on insertion, the post-write
  proof, the digest path (`setup._edit`, `config.offer`), `repo_tables`, `init._sections` and
  its users (`init --upgrade`, `_stamp`, `_retired_mode`), `workspace._key_line`,
  `load_config` and `CONFIG_CACHE_VERSION`.
- Existing texts the suite matches: "No config.toml changes", "declined; nothing written",
  "expected one TOML value", "dotted key", "list index", `a table; set one of its keys`.

## Project Structure

```text
cli/wuwei/configtext.py          new: line model, dumps, place, declared, describe, misplaced
cli/wuwei/calibrate.py           apply places through configtext; settle drops the one-line gate
cli/wuwei/commands/setup.py      write_value entry point, typed not-TOML refusal
cli/wuwei/commands/config.py     config check reports a key set in two tables
docs/site/configuration.md       config set and config check lines
tests/test_config_writer.py      new: corpus, spans, twice, two tables, mode
tests/test_setup.py              not-TOML refusal, owner command end to end
tests/test_config_transition.py  config check prints the two-tables line
tests/test_interview.py          one test now expects in-place replacement
tests/test_calibrate.py          one test now expects inline repos written
```
