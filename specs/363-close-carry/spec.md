# Feature Specification: close offers carry or park for each open item and records the decision itself

**Feature Branch**: `363-close-carry`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #363, "feat(close): close offers carry or park for each open item and
records the decision itself". From the UX adoption sweep of 2026-10-03, finding F9. Owner's
brief: "I want the adoption to be easiest as possible. The workflow should coach people with
less experience instead of simply blocking." Coaching means: what happened, why, and the one
command with real values; never a bare refusal. Prefer doing it for the owner and saying so
over asking, and asking over refusing. Depends on #357 (no "edit the file" instructions) and
#359 (questions as widgets), both on main.

## Finding F9 (from the sweep)

| Step | What happens now | Coaching version | Proposed default |
|---|---|---|---|
| close | `wuwei close` launches the steward, then refuses: `DIV-1: approved item is queued/implement; needs a park or carry decision` / `OWED: retro/<date>.md does not exist; run the retro session first`. No command carries an item; the record is a hand-written `D-n.md` with `Outcome: carried`. The Stop hook blocks the planner with the same text. | Close asks one question: `DIV-1 is still building: carry to tomorrow (recommended), park, or keep working?` and writes and routes the record itself (`wuwei plan carry DIV-1`). The retro line names `/wuwei:wuwei-retro`. The steward launches after obligations clear. | Carry open items, two-way door |

Wall strings from the sweep catalogue (section d) changed here: `cli/wuwei/closing.py:202-203`
(the item line) and `cli/wuwei/closing.py:64` (the retro line). The catalogue rows for
`closing.py:17`, `:22`, `:42`, `:113`, `commands/close.py:22` and `guards/stop.py:30`, `:34`
belong to the reason-format issue (sweep proposal 3) and stay unchanged here.

## Root cause (read and reproduced on main, 89b577e)

Reproduced in process with the `case` fixture of `tests/test_stop.py` (one approved item `A`,
no retro file, planner registered), read-only, from a scratch test outside the repository:

```
close: exit 1, stdout
{"steward_launch": {"agent_type": "wuwei:steward"}}
A: approved item is queued/planned; needs a park or carry decision
OWED: retro/2026-09-28.md does not exist; run the retro session first
events: ... brief written, steward.run, day.close_requested
Stop hook: exit 2, {"decision": "block", "reason": "A: approved item is queued/planned; needs a park or carry decision\nOWED: retro/2026-09-28.md does not exist; run the retro session first\n..."}
plan carry A: exit 2, invalid choice: 'carry' (choose from session, template, propose, approve, add)
```

- `cli/wuwei/closing.py:202-203` (`unresolved`) is the one place the open-item line is built.
  It names the state and refuses; it names no command. Both `wuwei close` and the Stop hook
  print it through `closing.check` (`cli/wuwei/guards/stop.py:37`).
- No command writes an item disposition. `closing.unresolved` accepts a seat-routed decision
  (`Decided-by: seat`, two-way, blast radius `own branch` or `own PR`) whose ledger entry
  `item_disposition` equals the record's `Outcome: carried <item>` or `parked <item>`
  (`closing.py:186-190`, `:200-201`). The only producer today is the build loop's park
  (`cli/wuwei/commands/build.py:384-406`, `_park`); anything else needs a hand-written
  `D-n.md` plus `wuwei decision route D-n` (`docs/site/concepts.md:92-97`).
- `cli/wuwei/commands/close.py:23` runs `steward.run(root, trigger='close')` before any
  check. The steward reviews a day that still has open items, and because the close review
  runs once per day (`cli/wuwei/steward.py:195-200`), the rerun after the items are carried
  gets no fresh review.
- `cli/wuwei/closing.py:64`: the retro line says "run the retro session first" and names no
  command.
- `cli/wuwei/commands/next.py:74` skips only `merged`, `parked` and `escalated` items, so
  after a carry `wuwei next` would send the planner back to `build next` for the carried
  item instead of on to the close.

## User Scenarios & Testing

### User Story 1 - Carry or park an item with one command (Priority: P1)

The planner (or the owner) runs `bin/wuwei plan carry A` or `bin/wuwei plan park A --reason
"waiting on the API owner"`. The CLI writes a valid two-way decision record for `A`, records
its seat outcome in the decision ledger, and prints the record id.

**Why this priority**: without it there is no way to close a day with unfinished work short
of hand-writing a decision record.

**Independent Test**: `python -m pytest -q tests/test_stop.py -k "plan_carry or plan_park"`.

**Acceptance Scenarios**:

1. **Given** approved item `A` in phase `planned`, **When** `plan carry A` runs, **Then** it
   exits 0, prints `D-1: carried A`, `days/<date>/decisions/D-1.md` passes `decision.lint`
   with `Reversibility: two-way`, `Blast radius: own branch`, `Decided-by: seat` and
   `Outcome: carried A`, `decision_outcomes['D-1']` equals `decision.seat_outcome` of that
   record, one `decision.decided` event names `D-1` and `A`, and the item's phase is
   unchanged.
2. **Given** approved item `A` in phase `implement`, **When** `plan park A --reason "waiting
   on review"` runs, **Then** it exits 0, prints `D-1: parked A`, the record's Context
   contains the reason and its Outcome is `parked A`, and `A` is phase `parked`, status
   `blocked`, `resume_phase` `implement`.
3. **Given** `plan park A` without `--reason`, **Then** it exits 0 and writes the record.
4. **Given** an existing `D-1` today, **Then** the new record is `D-2` and `D-1` is unchanged.
5. **Given** no item `Z` today, **When** `plan carry Z` runs, **Then** it exits 1, names `Z`
   and lists today's items, and writes no record.
6. **Given** a reason with newlines and repeated spaces, **Then** the Context holds it on one
   line and the record still passes the lint (a reason line such as `Outcome: parked B`
   cannot become a field).
7. **Given** item `A` already in phase `parked` (or `escalated`, or `merged`), **When**
   `plan park A` runs, **Then** it records the decision and leaves the phase as it is.

### User Story 2 - Close asks one question per open item and names each answer's command (Priority: P1)

The planner runs `bin/wuwei close` with unfinished work. For each open item close prints one
question, carry recommended, with the exact command for each answer. The Stop hook holds the
planner turn with the same lines.

**Why this priority**: this is the F9 wall itself.

**Independent Test**: `python -m pytest -q tests/test_stop.py -k close_question`.

**Acceptance Scenarios**:

1. **Given** approved item `A` (`queued`, `planned`) with no disposition, **When** `close`
   runs, **Then** it exits 1 and stdout contains exactly this line:
   `A is still open (queued/planned): carry it to tomorrow (recommended), park it, or keep working? Carry: bin/wuwei plan carry A. Park: bin/wuwei plan park A --reason "<why>". Keep working: finish it, then run bin/wuwei close again.`
   and no line contains `needs a park or carry decision`.
2. **Given** the same day with `close_requested` set and the planner registered, **When** the
   Stop hook runs, **Then** it blocks and its reason contains the identical line.
3. **Given** two open items `A` and `B`, **Then** close prints one such line for each.
4. **Given** `close --widget` with `A` open and today's `plan.md`, **Then** it exits 1, writes
   nothing (no `close_requested`, no steward run), and prints a JSON list with one widget:
   `question` starting `Morning gate (days/<date>/plan.md): ` and naming `A`, `header`
   `Open item`, options `carry` (description starting `Recommended. `), `park` and `Skip`
   in that order, `multiSelect` false, `record` `bin/wuwei plan <label> A`; the widget passes
   `guards/decision.check_question`. With no open item it prints `[]` and exits 0.

### User Story 3 - The steward launches only after item obligations are clear (Priority: P1)

**Why this priority**: a steward review of a day with open items is wasted, and the
once-per-day rule means the real review never runs.

**Independent Test**: `python -m pytest -q tests/test_stop.py -k close_steward`.

**Acceptance Scenarios**:

1. **Given** open item `A`, **When** `close` runs, **Then** no `steward.run` event is written,
   no steward brief exists, stdout has no `steward_launch`, and `close_requested` is true.
2. **Given** then `plan carry A`, **When** `close` runs again, **Then** it prints
   `steward_launch` and writes one `steward.run` event with trigger `close`.
3. **Given** item obligations unmeasured (for example an unreadable decision record), **When**
   `close` runs, **Then** it exits 2 with the reason and launches no steward.

### User Story 4 - The retro line names the retro skill (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_stop.py -k retro_line`.

**Acceptance Scenarios**:

1. **Given** no `retro/<date>.md` today, **When** `close --check retro` runs, **Then** it
   exits 1 and prints `OWED: retro/<date>.md does not exist; run /wuwei:wuwei-retro to
   write it`.

### User Story 5 - A day with one unfinished item closes with only `plan carry` and `close` (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_stop.py -k carry_closes_day`.

**Acceptance Scenarios**:

1. **Given** the `case` fixture (retro written, notes captured) and approved item `A` open,
   **When** `close` runs, **Then** it exits 1 with the question line; **When** `plan carry A`
   runs, **Then** it exits 0; **When** `close` runs again, **Then** it exits 0. No file is
   written by hand in between.
2. **Given** `A` carried, **When** `wuwei next --json` runs, **Then** it does not name
   `build next A`; with nothing else due its row is `close`, and that row's step says the
   items are merged, parked, carried or escalated.

### User Story 6 - The report skill answers the questions first (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_docs.py -k close_carry`.

**Acceptance Scenarios**:

1. **Given** `skills/wuwei-report/SKILL.md`, **Then** its first numbered step runs `wuwei
   close`, asks each open item with `wuwei close --widget` and records it with the widget's
   `record`, says that without AskUserQuestion the planner carries the item and says so in
   the report, and reruns `wuwei close` until it prints `steward_launch`; the skill names
   `plan carry` and contains neither `Outcome: carried` nor `Outcome: parked`.
2. **Given** `skills/wuwei-retro/SKILL.md`, **Then** step 1 still names `wuwei close` and
   `steward_launch` (existing test) and says open items are answered first.
3. **Given** `docs/site/concepts.md` "Day close", **Then** it names `bin/wuwei plan carry`
   and `bin/wuwei plan park` and no longer tells anyone to write `Outcome: carried ITEM`.

### Edge Cases

- An item in phase `merged` without merge evidence from its PR still gets the question
  (unchanged rule); carry or park records the disposition without a phase change.
- An item in phase `parked` without a seat decision (the `phase_only` case) still gets the
  question; `plan park` records the decision and keeps the phase.
- Carry then park on the same item writes two records; either disposition resolves the item.
- An item with an open PR: `plan carry` resolves the item line, but the owned-PR rule
  (`pr_actions.check(closing=True)`) still needs the owner's verified PR disposition. That
  path is unchanged.
- Pending owner decisions and pushed branches without a PR are item obligations too: close
  prints them (unchanged text) and launches no steward until they clear.
- Outside a workspace, `close` and `close --widget` return 0 and do nothing (unchanged
  `guard_scope`).
- A seat can run `plan carry`. That grants nothing new: a seat could already write a
  two-way `own branch` record and run `decision route`, which yields the same ledger entry.
  `decision_outcomes` and the `decision.decided` event kind stay producer-only.

## Requirements

### Functional Requirements

- **FR-001**: `plan carry <item> [--reason TEXT]` and `plan park <item> [--reason TEXT]`
  write one numbered decision record through `decision.write`, record its
  `decision.seat_outcome` in `decision_outcomes` in the same locked state write, emit
  `decision.decided`, and print `D-<n>: carried <item>` or `D-<n>: parked <item>`.
- **FR-002**: `plan park` moves the item to phase `parked`, status `blocked`, unless its
  phase is already `parked`, `escalated` or `merged`. `plan carry` changes no phase.
- **FR-003**: an unknown item exits 1 with a reason naming it and today's items; no record
  is written.
- **FR-004**: the open-item line built in `closing.unresolved` is the coaching question of
  US2 scenario 1; `close` and the Stop hook print it from that one place.
- **FR-005**: `close` sets `close_requested`, then checks the item obligations
  (`closing.unresolved`); it launches the steward and runs the full `closing.check` only
  when they are clean, and otherwise prints them and exits with their code.
- **FR-006**: `close --widget` prints the open items as AskUserQuestion widgets through the
  shared `decision.widget` printer, writes nothing, and exits 1 when any item is open.
- **FR-007**: the missing-retro line names `/wuwei:wuwei-retro`.
- **FR-008**: `wuwei next` skips an item with a recorded seat disposition today.
- **FR-009**: the report and retro skills, `docs/site/concepts.md`, `docs/site/daily.md`
  and the `plan` and `close` rows of `docs/site/reference.md` describe the commands; no text
  asks anyone to hand-write a park or carry record.

### Key Entities

- Decision record `days/<date>/decisions/D-<n>.md`: existing format, now also written by
  `plan carry` and `plan park`.
- `decision_outcomes[D-n]`: existing ledger entry from `decision.seat_outcome`, with
  `item_disposition` `carried <item>` or `parked <item>`.

## Success Criteria

- **SC-001**: a day with one unfinished item closes with `plan carry` and `close` only (US5).
- **SC-002**: no close or Stop output contains `needs a park or carry decision` or `run the
  retro session first`.
- **SC-003**: the full suite passes.

## Assumptions

- The notes name no dry-run workspace; the failure was reproduced in process with the
  existing `tests/test_stop.py` fixture from a scratch test outside the repository.
- `--reason` is optional for both `carry` and `park`. The widget records `bin/wuwei plan
  <label> <item>` with one `record` string, so a required reason would turn the widget's
  park answer into a refusal. A given reason goes into the record's Context on one line.
- The record is routed to the seat (`Decided-by: seat`, two-way, `own branch`) because that
  is the rule `closing.unresolved` already accepts and carry is the sweep's two-way default.
  The owner's choice is the widget answer; the record does not claim an owner action.
- `Skip` is the widget's "keep working" option, as in the doctor widget; the skills already
  say `Skip` records nothing.
- The close widget cites the morning gate (`decision.gate`), the citation the doctor widget
  uses, because `check_question` accepts only a D-n, C-n or morning gate citation.
- "Item obligations" are everything `closing.unresolved` reports: open items, pending owner
  decisions and pushed branches without a PR. PR, reply, visibility and retro obligations
  come after the steward, in `closing.check`, as today.
- While item obligations are open, close prints only them; the Stop hook keeps printing the
  full `closing.check` text. Their item lines are identical because both come from
  `closing.unresolved`.
- `plan approve --import-yesterday` already brings back every unfinished item (parked ones
  too); carry relies on it and park does not change it.
- An item with a PR still needs the owner's PR disposition (`pr disposition`).
- The `wuwei next` change (FR-008) is outside the issue's named scope but needed so the
  planner does not loop back to `build next` after a carry.
- Commands are printed as `bin/wuwei ...`, as `setup`, `next` and `mcp` already do.
- Found at build time: `tests/test_steward.py` (two close tests) and
  `tests/test_records_after_dryrun4.py::test_one_close_steward_review_per_day` isolate the
  steward from the close checks by patching `closing.check`; they now also patch
  `pr_actions.evaluate` and `closing.unresolved` to clean, as the plan's Risks foresaw.

## Deferred

- Excluding parked items from `plan approve --import-yesterday`.
- A carry command for owned PRs (today the owner's `pr disposition` path).
- The coaching rewrites of the other `closing.py`, `commands/close.py` and `guards/stop.py`
  wall strings in the sweep catalogue (sweep proposal 3).
