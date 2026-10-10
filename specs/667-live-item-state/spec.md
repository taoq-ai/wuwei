# Feature Specification: seats read live item state

**Feature Branch**: `667-live-item-state`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #667 (owner, 2026-10-10, item 25): fix(brief): seats read live item
state: the brief names the record and the commands, and the values that change during the
day (docs path, ticket, spec state) are read when the seat starts, not copied into the brief.

## Root cause (reproduced read-only on the owner's day of 2026-10-10, code read on main at 35306d9)

`brief.write` copies the item's record into the brief once, under `brief.lock`, at write
time:

- `cli/wuwei/brief.py:367` reads `current = data['items'].get(item, {})`.
- `cli/wuwei/brief.py:483` appends `docs.brief_line(config, current, item, role)`. For a
  quality brief, `cli/wuwei/docs.py:116-118` turns an unset `docs` key into
  `Docs: required (tier <t>); value missing: a blocking DOC: FINDING naming <command>.`
- `cli/wuwei/brief.py:440-444` appends `specmode.brief_line(...)`; for a gate brief
  `cli/wuwei/specmode.py:321-322` writes `Spec: <engine> artifacts: <dir>` or
  `Spec: not found (<why>)` from the worktree as it was at that second.

Nothing refreshes those lines afterwards. In the owner's day the quality brief of one item was
written at 10:11:24 (`brief written` event) with `value missing`; the planner recorded the
docs path at 10:11:40 (`docs.set` event, 16 seconds later). The brief kept telling the
quality sentinel to file a blocking `DOC: FINDING`. That seat happened to check live and
passed; a seat trusting its brief would have filed a false blocking finding, and
`dispatch receive` (`cli/wuwei/dispatch.py:676-682`) only refuses the opposite case (a PASS
while the value is missing), so the false FIX would have been recorded.

`wuwei why <item>` (`cli/wuwei/commands/why.py`) already reads the item from the day records
at call time, but it has no `--json` output and prints no docs, ticket or spec value. The
verdict lint (`cli/wuwei/verdict.py:87`, `lint_file` at `:195`) is text only: it cannot tell
that a finding claims a value is missing while the record holds it.

No `Ticket:` line exists in any brief on main (grep over `cli/`); the ticket lives only in
`state.json` at `tickets.<item>.id`. No orchestrator notes file exists for this issue.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What does `wuwei why <item> --json` print? A: One JSON object read at call time from the
  latest day that holds the item: `item`, `day`, `docs` (`value`: the recorded value,
  `missing`, or `n/a` when the item carries no docs obligation; `reason`; `command`: the
  command that records it), `ticket` (the id or `null`), `spec` (the gate's spec state text,
  such as `speckit artifacts: specs/001-x`, `not found (<why>)` or `skipped (<reason>)`, or
  `null` when spec mode is off) and `steps` (the same lines the text view prints). Every
  string passes the same redaction the text view applies.
- Q: Which brief lines go? A: In a gate brief, the `Spec:` line and the quality `Docs:` line.
  They are the only lines that copy a value the day changes. The builder brief keeps its
  `Spec:` line (engine, steps and create command) and its `Docs:` line (the rule and the
  command): both are instructions from config, not recorded values.
- Q: What replaces them? A: One `Live:` line in every builder and gate brief:
  `Live: run bin/wuwei why <item> --json when you start and again before your verdict or
  handoff; its docs, ticket and spec fields are the record at that moment. This brief copies
  none of them.`
- Q: What does the lint reject? A: When the gate file's seat resolves to an item whose docs
  value is recorded (not `missing`, not `n/a`) at lint time, any finding block that says the
  docs value is missing is a lint failure:
  `finding <n>: says the docs value is missing, but <item> records docs <value> (bin/wuwei why
  <item> --json); drop or correct the finding`. The lint runs at the verdict write (the
  verdict guard), at `seat stop` and at `dispatch receive`, so "at receive time" is the
  record when `receive` runs.
- Q: Which phrases count as "says the docs value is missing"? A: A narrow pattern on the
  value, never on the page: `docs value` (or `docs path`) directly followed by `missing`,
  `not set`, `not recorded`, `unset` or `absent` (an optional colon, `is`, `was` or `still`
  between); `missing`, `no` or `unset` directly before `docs value` or `docs path`; and the
  old brief phrase `value missing` within a line that names `DOC`. A finding about the page's
  content (`the docs path docs/cli.md is missing the --json flag`), about a `none` value for a
  documented change, or about any other value (`the return value missing a zone`) is never
  matched.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A gate seat reads the docs value when it starts (Priority: P1)

The planner writes the quality brief, then records the docs path. The quality sentinel runs
`bin/wuwei why <item> --json` as its brief says and sees the recorded path, so it checks the
path against the diff instead of filing a missing-value finding.

**Why this priority**: it is the owner's report: a stale copy in the brief drives a false
blocking finding.

**Independent Test**: write a quality brief with no docs value, record the value, then run
`main(['why', 'X', '--json'])`: the brief has no `Docs:` line and names the command, and the
JSON shows the recorded value.

**Acceptance Scenarios**:

1. **Given** a docs path recorded after the brief, **When** a seat follows the brief, **Then**
   it reads the path from `why <item> --json`, and the lint rejects a "docs missing" finding.
2. **Given** a quality or arch gate brief, **When** it is written, **Then** it carries no
   `Docs:` and no `Spec:` line and carries the `Live:` line naming `bin/wuwei why <item>
   --json`.
3. **Given** a builder brief, **When** it is written, **Then** it keeps its `Spec:` and
   `Docs:` instruction lines and carries the `Live:` line.

### User Story 2 - The lint refuses a false missing-value finding (Priority: P1)

A seat that still writes "docs value missing" after the value was recorded gets its verdict
rejected with the value and the command to read it, at write, at stop and at receive.

**Why this priority**: the brief fix removes the cause; the lint stops a stale or careless
seat from recording the false finding anyway.

**Independent Test**: a gate file whose seat resolves to an item with `docs.value` set, with a
finding `docs value is missing`: `lint_file` returns 1 naming the value; with the value unset
it returns 0.

**Acceptance Scenarios**:

1. **Given** an item with a recorded docs value, **When** a verdict finding says the docs
   value is missing, **Then** `verdict.lint_file` returns 1 with
   `says the docs value is missing, but <item> records docs <value>`.
2. **Given** an item with no recorded value, **When** the same verdict is linted, **Then** this
   rule adds nothing (the existing receive check still requires the DOC finding).
3. **Given** an item with a recorded value, **When** a finding says the docs page does not
   describe a changed command, or that `none` is wrong for a documented change, **Then** this
   rule adds nothing.
4. **Given** a gate file whose seat or item cannot be resolved (outside a workspace, unknown
   seat), **When** it is linted, **Then** this rule adds nothing, as `verdict.light` does.

### User Story 3 - Any reader gets the live values as JSON (Priority: P2)

**Why this priority**: the seat instruction needs it; other readers (planner, owner) get it
for free.

**Independent Test**: `main(['why', 'X', '--json'])` on a fixture item with a ticket, a docs
value and a spec directory in its worktree.

**Acceptance Scenarios**:

1. **Given** an item with a ticket, a docs value and a found spec directory, **When**
   `why <item> --json` runs, **Then** it prints `ticket`, `docs` and `spec` from the record
   and the worktree as they are now, and exits 0.
2. **Given** an unknown item, **When** `why <item> --json` runs, **Then** it exits 1 as the
   text view does.
3. **Given** a decision, draft, event id, `last refusal` or target key with `--json`, **When**
   `why` runs, **Then** it exits 2 with `why --json reads an item; pass an item id`.

### Edge Cases

- A docs reason or ticket id holding a credential is redacted in the JSON as in the text view.
- `docs.system = "none"`: `docs.value` is `n/a`; the lint rule never fires.
- The item exists on an earlier day only: the JSON reads that latest day, as `why` does.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `wuwei why <item> --json` MUST print one JSON object with `item`, `day`, `docs`
  (`value`, `reason`, `command`), `ticket`, `spec` and `steps`, read at call time.
- **FR-002**: A gate brief MUST NOT carry a `Docs:` or `Spec:` line; builder and gate briefs
  MUST carry the `Live:` line naming `bin/wuwei why <item> --json`, at start and before the
  verdict or handoff.
- **FR-003**: The builder brief's `Spec:` and `Docs:` instruction lines MUST stay unchanged.
- **FR-004**: `verdict.lint_file` MUST reject a finding block that says the docs value is
  missing while the item's docs value is recorded at lint time, naming the value and the
  `why` command.
- **FR-005**: The quality charter MUST tell the sentinel to judge the docs obligation from
  `why <item> --json`, not from the brief; `agents/sentinel-quality.md` is rebuilt with
  `bin/wuwei agents build`.
- **FR-006**: The design spec 5.12 sentence "The quality brief carries the obligation and the
  recorded value" MUST be amended to the live read, and 9.2 MUST gain the invariant for the
  new lint rule (I46) with its test in `tests/test_invariants.py`.

### Key Entities

- **Live item values**: the docs value (`items.<id>.docs`, read through `docs.shown`), the
  ticket (`tickets.<id>.id`) and the spec state (`specmode.brief_line(..., gate=True)`), read
  when asked, never stored in a brief.

## Success Criteria *(mandatory)*

- **SC-001**: A docs value recorded any time after the brief is what the seat reads and what
  the lint checks against; no brief line contradicts it.
- **SC-002**: A verdict that calls a recorded docs value missing never reaches
  `gate_verdicts`.

## Assumptions

- A1: The ticket has no brief line on main, so nothing is removed for it; `why --json`
  carries it. What would overturn it: a brief line that copies `tickets.<id>`.
- A2: The issue's "stable parts (item, role, round, depth, charter)" lists what stays: the
  `Item:`, `Charter:` (which names the role) and `Depth:` lines; the round is in the seat name
  dispatch gives. No `Role:` or `Round:` line is added. Overturn: a seat that cannot tell its
  round.
- A3: Only the docs value is linted. Ticket and spec have no charter rule that produces a
  missing-value finding, and a "spec missing" pattern would also match a real finding about a
  spec that misses an acceptance scenario. Overturn: a recorded false ticket or spec finding.
- A4: An unresolvable seat or item, or a config that cannot be read, adds no lint failure (the
  fallback `verdict.light` uses); the existing `dispatch receive` docs check is unchanged.
- A5: A finding block of any severity is checked, blocking or not: a false note is as wrong as
  a false blocker.
- A6: `--json` takes only an item; other targets exit 2 rather than inventing a second JSON
  shape nobody reads yet.
- A7: The builder brief keeps its `Spec:` line although it can name a found directory: the
  builder creates that directory itself, so a stale location there cannot drive a false
  finding.

## Deferred

- None.
