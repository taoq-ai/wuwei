# Feature Specification: tickets are attached without the owner

**Feature Branch**: `636-tickets-from-card`
**Created**: 2026-10-10
**Status**: Ready
**Input**: GitHub issue #636, "fix(tracker): tickets are attached without the owner: the lead
proposes a ticket per item (an existing workstream issue or a draft) in the plan, the gate's
Approve records the links and creates the drafts, and tracker create and plan set ticket= run
from the planner after a card answer in every posture below strict". Owner, 2026-10-10: "I
don't want to interact at this level, this should be automated too." The plan was approved on
the card, but no item could start until the owner pasted terminal commands that linked items
to existing workstream issues and dropped a drafted issue.

## Problem (reproduced)

Reproduced read-only on `main` (db96bff) in a scratch workspace through the real hook
(`wuwei.commands.hook.run`, PreToolUse) and `tracker.check`, posture `guarded`, a tracker set
and `tracker.required` on:

- The registered planner session running `bin/wuwei plan set A ticket=ENG-1` is refused
  (exit 2): "Spec overrides are an owner action ... To link an existing ticket, the owner runs
  bin/wuwei plan set <item> ticket=<id> there; a seat runs bin/wuwei tracker create <item>."
- A seat (payload with `agent_id`) running `bin/wuwei tracker create A` passes (exit 0).
- `tracker.check` on an item with no ticket returns `A has no ticket: bin/wuwei tracker create
  A (opens one from the item's record) or bin/wuwei plan set A ticket=<id>`.

Root causes, with file and line on `main`:

1. `cli/wuwei/guards/protect_state.py` lines 87 to 92: `('plan', 'set')` is owner-only for
   every assignment except `docs=` (`_seat_docs_set`, line 150) and `pace=`
   (`_planner_pace_set`, line 161). Linking an existing ticket needs a host terminal in every
   posture, the planner included.
2. `cli/wuwei/outward.py` lines 676 to 680 with the default `tracker.auto` (`["progress",
   "pr", "close"]`, `cli/wuwei/workspace.py` line 105): `tracker create <item>` (class
   `items`) is held as a draft. Sending it is `drafts approve`, owner-only
   (`protect_state.py` line 50) unless the planner asked that draft on a card
   (`protect_state.py` lines 274 to 279). Nothing asks it, so the draft waits for the owner.
3. `cli/wuwei/plan.py` lines 240 to 249 (`propose`) and 281 to 290 (`gate_widget`) never show
   an item's ticket, so the owner approves without seeing which items lack one, and
   `charters/lead.md` never asks the lead for a ticket per candidate.
4. `cli/wuwei/plan.py` lines 363 to 379 (`approve`) record only a candidate's `ticket` field
   or a tracker-discovered id, then refuse every item without a ticket with the reason above:
   the card answer is lost and the owner is sent to a terminal.
5. `cli/wuwei/tracker.py` lines 35 to 48 (`check`): the one missing-ticket reason names
   terminal commands in every posture.
6. The guard lets any seat run `tracker create <item>` (it is not in `_OWNER_ACTIONS`), so a
   builder can open an item ticket nobody approved.

## Clarifications

### Session 2026-10-10

- Q: How does the lead express "a draft"? A: By leaving `ticket` out. `tracker create <item>`
  already builds the draft from the item's record (title from `scope`, body from evidence,
  goal and track, `tracker.py` lines 83 to 93), so no new proposal field is needed.
- Q: How does the owner pick "none" on Change something? A: The planner proposes again with
  `"ticket": null` for that item. Approve records it as the owner's none and the ticket rule
  treats it as skipped, like a tier in `tracker.skip_tiers`.
- Q: What is "tracker link"? A: There is no such verb on `main`; `plan set <item>
  ticket=<id>` is the link. No new verb is added.
- Q: How does Approve send a held ticket draft? A: The Approve answer listed the ticket's
  title, so it is the Send answer: `plan approve` runs `tracker.create` and, when the outward
  tier holds it, `drafts.approve` on that draft, in-process. `tracker.auto` and the outward
  tier table do not change.
- Q: Under strict? A: `plan approve` opens nothing and refuses, listing each missing item's
  `bin/wuwei tracker create <item>` for a host terminal, as today. Proposed links are recorded
  in every posture, as today (local records from the lead's discovery).
- Q: Why does `plan add` draft instead of sending, as Approve does? A: `plan add` runs all
  day and the guard does not restrict it to the planner, so a seat can reach it. Sending
  there would let a seat open a ticket nobody answered. A held draft is owner-gated by its
  Send card (#493), which shows the proposed title: that is the item's card.
- Q: Does the guard verify the card answer for the planner's `tracker create` and `plan set
  ticket=`? A: No, as for `plan set pace=` (#579): the registered planner session runs them
  below strict. `tracker create` still holds a draft whose Send is the owner's card answer;
  `plan set ticket=` writes a local record only after the tracker confirms the id.

## User Scenarios and Testing

### User Story 1 - Approve attaches every ticket (Priority: P1)

The owner approves the plan on the card. Items matching open workstream issues are linked,
the rest get a new ticket, and dispatch starts with no terminal command.

**Independent Test**: in-process `plan.propose`, `plan.gate_widget`, `plan.approve` with the
fake tracker port behind the real outward wrapper (`tests/fakes/tracker.py`), posture
`guarded`.

**Acceptance Scenarios**:

1. **Given** three candidates `A` (`"ticket": "ENG-1"`), `B` (`"ticket": "ENG-2"`) and `C`
   (no `ticket`), a tracker set and `tracker.required` on, **When** the plan is proposed,
   **Then** `plan.md` shows `Ticket: ENG-1 (existing)`, `Ticket: ENG-2 (existing)` and
   `Ticket: new <C's scope on one line>`, and the gate card's Approve description lists the
   three tickets.
2. **Given** that proposal and the default `tracker.auto`, **When** `plan approve --items A B
   C --goals-confirmed` runs, **Then** it exits 0, `tickets` holds `A: ENG-1` and `B: ENG-2`
   (source `candidate`) and `C: <the created id>` (source `create`), the port's `create` was
   called once, for `C`, the held draft is `sent`, and `tracker.check` returns `ticket` for
   all three, so dispatch starts.
3. **Given** the same under `observe`, **Then** the same result.
4. **Given** a candidate with `"ticket": null`, **When** approved, **Then** no ticket is
   opened, `tickets` records the owner's none, `tracker.check` returns `skipped` and one
   `tracker.skipped` event names the item.

### User Story 2 - Strict prints the commands (Priority: P1)

**Acceptance Scenarios**:

1. **Given** posture `strict` and candidate `C` without `ticket`, **When** `plan approve`
   runs, **Then** it exits 1, opens nothing (no port call, no draft), approves nothing, and
   its stderr names `bin/wuwei tracker create C` and `host terminal`.

### User Story 3 - A seat cannot attach tickets (Priority: P1)

**Acceptance Scenarios**:

1. **Given** any posture, **When** a seat runs `bin/wuwei tracker create A`, **Then** the hook
   refuses it with a reason naming the planner.
2. **Given** any posture, **When** a seat runs `bin/wuwei plan set A ticket=ENG-1`, **Then**
   it is refused.
3. **Given** `observe` or `guarded`, **When** the registered planner session runs either
   command, **Then** the hook passes it; under `strict` it is refused naming a host terminal.
4. **Given** any posture, **When** a seat runs `bin/wuwei tracker create --bug A "<title>"
   --evidence cli/x.py:1`, **Then** the hook passes it as today; `bin/wuwei tracker create A
   -- --bug` from a seat is refused.

### User Story 4 - The missing-ticket reason names the card (Priority: P2)

**Acceptance Scenarios**:

1. **Given** posture `guarded` and an item without a ticket, **Then** `tracker.check` says the
   planner proposes one on the item's card and contains no `bin/wuwei` command.
2. **Given** a pending ticket draft for the item below strict, **Then** the reason names the
   draft's Send answer and its card (`bin/wuwei drafts show <draft> --widget`).
3. **Given** `strict`, **Then** the reason names the host terminal commands as today.

### User Story 5 - An item the owner adds mid-day gets its ticket on a card (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the gate approved, posture `guarded` and the default `tracker.auto`, **When**
   `plan add X --goal G-1 --title "Fix the export"` runs with no `--ticket`, **Then** it
   exits 1 without admitting `X`, a pending tracker draft titled `Fix the export` exists for
   `X`, and the reason names that draft's Send card (`bin/wuwei drafts show <draft>
   --widget`), never a host terminal.
2. **Given** that draft, **When** the owner answers Send and the planner records it
   (`drafts.approve`), and `plan add X --goal G-1 --title "Fix the export"` runs again,
   **Then** `X` is admitted with the created ticket and no second draft exists.
3. **Given** `--ticket ENG-7`, **Then** that ticket is recorded as today and nothing is
   drafted.
4. **Given** `strict`, **Then** no draft is created and the reason names the host terminal.

### Edge Cases

- An approved item whose tier is in `tracker.skip_tiers`: no `Ticket:` line, nothing opened,
  `tracker.skipped` as today.
- A rerun of `plan approve` after a failed creation: `tracker.create` is idempotent (an
  existing ticket or a queued draft is reused), so nothing is opened twice.
- A creation the adapter refuses or cannot run: `plan approve` refuses with that reason and
  approves nothing (design 5.11, "nothing is approved").
- The gate already approved: `plan approve` opens nothing and refuses as today.
- A tracker-discovered candidate (its id is the ticket) shows `Ticket: <id> (existing)`.

## Requirements

- **FR-001**: `charters/lead.md` asks for a `ticket` per candidate under tracker hygiene: the
  open backlog ticket that matches it (same workstream, same title words), or no field so the
  gate opens a new one from the item's record; `null` only for the owner's none.
- **FR-002**: `plan propose` writes one `Ticket:` line per candidate while tracker hygiene is
  in force and the candidate's tier is not skipped: `<id> (existing)`, `new <title>` or
  `none`. `plan gate` lists the same per item in the Approve description, and Change
  something names tickets among its separate questions.
- **FR-003**: `plan approve` below strict opens each approved item's new ticket before the
  gate write: `tracker.create`, then `drafts.approve` on the draft it returns. It records
  every proposed link as today. Any creation failure refuses the approval with its reason.
- **FR-004**: Under strict, `plan approve` opens nothing; its refusal lists the host terminal
  commands per missing item.
- **FR-005**: `"ticket": null` is a valid candidate value; approve and add record it as
  `{"id": null, "source": "none"}` and `tracker.check` returns `skipped` for it.
- **FR-006**: `tracker.check` names the card below strict and the host terminal commands
  under strict.
- **FR-007**: The hook refuses `tracker create <item>` (no class flag) and `plan set <item>
  ticket=<id>` from a seat in every posture with a reason naming the planner; it passes both
  from the registered planner session below strict. Class creates (`--bug`, `--triage`,
  `--follow-up`) stay seat commands.
- **FR-008**: `plan add` of an owner-named item below strict with no ticket drafts its ticket
  from the title (`tracker.create` with the item's record passed in) and refuses with the
  draft's card reason; once the owner's Send records the ticket, the same `plan add` admits
  the item. `plan add` never sends a ticket itself.
- **FR-009**: Design 9.2 gains row I36 and `tests/test_invariants.py` checks it.
- **FR-010**: `charters/planner.md`, `docs/site/concepts.md`, `docs/site/configuration.md`
  and `docs/site/reference.md` describe the card path; agents are regenerated.

## Success Criteria

- **SC-001**: An approved plan whose items have proposed tickets dispatches with zero owner
  terminal commands under observe and guarded.
- **SC-002**: No seat opens or links an item ticket in any posture.
- **SC-003**: No missing-ticket reason below strict contains a terminal command.

## Assumptions

- The lead matches backlog tickets by judgement from the backlog it already queries; the CLI
  adds no title matcher.
- The Approve answer is the Send answer for the ticket drafts it lists; the card shows the
  title the draft sends. No second card is asked. `plan approve` refuses once the gate is
  approved, so its in-process send is reachable only at the morning gate, before any seat
  runs (the existing trust of `plan approve`, unchanged).
- A PR claimed at the gate (`shepherd.claim_pr`, `plan add ... source='adopted'`) takes the
  `plan add` path: its ticket is drafted for a Send card, as for any owner-named item.
- Proposed links are recorded without an adapter confirmation, as candidate tickets are today
  (design 5.11); `plan set ticket=` keeps its confirmation.
- Under strict, approve keeps today's refuse-and-list behaviour rather than approving the
  rest; the owner runs the printed commands and the planner approves again.
- `plan add --ticket` takes an id only; the owner's none applies on the gate card. Under
  strict an owner-named item still needs `--ticket`, because `tracker create` finds no record
  for it (unchanged).
- A discovery candidate admitted by `plan add` without a ticket is not opened automatically:
  no owner answered for it. The planner asks its card, then runs `tracker create` (allowed
  below strict), whose draft has its own Send card.
- No new `tracker link` verb.

## Design spec conflict (raised, not resolved)

Design 5.11 "Enforcement" quotes the reason `<item> has no ticket: bin/wuwei tracker create
<item> ... or bin/wuwei plan set <item> ticket=<id>` for every posture, and "Ticket of an
item" lists the writers of `tickets`. Proposed text for the owner: "Below strict the reason
names the item's card: `<item> has no ticket: the planner proposes one on the item's card (an
existing ticket or a new one from its record) and records the owner's answer`; under strict
it names the host terminal commands. `plan approve` records the proposed links and, below
strict, opens each proposed new ticket (`tracker create`, its draft sent as the Approve
answer); `"ticket": null` is the owner's none and counts as skipped. Item tickets (`tracker
create <item>`, `plan set <item> ticket=<id>`) are the planner's below strict, never a
seat's." The 9.2 row I36 is added in this feature (constitution Workflow).

## Deferred

- None.
