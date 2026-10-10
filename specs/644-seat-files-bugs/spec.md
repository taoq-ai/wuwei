# Feature Specification: a bug a seat finds is filed by the seat

**Feature Branch**: `644-seat-files-bugs`
**Created**: 2026-10-10
**Status**: Ready
**Input**: GitHub issue #644, "fix(tracker): a bug a seat finds is filed by the seat: tracker
create in the owner's own tracker is internal, not outward, so it sends without a draft under
send and is configurable as a tier row". Owner, 2026-10-10: a builder hit a lint break, filed
it with `tracker create --bug` and got a draft for the owner to approve. "A builder finding a
bug shouldn't need you to file it. Filing an issue in your own private repo isn't really
outward." Owner addition (item 27): gate seats file the out-of-scope bugs they find the same
way; their brief's limit to the verdict file is lifted for `tracker create --bug`.

## Problem (reproduced)

Reproduced read-only on `main` (51978f1) in a scratch workspace: `outward.classify` called as
the tracker port calls it (`port=True`, `kind='tracker'`, the nested draft `{title,
description, item, category: 'bugs', parent}`), with `adapters.tracker = "linear"`. Every case
returns `(1, 'draft')`:

| Config | Reason | Trace |
| --- | --- | --- |
| defaults (`outbound.default_tier = "send"`) | `approval tier tracker for tracker: category not in tracker.auto` | `party tracker: team, connector default class team`; no row matched |
| `default_tier = "ask"` | same | same |
| `default_tier = "block"` | same (the umbrella is not consulted) | same |
| row `{ tool = "tracker", audience = "owner", tier = "ask" }` | same; the owner's row never matches | `rule 1 owner { tool = "tracker", audience = "owner", tier = "ask" }: passed` |
| GitHub tracker, project `outside-org/repo` | `ask by rule 5 (audience=client) for board: ...` | the board is a client party (correct, keep) |

`tests/test_tracker.py::test_bug_drafts_once_by_default` passes on `main` and pins the
symptom: the CLI prints `bin/wuwei drafts approve <id>`.

Root causes, with file and line on `main`:

1. `cli/wuwei/outward.py` lines 539 to 540 (`_parties`): a port tracker write with no
   destination and no mention gets the connector party with `DEFAULT_CLASS['tracker']`,
   `team` (line 403). No default row matches a team party without a thread topic, and no
   owner row with `audience = "owner"` can ever match, so `decide` returns `None`.
2. `cli/wuwei/outward.py` line 664: the umbrella (`outbound.default_tier`) is skipped for
   every port tracker write (#535, design 9.2 I7), so send, ask and block all fall through.
3. `cli/wuwei/outward.py` lines 676 to 680: the tracker kind rule drafts every category not in
   `tracker.auto`, whose default is `["progress", "pr", "close"]`
   (`cli/wuwei/workspace.py` line 105), so `bugs` and `triage` always draft.
4. `cli/wuwei/tracker.py` lines 125 to 127 and 139 to 141 (`create`): a held creation prints
   `<item>: ticket drafted: bin/wuwei drafts approve <id>`, an owner-only command
   (`protect_state`), under every posture, without the rule that held it. The seat is told to
   hand the owner a terminal command.
5. `cli/wuwei/tracker.py` lines 290 to 305 (`record`): the `tracker.created` event carries
   class, subject, ticket and parent, never the seat; `cli/wuwei/commands/board.py` lines 149
   to 155 and `cli/wuwei/retro.py` cannot say which seat filed what.
6. `cli/wuwei/brief.py` line 478 tells a gate seat its verdict file is "your only write", and
   `charters/_common.md` line 10 says "A sentinel writes one verdict at the briefed path",
   while rule 7 (line 23) already asks the gate that finds a bug to file it.

## Clarifications

### Session 2026-10-10

- Q: What is "a tracker in the owner's own repositories"? A: The workspace's configured
  tracker (`adapters.tracker`) when it is not external by the existing rule
  (`outward._external_tracker`: a GitHub project or board whose owner is outside
  `outbound.code_host_orgs`; the GitHub project defaults to the first entry of the `repos`
  table). Linear and Jira are internal to their configured workspace (design 4.9). There is
  no class field on `repos`; no config key is added.
- Q: Which writes become internal? A: Only WUWEI's own port creation of a class ticket: a
  category in `tracker.create` (`bugs`, `triage`, `follow-ups`). Item tickets (`items`) stay
  with #636; comments (`tracker log`) keep `tracker.auto`; MCP tracker writes keep #527.
- Q: How does `audience = "owner"` match? A: When such a creation has no other reader (no
  destination, no mention, not external), its one party is the workspace tracker with class
  `owner` and the reason "the workspace tracker is the owner's own". An owner row with `tool
  = "tracker"` and `audience = "owner"` then matches it like any row.
- Q: The default row `{ audience = "owner", tier = "send" }` would send it under every
  umbrella. A: For this party, default send rows are passed; the owner's rows, the default
  ask rows (the sensitive topic, and commitment and disagreement under ask) and then the
  umbrella decide. So: send sends, ask holds it as a card, block refuses.
- Q: What is "a card for the planner, never a draft for the owner"? A: A held creation is a
  pending draft (#493), the planner's Send card. The seat's printed reason names the rule that
  held it and the card (`bin/wuwei drafts show <id> --widget`) below strict, and the host
  terminal `bin/wuwei drafts approve <id>` only under strict, as `tracker.check` words it
  (#636). No new card type.
- Q: How does the CLI know the seat? A: It cannot: a seat runs as the owner in the planner's
  session. The seat passes `--seat <role>` (`builder` or a `sentinel-*` role); the event
  records it next to the subject (the item). It is a label for the board and the retro,
  never trusted by a guard, sweep or metric.
- Q: Where do "plan" and the retro list them? A: The board's existing `Tickets created`
  table (the day's plan view; `plan.md` is written once at propose, before any seat runs)
  gains a `Seat` column, and the steward retro gains a `Tickets seats filed` section.

## User Scenarios and Testing

### User Story 1 - A seat files the bug it finds (Priority: P1)

A builder or a gate seat finds a bug outside its item and files it in the owner's own tracker
with one command. The ticket exists, nobody is asked.

**Independent Test**: in-process `main(['tracker', 'create', '--bug', ...])` with the fake
tracker port behind the real outward wrapper (`tests/fakes/tracker.py` `ported`, the `ws`
fixture of `tests/test_tracker.py`).

**Acceptance Scenarios**:

1. **Given** a builder seat, an internal (owner-class) tracker and the send umbrella (the
   default), **When** it runs `bin/wuwei tracker create --bug item-1 "Export fails on empty
   rows" --evidence cli/x.py:12 --seat builder`, **Then** it exits 0, prints the created
   ticket id, no draft exists, the port's `create` was called once, and one `tracker.created`
   event has `class: bugs`, `subject: item-1`, `seat: builder`.
2. **Given** the same with `--seat sentinel-quality` and `--triage`, **Then** the same.
3. **Given** a seat payload (`agent_id` set) in every posture, **When** the hook sees
   `bin/wuwei tracker create --bug A Broken --evidence cli/x.py:1 --seat sentinel-quality`,
   **Then** it passes (exit 0).

### User Story 2 - A client's tracker keeps the outward rules (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `adapters.tracker = "github"` with `tracker.project = "outside-org/repo"` (its
   owner not in `outbound.code_host_orgs`), **When** a seat runs the same `--bug` command,
   **Then** it exits 1, the port's `create` is not called, a pending draft holds it, and the
   reason names `audience=client`, as today.

### User Story 3 - The owner wants drafts: one tier row (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `outbound.tiers` row `{ tool = "tracker", audience = "owner", tier = "ask" }`
   and posture `guarded`, **When** a seat runs the `--bug` command, **Then** it exits 1, the
   port's `create` is not called, one pending tracker draft exists with its `draft.created`
   event (the planner's card), and stdout names the row (`rule 1`, `tool=tracker
   audience=owner`) and `bin/wuwei drafts show <id> --widget`, never `drafts approve`.
2. **Given** the same under `strict`, **Then** the reason names `bin/wuwei drafts approve
   <id>` and `host terminal`.
3. **Given** `outbound.default_tier = "ask"` and no row, **Then** the creation is held the
   same way (a card); with `"block"` it is refused (exit 1) naming `outbound.default_tier`
   and nothing is drafted.
4. **Given** `bin/wuwei outbound tiers`, **Then** the owner's row is listed (as today) and the
   umbrella line names bug, triage and follow-up tickets in the workspace's own tracker.

### User Story 4 - The day shows who filed what (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a `tracker.created` event with `seat: builder`, **When** the board renders,
   **Then** the `Tickets created` table has a `Seat` column showing `builder` (and `none` for
   a creation without a seat).
2. **Given** the same day, **When** the steward retro compiles, **Then** a `Tickets seats
   filed` section lists ticket, class, item and seat for each creation with a seat, or one
   `none` row.

### User Story 5 - The brief and the charters say the finder files (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a gate brief, **Then** its `Verdict file:` line says the verdict is the only
   file it writes and that an out-of-scope bug it finds it files itself (rule 7 of the common
   charter), so the brief no longer forbids it.
2. **Given** `charters/_common.md`, **Then** rule 1 lets a sentinel file the out-of-scope
   bugs it finds, rule 7 gives the command with `--seat <your role>` and says a held ticket
   is the planner's card (note it in the report and go on, never ask the owner), and the
   generated agents match the charters.

### Edge Cases

- A sensitive title (`outbound.sensitive_keywords`, for example "salary") is held as a card
  under the send umbrella: the default sensitive row still applies to this party.
- A title that mentions a person adds that person as a party, so the workspace tracker party
  is not added: a client person holds it (client row); a team or unknown person follows the
  umbrella like any connector write (#527).
- `tracker.create` excluding the class still refuses before the port (exit 1, unchanged).
- A held creation the planner's card later sends (`drafts.approve`) records
  `tracker.created` without a seat.
- Idempotency is unchanged: a second identical call prints the existing ticket or the held
  reason and writes nothing.
- The headless shepherd seat still holds every write (`outward.classify` first line).
- `--seat` with any other value is an argparse error (exit 2).

## Requirements

- **FR-001**: `outward.classify` treats WUWEI's own port creation of a class ticket (a
  category in `tracker.create`) on a tracker that is not external as internal: the owner's
  tier rows first, then the default ask rows, then `outbound.default_tier` (send sends, ask
  holds it as a draft by the tracker kind rule, block refuses).
- **FR-002**: When that creation has no other party, its party is the workspace tracker,
  class `owner`, reason "the workspace tracker is the owner's own"; default send rows are
  passed for it, and a trace says so.
- **FR-003**: External trackers, item creations, comments, MCP tracker writes and the default
  tier table (rows and numbering) are unchanged.
- **FR-004**: `tracker.create` prints a held creation as the rule that held it plus the
  planner's card below strict, or the host-terminal `drafts approve` under strict, in both
  the fresh and the already-queued path; the result data keeps `{'draft': <id>}`.
- **FR-005**: `tracker create` takes `--seat` with choices `builder`, `sentinel-arch`,
  `sentinel-goal`, `sentinel-quality`, `sentinel-security`; `tracker.created` carries `seat`
  when given.
- **FR-006**: The board's `Tickets created` table gains `Seat`; the retro gains `Tickets seats
  filed`.
- **FR-007**: The gate brief line and `charters/_common.md` rules 1 and 7 say the finder
  files; the generated agents are rebuilt.
- **FR-008**: `bin/wuwei outbound tiers` names these creations in its umbrella line.
- **FR-009**: Design 9.2 gains row I55 and `tests/test_invariants.py` checks it; the I7 check
  uses a comment kind outside `tracker.auto` for its held case.
- **FR-010**: `docs/site/configuration.md`, `docs/site/concepts.md` and
  `docs/site/reference.md` describe the change.

## Success Criteria

- **SC-001**: Under the default config a seat's `tracker create --bug` creates the ticket
  with zero owner interaction.
- **SC-002**: No reason printed to a seat below strict names `drafts approve`.
- **SC-003**: Every existing test of item tickets, comments and external trackers passes
  unchanged.

## Assumptions

- No orchestrator notes file exists for #644 (`notes/644-full.md` is absent); the issue and
  its owner addition are the inputs, and the reproduction above is from a scratch workspace.
- "The owner's own repositories" is the workspace's configured tracker unless the existing
  external rule says otherwise; the `repos` table enters only as the GitHub project default.
  No per-repository class key is added (YAGNI); an owner who files into a client's Linear or
  Jira adds a row `{ tool = "tracker", tier = "ask" }`.
- "Under ask" is `outbound.default_tier = "ask"` or a row with `tier = "ask"`; "refuse" is
  `block` (the issue mixes in the `outward.modes` word).
- The class `owner` applies only to this party; it does not make comments or item tickets
  send. A bug ticket is the owner's internal record like a self-DM, but the sensitive row
  still holds it, because the owner's tracker can have other readers.
- Under `strict` the same table and umbrella decide (strict only refuses sends to client or
  public parties, unchanged); the held reason names the host terminal.
- Follow-ups (`--follow-up`, the planner's) are class creations too and follow the same rule.
- `--seat` is a self-declared label (a seat cannot be identified from inside the CLI); it is
  validated by choices and never trusted. A held creation records its seat nowhere; the
  listing covers creations that went out from the seat's own call.
- The board is the "plan" view the issue names: `plan` has no listing verb and `plan.md` is
  written before any seat runs.
- The charter `version` of `_common.md` is bumped (1.8.0 to 1.9.0) and agents rebuilt.

## Design spec conflict (raised, not resolved)

Design 4.9 ("Tracker writes (5.11): comments and ticket creations whose kind is in
`tracker.auto` are auto-sent; every other tracker write is a draft"), 5.11 Approval ("With the
defaults, ... every creation, the item's own ticket included, are drafts") and 9.2 I7 ("Docs
and tracker writes follow `docs.auto` and `tracker.auto`") say a seat's bug ticket drafts.
Proposed text for the owner, 5.11 Approval: "A bug, triage or follow-up ticket WUWEI opens in
the workspace's own tracker (not external by the rule above) is internal: the owner's tier
rows decide first (`tool = "tracker"`, `audience = "owner"`), then the sensitive row, then
`outbound.default_tier`; with the defaults it is sent. Item tickets and comments keep
`tracker.auto`." This feature adds 9.2 row I55 and a note on I7 pointing to it (constitution
Workflow), as #636 added I36.

## Deferred

- None.
