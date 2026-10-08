# Feature Specification: Cruise mode

**Feature Branch**: `283-cruise-mode`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #283, feat(decisions): cruise mode: decision classes, levels,
auto-answer with undo, promotion from the ledger. Implements design 5.8.1 (#282) on top of
the #530/#544 mandate (MIT CISR class, `autonomy.mode`).

## Root cause

Cruise mode is designed (design 5.8.1) and half wired: nothing answers at a level, nothing
undoes, nothing moves a level.

- `cli/wuwei/decision.py:42-46` (`level`): the running level is never read (line 44:
  "memory/cruise.json (running level, #283) does not exist yet; the default stands in"), and
  `autonomy.mode = supervised` does not put classes at L0.
- `cli/wuwei/decision.py:31-32` and `cli/wuwei/workspace.py:141-143`: `margin`,
  `max_per_day`, `undo_minutes` and the promotion numbers are not in the config schema; the
  margin is a constant and a configured `decisions.cruise.margin` is an unknown key
  (`tests/test_workspace.py:1132`).
- `cli/wuwei/commands/decision.py:81-106` (`mandate`): every record the CLI takes is written
  `Decided-by: mandate`. The class level, the 5.8.1 conditions, the rule id, the daily
  budget, the undo window and the notification do not exist; `cli/wuwei/decision.py:130`
  accepts only `seat|owner|mandate` as `Decided-by`.
- `cli/wuwei/commands/decision.py:17-39`: there is no `decision undo`.
- `cli/wuwei/promotion.py:60-74` (`_target`): the promote writer knows charters, notes and
  voice; no writer exists for `memory/cruise.json`, so no level is ever raised or lowered.
- `cli/wuwei/commands/status.py:325-362` (`line`): no `cruise` part.

## How cruise fits the mandate

`decision route` stays the one routing point (#530). Under `autonomy.mode = autonomous` the
#530 mandate decides whether the CLI takes a record (Routine, Consequential, or Exploratory
that scores ahead; owner-written, one-way, Strategic and tied records go to the owner).
Cruise decides how a taken record is taken: when the record's class runs at L2 or L3 and
every 5.8.1 condition holds, it is a cruise answer (`Decided-by: cruise <class>@L<n>`; at L2
with a nudge and an undo window, at L3 in the digest); otherwise it stays a `mandate` answer
as today. Under `supervised` every class runs at L0, so the CLI answers nothing new (the
#530 legacy route is unchanged). `decisions.cruise.enabled = false` runs every class at L0
without touching running or configured levels.

## User Scenarios and Testing

### User Story 1: A clear two-way decision is answered with an undo (Priority: P1)

The owner runs the default (autonomous, cruise on). A class runs at L2. A seat writes a
two-way record inside the workspace with a wide margin. The CLI takes it, writes the rule
id, tells the owner, and the owner can undo it with one reply for `undo_minutes`.

**Independent Test**: neutral workspace in `tmp_path`; `memory/cruise.json` written through
the promote writer with `defer` at L2; a `Class: defer` record, `Reversibility: two-way`,
`Blast radius: workspace`, Confidence high, margin 0.47 (the `VALID` scores); run `decision
route D-3`, then `decision undo D-3`.

**Acceptance Scenarios**:

1. **Given** that record, **When** `wuwei decision route D-3` runs, **Then** it exits 0 and
   prints `mandate`; the record reads `Decided-by: cruise defer@L2` and `Outcome: A`;
   `decision_outcomes[D-3]` has `decided_by: mandate`, `rule: cruise defer@L2`, `class:
   defer`, `level: 2`, `at` and `undo_until` (`at` plus `undo_minutes`); one
   `decision.decided` event carries `decided_by: cruise defer@L2` and the same fields; no
   `decision_routes` entry exists.
2. **Given** the answer, **When** `wuwei nudges` runs, **Then** its first line is `nudge: D-3
   taken as A by cruise defer@L2, undo until <HH:MM>. Run: wuwei decision show D-3
   --widget`; **When** `decision show D-3 --widget` runs, **Then** it prints one widget with
   options `Keep` (Recommended) and `Undo` and record `wuwei decision undo D-3 --answer
   "<label>"`.
3. **Given** the answer and a listener transport, **When** `listen.notify` runs, **Then** the
   owner DM gets `D-3 taken as A by cruise defer@L2. Reply undo D-3 by <HH:MM> to ask
   again.` once, and a `decision.notified` event is written.
4. **Given** the open window, **When** `wuwei decision undo D-3` runs with the owner's
   confirmation (the card asked in the planner session, a y at the host terminal, or the DM
   reply `undo D-3`), **Then** it exits 0 and prints `owner: ask with wuwei decision show
   D-3 --widget`; the outcome is removed, `decision_routes[D-3]` exists, the record reads
   `Decided-by: owner`, `Outcome: pending` and a `Notes: Undone at ...` line; one
   `decision.reversed` event carries `undo: true`, the rule and the class; `defer` now runs
   at L1 and the ledger has a line naming `undo D-3` as the reason.
5. **Given** `--answer Keep`, **Then** undo exits 0, prints `kept` and writes nothing.
6. **Given** the window closed, **Then** undo exits 1 with `undo window closed at <HH:MM>;
   reverse it with wuwei decide D-3 <option>` and writes nothing; **given** a record with no
   L2 cruise answer, **then** undo exits 1 with `D-3 has no undo window; reverse it with
   wuwei decide D-3 <option>`.

### User Story 2: A thin margin goes to the owner (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the US1 record with the `LEAD` scores (margin 0.05), **When** `decision route`
   runs, **Then** it prints `owner` (Strategic: workspace blast radius, thin margin), writes
   a route with `class: defer`, `thin: true` and `at`, and no outcome.
2. **Given** three such thin escalations of `defer` in a row today while it runs at L2,
   **Then** after the third `defer` runs at L1 and the ledger line names `three thin-margin
   escalations` as the reason; a fourth thin record does not lower it again (at L1 it is no
   longer an escalation).
3. **Given** a Routine-by-definition record (`Class: approach`, own branch) with a thin
   margin, **Then** it prints `mandate` and is written `Decided-by: mandate` (the #530 rule
   is unchanged; it is neither a cruise answer nor an escalation).

### User Story 3: Config levels above a ceiling are refused (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `[decisions.cruise.levels] message = 2` (ceiling L1), **When** `wuwei config
   check` runs, **Then** it exits 1 naming `decisions.cruise.levels.message` and `above its
   ceiling L1`.
2. **Given** a record with `Class: autopilot`, **When** `wuwei decision lint` runs, **Then**
   it exits 1 naming `Class: expected one of`.
3. **Given** `margin = 0` or `margin = 1.5`, **Then** `config check` exits 1 naming
   `decisions.cruise.margin`; `margin = 0.3`, `max_per_day = 5`, `undo_minutes = 30`,
   `promote_agreements = 8` and `promote_days = 10` load.

### User Story 4: Levels move from the ledger (Priority: P1)

**Acceptance Scenarios**:

1. **Given** ten agreements in `defer` since its last level change and within
   `promote_days` (owner answers equal to the recommendation, or cruise answers whose undo
   window closed), `defer` at L0 and no raise card for `defer` in the window, **When**
   `wuwei plan propose` runs, **Then** it writes one owner record (`Decided-by: owner`,
   options `raise` "Raise defer to L1" recommended and `keep` "Keep defer at L0"), routes it
   to the owner, stores `cruise_cards[D-n] = {kind: raise, class: defer, level: 1}`, and
   `wuwei plan gate` prints its widget after the gate and grant widgets.
2. **Given** the owner answers `raise` with `wuwei decide D-n "<label>"`, **Then** `defer`
   runs at L1 and the ledger records the raise with the record as evidence; a level is never
   raised above the ceiling or the configured level.
3. **Given** nine agreements, or a level change of `defer` since the window started,
   **Then** no card.
4. **Given** the owner later answers a cruise-answered record with a different option
   (`wuwei decide D-3 B`), **Then** decide writes `decision.reversed` and the class is
   lowered one level with reason `reversal D-3`.
5. **Given** an escaped defect (5.6: a merged item a later builder brief names) on an item a
   cruise answer of class `retry` named, **When** the steward review runs, **Then** `retry`
   is lowered one level with reason `escaped defect <item> D-n`, once.
6. **Given** no weekly sample in the last seven days and a cruise answer in `defer` within
   them, **When** `plan propose` runs, **Then** it writes one owner record copied from that
   answer (`Decided-by: owner`, `Outcome: pending`) and `cruise_cards[D-n] = {kind: sample,
   class, option, source}`; `plan gate` prints its widget with the options in record order
   and no `(Recommended)` mark; an owner answer different from the cruise answer lowers the
   class with reason `weekly sample D-n`.

### User Story 5: The kill switch and the status line (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `decisions.cruise.enabled = false` and the US1 record, **When** `decision
   route` runs, **Then** no cruise answer is written (no `rule`, no undo window; the #530
   mandate takes it as `mandate`); `cruise.json` is unchanged.
2. **Given** cruise on with default levels, **Then** `wuwei status` prints `cruise L2`;
   **given** `enabled = false`, **then** `cruise off | L2`; **given** `defer` raised to L3,
   **then** `cruise L3`; **given** supervised, **then** `cruise L0`. The `merge` class is
   left out of the maximum (the merge policy answers it, 4.6). The part sits just before
   `meeting`; the rest of the line is unchanged.
3. **Given** supervised and the US1 record, **Then** `route` behaves exactly as #530
   supervised (`owner` or `seat`), and the seat mandate block lists every class as going to
   the owner.

### User Story 6: The digest lists cruise answers first (Priority: P2)

1. **Given** a mandate answer D-1 and a cruise answer D-2, **When** the watch digest runs,
   **Then** the text lists `- D-2: A (cruise defer@L2)` before `- D-1: A`.

### Edge Cases

- A second `route` of a cruise-answered record prints `mandate` and writes nothing.
- Daily budget: when `max_per_day` cruise answers exist today, the next eligible record is
  taken as `mandate` (no undo window), not sent to the owner.
- A record naming an item whose goal is `unplanned` is never a cruise answer (5.8.1
  ceiling); the mandate rule still applies.
- `Class: merge` records are never cruise answers here; merge stays with the merge policy.
- A record without `Class:` is never a cruise answer.
- An L3 cruise answer has no undo window: no nudge row, no DM, `--widget` prints `[]`; it is
  in the digest and the owner reverses it with `wuwei decide`.
- A damaged `memory/cruise.json` (not JSON, unknown class, non-integer level, symlink) makes
  `route` exit 2 and `status` print `unmeasured`, each with the reason.
- A seat cannot write `memory/cruise.json` (protect-state guard), and a proposal file in
  `days/<date>/proposals/` naming it is rejected by `wuwei promote`.

## Requirements

### Functional Requirements

- **FR-001**: `[decisions.cruise]` MUST accept `enabled` (default true), `margin` (float,
  default 0.2, refused unless 0 < margin <= 1), `max_per_day` (int, default 20, min 0),
  `undo_minutes` (int, default 60, min 1), `promote_agreements` (int, default 10, min 1),
  `promote_days` (int, default 14, min 1) and `levels.<class>` (unchanged: refused when
  unknown, outside 0 to 3 or above the ceiling).
- **FR-002**: The running level MUST live in `.wuwei/memory/cruise.json` (`{"levels":
  {class: n}, "changed": {class: iso timestamp}}`), read by `decision.running(root)` and
  written only by `promotion.cruise_level`, which validates the class and the range, writes
  atomically and appends a ledger line (`target .wuwei/memory/cruise.json`, action `raise`
  or `lower`, status `landed`, reason, evidence).
- **FR-003**: `decision.level(config, name, running=None)` MUST return 0 when cruise is off
  or `autonomy.mode` is supervised, else the lowest of the running level (the 5.8.1 default
  when absent), the configured level (the ceiling when absent) and the ceiling.
- **FR-004**: Under autonomous, when `mandate()` takes a record and all hold: `Class:` set
  and not `merge`; the class runs at L2 or L3; `Reversibility: two-way`; `Blast radius:`
  starts with `own branch`, `own PR` or `workspace` (case-insensitive); the 5.8.1 margin is
  at least `decisions.cruise.margin`; fewer than `max_per_day` cruise answers today; no item
  the record names has goal `unplanned`; then the answer MUST be a cruise answer: record
  `Decided-by: cruise <class>@L<n>`, outcome row `decided_by: mandate` plus `rule`, `class`,
  `level`, `at`, `items` (the items the record names) and, at L2, `undo_until`; the
  `decision.decided` event payload carries the same with `decided_by` set to the rule.
  Otherwise the #530 path is unchanged. The command prints `mandate` either way.
- **FR-005**: The decision lint MUST accept `Decided-by: cruise <class>@L<2|3>` for a known
  class and refuse any other `cruise` value.
- **FR-006**: `wuwei decision undo D-n [--answer <label>]` MUST, inside an open window and
  after the owner's confirmation (the `Undo` answer on its card in the planner session, a y
  at the host terminal, or `where` from the DM listener), remove
  the outcome, write the owner route, set the record to `Decided-by: owner`, `Outcome:
  pending` with a `Notes: Undone at <stamp> <where>.` line, write one `decision.reversed`
  event (`undo: true`, `rule`, `class`, `decided_by: owner`) and lower the class one level.
  `--answer Keep` writes nothing. No window, a closed window or a declined confirmation is
  exit 1 with the next command; unreadable input is exit 2.
- **FR-007**: `decision show D-n --widget` MUST print the Keep/Undo widget while an undo
  window is open and `[]` for any other mandate or cruise answer.
- **FR-008**: The owner DM reply `undo D-n` MUST run the same undo with `where = 'in the
  owner DM'`; `listen.notify` MUST send each L2 cruise answer once through
  `control_plane.notify` and write `decision.notified` (producer `wuwei listen`, silent).
- **FR-009**: `status.scan` MUST add a nudge row (source `decision.cruise`) per open undo
  window and sort those rows first; `nudges` MUST print them with the widget command;
  `status --line` MUST show `cruise L<max>` or `cruise off | L<max>` (max over classes but
  `merge`, as they would run with cruise on).
- **FR-010**: The watch digest MUST list cruise answers first, each with its rule.
- **FR-011**: `wuwei decide` on a cruise answer with a different option MUST lower the class
  one level (reason `reversal D-n`); owner and seat outcome rows MUST carry `class` (the
  owner row also `recommendation`) so agreements can be counted.
- **FR-012**: An owner route MUST carry `class`, `thin` (the class runs at L2 or L3 and the
  margin is below `decisions.cruise.margin`) and `at`; when the last three route or outcome
  rows of a class today, after its last level change, are thin routes, the class MUST be
  lowered one level (reason `three thin-margin escalations`).
- **FR-013**: `plan propose` MUST write the raise cards and the weekly sample cards of US4
  (state key `cruise_cards`, producer `wuwei plan propose`); `plan gate` MUST print their
  widgets; the owner answer through `wuwei decide` MUST land a raise (`raise`) or a sample
  reversal (an option other than the cruise answer) through `promotion.cruise_level`.
- **FR-014**: The steward review MUST lower a class once for an escaped defect on an item its
  cruise answer named after its last level change.
- **FR-015**: `memory/cruise.json` MUST be protected from agent writes (protect-state
  guard); `promote` MUST reject a proposal file targeting it.
- **FR-016**: Profiles MUST NOT lower `decisions.cruise.margin` or raise
  `decisions.cruise.max_per_day` over the workspace's values (`profiles.DENIED`).
- **FR-017**: No new refusal under observe or guarded. Undo findings are records-floor
  findings of an owner record command.
- **FR-018**: Docs: `docs/site/daily.md` (cruise answers, the nudge, undo by card, terminal
  and DM, the status part), `docs/site/reference.md` (`decision undo`, the `why` note),
  `configuration.md` and `concepts.md` (keys and levels, no "not built"), README "What ships
  today", the template config comment; `tests/test_docs.py` follows.

### Key Entities

- `memory/cruise.json`: running levels and last change per class (promote writer only).
- `decision_outcomes[D-n]` cruise fields: `rule`, `class`, `level`, `at`, `items`,
  `undo_until` (L2 only).
- `decision_routes[D-n]` new fields: `class`, `thin`, `at`.
- `cruise_cards[D-n]`: `{kind: raise, class, level}` or `{kind: sample, class, option,
  source}`.
- Event kinds `decision.notified` (wuwei listen) and `cruise.carded` (wuwei plan propose).

## Success Criteria

- **SC-001**: Every acceptance bullet of the item passes as a test on neutral fixtures: L2
  wide-margin auto-answer with rule, notification and undo; thin margin to the owner;
  ceiling refused by `config check` and the lint; promotion after N agreements and demotion
  with a reason; `enabled = false` behaves as L0 with `cruise off | L<max>`; guard, mutation
  and hook-level tests pass and the new state key and event kind are producer-only (the
  #114 inventory test).
- **SC-002**: The full suite passes. Existing #530 tests keep their assertions; only
  `tests/test_workspace.py:1132` (margin was unknown) and the docs test that asserts "not
  built" change.

## Assumptions

- Composition with #530: the mandate (newer, 2026-10-05) decides whether the CLI takes a
  record; cruise decides whether a taken record is a cruise answer with the 5.8.1 extras.
  This keeps every #530 acceptance (Routine-by-definition classes are taken at any margin)
  and principle #530 (no extra cards under autonomous). So "a thin margin goes to the owner"
  holds for a record the mandate does not take: the acceptance tests use a class raised to
  L2 with blast radius `workspace` (the item's "in-workspace"), where a thin margin is
  Strategic.
- "Supervised means every class at L0" (orchestrator note) is applied in `decision.level`,
  so it also shapes the seat mandate block and the status line.
- `decision route` keeps printing `mandate` for a cruise answer: the planner contract
  ("`mandate` or `seat` means decided") and its skill stay unchanged; the rule is in the
  record, the state and the event. The state keeps `decided_by: mandate` so close, report,
  next and the digest keep working; the event's `decided_by` is the rule, which telemetry
  and `why` already read.
- L1 behaves as L0 in this item: the owner card already lists the recommendation first and
  marked. Nothing extra is built for "preselected".
- The undo window runs from the answer, not from when the nudge reaches the owner
  (`ponytail:` comment; the listener has no delivery receipt).
- Undo reverts the recorded outcome and routes the record to the owner; work a seat already
  did on the outcome is not rolled back.
- "Propose and promote (6.8)" is realised as a CLI-written owner record (the proposal) asked
  at the morning gate through `plan gate`; the owner's answer is the approval (the #529/#548
  card pattern) and `promotion.cruise_level`, in the module behind `wuwei promote`, lands it
  with the ledger line. A seat-written proposal file cannot change a level. The cards are
  written by `plan propose` (the gate's writer) because `plan gate` writes nothing and
  proposals are per day.
- Agreements are counted from CLI-written day state (`decision_outcomes`) after the class's
  last level change; every reversal lowers a class, so "no reversal in the window" is "no
  level change since the counting start". One raise card per class per `promote_days`.
- The owner's calibration weights do not exist on main (#279 records no Wants weights), so
  the margin uses the record's weights.
- The thin-margin streak is counted within one day (`ponytail:` comment).
- The escaped-defect attribution reuses the 5.6 escaped measure in `metrics` (a merged item a
  later builder brief names).
- Messages to people, scope agreed with other people and trust-boundary findings stay with
  the owner through their classes' ceilings, `Decided-by: owner` and the one-way rule; no
  text matching is added.
- `tests/test_invariants.py` is not on this base. If it exists at build time, each rule
  above gets its row in the design section 9 table and in that test.

## Deferred

- The `merge` class levels (L2 nudge at the soak window, L0/L1 owner merges) belong to the
  merge policy (4.6) and are not changed here.
- Owner calibration weights for the margin, when the interview records them.
