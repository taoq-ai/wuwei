# Feature Specification: tracker lifecycle updates become outward duties; the ticket walls go

**Feature Branch**: `b7-leftovers` (feature directory `specs/842-tracker-duties/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #842, part 20 of the #789 deletion pass: "chore(tracker): tracker lifecycle
updates become outward duties; the ticket walls go".

## Context

Tracker hygiene (design 5.11) has two halves today.

The walls, one rule (`tracker.check`, on while `tracker.required` and a tracker is set):

- `plan approve` and `plan add` open the missing tickets (auto-create) and refuse an item that
  still has none;
- `build next`, `dispatch next` (the gates) and the seat launch guard refuse an item with no
  ticket (the launch guard only logs since #837);
- `close` refuses, under `tracker.strict_close`, a merged item whose ticket is not done or that
  shipped without one;
- `tracker.skip_tiers`, the light-tier `later` exception, the `tracker.skipped` event, and the
  doctor `tracker` row that fails a required tracker.

The lifecycle updates:

- `claim` (assign, in progress) on the item's first build (`build next`);
- `in_review` (move the ticket) on `pr raise`;
- `done` (move the ticket) when the watch sees the PR merged;
- the PR link (`Pull request: <pr>.`) and the merged note (`Merged in <pr>.`), written later as
  comments by `tracker log` at the sweep or close, among the progress, verdict and close story.

Each move runs in `dispatch.tracker_call`, which records a `tracker.call` event and never
blocks. Nothing makes sure a failed move happens later: only `close` under `strict_close`
notices a missing `done`.

The owner (2026-10-11): the outward process must be followed. It becomes duties that `next`
lists; the model writes the content; an item is done only when its duties are recorded (pass
plan, "Outward duties"). The walls go: a missing ticket never refuses a launch, a gate or a
raise, and no ticket rule remains beyond linking the PR.

## Duties (the contract batch 8 reads)

A tracker duty exists for an approved item that has a recorded ticket
(`tickets.<item>.id`) while `adapters.tracker` is not `none`.

| Duty | Due when | Done when | Command `next` names |
| --- | --- | --- | --- |
| `tracker.claim` | the item's first build starts (`build next`) | the tracker claim (assign, in progress) returns exit 0 | `wuwei tracker move <item> claim` |
| `tracker.in_review` | the item's PR is raised (`pr raise`) or claimed (`pr claim`) | the move to `tracker.states.in_review` and the PR link comment both return exit 0 | `wuwei tracker move <item> in_review` |
| `tracker.done` | the item's PR merges (the watch's `merge.completed`) | the move to `tracker.states.done` and the merged comment both return exit 0 | `wuwei tracker move <item> done` |

Events, appended to the day's `events.jsonl` by `dispatch.tracker_call`, the one function that
performs a tracker duty:

- `duty.due` with payload `{item, duty, ticket, command}`, written before the tracker call;
- `duty.done` with payload `{item, duty, ticket, pr}` (`pr` is the item's PR reference or
  null), written only when every step of the duty returned exit 0.

A duty is open while a `duty.due` for `(item, duty)` has no later `duty.done` for the same
pair. The existing `tracker.call` event stays as the measurement row (exit and reason) for
status and signal. The tracker duties carry no model-written content: the comment texts are
fixed (`[<day> <item>] Pull request: <pr>.`, `[<day> <item>] Merged in <pr>.`). Later parts add
duties whose content the model writes (channel ping, shepherd replies) on the same two events.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A missing ticket never refuses (Priority: P1)

**Why this priority**: the issue's first acceptance line.

**Independent Test**: a workspace with `adapters.tracker = "linear"` and an approved item with
no ticket.

**Acceptance Scenarios**:

1. **Given** that item, **When** `wuwei build next <item>` runs, **Then** it writes the builder
   action; nothing names a ticket.
2. **Given** that item at the gate, **When** `wuwei dispatch next <item>` runs, **Then** it
   returns the gates.
3. **Given** a seat launch for that item, **When** PreToolUse Agent runs, **Then** the seat
   registers and no `guard.would_refuse` names a ticket.
4. **Given** that item's gates passed at head, **When** `wuwei pr raise --item <item>` runs,
   **Then** the PR is raised.
5. **Given** a proposal whose candidates carry no ticket, **When** `plan approve` and
   `plan add <item> --goal G-1` run, **Then** both admit the items and create no ticket.
6. **Given** a merged item with no ticket, **When** `wuwei close` runs, **Then** no line names
   a ticket.

### User Story 2 - Each lifecycle update happens at its phase and is recorded (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an item with ticket `ENG-7`, **When** its first `build next` runs, **Then** the
   events hold `duty.due` and, on a claim that returned 0, `duty.done` for
   `(item, tracker.claim)`.
2. **Given** `pr raise` for that item, **When** the move and the PR link comment both return 0,
   **Then** `duty.done` for `tracker.in_review` is recorded, and the comment says
   `Pull request: <pr>.`.
3. **Given** the watch sees the PR merged, **When** the move and the merged comment return 0,
   **Then** `duty.done` for `tracker.done` is recorded.
4. **Given** `pr claim` adopting an open PR for an item with a ticket, **When** it records the
   PR, **Then** the `tracker.in_review` duty runs as on `pr raise`.
5. **Given** `tracker log` at a sweep, **When** it writes the day's story, **Then** it writes
   no `Pull request:` and no `Merged in` comment (the duties wrote them once).

### User Story 3 - `next` lists a due update; close waits on it (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a `tracker.in_review` duty whose move failed (exit 1 or 2), **When**
   `wuwei next --json` runs, **Then** it returns a `duty` row for the item with the command
   `wuwei tracker move <item> in_review`, listed in `rows` beside the build launches.
2. **Given** a merged item with an open `tracker.done` duty, **When** `wuwei next` runs,
   **Then** the `duty` row comes before the `close` row, although the item is terminal.
3. **Given** an open duty, **When** `wuwei close` runs, **Then** it exits 1 and names the item,
   the duty and the command.
4. **Given** `tracker move <item> in_review` that now succeeds, **When** `next` runs again,
   **Then** no `duty` row is left.
5. **Given** `adapters.tracker = "none"` set by the owner, **When** `next` and `close` run,
   **Then** open tracker duties no longer count.

### User Story 4 - `init --upgrade` removes the retired keys (Priority: P2)

1. **Given** `tracker.required`, `tracker.skip_tiers`, `tracker.strict_close` and
   `tracker.auto` in the config, **When** `init --upgrade` runs, **Then** each is removed and
   reported.

### Edge Cases

- An item carried to tomorrow with an open duty: the duty's events stay in yesterday's log, and
  today's `next` does not list it. The claim duty runs again on today's first build only if
  the item has no build yet; `in_review` and `done` run again at their phases. (Batch 8 decides
  whether derived state reads earlier days.)
- A `duty.due` repeated by a retry (`tracker move`) is harmless: readers use the
  `(item, duty)` pair.
- The `tracker.log` setting keeps accepting `pr` and `close`: `close` still writes carried and
  parked notes; `pr` no longer produces entries (the duty writes the link).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `tracker.check`, `tracker.in_force` and every refusal they fed MUST go: in
  `plan approve`, `plan add`, `build next`, `dispatch next`, the agent launch guard and
  `close`; with the auto-create at approve and add, the `tracker.skipped` event and
  `plan._skipped`, and the `CAPACITY` text `' has no ticket: '`.
- **FR-002**: `dispatch.tracker_call(item, action, root)` MUST, when `adapters.tracker` is not
  `none` and the item has a recorded ticket, append `duty.due`, perform the action (`claim`;
  `in_review` and `done` move the ticket and then write the fixed comment through
  `port.comment`), and append `duty.done` only when every step returned 0. It never raises
  and still records `tracker.call`.
- **FR-003**: `pr claim` MUST call `tracker_call(item, 'in_review')` after recording the PR, as
  `pr raise` does.
- **FR-004**: One pure function, `tracker.open_duties(rows)`, MUST return the open
  `(item, duty)` pairs from event rows. `next` (from the rows `_seen` already parses) and
  `closing.unresolved` MUST use it, and both MUST ignore tracker duties while
  `adapters.tracker` is `none`.
- **FR-005**: `next` MUST return a `duty` row per open duty (`item`, command
  `wuwei tracker move <item> <action>`, `then` the run line), placed with the runnable rows,
  also for terminal items.
- **FR-006**: `close` MUST exit 1 while a duty is open, naming each.
- **FR-007**: `tracker move` MUST accept `claim` as well as `in_review` and `done`.
- **FR-008**: `tracker._entries` MUST stop producing the `pr` entries, the merged `close`
  entry and the `decision.decided` entries (no producer since part 18). The fold category is
  the first folded kind.
- **FR-009**: `tracker.required`, `tracker.skip_tiers`, `tracker.strict_close` and
  `tracker.auto` MUST leave the schema and template and join `workspace.RETIRED`. The doctor
  `tracker` row fails only on a configured tracker that cannot answer a backlog read, naming
  the credentials or `config set adapters.tracker none`.
- **FR-010**: The `tracker.py` LEFT row (relabel's host-terminal text) MUST go: the reason names
  `bin/wuwei init --upgrade`, which creates the label, then the `tracker move` command.
- **FR-011**: Charters (lead, planner), the design spec 5.11 and 9.1, the docs site and the
  template MUST state no ticket wall and MUST describe the three duties.

### Key Entities

- **Duty event** `duty.due` `{item, duty, ticket, command}`; `duty.done`
  `{item, duty, ticket, pr}`; duty ids `tracker.claim`, `tracker.in_review`, `tracker.done`.

## Success Criteria *(mandatory)*

- **SC-001**: `grep -rnE "tracker\.check|in_force|tracker\.required|skip_tiers'\]|strict_close|has no ticket|tracker\.skipped"`
  over `cli/` returns only `spec.skip_tiers` readers.
- **SC-002**: Each US1 scenario has a test that would fail at d60253b8.
- **SC-003**: A day walk with a failing in-review move shows the `duty` row and holds close
  until `tracker move` succeeds (`tests/test_next.py`, `tests/test_stop.py`).
- **SC-004**: Every touched test file passes; no test is loosened.

## Assumptions

1. The three duties are the owner's "status, PR link, merged". `claim` is the status update at
   build start (it assigns and moves to in progress on every adapter); the PR link rides on
   `in_review`, the merged note on `done`, so each update is one duty with one command.
2. No ticket, no duty. An item with no recorded ticket gets no tracker duty, so a seat finding
   or an owner item without a ticket never holds the day. `tracker create <item>` stays for a
   ticket on demand, and seats still file bugs and follow-ups.
3. Auto-create at `plan approve` and `plan add` goes: it existed to satisfy `tracker.required`.
   Candidates from the tracker backlog keep their ticket (`plan.tracked`, `plan.proposed`).
4. `tracker.log` (progress, verdicts and carried or parked notes) stays: it is code, not a
   wall, and the owner kept tracker comments. Only the entries the duties now write move.
5. `outbound.code_host_orgs` and `outward._external_tracker` stay (part 16 handed them here):
   they stop WUWEI creating a label on a tracker someone else owns, a guard on an outward
   write (b), not a ticket wall.
6. The escape from a tracker that never answers is the owner's `adapters.tracker = "none"`
   (one Owner step card through `config set`); then tracker duties stop counting.
7. Duties live only in events. `state.json` gets no duty key, so batch 8's derived `next` reads
   the same two events.
8. `signal` classifies `duty.due` and `duty.done` silent; `tracker.call` stays the warn row. Its
   none-adapter test compares the full reason (`startswith`), fixing the mismatch where the
   longer text tiered a none adapter as warn.
9. B7 lead call (part 842, binding over US3 scenarios 1 and 3): a duty whose adapter call fails
   after the adapter's own retry is recorded `duty.skipped {item, duty, ticket, error}`. Close
   accepts it and the day report lists it under Skipped duties with its `tracker move` retry;
   a duty is open only while its last event is `duty.due`. `tracker.auto` only picked a folded
   comment's kind, so it is retired; a fold is filed under the first folded kind.
