# Feature Specification: Error budget per decision class

**Feature Branch**: `558-error-budget`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #558: reversals and escaped defects spend a 14-day budget per
decision class, a burn rate warns early, a spent budget lowers the class until the window
refills, and promotion needs the budget unspent. Builds on #283 (cruise mode, on main).

## Root cause

Demotion in cruise mode (design 5.8.1, "Promotion and demotion") fires on single triggers,
each calling `cruise.lower` (`cli/wuwei/cruise.py:84-89`) at once:

- an undo: `cli/wuwei/commands/decision.py:295` (`undo`);
- an owner answer that differs from a cruise answer, and a weekly sample answered
  differently: `cli/wuwei/cruise.py:126-139` (`answered`), called from
  `cli/wuwei/commands/decision.py:235` (`owner_outcome`);
- three thin-margin escalations in a row: `cli/wuwei/cruise.py:92-102` (`streak`), called
  from `cli/wuwei/commands/decision.py:74-75` (`decide`);
- an escaped defect on an item a cruise answer named: `cli/wuwei/cruise.py:233-247`
  (`escaped`), called from `cli/wuwei/steward.py:25` (`review`).

None of them looks at how many decisions the class answered, so one unlucky reversal in 50
good answers drops a class, while a slow drift of bad calls spread across days (each one
after a level change resets `changed`) never adds up to anything. There is no early warning
and no return path: a lowered class only comes back through a new raise card, and the
"no reversal" condition of promotion exists only implicitly, because every reversal reset
the class's `changed` stamp that `agreements` (`cli/wuwei/cruise.py:150-158`) counts from.
Removing the single triggers without adding the check would let a class with reversals be
promoted.

## User Scenarios and Testing

### User Story 1: A class that keeps getting reversed runs one level lower (Priority: P1)

The owner runs autonomous with cruise on. The `defer` class runs at L2 and the CLI answered
20 of its records in the last 14 days; the owner undid or reversed three of them. The next
steward run lowers `defer` to L1 (its records come to the owner preselected, a card, never a
refusal), and the ledger line says why, naming the three events.

**Independent Test**: neutral workspace in `tmp_path`, `defer` raised to L2, events for 20
cruise answers and 3 reversals written to the day's `events.jsonl`, `steward.review` (or
`budget_classes.evaluate`) runs.

**Acceptance Scenarios**:

1. **Given** a class with 20 answered decisions in the window and 3 reversals, **When** the
   steward run evaluates budgets, **Then** the class runs one level lower and the ledger line
   names the three events.
2. **Given** a class with 20 answered decisions and 2 reversals (allowance 2), **When** the
   steward run evaluates budgets, **Then** the level is unchanged (2 is not more than 2).
3. **Given** a class with 5 answered decisions and 1 reversal (allowance 0.5), **When** the
   steward run evaluates budgets, **Then** the level is unchanged: at least two events are
   needed before a budget can be spent.
4. **Given** a spent class already lowered by its budget, **When** the steward runs again
   with no new event, **Then** nothing changes and no second ledger line is written.

### User Story 2: The level comes back when the window refills (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the class of US1 after the window refills with no new reversal (the clock moved
   15 days on), **When** the steward run evaluates budgets, **Then** the level is restored to
   the level it ran at before the budget lowered it and the ledger says so (`budget refilled`).
2. **Given** a class at L0 whose budget is spent, **When** the steward runs, **Then** nothing
   is lowered and nothing is held (there is no lower level), and nothing is restored later.

### User Story 3: A burn-rate nudge warns before the budget is spent (Priority: P2)

**Acceptance Scenarios**:

1. **Given** 2 reversals inside 48 hours against an allowance of 2 per window, **When** the
   steward run evaluates budgets, **Then** a `cruise.burn` nudge naming the two events is
   written before the budget is spent, and the level is unchanged.
2. **Given** that nudge today, **When** the steward runs again with no new event, **Then** no
   second nudge is written for that class today.
3. **Given** the nudge, **When** `wuwei nudges` runs, **Then** its line ends with
   `Run: wuwei cruise budget`.

### User Story 4: No promotion while the budget is spent or after a reversal (Priority: P1)

**Acceptance Scenarios**:

1. **Given** 10 agreements and a spent budget, **When** `plan propose` runs, **Then** no
   raise card is proposed for that class.
2. **Given** 10 agreements and one reversal of that class after its last level change in
   `promote_days`, budget unspent, **When** `plan propose` runs, **Then** no raise card is
   proposed (the 5.8.1 "no reversal" condition, now explicit).

### User Story 5: The owner reads the budgets (Priority: P2)

**Acceptance Scenarios**:

1. **Given** cruise answers and reversals in the window, **When** `wuwei cruise budget`
   runs, **Then** it prints one row per class but `merge` with class, level, answered,
   spent, allowance, burn and state (`ok`, `warn`, `spent`), and exits 1 when any class is
   `warn` or `spent`, 0 otherwise, 2 with the reason on a damaged event stream or
   `cruise.json`.
2. **Given** a class held lower by its budget, **When** the status line renders, **Then**
   its cruise part reads `cruise L<max> · budget <class> spent` (several classes joined with
   `, `).

### User Story 6: Single triggers are gone (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a cruise answer at L2, **When** the owner undoes it or reverses it with
   `wuwei decide`, **Then** the record goes back to the owner as before and the class level
   is unchanged; the event counts toward the budget.
2. **Given** a weekly sample answered differently, **When** the answer is recorded, **Then**
   the level is unchanged and the sample counts as a reversal of the sampled class.
3. **Given** three thin-margin escalations in a row, **When** the third routes, **Then** the
   level is unchanged (the route row still records `thin: true`).
4. **Given** an escaped defect on an item a cruise answer named, **When** the steward runs,
   **Then** it counts as one event of that class's budget and lowers nothing on its own.

### Edge Cases

- No cruise answers and no events: every class is `ok`, burn 0.
- Allowance 0 with events (an event whose answer fell out of a short window): burn prints
  `inf`; state follows the spent rule.
- Cruise off or supervised: the effective level is 0, so a spent budget lowers nothing; a
  held class is still restored when its window refills.
- An owner-approved raise lands while a class is held: the raise clears the hold (any write
  through the promote writer that is not a budget lowering clears it); the next steward run
  lowers it again if the budget is still spent.
- A damaged `events.jsonl` in the window or a damaged `cruise.json`: the steward run and
  `cruise budget` exit 2 with the reason, never report clean.

## Requirements

### Functional Requirements

- **FR-001**: `wuwei.budget_classes` (stdlib) selects, for a window of N days ending now,
  the cruise answers (`decision.decided` events whose payload has a `cruise ` rule) and the
  events against them: an undo (`decision.reversed` with `undo: true`), a reversal
  (`decision.reversed` on the same day and id as a cruise answer), a weekly sample answered
  differently (`cruise.carded` kind `sample` followed by an owner `decision.decided` on that
  card with another option), and an escaped defect (an item in `metrics._escaped` named by
  a cruise answer). One selector serves this item and #559 (calibration).
- **FR-002**: per class, allowance = `budget_share` x answered in the window; spent = the
  number of events in the window; the budget is spent when spent > allowance and spent >= 2.
  Burn = events in the last 48 hours x `budget_window_days` / (2 x allowance) (the SRE burn
  rate: 1.0 spends the budget exactly over the window). State is `spent`, else `warn` when
  burn >= `burn_warn`, else `ok`.
- **FR-003**: the steward run (`steward.review`) evaluates budgets: a spent class not yet
  held is lowered one level through `promotion.cruise_level`, which records the running
  level it held in `memory/cruise.json` and writes a ledger line whose reason names every
  event; a held class whose budget is no longer spent is restored to the held level through
  the same writer with its own ledger line; a `warn` class gets one `cruise.burn` nudge per
  day naming the events.
- **FR-004**: the single triggers are removed: `cruise.lower`, `cruise.streak`,
  `cruise.escaped`, the reversal and sample branches of `cruise.answered`, and the
  `cruise.lower` call in `decision undo`. The weekly sample stays; its different answers
  count as reversals.
- **FR-005**: `cruise.propose` proposes no raise for a class whose budget is spent or that
  has any budget event after its last level change within `promote_days`.
- **FR-006**: `wuwei cruise budget` prints the table (read-only command, exit 0, 1 or 2).
- **FR-007**: the status line cruise part appends ` · budget <classes> spent` for held
  classes, read from `memory/cruise.json` only (no event scan on the hook path).
- **FR-008**: config `[decisions.cruise] budget_share` (default 0.1),
  `budget_window_days` (default 14, at least 1), `burn_warn` (default 2.0); `config check`
  refuses a share not above 0 or above 0.5.
- **FR-009**: `cruise.burn` is reserved to `wuwei steward run` in the event command's
  producers; it is a nudge tier event; `memory/cruise.json` stays seat-protected as today.
- **FR-010**: design 5.8.1 gains the "Error budget" amendment replacing the single
  triggers; design 9.2 and `tests/test_invariants.py` gain the invariant row; docs
  (concepts.md, reference.md, daily.md, configuration.md, README line, template config) say
  the same.

### Key Entities

- **Budget event**: `{class, at, kind (undo, reversal, sample, escaped), label, day, id}`,
  `day` and `id` naming the cruise answer it counts against.
- **Hold**: `memory/cruise.json` key `budget`, `{class: running level before the budget
  lowered it}`, present only while a class is held.

## Success Criteria

- **SC-001**: the four Acceptance scenarios of #558 pass as tests.
- **SC-002**: no code path lowers a class at once on a single event; `grep` finds no
  `cruise.lower`, `cruise.streak` or `cruise.escaped`.
- **SC-003**: no new refusal under observe or guarded: the budget only changes a class
  level, so a record goes to the owner as a card.
- **SC-004**: the full suite passes; the status line adds no file read beyond
  `cruise.json`, which it already reads.

## Assumptions

- "At least two events before the budget can be spent" means the spent rule needs at least
  two events as well as more events than the allowance; the allowance itself is the plain
  share (acceptance 3 of #558 says 2 events against an allowance of 2 is not yet spent).
- The issue names a `decision.undone` event; none exists. An undo writes `decision.reversed`
  with `undo: true` (`cli/wuwei/commands/decision.py:288-292`), and that is what counts.
- An owner reversal is joined to its cruise answer by day and id (both are today's record;
  `decide` and `undo` only answer today's records), so the `decision.reversed` payload of
  `decide` needs no new field. A reversal of a plain `mandate` answer (no cruise rule) does
  not count.
- An escaped defect is dated at its cruise answer's time; `metrics._escaped` carries no
  detection time. ponytail: an escape found later about an answer older than the window is
  not counted.
- Answered counts only cruise answers (`rule` starting with `cruise `); auto-merges write no
  cruise `decision.decided` and are not in the table.
- The steward run is the one evaluation point (it already ran `cruise.escaped`); a restore
  waits for the next steward run after the window refills.
- A spent class at L0 is not held, so the status line names only classes the budget
  lowered; `cruise budget` shows every spent class.
- The nudge is one per class per day, deduplicated from today's events, like
  `calibration.drift`.
- The `thin` flag on a route row stays as data; only the streak that acted on it goes.
- The invariant id is the next free row of design 9.2 on the base at build time (I11 on
  today's base).
- Both owner phrases in the issue ("one level lower", "until the window refills") are taken
  literally: one level per spend, restored to the held level, not re-earned through a card.

## Deferred

- Calibration (#559) reuses `budget_classes.select`; its scoring is not part of this item.
