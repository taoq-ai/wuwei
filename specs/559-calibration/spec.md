# Feature Specification: Confidence calibration per class and per role

**Feature Branch**: `559-calibration`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #559: a Brier score per class and per role against outcomes gates
promotion, an uncalibrated class runs at most L1, and an uncalibrated role routes with high
ambiguity until it returns. Builds on #283 (cruise mode) and #558 (error budget), both on main.

## Root cause

Every decision record carries `Confidence: high|medium|low`, and routing trusts it as written:

- `cli/wuwei/decision.py:356-363` (`cisr`) treats ambiguity as low whenever Confidence is not
  low and the margin holds. Nothing checks whether a writer's "high" has been right.
- `cli/wuwei/cruise.py:151-189` (`propose`) raises a class after `promote_agreements`
  agreements with the error budget unspent. Agreement counts how often the owner agreed, not
  whether the stated confidence matched how often the record stood, so ten lucky agreements
  promote a class.
- The confidence is never stored where a reader could score it: `seat_outcome`
  (`cli/wuwei/decision.py:465-473`) builds the `decision.decided` payload and the
  `decision_outcomes` row without `Confidence`, and a record does not say which role wrote it.
  The #558 window reader `budget_classes.select` (`cli/wuwei/budget_classes.py:11-58`) already
  pairs taken records with their reversals, undos, samples and escaped defects, but only for
  cruise answers.

## User Scenarios and Testing

### User Story 1: An overconfident class is not promoted and runs at most L1 (Priority: P1)

The owner runs autonomous with cruise on. The CLI took 12 `defer` records in the last 14 days,
all written `Confidence: high`; the owner reversed or undid 5. The class's Brier score is
above the threshold, so the steward gets no raise card for it, and while it stays
uncalibrated it runs at most L1 (its records come to the owner as cards, never a refusal).

**Acceptance Scenarios**:

1. **Given** a class with 12 scored records, all high confidence, 5 reversed, **When** the
   steward runs, **Then** its Brier score (0.343) is above 0.15, `wuwei cruise calibration`
   shows it `uncalibrated`, `cruise.propose` writes no raise card for it, and
   `cruise.level` returns at most 1 for it whatever its running level and agreement count.
2. **Given** the same class later back at or below the threshold, **When** the steward runs,
   **Then** the cap lifts and the class runs at its running level again, with no card.
3. **Given** a class with fewer than `calibration_min` scored records, **When** promotion is
   checked, **Then** it gets no raise card (`too few`), and its level is not capped.

### User Story 2: A calibrated role routes as before (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a role with 10 scored records, all high confidence, that all stood, **When** the
   steward runs, **Then** the role is `calibrated` (Brier 0.01) and `decision route` of its
   next record routes exactly as before this feature.

### User Story 3: An uncalibrated role routes with high ambiguity (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a role whose Brier score crosses the threshold, **When** the steward runs and
   then `decision route` routes the next Routine record written `Role: <role>`, **Then** it
   routes as Exploratory (a Consequential one as Strategic, which goes to the owner as a card),
   and the status line shows `uncalibrated <role>`.
2. **Given** that role back at or below the threshold, **When** the steward runs, **Then**
   routing and the status line return to normal.

### User Story 4: The owner sees why (Priority: P2)

**Acceptance Scenarios**:

1. **Given** any scored records, **When** the owner runs `wuwei cruise calibration`, **Then**
   it prints one row per class (but merge) and per scored role: name, scored, Brier, state,
   and exits 1 when any row is `uncalibrated`, 0 otherwise, 2 on a damaged stream.
2. **Given** an uncalibrated role, **When** the day report and the steward retro are built,
   **Then** both carry a `## Calibration` section with the table and one line for that role
   naming the records that broke it (the reversal, undo, sample and escaped labels).

### Edge Cases

- A taken record whose undo window is still open is not scored yet.
- A record from before this feature (no `confidence` in its event) is not scored.
- A record without `Role:` scores for its class only.
- A damaged event stream or `cruise.json` fails closed (exit 2 with the reason), never clean.
- `decisions.cruise.enabled = false` or supervised: the cap and the routing change are moot
  for cruise levels (everything runs at L0); the table still prints.

## Requirements

### Functional Requirements

- **FR-001**: A decision record may carry an optional one-line `Role:` naming a shipped
  charter role; the lint refuses an unknown role. `decision template` and
  `charters/_common.md` show it.
- **FR-002**: `seat_outcome` adds `confidence` (and `role` when written) to the
  `decision_outcomes` row and the CLI-written `decision.decided` payload.
- **FR-003**: `wuwei.calibration_scores` scores, from the #558 window reader over
  `budget_window_days`, every record the CLI or a seat took (decided by seat, mandate or a
  cruise rule) with a stored confidence and a closed undo window: forecast high 0.9, medium
  0.6, low 0.3; outcome 1 when no reversal, undo, differing sample or attributed escaped
  defect names it, else 0; Brier is the mean of (forecast - outcome) squared, per class and
  per role.
- **FR-004**: State per row: `calibrated` when scored >= `calibration_min` and Brier <=
  `calibration_threshold`; `uncalibrated` when scored >= `calibration_min` and Brier above;
  `too few` otherwise.
- **FR-005**: Config `[decisions.cruise] calibration_threshold` (float, default 0.15, above 0
  and below 1) and `calibration_min` (int, default 10, at least 1).
- **FR-006**: The steward review (`steward.review`, after the budget step) writes the
  uncalibrated classes and roles into `memory/cruise.json` key `calibration` through the
  promote writer, with one ledger line naming the change and the records, only when the
  sets change.
- **FR-007**: `cruise.level` caps an uncalibrated class at L1. `cruise.propose` writes no raise
  card for a class that is not `calibrated`.
- **FR-008**: `decision route` (mandate and owner route) computes the CISR class with
  ambiguity high when the record's role is stored uncalibrated, Routine-by-definition records
  included. It never refuses.
- **FR-009**: The status line cruise part appends ` · uncalibrated <roles>` while any role
  is stored uncalibrated.
- **FR-010**: `wuwei cruise calibration` prints the table (FR-004) with exits 0, 1, 2.
- **FR-011**: The day report and the retro add a `## Calibration` section from one shared
  function.
- **FR-012**: Design 5.8 and 5.8.1 amended ("Calibration"), invariant row I12 in 9.2 and its
  check in `tests/test_invariants.py`; docs `concepts.md`, `reference.md`, `daily.md`,
  `configuration.md`.

### Key Entities

- Scored record: `{class, role, confidence, outcome, label}` derived per run, never stored.
- `memory/cruise.json` `calibration`: `{"classes": [names], "roles": [names]}`, the stored
  uncalibrated sets; written only by the promote writer, already refused to seats.

## Success Criteria

- **SC-001**: The three issue acceptance scenarios pass as in-process tests.
- **SC-002**: No new refusal under observe or guarded; the invariant test covers I12.
- **SC-003**: Only the touched test files run green; no network or real tool needed.

## Assumptions

- Role attribution: no hook-trusted role reaches `decision route` (seats share the planner's
  session id and the CLI gets no agent type), so the role is the record's own optional
  `Role:` field, as `Class:` is. A seat lying about its role only shifts its own score; the
  stored states and the events counted are CLI-written and protected.
- Scored population: records the CLI or a seat took (seat, mandate, cruise). Owner-answered
  records are not scored: "stood" (no reversal, undo window closed) is defined for taken
  records; the owner's agreement already feeds promotion.
- Fewer than `calibration_min` scored records is `too few`: it blocks promotion (calibration
  is required) but does not cap the level or change routing, so an upgrade does not drop the
  default L2 classes the day it lands. The cap and the routing change follow only a measured
  miscalibration ("falls out of calibration").
- A role that always writes `medium` and is always right scores 0.16 and is uncalibrated at
  the default threshold: Brier also penalises underconfidence. This follows the owner's
  mapping and threshold; the remedy is to write `high` when warranted.
- A Routine-by-definition record (retry, approach, park, accept-residual) from an
  uncalibrated role routes Exploratory too: the rule says the role routes with high
  ambiguity. Under the mandate an Exploratory record with a positive margin is still taken,
  so the practical change is ties and the Consequential to Strategic move.
- Same window as #558 (`budget_window_days`); no separate calibration window.
- The states are computed by the steward and stored; `decision route` reads the stored role
  set (cheap, one JSON read) rather than scoring 14 days of events per route. Promotion
  computes the table live, as #558's promotion gate already does.
- The invariant id is I12; if another item lands I12 first, the builder takes the next id.
