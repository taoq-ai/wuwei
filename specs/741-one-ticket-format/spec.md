# Feature Specification: one ticket id format

**Feature Branch**: `741-one-ticket-format`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #741 (owner, 2026-10-10, item 67): `plan add --ticket 24` stored `"24"`
while the other items hold `owner/repo#N`; `tracker create` printed no full id to copy;
`build next` then printed "github.claim: invalid GitHub issue id" and the item could never
link to its ticket. Fixing it needed an owner command (`plan set <item> ticket=owner/repo#24`).

## Root cause (reproduced read-only on main at d3b7066)

Reproduced from the records of the owner's workspace for the paper project (day 2026-10-10),
read only:

1. 15:33:11 `drafts approve` sent a held `tracker create --bug ZIRAN-DEP-BUMP ...` draft. The
   adapter returned the id `taoq-ai/ziran-paper#24` and `tracker.record` wrote a
   `tracker.created` event with it, but the CLI printed only `drafts: <draft> sent`
   (`cli/wuwei/drafts.py:386`): the id never reached the owner.
2. 15:33:29 `plan add ZIRAN-AUDIT-GREEN --goal G-2 --ticket 24`. `plan.add`
   (`cli/wuwei/plan.py:499`) copies the `--ticket` text into the candidate unchanged;
   `proposed()` (`cli/wuwei/plan.py:138`) turns it into the record and `admit` stores
   `tickets.ZIRAN-AUDIT-GREEN = {"id": "24", "source": "candidate"}` (`plan.py:565`). The only
   check is `TICKET` (`plan.py:14`), a shape regex that accepts a bare number for every
   tracker. `plan.set_ticket` (`plan.py:643`) and the lead's candidates in `plan.propose`
   (validated by the same regex at `plan.py:97`) have the same gap.
3. 15:39:40 `build next` claimed the item: `dispatch.tracker_call` (`cli/wuwei/dispatch.py:258`)
   passes the stored id to `github.claim`, whose `_ref` (`adapters/tracker/github.py:80`)
   accepts only `owner/repo#N` and raises `invalid GitHub issue id; expected owner/repo#N`
   (the recorded `tracker.call` event, exit 2). Every later claim, transition and comment for
   the item fails the same way.

The same workspace shows that every other stored ticket is `taoq-ai/ziran-paper#N`, including
items whose code repository is `taoq-ai/ziran` (ZIRAN-RAG-MAPPING holds
`taoq-ai/ziran-paper#1`, CREWAI-EXTRACTOR holds `taoq-ai/ziran-paper#2`). Tickets live in the
tracker repository, not in the item's code repository. Design 5.11 names that repository:
GitHub `tracker.project` is "a GitHub `owner/repo` (empty: the first configured repository)",
the rule `github._repo` (`adapters/tracker/github.py:87`) already applies to `create` and
`backlog`. No orchestrator notes file exists for this issue; the root cause above is read from
the workspace records and the code.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which repository does a bare number take? A: The tracker repository of design 5.11:
  `tracker.project` when set, else the first `[[repos]]` entry. That is where
  `tracker create` opens tickets and where discovery reads the backlog, so a number printed or
  seen there belongs to it. The item's code repository is not used (see Assumptions).
- Q: When is a bare number refused? A: When no tracker repository can be named: no
  `tracker.project` and no `[[repos]]` entry, or a `tracker.project` that is not
  `owner/repo`. The refusal names the full form `owner/repo#<n>` and how the owner sets
  `tracker.project`. Exit 2, like the existing invalid-ticket refusal of `plan set`.
- Q: Which trackers normalise? A: Only `adapters.tracker = "github"`. Linear and Jira ids carry
  a team or project key the number alone cannot supply, and no failure was reported there;
  their values pass through unchanged, as today.
- Q: Where does normalisation run? A: One function, `tracker.full_id(config, ticket)`, called
  at each place a ticket id enters the plan: `plan add` (owner and discovery candidates),
  `plan set <item> ticket=`, and `plan propose` (the lead's candidate `ticket` field). The
  stored id is always the full form; nothing downstream (claim, transition, comment, close)
  changes.
- Q: What does "tracker create prints the full id" change? A: `tracker create` already prints
  `<item>: ticket <id> <url>` when it opens a ticket directly (`cli/wuwei/tracker.py:143`).
  The gap is the held path: when the owner sends the draft, `drafts approve` prints only
  `drafts: <draft> sent`. It now prints `drafts: <draft> sent; ticket <id> <url>` for a
  tracker create.
- Q: What does the `init --upgrade` pass touch? A: The `tickets` map of the latest day
  directory that has a `state.json` (today, or the last working day, whose tickets
  `plan approve --import-yesterday` carries). Each bare id on a GitHub tracker becomes
  `<repo>#<n>` with one `plan.set` event `{item, ticket, was}`, and the upgrade prints
  `Upgraded <day>/state.json: ticket <item> <old> to <new>` (`Would upgrade` under
  `--dry-run`, which writes nothing). A bare id that cannot be normalised is left as is with a
  printed line naming the fix; it never stops the upgrade. Older day directories are history
  and are not rewritten. Running it again finds nothing, so it is one-time by construction.
- Q: May the planner run `plan set <item> ticket=` for the normalisation? A: It already may:
  `_planner_ticket` (`cli/wuwei/guards/protect_state.py:193`) lets the registered planner run
  the literal command below strict (#636). This feature adds a regression test for the
  bare-number and full forms and no guard change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A bare ticket number is stored in the full form (Priority: P1)

The owner adds an item with `--ticket 24` (or links one with `plan set <item> ticket=24`) on
a GitHub tracker. The plan stores `owner/repo#24`, so `build next` claims the ticket.

**Why this priority**: it is the reported failure; without it the item never links.

**Independent Test**: on a workspace with `adapters.tracker = "github"` and one `[[repos]]`
entry, `plan add X --goal G-1 --ticket 24` stores `{"id": "<repo>#24"}`, and
`dispatch.tracker_call(X, 'claim')` passes `<repo>#24` to the adapter.

**Acceptance Scenarios**:

1. **Given** `plan add X --ticket 24` with one tracker repository, **When** the item is
   admitted, **Then** the stored ticket is `<repo>#24` and `build next` claims it.
2. **Given** `tracker.project = "acme/tracker"` and two `[[repos]]` entries, **When** `plan add
   X --ticket 24` runs, **Then** the stored ticket is `acme/tracker#24`.
3. **Given** no `tracker.project` and two `[[repos]]` entries, **When** `plan add X --ticket
   24` runs, **Then** the stored ticket is `<first repo>#24` (design 5.11's tracker
   repository).
4. **Given** `plan set X ticket=24`, **When** the tracker confirms it, **Then** `created()` is
   asked for `<repo>#24`, the stored id is `<repo>#24` and the command prints it.
5. **Given** a lead proposal whose candidate has `"ticket": "24"`, **When** `plan propose`
   runs, **Then** `proposal.json` holds `<repo>#24` and `plan approve` stores it.
6. **Given** a full id `owner/repo#24`, or `ENG-24` on a Linear tracker, **Then** it is stored
   as given.

---

### User Story 2 - A bare number with no nameable repository is refused (Priority: P1)

**Why this priority**: storing a guess would link the wrong issue; storing the bare number is
the reported failure.

**Independent Test**: `tracker.full_id` with no `tracker.project` and no `[[repos]]` raises
`ValueError` naming `owner/repo#24`; `plan add` exits 2 and writes nothing.

**Acceptance Scenarios**:

1. **Given** a GitHub tracker with no `tracker.project` and no `[[repos]]` entry (or a
   `tracker.project` that is not `owner/repo`), **When** `plan add X --ticket 24` or `plan set
   X ticket=24` runs, **Then** it exits 2 with a refusal naming `owner/repo#24` and
   `tracker.project`, and no ticket or item is written.

---

### User Story 3 - The owner sees the full id of a ticket a sent draft opened (Priority: P2)

**Independent Test**: approve a held tracker create draft whose adapter returns
`{id: 'acme/app#24', url}`; the printed line contains `acme/app#24`.

**Acceptance Scenarios**:

1. **Given** a held tracker create draft, **When** the owner runs `drafts approve <draft>` and
   the tracker opens the ticket, **Then** the output is `drafts: <draft> sent; ticket <id>
   <url>`.

---

### User Story 4 - init --upgrade normalises stored bare ids (Priority: P2)

**Independent Test**: seed today's state with `tickets.X = {"id": "24", "source":
"candidate"}` on a GitHub tracker with one repository; `init --upgrade` prints the change,
stores `<repo>#24` and appends one `plan.set` event; a second run prints `No workspace changes
needed`.

**Acceptance Scenarios**:

1. **Given** a stored bare id, **When** `init --upgrade` runs, **Then** it normalises it and
   prints the change.
2. **Given** `--dry-run`, **Then** it prints `Would upgrade ...` and the state is unchanged.
3. **Given** a bare id with no nameable repository, **Then** the upgrade prints the line naming
   the fix, leaves the id, and exits as it would without it.

---

### User Story 5 - The planner links the ticket below strict (Priority: P3)

**Acceptance Scenarios**:

1. **Given** the registered planner below strict, **When** it runs `bin/wuwei plan set A
   ticket=24` or `bin/wuwei plan set A ticket=acme/app#24`, **Then** `protect_state` passes it;
   a seat is refused naming the planner; under strict the owner runs it (unchanged #636 rule).

### Edge Cases

- `--ticket 0` or `--ticket 024`: not a GitHub issue number (`[1-9][0-9]*`), so it is not
  normalised and is stored as given, as today; the adapter names it. Only `[1-9][0-9]*` is a
  bare number.
- A full id in another repository (`other/repo#24`) is kept: the owner named it.
- `adapters.tracker = "none"`: ids pass through; no tracker is in force.
- A ticket recorded by `tracker create`, discovery or yesterday's carry is already full and is
  never rewritten.
- `init --upgrade` on a workspace with no day directory or no `tickets`: nothing to do, no
  line.
- `init --upgrade` with an unreadable latest `state.json`: one warning line, the upgrade
  continues (the ticket pass decides nothing else).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `tracker.full_id(config, ticket)` returns `<repo>#<n>` for a bare `[1-9][0-9]*`
  on a GitHub tracker, where `<repo>` is `tracker.project` or else the first `[[repos]]` name;
  returns every other value unchanged; raises `ValueError` naming `owner/repo#<n>` and
  `tracker.project` when that repository is empty or not `owner/repo`.
- **FR-002**: `plan add` normalises the candidate's `ticket` with FR-001 before the tracker
  check and before anything is written.
- **FR-003**: `plan set <item> ticket=<id>` normalises with FR-001 before the tracker
  confirmation; it confirms, stores and prints the normalised id.
- **FR-004**: `plan propose` normalises each candidate's `ticket` with FR-001 before the
  proposal is written.
- **FR-005**: `drafts approve` of a tracker create that the tracker confirms prints
  `drafts: <draft> sent; ticket <id> <url>`.
- **FR-006**: `init --upgrade` normalises the bare GitHub ids of the latest day's `tickets`
  with FR-001, one `plan.set` event `{item, ticket, was}` each, prints each change (`Would
  upgrade` under `--dry-run`, no write), counts it as a workspace change, and prints a line
  instead of failing for an id it cannot normalise or an unreadable state.
- **FR-007**: The registered planner's `plan set <item> ticket=<n>` and `ticket=<owner/repo#n>`
  pass `protect_state` below strict and are refused for a seat (existing rule, regression
  test only).

### Key Entities

- **Ticket record**: `tickets.<item> = {"id": str, "source": str}` in a day's `state.json`.
  After this feature a GitHub id is always `owner/repo#N`. No schema change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the reproduction (`plan add X --ticket 24` on a GitHub tracker with a nameable
  repository), the stored id is the full form and a claim through the fake tracker receives it.
- **SC-002**: No code path can store a bare GitHub number from `plan add`, `plan set` or
  `plan propose`.
- **SC-003**: The owner can copy the full id from the output of the command that opened the
  ticket, direct or through a sent draft.
- **SC-004**: The full suite passes.

## Assumptions

- The issue text says "from the item's repository (or the only configured tracker
  repository)" and "refuse a bare number when the repository is ambiguous". The owner's
  workspace shows the item's code repository is the wrong source (items in `taoq-ai/ziran`
  hold tickets in `taoq-ai/ziran-paper`), and design 5.11 already defines exactly one tracker
  repository (`tracker.project`, else the first configured repository). So the item's
  repository is not used, and two configured repositories are not ambiguous. The owner's own
  request ("`plan add --ticket` should accept a bare number and add the repo itself") comes
  from a workspace with two repositories and no `tracker.project`; refusing there would not
  meet it. The refusal of the issue's second acceptance scenario therefore applies when no
  tracker repository can be named (no `tracker.project` and no repository, or a malformed
  `tracker.project`), and it names `owner/repo#24`.
- Linear and Jira are out of scope: a bare number cannot be completed without a key the
  config does not always hold, and no failure was reported for them.
- The `init --upgrade` pass rewrites only the latest day's `state.json`, the record every
  later command reads (and the one `--import-yesterday` carries from). Earlier days are
  history; `proposal.json` files are not rewritten (an approved proposal's tickets are
  already in state).
- The `plan.set` event kind is reused for the upgrade change (it is the ticket-record event
  and already reserved); its producer text in `cli/wuwei/commands/event.py` also names
  `wuwei init --upgrade`. No new event kind.
- Exit codes: the refusal is a `ValueError` (exit 2), matching the existing invalid-ticket
  refusal of `plan set` (`plan.py:648`).
- The design spec needs no amendment (and is amended only by its owner): 5.11 already states
  the GitHub id form and the tracker repository; this feature makes the CLI store that form.
