# Feature Specification: delete cruise, calibration scores, budget classes and the shadow report

**Feature Branch**: `b3-decision-framework` (feature directory `specs/814-cruise-scores-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #814, part 9 of the #789 deletion pass: "chore(decisions): delete cruise, calibration scores, budget classes and the shadow report".

## Context

Cruise mode (#282, #283) gives each decision class a level from L0 to L3. The level comes
from a running file (`memory/cruise.json`) that the steward moves. Three machines move it:

- an error budget per class (#558, `budget_classes.py`);
- a Brier score per class and role (#559, `calibration_scores.py`);
- a shadow that scores what a higher level would have answered (#560).

The levels feed four places:

- the mandate block of every seat prompt (`brief.mandate`);
- the `rule` and `undo_until` fields the mandate writes on a taken record;
- raise and weekly-sample cards at the morning gate;
- the status line.

The guard shadow report (`wuwei shadow report`) lists what guards would have refused under
the observe posture.

Each of these makes a model or the owner reason about the process: which level a class runs
at, whether a budget burns, whether a role is calibrated, what a shadow agreed. Decision
routing does not need any of it. `decision route` already decides in code:

- a two-way record inside the item is the seat's or the mandate's (`autonomy.mode`);
- a one-way, Strategic, tied or owner-written record goes to the owner;
- an owner route comes back from `wuwei next` as one named decision (`Decision D-n waits for
  your answer`).

`cruise.rule` never gated the mandate. It only decorated the record the mandate took.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Routing is fixed in code (Priority: P1)

A seat routes a record. Who decides follows the record's door, blast radius, CISR class and
`autonomy.mode` only. No level, budget, Brier score or shadow is read.

**Why this priority**: owner decisions are process control kept in code (pass plan, "Process
control kept": owner decisions from `next`). Every record that reached the owner before must
still reach the owner.

**Independent Test**: route records of each kind with and without a `memory/cruise.json` and
a `[decisions.cruise]` table in the config, and compare.

**Acceptance Scenarios**:

1. **Given** autonomous mode and a Routine two-way `park` record, **When** it routes, **Then**
   it prints `mandate`. The `decision.decided` payload has `decided_by: mandate` and no
   `rule`, `level`, `undo_until` or `items`. The record reads `Decided-by: mandate`.
2. **Given** a one-way, Strategic, tied or `Decided-by: owner` record, **When** it routes,
   **Then** it prints `owner` and `wuwei next` returns `Decision D-n waits for your answer`.
3. **Given** a stale `memory/cruise.json` that lowers `park` to L0 and stores role `builder`
   as uncalibrated, **When** a Routine `park` record with `Role: builder` routes, **Then** the
   route equals the one without the file.
4. **Given** supervised mode, **When** a two-way record on the own branch routes, **Then** it
   stays with the seat as today, and every other record goes to the owner.

### User Story 2 - The seat mandate is a fixed rule (Priority: P1)

A seat prompt's mandate block comes from `autonomy.mode` alone.

**Acceptance Scenarios**:

1. **Given** autonomous mode, **When** `brief.mandate` runs, **Then** "Decide and record" names
   the Assumptions rule and classes `retry, park, accept-residual, merge`. "Go to the owner"
   names `defer, scope-cut, re-plan, dependency-bump, design, boundary, refactor, message,
   other`.
2. **Given** supervised mode, **When** it runs, **Then** "Decide and record: none." and every
   class goes to the owner, `approach` first.
3. **Given** a `[decisions.cruise]` table or a `memory/cruise.json`, **When** it runs, **Then**
   the text equals the one without them.

### User Story 3 - Nothing names cruise, scores, budgets or the shadow report (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `wuwei cruise budget` or `wuwei shadow report` runs, **Then**
   argparse refuses it as an invalid choice (SystemExit 2).
2. **Given** a day, **When** the report and the retro are written, **Then** neither has
   `## Calibration` or `## Cruise shadow`. The day report keeps its `## Shadow` section of
   would-be guard refusals.
3. **Given** `wuwei status --line`, **When** it renders, **Then** no `cruise` token appears,
   even with a damaged `memory/cruise.json`.
4. **Given** `wuwei plan propose` and `wuwei plan gate`, **When** they run, **Then** no raise or
   sample card is written and the gate widget list has no cruise card.
5. **Given** `wuwei steward run`, **When** it reviews, **Then** it writes no `cruise.burn`
   event and no ledger line with target `memory/cruise.json`.
6. **Given** a config holding `[decisions.cruise]`, **When** it loads, **Then** it loads with
   an unknown-key warning (after #799), and `init --upgrade` removes it once
   `workspace.RETIRED` names it.

### Edge Cases

- Day state may still hold `cruise_cards`, `decision_shadows` and decision outcomes with
  `rule`, `level` and `undo_until`. Nothing reads them.
- Day events may hold `cruise.carded`, `cruise.burn`, `decision.shadow` and
  `decision.notified` rows. Their kinds leave `signal.SILENT` and the producer table, so on
  the upgrade day an old row may classify as a nudge.
- A record already written `Decided-by: cruise <class>@L<n>` before the upgrade reads as
  `mandate` on every read path (`wuwei close`, `decision show --widget`, the pending question),
  so `wuwei close` measures it. Lint, `decision.write` and the scanner refuse the form.
- `memory/cruise.json` stays on disk until removed. Nothing reads it, and it is no longer a
  protected record. Removal is listed for the lead with the retired files of part 10.
- `wuwei undo D-n` and `wuwei decision undo D-n` keep working on a mandate-taken record
  without a window check until part 10 (#815) deletes them. `wuwei undo rehearse decision`
  keeps passing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `decision route` MUST decide from the record fields, `autonomy.mode` and the
  existing day state only. It MUST NOT read cruise levels, budgets, calibration or shadows,
  and MUST NOT write `rule`, `level`, `undo_until`, `items`, `thin` or `uncalibrated`.
- **FR-002**: `decision.cisr` MUST take no `ambiguous` input. Each record's CISR class is its
  door, blast radius, confidence and margin.
- **FR-003**: `brief.mandate` MUST derive its lists from `autonomy.mode`. Under autonomous:
  assume `approach`; record `retry`, `park`, `accept-residual`, `merge`; the rest to the
  owner. Under supervised: record none; every class to the owner.
- **FR-004**: `decision.CLASSES` MUST be a tuple of the fourteen class names in today's
  order. Class validation, `telemetry.CLASSES` and `undo.KIND` keep reading it.
- **FR-005**: `Decided-by` MUST accept `seat`, `owner` and `mandate` only on a write; a stored
  `cruise <class>@L<n>` reads as `mandate`.
- **FR-006**: `decision undo` MUST NOT read a window. It reverts a mandate-taken row after
  the owner's confirmation, as `wuwei undo D-n` does. `decision show --widget` MUST return
  `[]` for a mandate-taken row.
- **FR-007**: These MUST be gone:
  - the modules `cruise.py`, `calibration_scores.py`, `budget_classes.py`,
    `commands/cruise.py`, `commands/shadow.py`;
  - the config table `decisions.cruise`;
  - the state keys `cruise_cards` and `decision_shadows`;
  - the events `cruise.carded`, `cruise.burn`, `decision.shadow`, `decision.notified`;
  - the writers `promotion.cruise_level`, `calibration`, `cruise_shadow`;
  - the steward budget, calibration and shadow steps;
  - the status `cruise` token and the `decision.cruise` attention row;
  - the report `## Calibration` and `## Cruise shadow` sections and the retro
    `## Calibration` section;
  - the plan cruise cards;
  - the `why` level step;
  - the profile refusals for `decisions.cruise.*`.
- **FR-008**: The guard shadow data stays: `guard.would_refuse` events, `report.shadow_lines`
  and the day report `## Shadow` section. `wuwei shadow report` goes, and every text that
  pointed to it names the day report's `## Shadow` section instead.
- **FR-009**: No charter, skill, generated agent, docs page, README, NOTICE or design spec
  section describes cruise levels, error budgets, Brier calibration, shadow promotion or
  `wuwei shadow report`.
- **FR-010**: The retired table `decisions.cruise` MUST be listed for `init --upgrade`
  removal: in `workspace.RETIRED` when the base has it, else under plan.md "RETIRED at
  rebase".

### Key Entities

- **Decision outcome** (`decision_outcomes.<id>`): option, score, decided_by, outcome,
  reversibility, blast_radius, item_disposition, cisr, class, confidence, role.
- **Decision route** (`decision_routes.<id>`): reversibility, recommendation, cisr, class,
  at, and `novel` until part 10.

## Success Criteria *(mandatory)*

- **SC-001**: Every touched test file passes; no test is loosened; only tests of deleted code
  are deleted.
- **SC-002**: `grep -rniE 'cruise|calibration_scores|budget_classes|brier|error budget|shadow report|decision_shadows|undo_until|uncalibrated'`
  over `cli/`, `charters/`, `skills/`, `agents/`, `hooks/`, `templates/`, `scripts/`,
  `.github/`, `docs/site/`, `README.md`, `NOTICE` and `docs/specs/2026-09-24-wuwei-design.md`
  returns nothing. CHANGELOG and earlier `specs/` keep their history. Tests may write a stale
  key only to prove it is ignored.
- **SC-003**: The same record and config route the same way whatever `memory/cruise.json`
  holds.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. "The shadow report" is the `wuwei shadow report` command. The data under it (the
   `guard.would_refuse` events and the day report `## Shadow` section) belongs to the
   observe posture. It stays until the posture becomes one boolean (pass part 15). The same
   goes for `guards.shadow_since` and `guards.shadow_days`, which drive the observe trial
   reminder, not the report.
2. The cruise undo window (#283) goes with cruise. `decision undo` and `wuwei undo D-n` stay
   one part longer without the window check, so `wuwei undo rehearse decision` keeps passing.
   Part 10 (#815) deletes both. This keeps measured reversibility unchanged between the two
   parts.
3. The class list stays: the `Class:` field, the CISR Routine-by-definition rule, telemetry
   and `undo.KIND` read it. Only its levels and ceilings go. The design spec keeps the class
   table under 5.8.
4. The `Role:` field stays an optional, validated record field (old records carry it). The
   charter drops "your stated confidence is scored per role" and the template drops
   `Role: builder`.
5. The uncalibrated-role bias (#559) goes. It only moved records toward the owner. With it
   gone, a role's records route by their own fields, as before #559.
6. A cruise answer added no route. The mandate takes the same records, so no record that
   reached the owner stops reaching the owner.
7. `decisions.cruise.enabled = false` was the kill switch. With no levels, there is nothing to
   switch. Supervised mode stays the owner's way to take every record.
8. A stored `Decided-by: cruise ...` reads as `mandate`; lint and writes refuse it, so no new
   record carries it.
9. The README principle about cruise is rewritten here into its end state for this batch. It
   also drops the novelty and undo text, so part 10 does not edit it again.
10. The design spec edits are part of the owner-approved #789 pass.
