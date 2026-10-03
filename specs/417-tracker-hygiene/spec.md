# Feature Specification: Tracker hygiene, required tickets per item, bug, triage and follow-up tickets, and the item's story as comments

**Feature Branch**: `417-tracker-hygiene`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #417, "feat(tracker): tracker hygiene: required tickets per item, mid-item
bug and triage tickets, decisions, progress and verdicts as comments, Linear by default with
Jira and GitHub Projects adapters". It implements design section 5.11 (amendment #416, merged
as #438) and the rows it changed in 4.1, 4.9 and section 8.

## Context and root cause

There is no failing behaviour to reproduce: the notes name no dry-run workspace, and the gap is
an absence. Confirmed on `main` (read-only) and by a baseline run of the tracker and drafts
tests (`tests/test_linear_loop.py`, `tests/test_reference_adapters.py`, `tests/test_drafts.py`:
108 passed):

- `cli/wuwei/registry.py:23-24`: the tracker port has `backlog`, `claim`, `transition`,
  `create`, `history`, `created`; there is no `comment`.
- `cli/wuwei/dispatch.py:107-131` `tracker_call`: claim and transitions send the item id as the
  ticket id (`tracker.claim(item)`, line 117); no state key maps an item to a ticket, and a
  failed call is only a `tracker.call` measurement, never a refusal.
- `cli/wuwei/plan.py:192-249` `approve`, `:252-309` `add`, `cli/wuwei/commands/build.py:102-145`
  `next_action`, `cli/wuwei/dispatch.py:148-223` `next_step` and
  `cli/wuwei/guards/agent_launch.py:134-193` `reserve`: nothing checks a ticket.
- `cli/wuwei/outward.py:345-348` `classify`: every tracker write falls to the final non-chat
  branch and drafts; nothing can be sent without approval. `cli/wuwei/drafts.py:10-11`: tracker
  drafts support `create` only, and `approve` (line 169) drops the send result, so an approved
  creation records nothing.
- `cli/wuwei/workspace.py:74-75`: `[tracker]` has only `backlog_filter` and `states`;
  `adapters/tracker/` holds only `linear.py` and `none.py`; `adapters/_http.py:41-66` `request`
  only POSTs and cannot read an empty body (Jira answers 204).
- `cli/wuwei/closing.py:150-228` `unresolved`: day close never looks at the ticket state.
- `cli/wuwei/interview.py:199-204`: the tracker question offers None and Linear only; `setup`,
  `doctor`, the board and `wuwei next` know nothing of tickets.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No item runs without a ticket (Priority: P1)

With a tracker configured, the owner never finds an item that ran a whole day without a ticket.
`plan approve`, `plan add`, `build next`, `dispatch next` and the Agent launch refuse an item
that needs a ticket and has none, with one reason that names the command that fixes it.

**Why this priority**: it is the rule the feature exists for and the first acceptance line.

**Independent Test**: a workspace with a fake tracker adapter, `required = true`, one approved
item at `gate` with no ticket; run `dispatch next`, then `tracker create`, then `dispatch next`.

**Acceptance Scenarios**:

1. **Given** `adapters.tracker = "linear"`, `required = true` and an approved item without a
   ticket, **When** `wuwei dispatch next <item>` runs, **Then** it exits 1 and the reason names
   `bin/wuwei tracker create <item>` and `bin/wuwei plan set <item> ticket=<id>`; **When**
   `wuwei tracker create <item>` then succeeds (recorded fixture, `items` in `auto`), **Then**
   `tickets` holds the ticket, `dispatch next` proceeds, and `wuwei board` shows the ticket id
   beside the item.
2. **Given** a ticket draft for the item is pending, **When** any refusal point refuses, **Then**
   the reason names `bin/wuwei drafts approve <draft>`; **When** the owner approves it and the
   adapter confirms, **Then** `tickets` holds the ticket.
3. **Given** two approved candidates without tickets, **When** `plan approve` runs, **Then** one
   refusal lists both and nothing is approved; **Given** a candidate with a `ticket` field or one
   discovered from the tracker backlog, **Then** approve records its ticket.
4. **Given** `plan add` for a candidate without a ticket, **Then** discovery intake turns it into
   an owner proposal carrying the reason; `wuwei plan add` exits 1.
5. **Given** a WUWEI seat launch (PreToolUse `Agent`) for an item without a ticket, **Then** the
   launch is refused with the same reason, under the `seats` area.
6. **Given** a LIGHT item with `skip_tiers = ["light"]`, **Then** no ticket is required, admission
   writes one `tracker.skipped` event, and a gate tier that later rises to `standard` makes
   `dispatch next` refuse until a ticket exists.
7. **Given** `adapters.tracker = "none"` or `required = false`, **Then** nothing refuses and
   behaviour is unchanged.
8. **Given** `wuwei plan set <item> ticket=<id>`, **Then** the ticket is recorded only after the
   adapter's `created(<id>)` confirms it; a tracker that cannot be read exits 2 and records
   nothing.

---

### User Story 2 - Bugs, triage results and follow-ups become tickets (Priority: P1)

A builder that finds a bug outside its item's scope opens a linked ticket instead of widening
the item; the planner does the same for a retro follow-up; the on-call seat for a triage result.

**Why this priority**: second acceptance line; the owner's "bugs found midway become tickets".

**Independent Test**: `wuwei tracker create --bug <item> "<title>" --evidence "<file:line>"`
twice against a fake adapter, with and without `bugs` in `auto`.

**Acceptance Scenarios**:

1. **Given** a builder reporting a bug mid-item, **When** `tracker create --bug <item> "<title>"
   --evidence "<line>"` runs, **Then** it opens a ticket whose parent is the item's ticket, as a
   draft with defaults, or directly when `bugs` is in `auto`; the description holds the evidence
   lines.
2. **Given** the same call again, **Then** it prints the existing ticket or draft and writes
   nothing.
3. **Given** an evidence line holding an absolute path, **Then** the creation exits 1 and writes
   nothing.
4. **Given** a class not in `tracker.create`, **Then** the command exits 1 naming the key.
5. **Given** each created ticket, **Then** one `tracker.created` event (class, subject, ticket,
   parent) is written and the board lists it under the item.

---

### User Story 3 - The ticket carries the item's story (Priority: P1)

Decisions, progress, gate verdicts, the pull request and the close outcome appear as comments
on the item's ticket, once each, mechanical ones sent, the rest drafted for the owner.

**Why this priority**: third and fourth acceptance lines.

**Independent Test**: seed today's events with a decision outcome, a phase change and a gate
verdict for an item with a ticket; run `wuwei tracker log` twice against a fake adapter.

**Acceptance Scenarios**:

1. **Given** a decision outcome, a phase change and a gate verdict on an item, **When** `wuwei
   tracker log` runs, **Then** one comment each is written (kinds in `auto`) or drafted (the
   rest), each prefixed `[<day> <item>]`; **When** it runs again, **Then** it writes nothing new.
2. **Given** more entries for one ticket than `max_per_item_per_day` allows, **Then** the last
   allowed comment is one fold `Folded <n> updates: <kind> <count>, ...`, one `tracker.folded`
   event records the counts, and later entries that day are counted in `tracker_log` only.
3. **Given** a comment the outward lint refuses, **Then** it is recorded as refused with the
   reason and not retried.
4. **Given** the watch sweep, or `wuwei close` after its checks pass, **Then** the same writer
   runs.

---

### User Story 4 - Close checks the ticket reached done (Priority: P2)

**Why this priority**: sixth acceptance line.

**Independent Test**: an item merged today with a ticket and no successful done transition;
`wuwei close` with `strict_close` on and off.

**Acceptance Scenarios**:

1. **Given** `close` on an item merged today whose ticket has no successful done transition,
   **Then** close refuses naming `bin/wuwei tracker done <item>`.
2. **Given** `strict_close = false`, **Then** the same line is printed and close does not refuse.
3. **Given** `wuwei tracker done <item>`, **Then** it runs the done transition on the ticket and
   writes the `tracker.call` event the check reads.

---

### User Story 5 - Linear, Jira and GitHub behind one port (Priority: P1)

**Why this priority**: fifth acceptance line; the owner's choice of tracker.

**Independent Test**: one parametrized contract test replays recorded fixtures per adapter.

**Acceptance Scenarios**:

1. **Given** each adapter's recorded fixtures, **When** the contract test calls `backlog`,
   `claim`, `transition`, `create`, `comment`, `history` and `created`, **Then** every call exits
   0 with the port's shapes, for `linear`, `jira` and `github`, with no network.
2. **Given** a missing credential, **Then** the call exits 2 naming the variable and makes no
   request.

---

### User Story 6 - Setup, interview, doctor and docs know the tracker (Priority: P3)

**Acceptance Scenarios**:

1. **Given** a repository whose README links `linear.app`, **When** `setup` runs, **Then** it
   prints the link it found before the interview.
2. **Given** the interview, **Then** the tracker question offers Linear first, Jira, GitHub,
   None or `<tracker> <project>` typed in, and two new questions set `tracker.required` /
   `skip_tiers` and `tracker.auto`.
3. **Given** `required` in force and a backlog read that fails, **Then** `doctor` fails the
   tracker row naming the missing credentials or `bin/wuwei config set tracker.required false`.
4. **Given** the site docs, **Then** configuration, adapters, glossary, daily and reference pages
   carry the `[tracker]` keys and the four commands.

### Edge Cases

- `adapters.tracker = "none"`: `required` is not in force; `tracker log` writes nothing and exits
  0; `tracker create` exits 2 (`tracker adapter is none`).
- An item with neither a recorded gate tier nor a lead tier is not exempt.
- A GitHub `project` or `board` whose owner is not in `outbound.code_host_orgs`: every write is
  a draft whatever `auto` says.
- A text that names a person (a mention or an address) or matches a sensitive, commitment or
  disagreement pattern drafts whatever `auto` says.
- A port call that cannot run (exit 2) leaves the log entry unrecorded and `tracker log` exits 2;
  the next run retries it.
- A claimed entry whose send outcome is unknown (crash between claim and result) is never
  retried, as for drafts.
- GitHub ticket ids (`owner/repo#12`) are never item ids; the lead names them in the
  candidate's `ticket` field.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `[tracker]` MUST gain `required` (true), `skip_tiers` ([]), `strict_close` (true),
  `create` (["bugs", "triage", "follow-ups"]), `log` (the five kinds), `auto` (["progress",
  "pr", "close"]), `max_per_item_per_day` (10), `project` ("") and `board` (""); unknown values
  in the four lists are config findings; `adapters.tracker` stays `none` by default.
- **FR-002**: `tickets` (item to `{id, source}`) and `tracker_log` (entry key to outcome) MUST be
  CLI-written state keys; `tracker.created`, `tracker.skipped`, `tracker.folded`,
  `tracker.logged` and `plan.set` MUST be CLI-written event kinds.
- **FR-003**: One pure function `tracker.check` MUST decide off, ticket, skipped or missing with
  the single 5.11 reason; `plan approve`, `plan add`, `build next`, `dispatch next` and the
  Agent launch MUST call it and refuse on missing.
- **FR-004**: `plan approve` and `plan add` MUST record the candidate's `ticket` field, or the
  candidate id when it was discovered from the tracker backlog; `plan approve
  --import-yesterday` MUST carry yesterday's tickets; `plan set <item> ticket=<id>` MUST verify
  with `created` before recording.
- **FR-005**: Every tracker operation on an item (claim, transitions, comments, lead-time
  history) MUST use its ticket id, falling back to the item id only when it has none.
- **FR-006**: `wuwei tracker create <item>` and `--bug|--triage|--follow-up <subject> "<title>"
  --evidence "<line>"` MUST build the neutral draft, refuse a class not in `create` and any
  absolute path, be idempotent per class, subject and title, and on a confirmed ticket write
  `tickets` (class `items`) and one `tracker.created` event; `drafts approve` of a tracker
  creation MUST do the same through the same writer.
- **FR-007**: `wuwei tracker log` MUST turn today's CLI events into the five comment kinds per
  5.11's table, filtered by `log`, once per stable key, with the cap and fold; the watch sweep
  and `wuwei close` (after its checks pass) MUST run it.
- **FR-008**: The outward policy MUST send a tracker write whose kind or class is in `auto` and
  draft every other, after the existing 4.9 checks; a GitHub destination outside
  `code_host_orgs` MUST draft.
- **FR-009**: `wuwei close` MUST refuse (strict) or print (not strict) for an item merged today
  with a ticket and no successful done transition today, naming `bin/wuwei tracker done
  <item>`.
- **FR-010**: The port MUST gain `comment(item, text, category)`; `create(draft)` MUST accept
  `{title, description, item, category, parent}` and return `{id, url}`; `linear` MUST be
  extended and `jira` and `github` added, each passing one contract test on recorded fixtures.
- **FR-011**: `setup` MUST print tracker links found in each repository; the interview MUST offer
  the four trackers and the two new questions; `doctor` MUST have a tracker row; the board,
  `wuwei next` and the loop DM MUST show the ticket id beside the item; the site docs and the
  charters MUST name the new commands.
- **FR-012**: No hook gains a module import on its common path (#346); `wuwei.tracker` is
  imported lazily and imports nothing beyond what hook paths already load.

### Key Entities

- **Ticket**: `tickets[item] = {'id': str, 'source': 'candidate' | 'tracker' | 'set' |
  'create' | 'yesterday'}`.
- **Log entry**: `tracker_log[key] = {'outcome': 'sending' | 'written' | 'drafted' | 'refused'
  | 'folded', 'ticket': str, 'kind': str, ...}`; creations use the key
  `create:<class>:<subject>:<title>`.
- **Creation class**: `items`, `bugs`, `triage`, `follow-ups`. **Comment kind**: `decisions`,
  `progress`, `verdicts`, `pr`, `close`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: each of the seven acceptance lines of #417 has a passing test named in tasks.md.
- **SC-002**: `python -m pytest -q` passes; no test uses the network.
- **SC-003**: no new import on a hook's common path (`tests/test_hooks.py` unchanged and green).

## Assumptions

- Tier names are lowercase (`light`, `standard`, `full`) as in `dispatch.TIERS` and 5.11; the
  issue's `skip_tiers = ["LIGHT"]` is `["light"]`, and `"LIGHT"` is a config finding.
- The deciding tier is `items[item]['gates']['tier']` when recorded, else the lead's `tier`;
  `dispatch next` checks after it records the tier, so a rise out of `skip_tiers` refuses.
- `plan add` refuses with `state.StateError` (exit 1 on the CLI); intake already turns any
  `ValueError` into an owner proposal.
- Progress lines are: a phase change (`Phase: <phase>.`; a park is the phase `parked`), a
  builder or review seat start or stop (`Build started.`, `Review quality stopped.`), and a
  fast-check result (`Fast checks: <n> passed, <m> failed.`, which needs the counts added to
  the `build.checked` event payload). A phase change to `merged` is a `close` entry (`Merged in
  <pr>.`), not progress.
- `Pull request: <pr>.` uses the recorded reference (`owner/repo#12`), not a URL; the code host
  links it.
- `decisions` covers `decision.decided` events whose payload or D-n record names the item; a
  carry or park decision from `plan carry|park` is a `close` entry (`Carried to <next day>
  (D-n).`, `Parked (D-n).`) and not also a decision comment.
- `tracker log` comments only on items with a recorded ticket; an item without one has nowhere
  to log, whatever `required` says.
- Each entry is claimed (`sending`) in state before the port call and settled after, so two
  concurrent runs never post one comment twice; an unknown outcome is not retried, as in
  `drafts.approve`.
- A fold comment's category is the first folded kind not in `auto`, else the first kind, so a
  fold holding any non-auto kind drafts.
- Idempotency of creations and the cap are per day, because `tracker_log` lives in the day's
  state; a creation on a later day sees `tickets` (items) but not yesterday's bug key.
- `tracker create` exits 0 when it created or found the ticket, 1 when it drafted (and prints
  `bin/wuwei drafts approve <draft>`) or refused, 2 when it could not run.
- `tracker log` failures in `wuwei close` are printed and do not change the close exit; comments
  are hygiene, `strict_close` is the close rule.
- "Names a person" is the existing audience evidence in `outward.classify` (mentions and
  addresses); no new person detection.
- Adapters read `[tracker]` (`project`, `board`, `states.done`) through one helper in
  `adapters/_http.py` that loads the workspace config, as the outward decorator already does.
  Linear's empty `project` falls back to `backlog_filter`, GitHub's to the first configured
  repository; Jira needs `project`.
- GitHub `history` reports the first assignment as `In Progress` (Projects v2 has no readable
  status history); creation does not add the issue to the board (the board's own auto-add
  workflow does); without a board, `in_review` is a label and `done` closes the issue.
- Jira `JIRA_SITE` is a full `https://` origin and public (kept from seats, not redacted);
  `JIRA_EMAIL`, `JIRA_API_TOKEN` and `GITHUB_TRACKER_TOKEN` are credentials.
- `--triage` subjects are day item ids or any safe id until #415 (incident ids) lands; the
  parent is the subject's ticket when one is recorded.
- The DM surface is the negotiation-loop notice in `listen.notify`, the one DM that names an
  item.

## Deferred

- Incident ids as `--triage` subjects: #415.
- Adding created GitHub issues to a Projects v2 board, and Projects v2 status history for lead
  time: not needed by any acceptance line.
