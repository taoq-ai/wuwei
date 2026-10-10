# Implementation Plan: config set on a list key replaces the list, and says so; adding to a list is the explicit --add

**Branch**: `673-config-set-replaces` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

Flip the default in the one function `config set` routes a value through (`setup.merged`),
put the old append behind `--add`, and print one `replaced:` or `added:` line from the
shared write frame (`setup._edit`) for the writers that name their keys. Root cause with
file and line: `spec.md`, Root cause.

## Technical Context

Stdlib-only Python 3.11+ runtime; pytest dev-only. Tests run in-process with the existing
fixtures: `workspace`, `Confirm` and `config_set` in `tests/test_setup.py`; `ws`,
`config_card`, `set_from_card`, `paper`, `proposed` in `tests/test_card_confirms.py`.

## Constitution Check

- Test first per behaviour. Pass.
- Stdlib only. Pass.
- Exits unchanged (0, 1, 2); `--add` on a scalar is exit 1 like today's `--replace` refusal.
  Pass.
- #530: no guard, posture or refusal added; one refusal moves from `--replace` to `--add`.
  Pass.
- No guard or decision rule changes: no design 9.2 row. Pass.
- Ponytail: no new module, file, event kind or state key; one argparse flag, one parameter
  rename, one report helper, one extracted one-line predicate. Pass.

## Changes

### 1. The flag (FR-001, FR-002)

`cli/wuwei/commands/config.py`, `register`, the `set` parser: put `--add`
(`action='store_true'`, help: add to the current list or named-entry table instead of
replacing it) and `--replace` (help: the default; writes the value as given) in one
`add_mutually_exclusive_group()`. Update the `value` help if it mentions appending.

### 2. Replace by default (FR-001, FR-002)

`cli/wuwei/commands/setup.py`, `merged(config, parts, value, add=False)` (rename the
`replace` parameter to `add` and invert):

- not `add`: return `[(tuple(parts[:-1]), parts[-1], value)]` for every key kind.
- `add` on a key that is neither a list rule nor a named-entry table: `ValueError`
  `<key>: --add applies to a list or a named-entry table; remove --add`.
- `add` on a list with a list value: the effective items plus the new ones (today's code),
  and `[]` returns `[]` settings, so nothing is written.
- `add` on a named-entry table with a dict value: one setting per entry (today's code).

`set_value`'s `change` passes `getattr(args, 'add', False)` instead of `args.replace`.
`--replace` is read nowhere any more (it is the default).

`cli/wuwei/commands/outbound.py:419`: `setup.merged(config, ['outbound', key], ids, add=True)`
so `outbound learn` keeps adding learned channels.

### 3. The line (FR-003, FR-004)

`cli/wuwei/calibrate.py`: extract the deploy-grow condition of `settle` (line 811) into
`grows(path, current)` returning `path == ('deploy',) and isinstance(current, list)`, and
call it from `settle`. One rule, used by the writer and by the line.

`cli/wuwei/commands/setup.py`, next to `effective`:

```python
def changed(key, before, after, add=False):
    """#673: the line a config write prints for one key, or None when it cannot be read back."""
```

Parts from `key.split('.')` with digits as ints (the `config show` form, no regex, so a
named-entry key never raises), `old = effective(before, parts)`,
`new = effective(after, parts)`; `(KeyError, IndexError, TypeError)` returns None. Verb
`added` when `add or calibrate.grows(tuple(parts[:-1]), old)`, else `replaced`. Returns
`f'{verb}: {key} = {configtext.dumps(new, inline=True)} (was {configtext.dumps(old, inline=True)})'`.

`_edit(label, what, confirm, change, root=None, keys=(), add=False)`: keep the two
`load_config` results it already computes (`before` for `raw`, `after` for `text`); when
`config.offer` returns `CLEAN`, print `changed(key, before, after, add)` for each key whose
line is not None. The early `No config.toml changes` return prints no line.

`card_write`: pass `keys=keys` to `_edit` (signature unchanged). This covers
`config set --from-card`, `calibrate.propose_checks` under mandate and the interview card
answers in `commands/calibrate.py`, with no change in those callers.

`set_value`: the final `_edit('config set', ...)` passes `keys=[args.key]` and
`add=getattr(args, 'add', False)`.

### 4. Docs (FR-005)

- `docs/site/configuration.md:336`: a value replaces the current one on every key kind and
  the output says `replaced: <key> = <value> (was <old>)`; `--add` adds to a list (no
  duplicates, built-in items kept) or adds entries to a named-entry table and says `added`;
  `--replace` is the default; `'[]'` empties a list; a deploy list only grows.
- `docs/site/configuration.md:415` (`outward.tool_patterns` row): `config set` replaces the
  defaults too; `config set --add` adds to them.
- `templates/workspace/config.toml:190`: same wording in the comment.

## What must not change

- `calibrate.settle` behaviour: a deploy list only grows; only the condition is extracted.
- `write_value` and its `mode` (grants use `mode='append'`), `_from_card`, `card_write`'s
  signature, the `config.set` event payload, `config.offer`.
- Output of the `_edit` callers that pass no keys: `grants`, `decide` (standing grant),
  `drafts approve`, `outbound learn`, `setup slack`, `config add-repo`.
- `outbound learn` adds learned channels (`tests/test_outbound_learn.py` unchanged).
- The session and strict refusals in `set_value`; the `protect_state` hook parsing of
  `--from-card`.
