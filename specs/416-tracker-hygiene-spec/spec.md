# Feature Specification: Tracker hygiene, a required ticket per item with bugs, triage and follow-ups as tickets and the item's story as comments

**Feature Branch**: `416-tracker-hygiene-spec`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #416, "spec: tracker hygiene: a required ticket system (Linear by
default, Jira and GitHub Projects as options) that every work item, mid-item bug and triage
result lives in, with decisions, progress and verdicts logged as comments". Owner,
2026-10-03: project management hygiene enforced through a ticket system, Linear by default,
Jira and GitHub Projects as options; bugs found midway and triage results become tickets;
decisions and progress are logged as comments. Owner, in this run: the setup could be part
of the interview.

## Context and root cause

This is a spec-only change: a new design section 5.11 "Tracker hygiene", one row in 4.1, one
bullet in 4.9, the tracker row in section 8, and one constitution paragraph. #417 implements
it. There is no failing behaviour to reproduce; the gap is an absence, confirmed on `main`:

- `cli/wuwei/registry.py:23-24`: the tracker port has `backlog`, `claim`, `transition`,
  `create`, `history`, `created`; no `comment`.
- `cli/wuwei/dispatch.py:107-131` `tracker_call`: claim and transitions pass the item id as
  the ticket id (`tracker.claim(item)`, line 117); no item records a ticket, and a failed
  call is only a measurement (`tracker.call` event), never a refusal.
- `cli/wuwei/commands/build.py:144`: the claim runs after the build has started; nothing
  checks a ticket before `plan approve`, `plan add`, `build next`, `dispatch next` or the
  Agent launch (`cli/wuwei/guards/agent_launch.py`).
- `cli/wuwei/drafts.py:10-11`: tracker drafts support `create` only;
  `cli/wuwei/outward.py:312-315` drafts every tracker write, with no kind that may be sent.
- `cli/wuwei/workspace.py:74-75` and `:165`: `[tracker]` has `backlog_filter` and `states`;
  `adapters.tracker` defaults to `none`; only `linear` and `none` exist under
  `adapters/tracker/`.
- `cli/wuwei/interview.py:199-204`: the tracker question offers None and Linear only.
- `cli/wuwei/closing.py:150-228` `unresolved`: day close never looks at the ticket state.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The owner reads one section that states the whole rule (Priority: P1)

The owner opens design section 5.11 and finds the configuration keys and defaults, where an
item without a ticket is refused (approve, add, build and dispatch, the Agent launch, close),
which sources open tickets and under which class, which comment kinds are written and which
are sent without approval, the three adapters' port methods, and the per-tier exemption.

**Why this priority**: it is the issue's first acceptance and the owner's request.

**Independent Test**: the check script in plan.md fails on a `main` export and passes on the
amended worktree.

**Acceptance Scenarios**:

1. **Given** the amended spec, **When** section 5.11 is read, **Then** it defines the
   `[tracker]` keys `required`, `skip_tiers`, `strict_close`, `create`, `log`, `auto`,
   `max_per_item_per_day`, `project` and `board` with their defaults, and the adapter choice
   `linear`, `jira`, `github`, `none`.
2. **Given** the amended spec, **When** 5.11 is read, **Then** it names the refusal points
   `plan approve`, `plan add`, `build next`, `dispatch next`, the `Agent` launch and `wuwei
   close`, with the one refusal reason naming `bin/wuwei tracker create <item>` and
   `bin/wuwei plan set <item> ticket=<id>`.
3. **Given** the amended spec, **When** 5.11 is read, **Then** it names the creation classes
   (`items`, `bugs`, `triage`, `follow-ups`) and who opens each, the comment kinds
   (`decisions`, `progress`, `verdicts`, `pr`, `close`) with their sources and templates,
   the approval rule per kind (`auto`, else a draft), the loop cap and fold, and the
   per-tier exemption.
4. **Given** the amended spec, **When** section 8 and 5.11 are read, **Then** the tracker port
   lists `comment(item, text, category)` and the draft shape of `create`, and the adapter
   table gives each of Linear, Jira and GitHub its ticket id form, credentials and the calls
   behind backlog, create, comment and transition.

---

### User Story 2 - The #417 builder needs no further design decision (Priority: P1)

The builder of #417 maps every #417 acceptance line to a 5.11 sentence and every file it must
touch to plan.md "Implementation map for #417", and finds no open choice.

**Why this priority**: the issue's second acceptance.

**Independent Test**: a reviewer walks the seven #417 acceptance lines against 5.11 and the
implementation map; each has its answer.

**Acceptance Scenarios**:

1. **Given** `required = true` and an approved item without a ticket, **When** 5.11 is read,
   **Then** it says `dispatch next` refuses naming `tracker create`, and that creation records
   the ticket so the dispatch proceeds and the board shows it.
2. **Given** a builder reporting a bug mid-item, **When** 5.11 is read, **Then** it says
   `tracker create --bug` opens a linked ticket, as a draft unless `bugs` is in `auto`, once,
   with repository-relative evidence lines only.
3. **Given** a decision outcome, a phase change and a gate verdict, **When** 5.11 is read,
   **Then** it says one comment each is written or drafted per `auto` and a second run
   writes nothing new.
4. **Given** `max_per_item_per_day` reached, **When** 5.11 is read, **Then** it says the rest
   fold into one comment with a count and one `tracker.folded` event.
5. **Given** each adapter's recorded fixtures, **When** 5.11 is read, **Then** it says Linear,
   Jira and GitHub each pass the tracker port contract test.
6. **Given** `close` on an item whose ticket is not done, **When** 5.11 is read, **Then** it
   says close refuses naming `bin/wuwei tracker done <item>` unless `strict_close = false`.
7. **Given** a `light` item with `skip_tiers = ["light"]`, **When** 5.11 is read, **Then** it
   says no ticket is required and one `tracker.skipped` event says so.

---

### User Story 3 - The rest of the spec agrees and nothing else changes (Priority: P2)

4.1, 4.9 and section 8 agree with 5.11, the constitution states that WUWEI's own work keeps
the same hygiene, and no runtime file changes.

**Why this priority**: consistency, and the issue is spec-only.

**Independent Test**: `git diff --stat main` lists only the design spec, the constitution
and this feature directory; `python -m pytest -q` passes.

**Acceptance Scenarios**:

1. **Given** the amendment, **When** 4.1 is read, **Then** the Agent launch row refuses an item
   without a required ticket (5.11).
2. **Given** the amendment, **When** 4.9 is read, **Then** tracker writes in `tracker.auto`
   are auto-sent and every other tracker write is a draft.
3. **Given** the amendment, **When** the constitution is read, **Then** its Workflow section
   says WUWEI's own features keep tracker hygiene through their GitHub issues.

### Edge Cases

- `adapters.tracker = "none"`: `required` is not in force; nothing refuses and nothing is
  written; existing behaviour is unchanged.
- An item whose ticket draft is pending: the refusal names `bin/wuwei drafts approve <draft>`.
- A tracker that cannot be read: `plan set` and `tracker create` exit 2 and record nothing;
  `doctor` fails the tracker row while `required` is in force.
- A gate tier that rises out of `skip_tiers` after the build: `dispatch next` refuses until a
  ticket exists.
- A comment the outward lint refuses: recorded as refused with the reason, never retried.
- An evidence line with an absolute path: the creation is refused.
- GitHub ticket ids (`owner/repo#12`) are not valid item ids: the lead names them in the
  candidate's `ticket` field.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The design spec MUST gain `### 5.11 Tracker hygiene (owner, 2026-10-03, #416)`
  with the text in contracts/design-amendment.md block A.
- **FR-002**: 5.11 MUST define every `[tracker]` key with its default and the four adapter
  names, keep `adapters.tracker` defaulting to `none`, and make `required` in force only
  with an adapter configured.
- **FR-003**: 5.11 MUST state where the ticket of an item lives (`tickets` in `state.json`,
  CLI-written), its three sources, and that tracker operations use the ticket id.
- **FR-004**: 5.11 MUST name one CLI check, its single refusal reason, the command and hook
  refusal points, the deciding tier, and the `tracker.skipped` event.
- **FR-005**: 5.11 MUST state the close rule, its event evidence, the `tracker done` command
  and the `strict_close` switch.
- **FR-006**: 5.11 MUST state the creation command, its classes and sources, parent linking
  per adapter, the evidence rule, idempotency and the `tracker.created` event.
- **FR-007**: 5.11 MUST state the comment writer, its triggers, its stable keys, the five
  kinds with their sources and templates, and the outward lint.
- **FR-008**: 5.11 MUST state the approval rule (`auto` or draft), its relation to 4.9 and
  to cruise mode, and the defaults.
- **FR-009**: 5.11 MUST state the loop cap, the fold and the `tracker.folded` event.
- **FR-010**: 5.11 MUST state the port changes and, per adapter, the ticket id, credentials
  and calls, and the contract test with recorded fixtures.
- **FR-011**: 5.11 MUST state the setup link detection, the three interview questions, the
  doctor row, and the owner-facing surfaces and documents.
- **FR-012**: 4.1, 4.9 and section 8 MUST change as blocks B, C and D say; the constitution
  as block E. The 3.1 layout lists the jira and github tracker adapters.
- **FR-013**: No file outside `docs/specs/2026-09-24-wuwei-design.md`,
  `.specify/memory/constitution.md` and `specs/416-tracker-hygiene-spec/` changes.

### Key Entities

- **Ticket**: a tracker issue an item lives in; id per adapter (`ENG-123`, `PROJ-123`,
  `owner/repo#123`); recorded in `tickets[item] = {id, source}`.
- **Creation class**: `items`, `bugs`, `triage`, `follow-ups`.
- **Comment kind**: `decisions`, `progress`, `verdicts`, `pr`, `close`.
- **Log entry**: one comment's stable key and outcome in `tracker_log`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: the plan.md check script fails on a `git archive main` export and prints `OK:
  tracker hygiene stated` on the worktree.
- **SC-002**: each of the seven #417 acceptance lines maps to a 5.11 sentence and a row of
  the implementation map, with no open choice.
- **SC-003**: `python -m pytest -q` passes with no test file changed.

## Assumptions

- Linear "by default" means the recommended choice in `setup` and the interview, not the
  schema default: `adapters.tracker` stays `none` so a fresh workspace works on defaults
  (#360) without a Linear key. Overturned if the owner wants a missing `LINEAR_API_KEY` to
  fail a first day.
- `required` is a plain boolean defaulting to `true` and in force only when an adapter is
  configured; this is the issue's "default when a tracker adapter is configured; false with
  none" without a conditional default in the schema.
- Tier names are lowercase (`light`, `standard`, `full`) as in `dispatch.TIERS` and
  `repos.gates.floor`; #411's `LIGHT` is the same tier.
- The issue's "dispatch next" covers both CLI paths that start work: `build next` (builder)
  and `dispatch next` (gates); `plan add` refuses too because intraday intake (#176) is the
  other way into the day.
- Day close (`wuwei close`) is the issue's "close": it checks items merged today; carried and
  parked items keep open tickets. The evidence is the CLI-written `tracker.call` done event,
  so close needs no tracker read.
- The item's own ticket (`tracker create <item>`) is creation class `items`. It is always
  allowed (it is how `required` is met) and is a draft unless `items` is in `auto`.
- Tracker writes are not decision records, so cruise levels (#282) do not apply; `auto` is the
  owner's list, like 4.9's work channels, and the `message` ceiling holds because any text
  naming a person drafts.
- `link` is a parent on `create`, not a separate port operation: Linear sub-issue, Jira
  Relates link, GitHub body reference.
- Comments are written at the watch sweep, at close and on demand, not after every event; a
  delay of up to one sweep is acceptable for hygiene.
- `max_per_item_per_day` defaults to 10 (the issue names no number): enough for one item's
  normal day once the build loop's fast-check lines fold, small enough to stop a loop.
- Comment templates avoid the words the outward lint refuses (`seat`, `agent`, `sentinel`,
  `WUWEI`, `queued`, `gate verdicts`); the day and item id prefix replaces a WUWEI marker.
- Jira's site URL is `JIRA_SITE` in `.wuwei/env` (public, like `SLACK_OWNER_DM_CHANNEL`);
  GitHub uses `GITHUB_TRACKER_TOKEN`, not `GITHUB_TOKEN`, so `gh` in seat environments never
  picks it up.
- Numbering: the wave assigns 5.9 to #411, 5.10 to #415, 5.11 to this and 5.12 to #418, while
  `main` has 5.9 Cockpit. This section keeps 5.11 and its heading and sits before `## 6.
  Memory`; renumbering 5.9 Cockpit is #411's concern.
- The owner's "could be part of the interview" adds two interview questions (tickets
  required, updates without approval) beside the widened tracker question; no separate
  wizard.
