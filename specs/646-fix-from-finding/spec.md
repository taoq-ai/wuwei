# Feature Specification: a seat's small fix becomes an item without a ticket

**Feature Branch**: `646-fix-from-finding`
**Created**: 2026-10-10
**Status**: Ready
**Input**: GitHub issue #646, "feat(plan): a small high-value fix a seat finds becomes an item
without a ticket: plan add from a seat's finding, size small, ticket optional, created later by
the planner when the tracker requires one". Owner, 2026-10-10: the lead proposed pinning a
linter in CI, but nothing turned it into an item, and a builder's small valuable fix needed a
ticket before the planner could add it.

## Problem (reproduced)

Reproduced read-only on `main` (5c0fe16) from the feature worktree with `PYTHONPATH=cli`. The
orchestrator named no dry-run workspace for this issue (see Assumptions), so the reproduction
calls the CLI and the shared ticket rule directly:

- `python3 -P -m wuwei note --fix "Pin ruff in CI"` exits 2: `argument note_action: invalid
  choice: 'Pin ruff in CI' (choose from 'add')`. A seat has no way to record a fix it found
  except a memory note (`note add`), which nothing reads as work.
- `python3 -P -m wuwei plan add --from-finding fix-x` exits 2: `unrecognized arguments:
  --from-finding`.
- `tracker.check({}, config, 'fix-x', {'tier': 'light'})` with a tracker set,
  `tracker.required` on, `skip_tiers = []` and posture guarded returns `('missing', "fix-x has
  no ticket: the planner proposes one on the item's card ...")`. A light item waits for its
  ticket like any other.

Root causes, with file and line on `main`:

1. `cli/wuwei/commands/note.py` lines 11 to 20: `note` has one verb, `add`, which writes a
   memory note under `.wuwei/memory/notes/`. There is no day record of a seat's finding, so
   nothing can list it or turn it into an item.
2. `cli/wuwei/commands/next.py` `step` (lines 156 to 323): no row reads seat findings, so the
   planner's loop never proposes one.
3. `cli/wuwei/plan.py` `add` (lines 463 to 564) admits a discovery candidate or an owner-named
   item (`--goal`). A finding is neither, and an owner-named item without a ticket either gets a
   ticket created or drafted before the work (lines 503 to 512, #636) or is refused (line 514).
4. `cli/wuwei/tracker.py` `check` (lines 35 to 53), the one ticket rule every refusal point
   reads (`plan approve` lines 405 and 429, `plan add` line 501, `build next`
   `commands/build.py` line 147, `dispatch next` `dispatch.py` line 336, the Agent launch guard
   `guards/agent_launch.py` line 237): an unticketed item is exempt only when its tier is in
   `tracker.skip_tiers` (default `[]`) or the owner chose none. Nothing lets a small item start
   before its ticket exists.
5. `cli/wuwei/plan.py` `approve` lines 400 to 411: a failed ticket creation at the gate is a
   refusal for every item, so a small item cannot be approved when its ticket cannot be opened.
6. `cli/wuwei/retro.py` `compile`: no section lists what seats found.

## Clarifications

### Session 2026-10-10

- Q: What is "size small"? A: An item whose deciding tier is `light`: its recorded gate tier
  when there is one, else its lead tier, read the same way `tracker.check` reads the tier for
  `skip_tiers` (design 5.11). Light is the tier the diff measures as within `light_max_lines`
  (design 5.3), the only size measure WUWEI already has. The lead's plan JSON already accepts
  `"tier": "light"` (`plan._proposal` line 88), so "the plan JSON schema accepts it" needs no
  schema change. A small item whose diff later measures standard or full is no longer small.
- Q: What does "never requires a ticket" mean while `tracker.required` is in force? A: The
  ticket is not a precondition for the work. `tracker.check` gains a status `later` for an
  unticketed light item that is not exempt: no refusal point refuses it, and it gets no
  `tracker.skipped` event (it is not exempt; its ticket comes later).
- Q: When is the ticket created? A: At the gate for an item `plan approve` admits (the #636
  creation runs for it; its failure is not a refusal), and after the item ships for an item
  added during the day: `close` names `bin/wuwei tracker create <item>` for a merged item
  without a ticket that `tracker.check` reads as `later`, under the same `strict_close` rule as
  the existing done line. `plan add --from-finding` never creates or drafts a ticket.
- Q: `wuwei note --fix "<title>"` or `note add` with a `fix` kind? A: `wuwei note --fix
  "<title>"`, the form the issue names first. A memory note is long-lived knowledge reviewed by
  consolidation; a finding is today's work proposal, so it lives in the day's state like
  `discovery_candidates` and `intraday_proposals`.
- Q: What is a finding's id? A: `fix-` plus the slug of the title's first six words
  (lowercase letters and digits joined by `-`, matching `notes.SLUG_RE`). The same title is the
  same finding. The id is the item id `plan add --from-finding` admits, so the ticket, the
  board and the retro all name it the same way.
- Q: Which goal does a finding item serve? A: `--goal G-n` when given, else the first of
  today's goals (`state.goals`, the order the gate approved).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A builder's fix becomes an item (Priority: P1)

A builder working on its item spots a small, valuable fix outside its promise. It records the
fix with one command and goes on. The planner's next action proposes adding it; the planner
adds it as a small item and dispatch offers it like any planned item, with no ticket first.

**Why this priority**: it is the owner's complaint: valuable work got lost or needed a ticket
before anyone could do it.

**Independent Test**: in a workspace with an approved gate and a tracker required, run `note
--fix`, then `next --json`, then the command it names, then `next --json` again.

**Acceptance Scenarios**:

1. **Given** an approved day and a tracker with `required` on, **When** a builder runs `wuwei
   note --fix "Pin ruff in CI"`, **Then** it exits 0, prints the finding id
   `fix-pin-ruff-in-ci`, `state.json` holds `seat_findings.fix-pin-ruff-in-ci` and the
   `finding.noted` event names it.
2. **Given** that finding, **When** the planner runs `wuwei next --json`, **Then** the row is
   `state: finding`, `item: fix-pin-ruff-in-ci`, command `wuwei plan add fix-pin-ruff-in-ci
   --from-finding`.
3. **Given** that row, **When** the planner runs the command, **Then** it exits 0 with
   `{"action": "build next", "item": "fix-pin-ruff-in-ci"}`; the item is in `approved_items`
   with `tier: light`, `source: finding`, the finding's title, the first goal and
   `budget_size` 1; no ticket is created or drafted; and `next` then returns the `dispatch`
   row (dispatch offers it).
4. **Given** the finding item, **When** `build next` or an Agent launch for its builder runs,
   **Then** neither refuses for a missing ticket.
5. **Given** a finding already added, **When** `next` runs, **Then** it does not propose that
   finding again.

### User Story 2 - A small item is approved without a ticket (Priority: P1)

The lead proposes a small item (tier light) with no ticket. The owner approves the plan on the
card; the planner tries to attach a ticket at the gate (#636) and the item is approved whether
or not the ticket could be opened.

**Why this priority**: issue Acceptance 2.

**Independent Test**: propose a plan with one light candidate and no `ticket`, approve it with
a fake tracker that opens tickets, and with one that refuses.

**Acceptance Scenarios**:

1. **Given** a tracker configured with `required` on, posture guarded and a light candidate
   without a ticket, **When** `plan approve` runs, **Then** it exits 0, the tracker's `create`
   was called once for that item, and `tickets.<item>` records the opened ticket.
2. **Given** the same with a tracker whose create is refused, **When** `plan approve` runs,
   **Then** it exits 0, the item is approved, and `tickets` has no entry for it.
3. **Given** the same with a standard candidate whose create is refused, **When** `plan
   approve` runs, **Then** it refuses as today (unchanged).
4. **Given** posture strict, **When** `plan approve` runs with an unticketed light candidate,
   **Then** it exits 0 and creates nothing (under strict the CLI sends no tracker write, as for
   every item today).

### User Story 3 - The ticket follows after the item ships (Priority: P2)

An item added from a finding merges without a ticket. Closing the day names the planner's
command that opens its ticket from the finding's title.

**Independent Test**: a merged light item without a ticket, tracker required, `close`.

**Acceptance Scenarios**:

1. **Given** a merged finding item without a ticket and `strict_close` on, **When** `close`
   runs, **Then** it reports `<item>: shipped without a ticket: bin/wuwei tracker create <item>`
   as owed.
2. **Given** that line, **When** the planner runs `bin/wuwei tracker create <item>`, **Then** the
   tracker receives a draft whose title is the finding's title and whose body names the item's
   goal and track.
3. **Given** `strict_close` off, **When** `close` runs, **Then** the line is printed and does
   not hold the close.

### User Story 4 - The retro lists seat findings (Priority: P3)

**Acceptance Scenarios**:

1. **Given** two findings, one added and merged and one not added, **When** `wuwei retro`
   compiles, **Then** the retro has a `## Seat findings` section with one line per finding:
   its id, its title and its item phase, or `not added`.
2. **Given** no findings, **Then** the section reads `none`.

### Edge Cases

- `note --fix` with an empty title, a multi-line title, a title over 120 characters, a title
  with no letters or digits, or a title holding an absolute path: exit 1 with the reason;
  nothing is written. The title is seat-written text the planner reads, so it stays one short
  line.
- `note --fix` for a title whose id is already a finding or a day item: exit 1 naming the
  existing id.
- `note --fix` with no day state: exit 2 with the reason, as every state write.
- `plan add <id> --from-finding` for an id that is not a finding: exit 1 naming `wuwei next`,
  which lists them.
- `plan add <id> --from-finding` before the gate: the existing refusal (gate not approved).
- `plan add <id> --from-finding --goal G-9` for a goal not approved today: the existing
  refusal naming today's goals.
- A finding item whose gate tier measures standard or full: `dispatch next` refuses for the
  missing ticket as for any item (design 5.11, "a gate tier that later rises out of
  `skip_tiers`"), and the planner opens it with `tracker create <item>`.
- `wuwei note add` is unchanged; `note` with neither a verb nor `--fix` exits 2 with usage.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `wuwei note --fix "<title>"` records a finding in today's state under
  `seat_findings.<id>` (`scope`: the title, `evidence`: `seat finding`, `track`: `SLICE`, `at`: the
  time) and appends `finding.noted` with `{id, title}`; it prints the id. `seat_findings` and
  `finding.noted` are written only by this command (state producer table and
  `EVENT_PRODUCERS`).
- **FR-002**: `wuwei next` returns, after the stuck-seat row and before the item loop, one
  `finding` row per finding that is not a day item and whose row has not been done, naming
  `wuwei plan add <id> --from-finding`.
- **FR-003**: `wuwei plan add <id> --from-finding [--goal G-n] [--size N]` admits the finding
  through the owner-item path with `source: finding`, the finding's title, `tier: light`,
  `track: SLICE`, no flags, `budget_size` from `--size` (default 1) and the goal given or the
  day's first goal; it creates and drafts no ticket.
- **FR-004**: `tracker.check` returns `('later', '')` for an item with no ticket, not exempt,
  whose deciding tier is `light`. Every refusal point keeps refusing only on `missing`.
- **FR-005**: `plan approve` below strict runs the #636 ticket creation for a `later` item as
  for a `missing` one; a failed creation for a `later` item is not a refusal.
- **FR-006**: `tracker.create <item>` finds a finding item's record when it is in neither
  today's proposal nor `discovery_candidates`: the finding row with the day item's goal.
- **FR-007**: `close` reports `<item>: shipped without a ticket: bin/wuwei tracker create
  <item>` for a merged item `tracker.check` reads as `later`: owed under `strict_close`,
  printed otherwise.
- **FR-008**: `wuwei retro` writes a `## Seat findings` section.
- **FR-009**: The builder, lead and planner charters say how a finding is recorded and added,
  and `bin/wuwei agents build` regenerates `agents/`. The reference page rows for `note` and
  `plan` name the new forms.
- **FR-010**: Design 9.2 gains row I56 and `tests/test_invariants.py` checks it: a small item
  never waits for its ticket, and one whose gate tier rose does.

### Key Entities

- **Finding**: `seat_findings.<id>` in the day's `state.json`: `{scope, evidence, track, at}`. It
  becomes the item `<id>` on `plan add --from-finding`; whether it was added is read from
  `items`, never stored twice.

## Success Criteria *(mandatory)*

- **SC-001**: From `note --fix` to a dispatchable item takes two CLI calls (`note --fix`,
  `plan add --from-finding`) and no ticket, owner command or card.
- **SC-002**: With a tracker required, an unticketed light item is refused by none of `plan
  approve`, `plan add`, `build next`, `dispatch next` (while light) and the Agent launch guard.
- **SC-003**: Every finding of the day appears in that day's retro.

## Assumptions

- No orchestrator notes exist for #646 (`_pipeline/notes/646-full.md` is absent), so no
  dry-run workspace was named; the reproduction above runs the CLI and `tracker.check`
  directly on `main`.
- "Size small" is the light tier (Clarifications). `--size` stays the budget size and does not
  decide the ticket rule.
- `later` does not depend on `tracker.skip_tiers`: a light tier listed there stays `skipped`
  (no ticket ever, `tracker.skipped` event), unchanged.
- The ticket rule is posture independent. Under strict, `plan approve` creates nothing (as
  today for every item) and `close` names the command the owner runs in a host terminal.
- A finding records no seat or item it came from: the CLI cannot tell reliably which seat runs
  a command, and the title is what the planner, the ticket and the retro need.
- Findings are per day. An unadded finding is listed in that day's retro and not carried; the
  seat or the lead records it again if it still matters.
- A seat can run `plan add --from-finding` as it can run `plan add` today. The item it admits
  is unflagged and light, and its gates come from its diff, so no gate is lowered.
- A light lead tier also skips the item's spec under the default `spec.skip_tiers`
  (design 5.10); that is intended for a small fix and re-checked by the diff at the gates.
- `note add --type fix` is not added; `wuwei note --fix` is the one form.

## Design spec conflict (raised, not resolved)

Design 5.11 Enforcement says "an item whose tier is not in `skip_tiers` and that has no ticket
is refused" and lists `plan approve` and `plan add` as refusal points. This feature adds an
exception for the light tier: never refused, ticket later. The 9.2 row I56 is added here
(constitution Workflow); the 5.11 text is raised in the pull request for the owner to amend.

## Deferred

- Carrying an unadded finding to the next day's proposal.
- Recording which seat or item a finding came from.
