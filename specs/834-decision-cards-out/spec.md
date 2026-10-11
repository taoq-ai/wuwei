# Feature Specification: delete decision cards, decide and steward steering; owner decisions come from next on one card

**Feature Branch**: `b4-setup-records` (feature directory `specs/834-decision-cards-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #834, part 14 of the #789 deletion pass: "chore(decisions): delete decision
cards, decide and steward steering; owner decisions come from next on one card".

## Context

Today an owner decision is a decision record (`days/<date>/decisions/D-<n>.md`):

- seats and the CLI write them;
- a guard lints them on write;
- `wuwei decision route` classifies them (CISR classes, the mandate, `autonomy.mode`);
- `wuwei decision show --widget` and `wuwei decide` ask and record the owner's answer.

Around them sit:

- external waits and negotiation loops (design 5.8.2);
- the watch's two-way decision digest;
- the steward's steering notes, which the planner must `steward ack` before it dispatches;
- the steward tool-call trigger (`steward.every_tool_calls`, `steward.due`);
- the decision guard: record lint, question citation, and the seat stop check.

Each makes a seat, the planner or the owner reason about the process: which class, which
route, which record to cite, which note to acknowledge. The owner decided (2026-10-11):

- what reaches the owner comes from `wuwei next` as one named decision on an Owner step card
  (#831);
- a seat assumes and records two-way choices in its spec.

The process checks stay in code: the round cap, gates at head, the merge policy.

Parts 12 (#832) and 13 (#833) are done on this branch:

- `commands/setup.py` is gone, and `card_write`, `_from_card`, `assignment` and `declared`
  live in `commands/config.py`;
- `decision.py` takes `ROLES` from `commands.agents`;
- the decision guard's `TOPICS` is `{'goals'}`.

`tests/test_reasons.py` has five LEFT rows naming part 14. The #831 handoff says this part keeps
two things and moves them out of the decision guard: the Owner step branch of `record_gate`,
and the `wuwei hook` refusal in `guards/protect_state.py`.

## Owner decisions after this part

| Decision | Where it comes from | The card | Yes | No |
| --- | --- | --- | --- | --- |
| Morning gate | `next` `gate` row | `wuwei plan gate` (unchanged) | `plan approve` | change something |
| Merge policy not cleared, owner_merge | `next` `merge` row (#816, #831) | `bin/wuwei merge <pr>` | merges | `plan park` (unchanged) |
| ESCALATE verdict, rounds left | `next` `verdicts` row | `bin/wuwei dispatch next <item>` | opens the fix round | the CLI parks the item |
| A builder's `Blocked:` line at gate entry | `next` `verdicts` row | `bin/wuwei dispatch next <item>` | the gates run, the answer in their briefs | the CLI parks the item |
| Critical scanner chain today | `next` `close` row | `bin/wuwei close` | the day closes | the day stays open |
| Round cap spent | `next` `verdicts` row, once, when the CLI parks the item | `bin/wuwei plan resume <item>` | resumes the item after the design change in its spec | it stays parked |
| Any other parked item (build limit, scanner chain, owner park) | the refusal or line that parked it names it | `bin/wuwei plan resume <item>` | resumes the item | it stays parked |
| Scope change a reviewer asks on a PR | `next` `pr` row, `wuwei pr act` | `bin/wuwei pr act <pr>` | opens a fix round for it | the thread waits for the owner |

Still on decision records until their parts land: the learning cards of `outbound learn`
(part 16) and the MCP registry decisions (part 18).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A gate's ESCALATE reaches the owner on one card; PARK parks in code (Priority: P1)

**Why this priority**: the pass plan names it an owner decision. The old path routed it by
class, and under observe and guarded took the recommendation without the owner.

**Independent Test**: an item at the gate with an ESCALATE verdict, rounds left; another with a PARK verdict.

Lead call (2026-10-11): a PARK verdict parks the item in code with its reason (`plan.disposed`,
shown in the report and `why`) and no card; only ESCALATE asks. A later `plan resume` on the
owner's Yes counts as Yes to the verdict that parked it and opens the fix round.

**Acceptance Scenarios**:

1. **Given** an ESCALATE verdict at the current head and rounds left, **When**
   `wuwei dispatch next <item>` runs with no recorded answer, **Then** it exits 1. It prints
   the Owner step card for `bin/wuwei dispatch next <item>` with a token bound to the verdicts
   asked. It writes no decision record and changes no state.
2. **Given** the owner answered Yes on that card, **When** it runs again, **Then** it opens
   the fix round with the blocking findings, as a FIX verdict does.
3. **Given** the owner answered No, **When** it runs again, **Then** the item is parked with
   the reason `gate <role> <VERDICT>: <finding>`, and no record is written.
4. **Given** that item, **When** `wuwei next` runs, **Then** its `verdicts` row has the
   command `wuwei dispatch next <item>` and the Owner step `then`. Other items' rows stay in
   `rows`.
5. **Given** a new verdict in a later round, **When** it runs, **Then** the earlier answer
   does not count (a new token).

### User Story 2 - Parks reach the owner, and only the owner resumes (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an item whose blocking finding remains at the round cap, **When**
   `dispatch next` runs, **Then** the CLI parks the item with the cap reason, and `next`
   returns one `verdicts` row whose command is `wuwei plan resume <item>`.
2. **Given** a parked or escalated item, **When** `wuwei plan resume <item>` runs without the
   owner's Yes, **Then** it exits 1 with its Owner step card. With the Yes, it returns the item
   to its resume phase and queues it.
3. **Given** a build that hits its iteration limit or repeats one failure, **When** it parks,
   **Then** `build check` prints a line naming `wuwei plan resume <item>`, and no record is
   written.
4. **Given** a scanner chain on a seat's session, **When** the watch sees it, **Then** the
   affected items park, the finding is recorded and pages as today, and no record is written.
5. **Given** `wuwei plan park|carry <item>` at close, **When** it runs, **Then** the item
   carries a `disposition` (`parked` or `carried`, with the reason) in the day state and one
   `plan.disposed` event. `next`, `close` and the report read it.

### User Story 3 - A reviewer's scope change waits for the owner (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an owed review thread whose text asks a scope change, **When** `wuwei pr act`
   runs with no answer, **Then** it exits 1 with the Owner step card for `bin/wuwei pr act
   <pr>`. The card's token is the thread fingerprint, and its detail quotes the thread.
2. **Given** Yes, **When** it runs again, **Then** it opens the fix round with the thread as
   feedback. **Given** No, **Then** it treats the thread as deferred to the owner and goes on
   to the next owed thread.

### User Story 4 - Seats assume and record; nothing routes or acknowledges (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a seat's launch prompt, **When** it is built, **Then** its mandate has three fixed
   lines and no decision class:
   - decide alone what the brief, the charter and the standards answer;
   - record two-way choices under `Assumptions:` in the spec or PR body;
   - name a one-way, scope, goal or trust-boundary question in your result (a sentinel's
     ESCALATE, a builder's `Blocked:` line).
2. **Given** a Write of `days/<date>/decisions/D-1.md`, an AskUserQuestion without a record
   id, or a seat stopping on a question, **When** the hook runs, **Then** nothing refuses or
   notes it. No decision guard is registered.
3. **Given** a third fix round, **When** `dispatch next` runs, **Then** no steward note blocks
   it, and `wuwei steward ack` does not exist.
4. **Given** 250 tool calls, **When** traces are recorded, **Then** no `steward.due` event is
   written, and `next` has no tool-call steward row. The steward still runs at sweep and close.
5. **Given** the CLI, **When** `wuwei decide`, `wuwei decision` or `wuwei steward ack` runs,
   **Then** argparse refuses it.

### User Story 5 - The Owner step recording and the hook refusal stay (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a main session answering an Owner step card, **When** PostToolUse
   AskUserQuestion runs, **Then** `gate.asked` records the topics as today (#831), from the
   new `guards/answers.py`.
2. **Given** `bin/wuwei hook PostToolUse` as a Bash command, **When** PreToolUse runs,
   **Then** `protect_state.check_bash` refuses it with exit 2, as today.
3. **Given** an AskUserQuestion with an Owner step question, **When** PreToolUse runs,
   **Then** nothing refuses it.

### Edge Cases

- Day state from before the upgrade may hold `decision_routes`, `decision_outcomes`,
  `steward_notes`, `steward_acks`, `negotiation_loops`, `scanner_decisions` and
  `pr_action_decisions`. Nothing reads them for items, and the state allowlist keeps
  accepting them as legacy keys for one day.
- An item parked before the upgrade with `decision: D-n` resumes with `plan resume`. Its
  record is ignored.
- A PR disposition is bound to the marker `WUWEI <kind> <ref> <day>`; old markers carrying a
  D-n no longer verify. The owner posts a fresh one.
- The verdict files stay at `days/<date>/decisions/gate-<name>.md`. Only `D-*.md` records go.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `dispatch.next_step` MUST park the item in code on a PARK verdict (no card) and
  MUST ask the owner on ESCALATE through `sessions.owner_answer` for
  `bin/wuwei dispatch next <item>`:
  - Yes opens the fix round;
  - No parks the item;
  - no answer returns `{'action': 'escalate', 'reason', 'command', 'card'}` (the action name
    callers already treat as exit 1), and the `dispatch next` command prints it and exits 1.

  `CARD`, `_card` and the routing under strict MUST go.
- **FR-002**: At the round cap, `dispatch.next_step` MUST park the item through `plan.park`
  (state only) and return the owner action naming `wuwei plan resume <item>`.
- **FR-003**: `wuwei plan resume <item>` MUST move a parked or escalated, blocked item to its
  `resume_phase`, queued, only when `sessions.needs_owner` is None. Otherwise it refuses with
  the card.
- **FR-004**: `plan.dispose`, `build._park`, `scanner._trace_response` and
  `pr_actions._thread` MUST write no decision record:
  - dispositions live on the item;
  - parks are state plus an event;
  - the scope thread uses `sessions.owner_answer`.
- **FR-005**: `sessions.owner_answer(root, command, detail, token='')` MUST return `'Yes'`,
  `'No'` or None from today's recorded answers. `needs_owner` MUST be `None` exactly when it
  is `'Yes'`. Its refusal text MUST be unchanged.
- **FR-006**: These MUST be deleted with their tests, keeping the record library that parts 16
  and 18 still call (plan.md):
  - `guards/decision.py`;
  - `commands/decision.py` and `commands/decide.py`;
  - from `decision.py`: lint, route, show, waits, naming and the classes and mandate;
  - `steward.review`, `pending`, `acknowledge`, `negotiation`, `decision_queue` and
    `maybe_run_for_tool_calls`, with `wuwei steward ack` and the `tool-calls` trigger;
  - the watch decision digest and external waits.
- **FR-007**: `record_gate` and its helpers MUST move to `guards/answers.py` (PostToolUse
  AskUserQuestion, area `records`). It keeps three branches: the Owner step, the D-n card hash
  topics (learning cards, MCP) and the Draft topics. The gate-question and `goals` topics go.
- **FR-008**: The learning card's answer path MUST move from `decide` to
  `wuwei outbound answer <D-n> "<label>" --card <hash>` (the narrowed `owner_outcome`), and its
  widget MUST name that command. Part 16 deletes it.
- **FR-009**: `next`, `close`, `closing`, `status`, `memory.constraints`, `sessions` take-over,
  `why`, `report`, `retro` and `doctor` MUST NOT read item decision records or routes. The
  pending-decision rows, the close-holding decision row, the `steward` due row, the trace
  decisions fix and the decision sections go.
- **FR-010**: The config keys `autonomy`, `decisions`, `steward` and `owner.verbosity.digest`
  MUST go into `workspace.RETIRED` and out of the schema and template. Charters, skills, the
  generated agents, the design spec, the docs and README MUST name no decision record,
  `decide`, route, mandate class, steward note or tool-call trigger. The part 14 LEFT rows
  MUST be deleted.

### Key Entities

- **Owner action** (`dispatch.next_step`): `action: 'escalate'`, `reason`, `command` (the
  command whose Owner step card decides), `card` (`sessions.owner_card` for that command).
- **Item disposition**: `items.<item>.disposition = {'kind': 'parked'|'carried', 'reason': str}`.

## Success Criteria *(mandatory)*

- **SC-001**: Every owner decision that reached the owner before reaches the owner from `next`
  or from the command that parked the item, on one Owner step card. Each row of the table
  above has a test.
- **SC-002**: No item path writes `days/<date>/decisions/D-*.md`. A walked fixture day
  (`tests/test_path_day.py`) writes none.
- **SC-003**: `grep -rnE "wuwei decide|decision show|decision route|decision lint|decision template|steward ack|steward_notes|every_tool_calls|tool-calls|cisr|mandate class|autonomy\.mode|decision record"`
  over `cli/`, `charters/`, `skills/`, `agents/`, `hooks/`, `templates/` and `docs/site/`
  returns only `mcp.py` and `commands/outbound.py` (parts 18 and 16).
- **SC-004**: Every touched test file passes. No test is loosened: a deleted test covers only
  deleted code, and the round cap, gate-at-head, Owner step and hook refusal tests keep their
  assertions.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. ESCALATE waits for the owner in every posture; a PARK verdict parks the item in code
   (lead call). The waiting item blocks only itself. No parks it in code, so a declined card
   never stalls, and a later `plan resume` opens the fix round.
2. The round cap keeps parity. The CLI parks at the cap, as today, and the owner's choice is to
   resume after a design change. A resume without one parks again at the next dispatch, as
   the old `keep` answer did. No fix round runs past the cap.
3. `plan resume` is the one new subcommand. It replaces the item-resume branch of
   `decide`/`owner_outcome`, the only way a parked item came back. It asks the owner, as that
   path did.
4. `sessions.owner_answer` is the smallest change that reads a No. It lets the code apply the
   safe choice instead of asking the same card again.
5. The learning cards (part 16) and the MCP decisions (part 18) keep their records until their
   parts. `decision.py` keeps what they call, and nothing else. The `decide` command goes now,
   and the learning card gets its own `outbound answer`, so no `decide` survives.
6. `decision_routes` and `decision_outcomes` stay as state keys while the learning card writes
   them. No item path reads or writes them.
7. A reviewer's scope ask is the "scope" owner decision. A seat's own scope question surfaces
   as a sentinel ESCALATE (US1) or a builder's `Blocked:` line that the gate reads.
8. Telemetry and metrics keep their decision counts (owner kept telemetry). With no item
   records they read zero, and parts 16 and 18 take the last producers. Their schemas do not
   change here.
9. `autonomy.mode` goes. It fed only the mandate, the routes and one outward warning; the
   outward lint under non-strict passes the internal-state word without the supervised event.
10. The design spec sections on the decision framework (5.2 mandate and records paragraphs, 5.4,
    5.5, 5.8, 5.8.1, 5.8.2) are rewritten as part of the owner-approved #789 pass.
