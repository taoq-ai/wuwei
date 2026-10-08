# Feature Specification: Shadow-before-live promotion

**Feature Branch**: `560-shadow-promotion`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #560: a proposed level raise runs in shadow for five days and lands
only when every shadow answer agreed with the live one, then the morning gate asks once.
Builds on #283 (cruise mode, promote writer, `memory/cruise.json`), #308 (the would-have-done
record pattern), #558 (error budget) and #559 (calibration), all on main.

## Root cause

A raise is proposed from a count and lands on one click. Nothing tests the higher level on
live records before it runs:

- `cli/wuwei/cruise.py:188-200` (`propose`): once `agreements` reaches `promote_agreements`
  the morning plan writes the raise card at once. The count only says the owner agreed with
  past recommendations at the current level. It never checks what the raised level would have
  done on the records that came in after.
- `cli/wuwei/cruise.py:124-128` (`answered`): any `raise` card answered `raise` lands the
  level through `promotion.cruise_level`. There is no evidence on the card beyond the count.
- `cli/wuwei/commands/decision.py:107-108` (`mandate`): the one routing point where the cruise
  level matters (`cruise.rule`, which reads the level at `cli/wuwei/cruise.py:69`) computes
  only the live level. There is no record of what the next level would have answered, so
  nothing could score it.

## User Scenarios and Testing

### User Story 1: A raise runs in shadow first and lands after it passed (Priority: P1)

The owner runs autonomous with cruise on. `approach` has met the raise conditions at L2. The
morning plan no longer writes a raise card: `approach` enters shadow at L3 for `shadow_days`.
Each `approach` record routes live at L2 exactly as before; the CLI also writes
`decision.shadow` with what L3 would have answered. The steward scores the shadow against the
live outcome. After five days, five scored records and no disagreement, the shadow passes;
the next morning plan writes one raise card, and the owner's `raise` answer lands L3 with the
counts in the ledger line.

**Acceptance Scenarios**:

1. **Given** a proposal to raise `approach` to L3 and five records in shadow that all agree,
   **When** `shadow_days` have passed and the steward runs, **Then** the shadow is `passed`;
   **When** the next morning plan runs, **Then** it writes exactly one raise card (the morning
   gate asks once) and a second plan run writes none; **When** the owner answers `raise`,
   **Then** `approach` runs at L3, its shadow row is gone, and the ledger line reads
   `raise approved D-n; shadow agreed 5 of 5`.
2. **Given** the class met the raise conditions and has no shadow, **When** the morning plan
   runs, **Then** no card is written, `memory/cruise.json` holds a `shadow` row for the class
   (level, started, scored 0, agreed 0, state `running`) and the ledger has a
   `shadow started` line.

### User Story 2: One disagreement ends the shadow (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a class in shadow and one scored record whose live outcome differs from the
   shadow answer (the owner reversed or undid it and answered another option), **When** the
   steward runs, **Then** the shadow row's state is `ended`, the ledger line names the record
   (its decision path) and the two options, the class stays at its level, no raise card is
   written, and a new shadow starts only after `promote_agreements` fresh agreements.

### User Story 3: A shadow never changes a live route (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a class in shadow, **When** `decision route` routes its records (taken by the
   mandate, a cruise rule, or sent to the owner), **Then** the `decision_outcomes` row, the
   `decision.decided` payload, the record file and the command output are the same as with
   no shadow; the only addition is a `decision_shadows` row and a `decision.shadow` event.

### User Story 4: The owner sees the shadow (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a class in shadow, **When** the owner runs `wuwei cruise shadow`, **Then** it
   prints one row per shadow: class, level, started, scored, agreed, state; `none` when there
   is none; exit 0, and 2 on a damaged `cruise.json`.
2. **Given** a class in shadow (running or passed), **Then** the status line cruise part
   reads `cruise L<max> · shadow <class>`.
3. **Given** any shadow row, **When** the day report is built, **Then** it has a `## Shadow`
   section with one line per shadow and its counts; `none` otherwise.

### Edge Cases

- A shadowed record whose live outcome is not final (undo window open, or undone and not yet
  answered) is not scored yet.
- A record that the shadow level would also send to the owner gets no shadow row: it routes
  the same at both levels, so there is nothing to score.
- Fewer than `shadow_min` scored records after `shadow_days`: the shadow keeps running until
  it has them or a disagreement ends it.
- Any level write for the class (approved raise, budget lowering, budget restore) clears its
  shadow row.
- A class with a spent budget, a budget event since its last change, or calibration not
  `calibrated` starts no shadow and gets no card; a running shadow keeps scoring.
- Supervised or cruise off: `propose` returns early as today, so no shadow starts; a running
  shadow gets no new rows (the mandate path does not run) and simply waits.
- A damaged `cruise.json` (bad shadow row) fails closed with exit 2 and the reason.
- A shadow write that fails after the live route was written prints a warning on stderr and
  does not change the live result or exit code.

## Requirements

### Functional Requirements

- **FR-001**: Config `[decisions.cruise] shadow_days` (int, default 5, at least 1) and
  `shadow_min` (int, default 5, at least 1).
- **FR-002**: `memory/cruise.json` gains `shadow`: `{class: {level, started, scored, agreed,
  state, ended?, record?}}`, state one of `running`, `passed`, `ended`. It is written only by
  the promote writer (`promotion.cruise_shadow`, through `_cruise_write`, one ledger line per
  write). `cruise.running` validates it and fails closed on damage.
- **FR-003**: `cruise.propose`: a class that meets today's raise conditions and has no
  running or passed shadow starts one at level + 1 instead of a card. A class whose shadow is
  `passed` (and is not blocked) gets the raise card; the card row carries the shadow row, and
  the writer marks the shadow `ended` with reason `asked D-n`, so the gate asks once.
- **FR-004**: `cruise.answered` lands a raise only from a card whose stored shadow is
  `passed`; the ledger reason appends `shadow agreed <a> of <s>`. `promotion.cruise_level`
  drops the class's shadow row on any level write.
- **FR-005**: `decision route`: in `mandate`, after the live record is written, when the
  record's class has a `running` shadow, the CLI computes `cruise.rule` at the shadow level
  and, when it would answer, writes `decision_shadows[id] = {class, level, option, at}` with
  a `decision.shadow` event. The live route is unchanged. `decision_shadows` and
  `decision.shadow` are reserved to `wuwei decision route`.
- **FR-006**: The steward review (`steward.review`, after calibration) scores each running
  shadow over the days since it started: a shadow row is scored when the same day's
  `decision_outcomes` row is final (decided by the owner, or by the mandate with the undo
  window closed); agreed when the options match. One disagreement: state `ended`, ledger
  names the record. Passed: at least `shadow_days` since start, scored >= `shadow_min`, all
  agreed: state `passed`. Otherwise the counts are written only when they changed.
- **FR-007**: `cruise.agreements` counts from the later of the class's last level change and
  its last shadow end, so an ended shadow needs fresh agreements.
- **FR-008**: `wuwei cruise shadow` prints the shadow table. The status line cruise part
  appends ` · shadow <classes>` for running and passed shadows. The day report adds a
  `## Cruise shadow` section.
- **FR-009**: Design 5.8.1 amendment "Shadow promotion"; invariant rows I13 (a shadow never
  changes a live route) and I14 (a raise lands only after a passed shadow) in 9.2 and their
  checks in `tests/test_invariants.py`; docs `configuration.md` and `concepts.md`.
- **FR-010**: Nothing here refuses: shadow, scoring and cards never block a command under any
  posture (#530).

### Key Entities

- Shadow row (`cruise.json`): `{level, started, scored, agreed, state, ended?, record?}`.
- Shadow answer (day state `decision_shadows`): `{class, level, option, at}`, written only by
  `decision route`.

## Success Criteria

- **SC-001**: The three issue acceptance scenarios pass as in-process tests.
- **SC-002**: I13 and I14 hold across the invariant grid; no new refusal anywhere.
- **SC-003**: Only the touched test files run green.

## Assumptions

- "What L<n+1> would have decided": the only place the cruise level changes a route is
  `cruise.rule` inside `mandate`. Records that leave `mandate` before it (one-way, written for
  the owner, novel, Strategic, thin Exploratory) route the same at any level, so they get no
  shadow row. The shadow answer is the recommendation when `cruise.rule` at the shadow level
  would answer, else no row.
- The reference is the final live outcome row of the record: an owner answer, or a mandate or
  cruise answer whose undo window closed. A reversal or an undo followed by another option is
  the disagreement. An undone record not yet answered is pending.
- The window has no expiry: after `shadow_days` with fewer than `shadow_min` scored, the
  shadow keeps running. Simplest rule that never lands an unscored raise.
- "Asked once": writing the card ends the shadow (state `ended`, reason `asked D-n`). A `keep`
  answer leaves the class at its level; a new proposal needs fresh agreements and a new
  shadow.
- The card is written at the next morning plan, not by the steward mid-day, because the
  issue keeps the morning-gate approval.
- The stored `scored` and `agreed` counts are refreshed by the steward only when they change,
  each with a ledger line, as #559 does for its sets.
- A raise card in today's state from before this feature (no shadow) no longer lands; the
  next morning starts a shadow for it.
- The #558 budget restore stays the one raise without a card or a shadow (design 5.8.1).
- Invariant ids I13 and I14; if another item lands them first, the builder takes the next ids.

### Builder amendments

- **A raise to L1 shadows at once.** `cruise.rule` answers only from L2, so a shadow at L1 would never score and the class could never leave L0. A shadow that targets L1 starts `passed` and gets its raise card in the same `propose`.
- **The report section is `## Cruise shadow`.** The day report already has a `## Shadow` section for #308 shadow refusals.
