# Feature Specification: after a gate blocks, next offers the fix round or the decision card and writes the record the gate asked for

**Feature Branch**: `732-next-after-block`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #732 (owner, 2026-10-10, item 59): after the quality gate blocked,
`dispatch next` reported `escalate` and `build next` reported `done`; neither offered a fix
round or a card, and nothing wrote the decision record the gate asked for. Deliver: a
blocking verdict routes to a fix round (`build next` names it, with the findings), a
decision card (written by `dispatch` from the verdict's decision request, routed to the
planner below strict) or a park with its record; `escalate` always carries the card id and
the next command; `build next` and `dispatch next` agree (#666). The retro lists blocks and
what followed.

## Root cause

### What the owner saw

In the owner's dry-run workspace (day 2026-10-10, a dependency-bump item) arch and security
returned PASS and quality returned `Verdict: ESCALATE` with one finding marked
`blocks: yes (owner choice, not a fix round)` and two options for the owner in the finding
text. The day's events show the plugin was 0.24.1. `build next` answering `done` for an item
at its gates is the #666 defect, fixed in 0.26.0 (`cli/wuwei/commands/build.py:41` now asks
`dispatch.next_step`). What remains on `main` is a dead end that both commands now share.

### Reproduced on `main`

In-process on a temporary workspace (the `root`, `built` and `record` helpers of
`tests/test_dispatch.py`): a completed build at `gate`, arch and security PASS, quality
ESCALATE with a blocking finding. Two rounds of `wuwei dispatch next A` then
`wuwei build next A <brief> <worktree>` print:

```text
dispatch next A -> exit 1 {"action": "escalate", "reason": "gate parked or escalated"}
build next A    -> exit 1 {"action": "escalate", "reason": "gate parked or escalated"}
dispatch next A -> exit 1 {"action": "escalate", "reason": "gate parked or escalated"}
build next A    -> exit 1 {"action": "escalate", "reason": "gate parked or escalated"}
phase gate, no decision record in decisions/
```

### Defect 1: a PARK or ESCALATE verdict is a bare `escalate` with no record

`cli/wuwei/dispatch.py:361-364` (any PARK or ESCALATE among the verdicts received so far)
and `cli/wuwei/dispatch.py:374-375` (after every verdict is in) return
`{'action': 'escalate', 'reason': 'gate parked or escalated'}`. No card is written, no id
or command is returned, the phase does not move, and every later call returns the same
line. The charter says PARK "records a decision" (`charters/_common.md:24`), but no code
writes it. The only record writer reachable from here is `wuwei next`, whose `verdicts` row
(`cli/wuwei/commands/next.py:389-391`) turns any `escalate` into `wuwei plan park <item>`,
a park the gate never asked for.

### Defect 2: the round-cap park and the used-round escalate carry no record

`cli/wuwei/dispatch.py:384-392` (#623, a blocking finding at the round cap) and
`cli/wuwei/dispatch.py:345-346` (`fix round already used`, reached only after a manual
transition) return `escalate` with a reason and nothing else. The park record is left to
`wuwei next` (`plan park --reason`), so `dispatch next` and `build next` never name it.
`plan.dispose` (`cli/wuwei/plan.py:720`), the one park-with-record writer, parks the item
without linking the record on it, so the owner's answer on that record
(`cli/wuwei/commands/decision.py:231-239`) never resumes it.

### Defect 3: a parked item answers `done` from `build next`

`build.py:41` asks `dispatch.next_step` only at `gate` or `delta`. Once an item is parked on
a record, `build next` returns the build record's stale `done`, and `dispatch next` refuses
with "not at a gate; run bin/wuwei build next": a loop between the two commands.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is "the verdict's decision request"? A: A `Verdict: PARK` or `Verdict: ESCALATE`
  verdict. The charter already defines both as a request for a decision (PARK "records a
  decision", ESCALATE is "an owner-only choice"). No new verdict row is added: the card
  names the verdict file, which holds the sentinel's findings and options.
- Q: What does the card offer? A: Two options, `fix` (open a fix round on the gate's
  findings; the builder reads the verdict file) and `park` (park the item on this card). Its
  recommendation follows the verdict: `park` for PARK, `fix` for ESCALATE. `Class: park`,
  two-way, blast radius own branch, `Outcome: pending`.
- Q: Who answers it? A: Below strict the planner: the card is written `Decided-by: seat`
  and the command is `wuwei decision route <D-n>` (autonomous takes the recommendation
  under mandate, supervised records the seat outcome). Under strict the owner: the card is
  written `Decided-by: owner`, routed to the owner when written, and the command is
  `wuwei decision show <D-n> --widget`. A card the route sent to the owner (novelty, an
  uncalibrated role) also answers with the widget command.
- Q: What follows the answer? A: `dispatch next` reads the recorded option. `fix` opens the
  fix round for every blocking gate (FIX, PARK and ESCALATE) and answers `fix`; `park`
  parks the item with the card linked on it and answers `escalate` with the card and the
  owner's widget command. The owner reverses a planner's park with `wuwei decide <D-n> fix`,
  which resumes the item; the next `dispatch next` opens the round.
- Q: When is the card written? A: Once all gate verdicts of the round are in, like a FIX
  round. The early return at `dispatch.py:361-364` is deleted, so the other gates still run
  and one fix round covers every blocking gate.
- Q: What if no fix round remains? A: The cap rule (#623) wins: the item parks with its
  record (the `plan.dispose` park record, now linked on the item), whatever the verdict.
  The `fix round already used` branch parks the same way.
- Q: What does a parked item answer? A: An item at `parked` or `escalated` with a linked
  record answers, from both commands, `escalate` with that record id and
  `wuwei decision show <D-n> --widget`. This deliberately changes the #666 edge case "a
  build done on a parked item answers done" for parked items with a linked record.
- Q: What does "the retro lists blocks" mean? A: A `## Blocks` table in the steward retro:
  one row per non-PASS gate verdict of the day with what followed (the card and its answer,
  the park and its record, or the fix round).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A gate's decision request becomes a card both commands name (Priority: P1)

The planner runs `dispatch next` after a quality gate returned ESCALATE. It gets the card
id and the command that answers it; `build next` prints the same. After the answer the
item moves on.

**Why this priority**: the reported defect; the planner loop stalls on a bare `escalate`.

**Independent Test**: the `root`, `built` and `record` helpers in `tests/test_dispatch.py`,
then `main(['dispatch', 'next', 'A'])` and `main(['build', 'next', 'A', ...])`.

**Acceptance Scenarios**:

1. **Given** item A at `gate` with a completed build, arch and security PASS and a quality
   ESCALATE verdict, posture below strict, **When** `dispatch next A` runs, **Then** it
   writes `D-1` (Class park, options fix and park, recommendation fix, `Decided-by: seat`),
   exits 1 and prints `escalate` with `decision: D-1` and
   `command: wuwei decision route D-1`; **And** `build next A` prints the same object and
   exits 1; **And** a second `dispatch next A` writes no second card.
2. **Given** the same state under `security.posture = "strict"`, **When** `dispatch next A`
   runs, **Then** the card is written `Decided-by: owner`, `D-1` is in `decision_routes`
   and the command is `wuwei decision show D-1 --widget`; `build next A` prints the same.
3. **Given** scenario 1 and the planner ran `wuwei decision route D-1` (option fix
   recorded), **When** `dispatch next A` runs, **Then** it answers `fix` with
   `wuwei build next A`, the item is in `fix`, and the builder's feedback names the
   quality verdict file.
4. **Given** a PARK verdict instead (recommendation park) and the planner routed it,
   **When** `dispatch next A` runs, **Then** the item is `parked` with `decision: D-1`,
   the answer is `escalate` with `decision: D-1` and `wuwei decision show D-1 --widget`,
   and `build next A` prints the same.

### User Story 2 - A blocking finding without a decision is a fix round from both (Priority: P1)

**Why this priority**: the second acceptance line of the issue; it pins that the change
keeps the FIX path and the #666 agreement.

**Independent Test**: as above with a quality FIX verdict.

**Acceptance Scenarios**:

1. **Given** item A at `gate` with a completed build and a blocking FIX finding (no PARK or
   ESCALATE), **When** `dispatch next A` runs, **Then** it answers `fix` with
   `wuwei build next A` and writes no card; **When** `build next A` runs (either order),
   **Then** it prints the opened round's builder action, as #666 pinned.

### User Story 3 - No round left is a park with its record, named by both commands (Priority: P2)

**Independent Test**: the round-cap fixtures in `tests/test_dispatch.py` (`caps`,
`gate_fix`, `record` with `--round delta`).

**Acceptance Scenarios**:

1. **Given** a blocking delta finding at the round cap, **When** `dispatch next A` runs,
   **Then** the item is `parked`, a park record `D-n` exists with the finding in its
   Context and is linked as the item's `decision`, and the answer is `escalate` with the
   `round cap` reason, `decision: D-n` and `wuwei decision show D-n --widget`; a following
   `build next A` and `dispatch next A` print `escalate` with the same id and command.
2. **Given** that park, **When** the owner answers `wuwei decide D-n keep`, **Then** the
   item resumes to `delta`.
3. **Given** `wuwei next` on an item whose verdicts answer `escalate`, **When** it resolves
   the `verdicts` row, **Then** the row command is the answer's `command`, never
   `wuwei plan park`.

### User Story 4 - The retro lists blocks and what followed (Priority: P3)

**Independent Test**: `retro.compile` on a seeded day.

**Acceptance Scenarios**:

1. **Given** a day with a FIX verdict that opened round 1, an ESCALATE verdict on card
   D-1 answered fix, and an item parked on D-2, **When** `retro.compile` runs, **Then** the
   retro has a `## Blocks` table with one row per non-PASS verdict naming
   `fix round 1`, `card D-1: fix` and `parked: D-2`.

### Edge Cases

- Two gates return PARK or ESCALATE: one card, for the first in gate order; a `fix` answer
  opens one round for every blocking gate.
- A PARK or ESCALATE verdict with no `blocks: yes` finding still gets the card (the verdict
  is the request).
- The card is written once per verdict record: its id is stored on the record and a second
  call reads it. A race that finds the id already set writes nothing.
- A delta PARK or ESCALATE below the cap gets its own card on the delta record; a `fix`
  answer rotates it with the other records (#623).
- An item parked by the build loop (`builds.<item>.action.decision`) keeps today's answers.
- `wuwei dispatch next --all` carries the same `escalate` entries and already exits 1 on one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `dispatch.next_step` MUST, once every gate verdict of the round is in and a
  fix round remains, answer a PARK or ESCALATE verdict with a card: written once through
  `decision.write`, its id stored on the verdict record (`gate_verdicts[...]['decision']`)
  in the same state write, a `gate.card` event appended, and routed to the owner under
  strict.
- **FR-002**: While the card has no recorded outcome, `next_step` MUST answer
  `{'action': 'escalate', 'reason', 'decision', 'command'}` with the command from FR-003.
- **FR-003**: The command MUST be `wuwei decision show <D-n> --widget` when the card is in
  `decision_routes` or the item is parked on it, else `wuwei decision route <D-n>`.
- **FR-004**: A recorded `fix` MUST open the fix round for every blocking gate through
  `build.open_fix` and answer `fix`; a recorded `park` MUST park the item with
  `decision: <D-n>` and answer as FR-006.
- **FR-005**: A blocking gate with no fix round left (`rounds_used >= max_rounds`), and the
  `fix round already used` branch, MUST park the item through `plan.dispose` and answer
  `escalate` with the reason, the record id and `wuwei decision show <D-n> --widget`.
  `plan.dispose` MUST link the record as the parked item's `decision`.
- **FR-006**: `next_step` on an item at `parked` or `escalated` with a linked `decision`
  MUST answer `escalate` with that id and `wuwei decision show <D-n> --widget`; `build next`
  MUST print the same when its build is `done`.
- **FR-007**: A delta round MUST re-gate every gate whose initial verdict was not PASS
  (today only FIX): `next_step`, `delta_due`, `receive --round delta` and `opinion`.
- **FR-008**: `wuwei next`'s `verdicts` row MUST use the `escalate` answer's `command`.
- **FR-009**: The steward retro MUST carry a `## Blocks` table (item, gate and round,
  verdict, what followed).
- **FR-010**: `gate.card` MUST be a reserved event kind whose producer is
  `wuwei dispatch next`.
- **FR-011**: The design spec 9.2 table and `tests/test_invariants.py` MUST carry the new
  invariant (constitution, Workflow: a changed decision rule), the design spec's
  negotiation-budget bullet MUST carry a dated amendment line, and `docs/site/daily.md`
  (gate steps 4 and 5) MUST say what a PARK or ESCALATE verdict returns.

## Success Criteria *(mandatory)*

- **SC-001**: Tests pin US1.1 and US1.2 through `main` for both commands and both postures.
- **SC-002**: Tests pin US1.3, US1.4, US2.1 and US3.1 to US3.3.
- **SC-003**: The retro test pins US4.1.
- **SC-004**: The invariant walk passes with the new invariant; the full suite passes.

## Assumptions

- No orchestrator notes file existed for #732 at the path the task named. The failure was
  read from the owner's dry-run workspace for that day (read only) and reproduced
  in-process on `main` (Root cause).
- The owner's `build next` -> `done` came from plugin 0.24.1, before #666; on `main` both
  commands already agree on `escalate`. The remaining defect is the dead end itself.
- A decision request is a PARK or ESCALATE verdict; no `Decision:` verdict row is added, so
  the verdict format, the lint and the rendered sentinel agents stay unchanged. Overturn:
  sentinels need to name options the CLI can act on beyond fix and park.
- "Routed to the planner below strict" means the planner answers with
  `wuwei decision route`, which takes the card's recommendation under autonomous (mandate)
  and records the seat outcome under supervised. The planner does not pick another option;
  the owner can, with `wuwei decide`.
- The card does not copy finding text: its Context names the verdict file, so a sentinel's
  wording (dashes, pipes, newlines) never breaks the decision lint. The `escalate` reason
  carries the first finding's first line, as the round-cap reason already does.
- Deleting the early PARK/ESCALATE return lets the remaining gates run before the card, so
  one or two more seats may be spent; in exchange one fix round covers every blocking gate
  and the fix phase's "all initial verdicts" rule holds.
- `plan.dispose`'s question still reads "Park <item> at day close?" for a round-cap park;
  its Context carries the round-cap reason (as #623 already accepted through
  `wuwei next`). Rewording it is out of scope.
- The owner's answer on a linked park record resumes the item whatever the option
  (`commands/decision.py:231-239`, today's rule for build parks). A resumed round-cap item
  parks again on the next `dispatch next` with a fresh record until a design change lands
  (#623's "unpark after a design change"); defining that unpark flow is out of scope.
- Linking the `plan park` record on the item lets the owner's answer on it resume the item
  and lets `wuwei why` name it; no other reader of `items.<item>.decision` changes meaning.
- The charters keep their PARK and ESCALATE wording; the sentinels do not write the record
  themselves, `dispatch next` does.
