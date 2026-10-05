# Feature Specification: Decision classes (MIT CISR) and fewer cards

**Feature Branch**: `530-decision-classes`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #530 part A: decision classes (MIT CISR) on every decision record, and
fewer cards: a question the owner would answer with the recommendation is not asked (owner
comments 1 and 2 of #530).

## Root cause

- `cli/wuwei/decision.py:349-351` (`route`): a record stays with the seat only when
  `Reversibility` is `two-way` and `Blast radius` is exactly the string `own branch` or
  `own PR`. Every other record goes to the owner as a card, including the template's own
  `Blast radius: Own branch and PR.` (`cli/wuwei/commands/decision.py:195`), any record whose
  blast radius is written in words, and every one-way record however clear its scores. The
  rule has no ambiguity axis and no owner setting for autonomy.
- `cli/wuwei/commands/decision.py:39-71` (`decide`, the `decision route` command) knows only
  two answers, `seat` and `owner`; `cli/wuwei/decision.py:124` accepts `Decided-by:` `seat`
  or `owner` only, so there is no way to record "taken under the mandate".
- `skills/wuwei-plan/SKILL.md:10` tells the planner to ask "a pending owner decision" with
  `decision show D-n --widget`, without routing first, and `charters/_common.md:28` (rule 2)
  sends everything but a two-way own-branch decision to the owner. So the planner asks how a
  fix round should run, whether to approve a builder's task round, and how a seat procedure
  should run: questions whose answer is the recommendation.
- `cli/wuwei/workspace.py` (`SCHEMA`) has no key for the owner's autonomous or supervised
  answer; nothing reuses an existing key for it (`decisions.cruise` feeds only the seat
  mandate text; cruise answering is not built, `templates/workspace/config.toml:259`).

## User Scenarios and Testing

### User Story 1: Routine questions are not asked under autonomous (Priority: P1)

The owner runs the default (autonomous). The planner writes a record for a fix round after
FIX verdicts, a builder's proposed task round and a parked item's next step. None of them
reaches the owner; each is decided as recommended and shows in the digest and the report.

**Independent Test**: a neutral workspace in `tmp_path` with default config; three records
(`Class: retry`, `Class: approach`, `Class: park`, blast radius `item`); run
`decision route D-n` for each.

**Acceptance Scenarios**:

1. **Given** autonomous (the default) and a fix-round record (`Class: retry`), **When**
   `wuwei decision route D-1` runs, **Then** it prints `mandate` and exits 0, the record now
   reads `Decided-by: mandate` and `Outcome: <recommendation>`, `decision_outcomes[D-1]` has
   `decided_by: mandate` and `cisr: Routine`, a `decision.decided` event carries the same,
   and no `decision_routes` entry and no `decision.routed` event exist (no card).
2. **Given** the same for a builder task round (`Class: approach`) and a parked item's next
   step (`Class: park`), **Then** the same holds, whatever their `Reversibility`, `Blast
   radius`, `Confidence` or margin (two-way by definition).
3. **Given** a mandate-decided record, **When** `wuwei decision show D-1 --widget` runs,
   **Then** it prints `[]` (nothing to ask).
4. **Given** the three mandate decisions, **When** the watch digest runs, **Then** it lists
   them; **When** the day report is built, **Then** its `Taken under mandate` section lists
   each with its record path and the reversal command `bin/wuwei decide D-n <option>`.

### User Story 2: Who decides follows the class (Priority: P1)

**Acceptance Scenarios** (all under autonomous, records outside the four Routine-by-definition
classes):

1. **Given** a two-way record with blast radius `item` or `day`, Confidence high or medium
   and margin at least 0.2, **Then** it is Routine and `route` prints `mandate`.
2. **Given** a one-way record (or `unsure`, or blast radius `repository`, `outside` or any
   text not starting with a known level) with Confidence high or medium and margin at least
   0.2, **Then** it is Consequential and `route` prints `mandate`; the report lists it first
   under `Taken under mandate`.
3. **Given** a low-risk record with Confidence low (or margin below 0.2) whose
   recommendation is strictly ahead of every other option, **Then** it is Exploratory and
   `route` prints `mandate`.
4. **Given** a low-risk record whose recommendation ties the best other option (margin 0),
   **Then** it is Exploratory and `route` falls back to the legacy rule: `seat` for a two-way
   record on `own branch` or `own PR` with `Decided-by: seat` (as today), otherwise `owner`
   (a card with the lens lines).
5. **Given** a high-risk record with Confidence low or margin below 0.2, **Then** it is
   Strategic and `route` prints `owner`.

### User Story 3: Supervised keeps today's cards (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `[autonomy] mode = "supervised"` and the three records of US1 with blast radius
   `item`, **When** `decision route` runs, **Then** each prints `owner`, a `decision_routes`
   entry is written with `cisr: Routine` and no mandate outcome exists (cards as today).
2. **Given** supervised and a two-way `own branch` record with `Decided-by: seat`, **Then**
   `route` prints `seat` (unchanged).

### User Story 4: No bare question (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a record whose `Recommendation:` is missing or blank, **When** `decision lint`
   runs, **Then** it exits 1 and the message contains `add the recommendation and the
   reasoning`.
2. **Given** a new record with a recommendation and no `Reasoning:`, **Then** the same
   message.
3. **Given** a valid record, **When** `decision lint` runs, **Then** it exits 0 and the OK
   line names the derived class, for example `OK: A (80), Routine`.

### User Story 5: The report counts by class (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a day with two Routine mandate decisions, one Consequential mandate decision
   and one Strategic card, **When** the report is built (brief and full), **Then** a
   `Decisions by class` section prints one line per class with its decisions and cards
   (`- Routine: 2 decisions, 0 cards`, `- Consequential: 1 decisions, 0 cards`,
   `- Exploratory: 0 decisions, 0 cards`, `- Strategic: 1 decisions, 1 cards`) and the line
   `Target: cards only for Strategic and for floors (publish, merge).`
2. **Given** the owner reversed a mandate decision with `bin/wuwei decide D-n <other>`,
   **Then** the decide command accepts it (a mandate outcome is a valid prior outcome), a
   `decision.reversed` event is written, and the record leaves the `Taken under mandate`
   list.

### Edge Cases

- Under autonomous, a record already routed to the owner (`decision_routes` holds its id)
  stays with the owner on a second `route`: `route` prints `owner` and changes nothing.
- Under autonomous, a record that already has an outcome (seat, mandate or owner) is not
  decided again by a second `route`: it prints the recorded `decided_by` and writes nothing.
  Under supervised the legacy path is unchanged.
- Records the CLI routes itself through `route_owner` (grants, outbound learn, MCP, remote,
  PR dispositions) keep their cards: they are floors or owner records, not `decision route`
  calls. They gain only the `cisr` field on their route entry, for the report counts.
- Close does not report a mandate-decided record as a pending owner decision.
- Old records and state without `cisr` are read as before and are not counted per class.

## Requirements

### Functional Requirements

- **FR-001**: The config MUST have exactly one new key, `autonomy.mode`, values `autonomous`
  or `supervised`, default `autonomous`. This part only reads it.
- **FR-002**: `decision.cisr(fields, scores)` MUST derive one of `Routine`, `Consequential`,
  `Exploratory`, `Strategic` from fields already in the record: `Class:` in `approach`,
  `retry`, `park`, `accept-residual` is Routine by definition; otherwise risk is low only
  when `Reversibility` is `two-way` and `Blast radius` starts (case-insensitive) with `item`,
  `own branch`, `own PR` or `day`; ambiguity is low only when `Confidence` is `high` or
  `medium` and the 5.8.1 margin is at least 0.2. The function is total over a record that
  passes `evaluate`.
- **FR-003**: The 5.8.1 margin MUST be one shared helper `decision.margin(fields, scores)`,
  used by `cisr` and by `why` (which computes it inline today).
- **FR-004**: Under autonomous, `wuwei decision route D-n` MUST decide as recommended (print
  `mandate`) a Routine or Consequential record, or an Exploratory record whose margin is
  above 0; every other record follows the legacy `route()` unchanged. Under supervised,
  `decision route` MUST behave exactly as today.
- **FR-005**: A mandate decision MUST write `decision_outcomes[D-n]` with `decided_by:
  mandate` and `cisr`, one `decision.decided` event with the same payload, and rewrite the
  record's `Decided-by:` to `mandate` and `Outcome:` to the recommendation. The lint MUST
  accept `Decided-by: mandate`.
- **FR-006**: Every outcome snapshot (`seat_outcome`) and every owner route entry
  (`route_owner`, state and `decision.routed` payload) MUST carry `cisr`.
- **FR-007**: `decision show D-n --widget` MUST print `[]` for a mandate-decided record.
- **FR-008**: `wuwei decide D-n <option>` MUST accept a mandate outcome as the prior outcome
  and record a reversal as it does for a seat outcome.
- **FR-009**: The decision lint MUST refuse a record with a missing or blank `Recommendation:`
  (any record) or a missing `Reasoning:` (new records) with a message containing `add the
  recommendation and the reasoning`; the OK line MUST name the derived class.
- **FR-010**: The watch digest MUST list mandate outcomes on a two-way door with the seat
  ones.
- **FR-011**: The day report MUST show, in brief and full, a `Taken under mandate` section
  before `Merged` (Consequential first, then by id; record path and `bin/wuwei decide D-n
  <option>`) and a `Decisions by class` section with decisions and cards per class and the
  target line. Counts come from `decision_outcomes` and `decision_routes`, both written only
  by the CLI.
- **FR-012**: Close MUST NOT report a mandate-decided record as a pending owner decision.
- **FR-013**: A calibration profile MUST NOT carry `autonomy.mode = "autonomous"` over a
  supervised workspace (added to `profiles.DENIED`).
- **FR-014**: `charters/_common.md` Decisions rule 2, the lead charter's routing line and
  the planner skill MUST say: route every record with `decision route D-n`; ask only on
  `owner`; the four two-way-by-definition cases and their `Class:` values. Short and plain.
- **FR-015**: No new refusal under observe or guarded. The only lint change is the message
  of an existing refusal (missing fields), which is the records floor.

## Success Criteria

- **SC-001**: The four acceptance bullets of the item pass as tests on neutral fixtures:
  autonomous mandate for the three Routine cases with digest and report, supervised cards,
  the no-recommendation refusal message, the per-class report counts.
- **SC-002**: The full suite passes. Existing tests whose subject is the owner card flow keep
  their assertions by setting `[autonomy] mode = "supervised"` in their workspace (that is
  today's behaviour); no other expectation changes except the lint OK line and where this
  spec changes behaviour.

## Assumptions

- The issue's acceptance "under supervised, the same decisions raise cards as today" and its
  scope "under supervised, Consequential and Exploratory also ask" are both met by keeping
  the legacy `route()` unchanged under supervised. Routine under supervised therefore stays
  as today (seat for a two-way own-branch record, owner otherwise).
- The key is `autonomy.mode` (the issue's example); part C of #530 writes it from the setup
  question. Nothing existing carries this meaning.
- The four two-way-by-definition cases are recognised by the existing 5.8.1 `Class:` field:
  a fix round after FIX verdicts is `retry`, a builder's task round and a choice between two
  seat procedures are `approach`, a parked item's next step is `park`; `accept-residual`, the
  fourth L2 default class, is included. The charters tell seats which class to write. No
  keyword matching on the question text.
- Blast radius stays free text. Its level is read from its first words: `item`, `own
  branch`, `own PR` (the item) and `day` are low risk; anything else, `repository` and
  `outside` included, is high risk ("when unsure, it is one-way", design 5.8). So a class can
  always be derived and the "no class" refusal reduces to the no-recommendation refusal.
- "Clearly above" uses the 5.8.1 margin and its documented default 0.2 as a constant;
  `decisions.cruise.margin` is not in the config schema and cruise answering is not built.
  A "tie" is a margin of 0 or less.
- Consequential under autonomous is decided at `route` time. The floors stay where they are
  enforced, at the action: publish and merge through the grant card (#478, #524), outward
  sends through the tiers and the umbrella, records through the records floor. A decision
  record does not wait for them.
- The posture (observe, guarded, strict) does not change decision routing; `autonomy.mode`
  alone does. An owner who wants every card picks supervised.
- Cruise levels (`decisions.cruise`) keep feeding only the seat mandate text; this part does
  not build cruise answering and does not read the levels for routing.
- The seat mandate block in launch prompts (`brief.mandate`) is unchanged: seats still write
  a record for those cases and `decision route` decides who answers.
- "Cards" in the report are owner routes (`decision_routes`), one per record; morning-gate
  and grant cards created by `plan gate` are counted when they route through `route_owner`.
- The `delivery-team` skill the owner mentions lives outside this repository and is out of
  scope.
- `tests/test_invariants.py` is not on this base. If it exists when this is built, the rule
  gets its invariant row in design section 9 and in that test (task T026).

## Deferred

- Telemetry `decided_by` counts (`cli/wuwei/telemetry.py:175`) ignore `mandate`; the shared
  telemetry schema is not changed here.
