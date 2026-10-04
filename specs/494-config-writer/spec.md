# Feature Specification: config set writes list and table keys in any config.toml layout

**Feature Branch**: `494-config-writer`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #494, "fix(config): config set writes list and table keys correctly in
any config.toml layout (subtables after the section, inline tables, arrays of tables, missing
section) and round-trips the rest of the file". Owner, 2026-10-04, on 0.15.0, from the day's
report: "`config set` can't place list or table keys in this file's layout." The file was
written by setup and the interview; `config set outward.tool_patterns '[...]'` and the
table-valued keys (`outbound.people`) could not be placed.

## Root cause (read and reproduced on main, 6b82f7b, read-only)

Reproduction: `commands/setup._settle` was called in process on
`templates/workspace/config.toml` (the file setup writes, plus `[[repos]]` tables) and on small
layouts. The notes name no dry-run workspace; the evidence is the owner's words and these runs.

1. **The serializer writes JSON, not TOML** (the owner's failure). `calibrate.apply`
   (`cli/wuwei/calibrate.py:529-531`) writes a list with `json.dumps` and a table as
   `{k = json.dumps(v)}` with bare keys. `outward.tool_patterns = [{pattern = "x", channel =
   "slack"}]` becomes `tool_patterns = [{"pattern": "x", "channel": "slack"}]`, and
   `outbound.people = {"slack:U1" = {email = "a@example.test"}}` becomes
   `people = {slack:U1 = {"email": "a@example.test"}}`. Neither parses
   (`Expected '=' after a key`), the post-write check at `calibrate.py:555-558` raises
   `LAYOUT`, and the owner reads "cannot place calibration keys in this config.toml layout".
   `json.dumps` also escapes a non-BMP character as a surrogate pair, which TOML rejects, so
   `owner.name` with such a character fails the same way.
2. **A present value that spans lines is a hand edit.** `calibrate.settle`
   (`calibrate.py:663`) replaces a key only when one line holds the whole assignment
   (`_assignment`, `calibrate.py:442-449`); a multi-line array, a dotted key
   (`merge.auto = false`), a key inside an inline table (`rotate_after = { turns = 200 }`)
   and an array-of-tables list (`[[outward.tool_patterns]]`) all fall to `edits`, and
   `setup._settle` (`cli/wuwei/commands/setup.py:81`) refuses "not a one-line assignment".
3. **Headers are found by a narrow regex.** `commands/init._sections`
   (`cli/wuwei/commands/init.py:191-197`) recognises only `[A-Za-z_.]+`. A header with
   spaces (`[ outward.max_length ]`), quotes (`[owner."verbosity"]`) or digits and dashes is
   read as a line of the table above it, so a new `[outward]` key is appended inside
   `[outward.max_length]`; the post-write check catches it and refuses with `LAYOUT`. With
   plain headers (the template) placement is already right: a new `[outward]` key lands
   before `[outward.max_length]`.
4. **Line endings.** A CRLF file gets LF lines inserted (`calibrate.py:531`), so the result
   mixes endings.
5. **A value that is not TOML** reaches `tomllib.loads` in `setup.set_value`
   (`setup.py:93`) and the owner reads the decoder's text (`Invalid value (at line 1, column
   9)`) with no type and no example.

Not reproduced: a missing table is created today (`[telemetry.otlp]`, `[decisions.cruise]`,
`[repos.shepherd]` after its repository). The new writer keeps that and also writes missing
parent headers, as the issue asks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A list or table value lands in the owner's file (Priority: P1)

The owner runs `bin/wuwei config set <key> <value>` with a list of tables, a table or a list,
in the file setup and the interview wrote, and the value lands under its own table, written as
TOML that reads back equal to what was asked.

**Why this priority**: it is the owner's report; today every list-of-tables and table key fails.

**Independent Test**: `python -m pytest -q tests/test_config_writer.py -k "template or corpus"`.

**Acceptance Scenarios**:

1. **Given** the interview template and `config set outward.tool_patterns '[{pattern = "x",
   channel = "slack"}]'`, **When** the owner confirms, **Then** the file parses, the key sits
   under `[outward]` before `[outward.max_length]`, and the value read back equals the list.
   The writer's `mode` argument is where #492's append rule plugs in: `mode="append"` keeps
   the items already in the file and adds the new ones once.
2. **Given** a key whose table does not exist (`telemetry.otlp.endpoint` with no `[telemetry]`
   and no `[telemetry.otlp]`), **Then** the missing headers are created, parents first, and the
   key is written under the last one.
3. **Given** the corpus layouts (template, section then subtables, a spaced or quoted header,
   inline table, array of tables, missing section, trailing comments, CRLF) and a string, a
   list and a table value each, **Then** every result parses, the target equals the intended
   value, every other value is unchanged, and every line outside the written span is
   byte-identical.

### User Story 2 - A value that spans lines is replaced in place (Priority: P1)

A key already set over several lines (a multi-line array, an array of tables, a key inside an
inline table, a dotted key) is replaced whole, where it is, instead of being refused as a hand
edit.

**Why this priority**: the issue's second cause; otherwise the owner edits by hand.

**Independent Test**: `python -m pytest -q tests/test_config_writer.py -k span`.

**Acceptance Scenarios**:

1. **Given** `[shepherd]` with `reviewers = [` over three lines, **When** `shepherd.reviewers`
   is set, **Then** those three lines become the new value and nothing else changes.
2. **Given** `rotate_after = { turns = 200 }` in `[sessions]`, **When**
   `sessions.rotate_after.turns` is set to 100, **Then** that line reads
   `rotate_after = {turns = 100}`.
3. **Given** `[[outward.tool_patterns]]` blocks, **When** `outward.tool_patterns` is set,
   **Then** the blocks are replaced by blocks for the new list at the first block's place.
4. **Given** `[[repos]]` with `merge.auto = false`, **When** `repos.0.merge.auto` is set,
   **Then** that dotted line is replaced.

### User Story 3 - The same set twice is a no-op (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_config_writer.py -k twice`.

**Acceptance Scenarios**:

1. **Given** the same value set twice, **Then** the file is byte-identical after the second
   run, and the second `config set` prints `No config.toml changes` without asking.

### User Story 4 - A value that is not TOML is refused with its type (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_setup.py -k not_toml`.

**Acceptance Scenarios**:

1. **Given** `config set outward.tool_patterns '[{pattern: "x"}]'`, **Then** exit 1 before the
   digest, the file unchanged, and the reason names the key, says it takes a list of tables,
   and gives an example (`'[{pattern = "text", channel = "text"}]'`).
2. **Given** `config set cap many`, **Then** exit 1 and the reason says an integer, with an
   example.
3. **Given** `config set owner.verbosity.default standard`, **Then** the reason says a string
   and shows a quoted example (`'"brief"'`).

### User Story 5 - config check names a key set in two tables (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_config_writer.py -k two_tables`.

**Acceptance Scenarios**:

1. **Given** `work_channels = ["C1"]` under `[outbound]` and again under `[outward]` (where the
   schema does not know it), **Then** `config check` prints one line naming the key, both
   tables and both line numbers, says to delete the misplaced line, and exits 1.
2. **Given** a key name that is legitimately in two tables (`auto` in `[tracker]` and
   `[repos.merge]`), **Then** nothing is reported.

### Edge Cases

- A file without a trailing newline: an insertion at the end adds the newline first.
- A table with no keys yet (only comments, like `[outward]` in the template): the key goes
  right after its header.
- The root table: a new top-level key goes after the last top-level key; with none, at the top.
- A list index past the end (`repos.3.merge_deploys` with one repository): refused, naming
  `bin/wuwei config add-repo`.
- A scalar onto a key whose current value is a table (`owner.verbosity '"brief"'`): refused as
  today, naming `owner.verbosity.default`.
- A value that cannot be placed safely (a key whose parent table exists only through dotted
  keys in another table): the post-write check refuses with the key and "edit by hand";
  nothing is written.
- A deploy list (`deploy.workflows`, `deploy.deny`) still only grows, whatever the mode.
- A string with a control or non-BMP character reads back equal.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The writer MUST read config.toml as a line model: table headers (`[a.b]`,
  `[[a.b]]`, with spaces, quoted parts and trailing comments) with their resolved path
  (array-of-tables index included), key entries with their full path (table path plus dotted
  key) and their whole value span (every line until the assignment parses), and other lines
  (comments, blanks) left as they are.
- **FR-002**: The writer MUST serialize values as TOML: strings as basic strings that TOML reads
  back equal (no surrogate escapes), booleans, integers, floats, tables as inline tables with
  keys quoted only when not bare, lists of scalars on one line, and lists holding a table or a
  list over several lines, one item per line with a trailing comma.
- **FR-003**: When the key exists, the writer MUST replace its whole span in place. When an
  ancestor of the key exists as a key whose value is an inline table or array, it MUST set the
  key inside that value and rewrite that span. When the key is an array of tables, it MUST
  replace those blocks with blocks for the new list. When the key is a table written as a
  header and the value is a table, it MUST rewrite that table's direct keys.
- **FR-004**: When the key does not exist, the writer MUST insert it after the last direct key
  of its own table (before any subtable header; right after the header when the table has no
  key), and when the table does not exist, create its header and any missing parent headers,
  parents first, after the last table of the nearest existing ancestor (end of file for the
  root).
- **FR-005**: Inserted lines MUST use the file's line ending (CRLF when the file has one).
- **FR-006**: After writing, the result MUST parse, the target MUST equal the intended value,
  and every other value MUST be unchanged; otherwise the writer refuses with the key and "edit
  by hand", and nothing is written.
- **FR-007**: There MUST be one entry point, `write_value(raw, key, value, mode="replace")`,
  that `config set` calls and #492 calls; `mode="append"` keeps the list items present in the
  file and adds new ones once; any other mode is refused.
- **FR-008**: Setting a value equal to the present one MUST leave the text byte-identical.
- **FR-009**: `config set` MUST refuse a value that does not parse as TOML with exit 1, before
  the digest, naming the key's declared type and an example value built from the schema, in
  the #362 shape (`<key>: <what>; <next step>`).
- **FR-010**: `config check` MUST report, with exit 1, a key name set in two tables where the
  schema declares it in one and not (or only through a `*` wildcard) in the other, with both
  line numbers.
- **FR-011**: Every existing caller of the writer (`config set`, `setup slack`, setup and the
  interview, `config promote`, `calibrate`) MUST go through the same placement code.

### Key Entities

- **Line model entry**: kind (table, array table, key), resolved path, first line, end line.
- **Declared type**: the `workspace.SCHEMA` node at a key's path, used for the refusal text and
  for the two-tables check.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every corpus layout and value kind (at least 8 layouts by 3 kinds), the result
  parses with `tomllib` and equals the intended config; 0 failures.
- **SC-002**: The owner's exact command on the template succeeds with one confirmation.
- **SC-003**: A second identical `config set` changes 0 bytes.
- **SC-004**: The full suite stays green; the only existing tests that change are the ones that
  asserted the old refusals for spans and inline repositories (plan.md lists them).

## Assumptions

- The notes name no dry-run workspace; reproduction used the shipped template and small layouts
  in process (above). The "interview template (#412)" in the issue is
  `templates/workspace/config.toml` as setup (#327) and the interview (#279) write it, plus
  `[[repos]]` tables.
- The issue's `set_value(key, value, mode)` is `commands/setup.write_value(raw, key, value,
  mode="replace")`; the CLI handler keeps its name `set_value(args, confirm)`, so `config.py`,
  `telemetry.py` and the tests that call it do not change. #492 owns the CLI default (append
  unless `--replace`) and the defaults merge in `load_config`; this item ships the `mode`
  argument and the append mechanics only, so "the defaults rule of #492 applies" is met through
  the one entry point.
- Inline tables stay on one line: TOML 1.0, which `tomllib` reads, forbids newlines inside them.
  "Multi-line TOML" applies to arrays.
- A replaced span loses its own trailing comment, as today (`tests/test_interview.py` asserts
  it); every other comment and line is untouched.
- The calibration comment line (`# Added by wuwei config promote from calibration.`) is still
  written once per table by `calibrate.apply`, for `config set` too, as today.
- The two-tables check runs only after `load_config` succeeds; a misplaced value of the wrong
  type is already a config error naming its key.
- The parsed shape does not change, so `CONFIG_CACHE_VERSION` stays 6.

## Deferred

- Placement into a table that exists only through dotted keys in another table is refused by
  the post-write check, not handled (no reproduction; the owner's layouts use headers).
