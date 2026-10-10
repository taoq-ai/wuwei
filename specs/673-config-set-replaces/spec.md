# Feature Specification: config set on a list key replaces the list, and says so; adding to a list is the explicit --add

**Feature Branch**: `673-config-set-replaces`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #673: fix(config): config set on a list key replaces the list, and
says so; adding to a list is the explicit --add.

Owner, 2026-10-10 (item 41): `config set repos.1.fast_checks '[...]'` with the whole value
produced the old list plus the new one, with no word that it appended. `config set` on a
list key should replace it, or at least say that it appended.

## Root cause

Reproduced in a scratch workspace with the CLI functions of this worktree: a repository with
`fast_checks = ["make lint", "make test"]`, then
`set_value(Namespace(key='repos.0.fast_checks', value='["pytest -q"]', replace=False))`.
The diff and the file end at `fast_checks = ["make lint", "make test", "pytest -q"]`, and the
only output after the diff is `Applied the change`.

- `cli/wuwei/commands/setup.py:132-137` (`merged`): without `replace`, a non-empty list
  value is added to the effective list (#492, chosen then so one `config set` could not drop
  the built-in items of `outward.tool_patterns` or `outbound.sensitive_keywords`).
- `cli/wuwei/commands/setup.py:226-227` (`set_value`): passes `args.replace`, which is
  false unless the owner typed `--replace` (`cli/wuwei/commands/config.py:35-36`).
- `cli/wuwei/commands/setup.py:46-72` (`_edit`) and `cli/wuwei/commands/config.py`
  (`offer`): the write path prints the diff and `Applied the change`; nothing names the key,
  its new value or what it held before. The card writers (`card_write`, `setup.py:75-82`:
  `config set --from-card`, `calibrate.propose_checks` under mandate at
  `cli/wuwei/calibrate.py:770-772`, interview card answers at
  `cli/wuwei/commands/calibrate.py:153-155`) go through the same `_edit` and print the same.

The card writers already replace (`write_value` and `_settle` write the value as given);
only the host-terminal `config set` appends.

## User Scenarios and Testing

### User Story 1: a list key is replaced and the line says so (Priority: P1)

**Independent Test**: `config set` on a list key with two entries, in a host terminal.

**Acceptance Scenarios**:

1. **Given** `repos.0.fast_checks = ["make lint", "make test"]`, **When** the owner runs
   `config set repos.0.fast_checks '["x"]'` and confirms, **Then** the value is `["x"]` and
   the output has the line
   `replaced: repos.0.fast_checks = ["x"] (was ["make lint", "make test"])`.
2. **Given** the same key and `--replace`, **Then** the result and the line are the same
   (`--replace` is the default's synonym).
3. **Given** a scalar key such as `owner.verbosity.default`, **When** `config set` runs with
   or without `--replace`, **Then** the value is written and the line says
   `replaced: owner.verbosity.default = "standard" (was "brief")`.

### User Story 2: adding to a list is the explicit --add (Priority: P1)

**Independent Test**: `config set --add` twice with the same item.

**Acceptance Scenarios**:

1. **Given** `outbound.work_channels` holding `C01`, **When** the owner runs
   `config set outbound.work_channels '["C1"]' --add`, **Then** the value is the effective
   list plus `C1`, and the line says `added: outbound.work_channels = [...] (was [...])`.
2. **Given** the same command again, **Then** `C1` is not added twice and the output is
   `No config.toml changes`.
3. **Given** `--add` on a named-entry table (`outbound.people`), **Then** the given entries
   are added or replaced and the other entries stay (the #492 behaviour, now behind `--add`).
4. **Given** `--add` on a key that is neither a list nor a named-entry table, **Then** it is
   refused, exit 1, nothing written, and the message names `--add`.
5. **Given** `--add '[]'`, **Then** nothing is written (`No config.toml changes`).

### User Story 3: the card writers print the same line (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a decision card answered `cap = 5`, **When** `config set --from-card D-1`
   writes it, **Then** the output has `replaced: cap = 5 (was <previous>)`.
2. **Given** the fast-checks card taken under mandate by `calibrate`, **Then** its stderr has
   `replaced: repos.0.fast_checks = ["make test"] (was [])`.
3. **Given** an interview answer written from its card (`calibrate --answer` with the card
   answered), **Then** each written key has its `replaced:` line.

### Edge Cases

- A deploy list (`deploy.deny`, `deploy.workflows`) still only grows (`calibrate.settle`,
  unchanged); its line says `added`, with the value actually written, never `replaced`.
- A value equal to the current one: `No config.toml changes`, no line, as today.
- `--add` and `--replace` together: an argparse usage error (exit 2).
- `--from-card` writes the value the card showed, as shown (unchanged); `--add` does not
  apply to it.
- Replacing a list that has built-in defaults (`outward.tool_patterns`,
  `outbound.sensitive_keywords`, `repos.N.merge.never_auto_paths`) drops the built-ins; the
  `(was ...)` part lists them, and `--add` keeps them.
- `outbound learn` keeps adding the learned channels to `outbound.work_channels` and
  `outbound.external_channels` (it calls `merged` with `add=True`).
- A key the line cannot read back after the write prints no line; the write is never failed
  or undone by the report.

## Requirements

### Functional Requirements

- **FR-001**: `config set KEY VALUE` writes VALUE as given on every key kind, list and
  named-entry table included. `--replace` stays accepted on every key as the default's
  synonym (it no longer refuses a scalar key).
- **FR-002**: `config set KEY VALUE --add` on a list adds the items not already in the
  effective list (no duplicates); on a named-entry table it adds or replaces the given
  entries. `--add '[]'` writes nothing. `--add` on any other key is refused (exit 1):
  `<key>: --add applies to a list or a named-entry table; remove --add`. `--add` and
  `--replace` are mutually exclusive.
- **FR-003**: after a confirmed write, every config writer that names its keys prints one
  line per key: `replaced: <key> = <value> (was <old>)`, or `added: ...` under `--add` and
  for a deploy list. `<value>` and `<old>` are the effective values after and before the
  write, in the inline TOML form `config set` takes (`configtext.dumps(..., inline=True)`).
- **FR-004**: `config set` (host terminal), `config set --from-card`, the fast-checks card
  under mandate and the interview card answers print the line through the same function,
  with the same wording. Other `_edit` callers (`grants`, `drafts approve`, `outbound
  learn`, `setup slack`, `config add-repo`) keep their output.
- **FR-005**: `docs/site/configuration.md` (the `config set` paragraph and the
  `outward.tool_patterns` row), the `tool_patterns` comment in
  `templates/workspace/config.toml` and the `config set` argparse help say that a value
  replaces, `--add` adds, and the line printed.

## Success Criteria

- **SC-001**: the issue's two acceptance scenarios pass as tests (US1 scenario 1, US2
  scenarios 1 and 2).
- **SC-002**: the existing tests of the touched modules pass, changed only where they relied
  on the old append default (`tests/test_setup.py`: they pass `add=True`) or on `--replace`
  refusing a scalar.
- **SC-003**: `tests/test_outbound_learn.py` passes unchanged (learned channels still add).

## Assumptions

- No orchestrator notes file exists for #673; the issue text is the brief. The reproduction
  used a scratch workspace with `repos.0.fast_checks`, not a named dry-run workspace.
- The owner's item reverses the #492 default deliberately. Dropping built-in list items on a
  replace is no longer silent: the `(was ...)` part prints them, and `--add` is the way to
  keep them. No new refusal or warning is added (#530).
- The line is printed after `Applied the change`, not in the digest the owner confirms: the
  diff already shows the change before confirmation, and the line reports what was written.
- "Merges a table" in the issue is the existing named-entry table behaviour of `merged`
  (`outbound.people`, `outward.servers`); a fixed table such as `owner.verbosity` is still
  set one key at a time.
- The card writers already replace; the item changes only their wording, through the same
  `_edit` report. `card_write`'s signature is unchanged; it forwards its `keys`.
- Under `calibrate`'s mandate path stdout is redirected to stderr (widget JSON on stdout);
  the line follows it there.
- No guard or decision rule changes, so no design 9.2 row (constitution, Workflow).

## Deferred

- Item 42 of the same owner message (wakes that repeat known events and fire on
  `updated_at`) is a separate issue, not part of #673.
