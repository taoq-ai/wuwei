# Feature Specification: Headless shepherd: a scheduled CLI sweep acts on owned PRs overnight and reports in the morning

**Feature Branch**: `511-headless-shepherd`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #511: the shepherd runs without a live session: a scheduled run sweeps
PR obligations, reviewer pings and merges overnight and reports in the morning. Owner's day,
2026-10-04: the shepherd only runs inside a live session, and session waits die overnight.

## Root cause

- Ownership is day-scoped and the day is the calendar date. `cli/wuwei/workspace.py:429-432`
  (`day_dir`) returns `days/<today>`; after midnight that directory has no `state.json`, so
  `cli/wuwei/state.py:119-128` (`read_state`) returns fresh defaults with empty
  `raised_prs` and `claimed_prs`. `cli/wuwei/watch.py:166` (`owned`) then returns no PRs,
  `watch.poll` reports every PR of yesterday as `gone`, and
  `cli/wuwei/pr_actions.py:235-236` (`evaluate`) raises `day state missing`. From midnight
  until the morning plan is approved nothing owns or reads the PRs, whatever process runs.
- Nothing mechanical acts on a PR without a session. `cli/wuwei/watch.py:532` (`tick`) only
  polls and marks a planner wake (`mark_wake`, line 485). A merge (`merge.execute`) and a
  review ping (`shepherd.post_review_request`) run only from `wuwei pr act`
  (`cli/wuwei/pr_actions.py:500`), which a live planner calls. The one background actor,
  the listener's autostart (`cli/wuwei/listen.py:171-178`), launches model seats through
  `shepherd.headless` (`cli/wuwei/shepherd.py:448`), which the owner rules out at night
  (headless means CLI only, no model calls).
- No command installs a periodic run, and `wuwei doctor` (`cli/wuwei/commands/doctor.py:548`,
  `_day`) says nothing about whether the shepherd survives the session.

## User Scenarios and Testing

### User Story 1: An approval at night is merged or first in the morning (Priority: P1)

The owner schedules the shepherd and ends the day. A reviewer approves a PR at 23:00 (or at
02:00, after midnight). The scheduled sweep merges it when the merge policy clears it, or
queues it. The morning plan shows the outcome first.

**Independent Test**: neutral workspace in `tmp_path` with one raised PR on yesterday's
approved day (fake code host from `tests/test_stop.py`), `WUWEI_NOW` after midnight, no
`state.json` for today; run `bin/wuwei sweep obligations --headless`, then
`bin/wuwei plan propose`.

**Acceptance Scenarios**:

1. **Given** the schedule installed, the PR approved at night and `wuwei merge check`
   clearing it, **When** the headless sweep runs, **Then** `merge.execute` merges it once,
   a `shepherd.overnight` event `{pr, state: approved, outcome: merged}` lands in
   yesterday's `events.jsonl`, `days/<yesterday>/overnight.md` lists it as merged, and the
   next morning's `plan.md` shows an `## Overnight` section, before the goals, with that
   event.
2. **Given** the same PR but the merge policy refuses (for example `merge.auto` off or quiet
   hours), **When** the sweep runs, **Then** nothing is merged, the event has `outcome:
   queued` with the policy reason, and the morning plan's Overnight queue lists it as item 1
   with `wuwei pr act <ref>`.
3. **Given** a second sweep with the PR unchanged, **Then** no second merge call and no
   second `shepherd.overnight` event for that PR.

### User Story 2: A review comment at night is never answered headless (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an unanswered review thread posted at night, **When** the headless sweep runs,
   **Then** no reply is posted on the code host, no draft is created and no seat or model
   is started; a `shepherd.overnight` event `{state: threads_unanswered, outcome: queued}`
   carries the thread as evidence (surface, id, author, path, comment text).
2. **Given** that event, **When** the morning plan is proposed, **Then** the first item of
   its Overnight queue is the reply for that PR with the thread lines under it and the
   command `wuwei pr act <ref>`.
3. **Given** a PR in `ci_red`, `conflicted`, `changes_requested` or `closed`, **Then** it is
   queued the same way with its evidence (failing checks, conflict, review text, closed);
   no fix round, rebase or decision record is started.

### User Story 3: Due review pings go out under the outward tiers (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a PR in `review_stale`, **When** the sweep runs, **Then** it calls the existing
   `shepherd.post_review_request` (re-request reviewers, then the review channel post); on
   exit 0 the event has `outcome: pinged`.
2. **Given** the channel post is held by the outbound tier (`ask`), **Then** nothing is
   sent, the draft stays for the morning and the event has `outcome: queued` with the reason
   `post_review_request` printed.

### User Story 4: The owner schedules it once, from a card (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a planner session (`WUWEI_SESSION_ID` set), **When** `bin/wuwei shepherd
   schedule` runs, **Then** it installs nothing, exits 1 and prints one JSON action
   `{"action": "owner_terminal", "command": "bin/wuwei shepherd schedule", "why": ...,
   "then": ..., "widget": ...}`; the widget is an AskUserQuestion card (header `Shepherd`,
   options `Schedule (Recommended)` and `Not now`) when today's `plan.md` exists, else the
   key is absent.
2. **Given** a host terminal (no session id), **When** `bin/wuwei shepherd schedule` runs,
   **Then** it installs a user launchd (macOS) or systemd (Linux) unit labelled
   `wuwei-shepherd-<hash>` that runs `bin/wuwei shepherd`, the same way `watch install` does;
   `--dry-run` prints the unit and the service commands and changes nothing, in a session
   too.
3. **Given** the unit installed, **When** `bin/wuwei shepherd unschedule` runs in a host
   terminal, **Then** the unit is stopped and removed; in a session it prints the
   `owner_terminal` action for that command instead and exits 1.
4. **Given** `bin/wuwei shepherd` (the unit's command), **Then** it runs the headless sweep
   every 900 seconds under the `.wuwei/shepherd.lock` workspace lock and stops cleanly on
   SIGTERM.

### User Story 5: No schedule, no change; doctor says so (Priority: P1)

**Acceptance Scenarios**:

1. **Given** no unit installed and no headless run, **When** `bin/wuwei doctor` runs,
   **Then** its Day and sessions section has an ok row `shepherd: runs only in a session;
   bin/wuwei shepherd schedule runs it overnight` and the doctor exit code is what it was.
2. **Given** the unit installed and a sweep recorded, **Then** the row reads `shepherd:
   scheduled (launchd|systemd), last swept <timestamp>` (`not yet` before the first sweep).
3. **Given** no headless run, **Then** `sweep obligations` without `--headless`, `watch`,
   `listen`, `pr act` and `plan propose` behave and print exactly as before (no Overnight
   section in `plan.md`).

### Edge Cases

- A planner session is live (registered and not stale, on today's state or on the owning
  day's): the sweep does nothing, writes nothing and exits 0 printing `shepherd: planner
  live; the session shepherd owns the PRs`.
- Today's plan is approved: the owning day is today (daytime runs with no live planner act
  on today's PRs and report into tomorrow's plan).
- No day with a `state.json`, or the owning day owns no PR: exit 0, `shepherd: no owned
  PRs`, no event.
- A PR that cannot be read: `outcome: unmeasured` with the reason, exit 2; the other PRs are
  still swept (fail closed per PR).
- A parked PR or one in `waiting`: no action, no event.
- A PR merged by a person overnight (state `merged`): one `outcome: merged` event.
- A PR whose last overnight event is `merged`: skipped, so a merge the host accepted but has
  not finished is never re-checked into `queued` by "PR already has a merge intent".
- Another process holds `.wuwei/shepherd.lock` (the unit while the owner runs
  `sweep obligations --headless`): exit 2 with the existing `watch.serve` message.
- The listener's opt-in model autostart (`shepherd.autostart`) is unchanged; both can be on.
  Each refreshes state before acting and the ping gate re-checks, so a PR pinged by one is
  `waiting` for the other.

## Requirements

### Functional Requirements

- **FR-001**: `workspace.day_dir` MUST honour an in-process day pin (a module global, never
  an environment variable); with no pin it returns `days/<today>` exactly as now.
- **FR-002**: `shepherd.owning_day(root)` MUST return today's day directory when today's
  state has `gate_approved`, else the newest earlier day directory holding a `state.json`,
  else None.
- **FR-003**: `shepherd.overnight(root)` (one sweep) MUST return 0 and write nothing when a
  planner session is live on today's or the owning day's state. Otherwise it pins the
  owning day for the rest of the call (unpinned in `finally`), refreshes PR state with
  `pr_actions.evaluate`, and acts per PR: `approved` runs `merge.check` and, when it clears,
  `merge.execute`; `review_stale` runs `shepherd.post_review_request`; `merged` is
  recorded; `conflicted`, `ci_red`, `changes_requested`, `threads_unanswered` and `closed`
  are queued with evidence; `waiting` and parked PRs are skipped.
- **FR-004**: The headless sweep MUST NOT call a reply, a fix round, a rebase, a decision
  write, a seat launch or any runtime (model) adapter. Pings and posts go only through the
  existing `post_review_request`, so the outbound tiers (#496) decide send or draft.
- **FR-005**: Each per-PR outcome MUST be one `shepherd.overnight` event `{pr, state,
  outcome (merged|pinged|queued|unmeasured), reason?, evidence?}`, written only when the
  (state, outcome) pair differs from that PR's last `shepherd.overnight` event on the owning
  day. Each sweep past the live-planner and no-PR checks MUST end with one `shepherd.swept`
  event with the counts and the exit, and rewrite `days/<owning day>/overnight.md` from the
  day's events.
- **FR-006**: Both event kinds MUST be listed in `EVENT_PRODUCERS`, so `bin/wuwei event`
  refuses them (producer-only).
- **FR-007**: One renderer, `shepherd.overnight_lines(directory)`, MUST build the Overnight
  text: a heading, the events in order, then the Morning queue (PRs whose latest outcome is
  `queued` or `unmeasured`, oldest first, each numbered with its state, reason, evidence
  lines and `wuwei pr act <ref>`). It returns `[]` when the day has no `shepherd.overnight`
  event. `overnight.md` and `plan.propose` both use it; the plan reads the events, not the
  file.
- **FR-008**: `plan.propose` MUST insert the lines for the newest earlier day directory
  (the `prior[0]` it already computes) right after the Status and Finding lines, before
  `## Goals to confirm`; nothing else in the plan changes.
- **FR-009**: `bin/wuwei sweep obligations --headless` MUST run one sweep under the
  `shepherd` workspace lock (`watch.serve(..., once=True)`) and exit 0 clean, 1 when the
  queue is not empty, 2 when anything was unmeasured. Without `--headless` the command is
  unchanged.
- **FR-010**: New command `bin/wuwei shepherd`: no action runs the loop
  (`watch.serve(root, 'shepherd', overnight, 900)`); `schedule [--dry-run]` and
  `unschedule` reuse `commands.watch.service(..., 'shepherd', ...)` for install and
  uninstall. In a session (`sessions.current()`), `schedule` and `unschedule` without
  `--dry-run` print the `owner_terminal` action and exit 1.
- **FR-011**: `doctor` `_day` MUST add one `shepherd` row, status ok (unmeasured only when
  the events cannot be read), naming scheduled or session-only and the last `shepherd.swept`
  timestamp from the newest two day directories.
- **FR-012**: Registration and docs: `shepherd` in the Owner help group, its write paths in
  `commands.WRITES`, a `bin/wuwei shepherd` row in `docs/site/reference.md` and `shepherd` in
  its Doctor Day list, and one dated paragraph in design 4.2.1.
- **FR-013**: No new guard and no new refusal under any posture. The session path of
  `shepherd schedule` is the command's own owner path (as for `watch uninstall`), not a hook.

### Key Entities

- **Owning day**: the day directory whose state owns the PRs the sweep acts on.
- **Overnight event** (`shepherd.overnight`): one PR outcome. **Sweep event**
  (`shepherd.swept`): one run's counts and exit.
- **Overnight report**: `days/<owning day>/overnight.md`, and the same lines at the top of
  the next morning's `plan.md`.

## Success Criteria

- **SC-001**: The three acceptance bullets of the issue pass as in-process tests on neutral
  fixtures: an approval at night is merged (policy clears) or first in the morning queue; a
  night review comment gets no reply and is the morning plan's first queued item with the
  thread; with no schedule nothing changes and doctor says the shepherd runs only in a
  session.
- **SC-002**: The headless sweep makes zero runtime adapter calls (asserted with a runtime
  fake that fails on any call).
- **SC-003**: The full suite passes with no existing assertion changed.

## Assumptions

- Scheduled run, local variant only: a user launchd (macOS) or systemd `--user` (Linux)
  unit through the existing `watch install` machinery, a loop with a fixed 900 second
  interval. The issue's "user cron" is met by the platform service manager WUWEI already
  uses; cron is not added. Like the listener (design 15.7), it runs while the host is awake.
- The Claude Code scheduled task variant is not built: a scheduled task starts a model
  session to run the command, and the binding note says headless means CLI only, no model
  calls at night. Deferred.
- The repository workflow variant (`.github/workflows/wuwei-sweep.yml`) is not built: the
  sweep needs the workspace (day state, `config.toml`, adapter credentials), which lives on
  the owner's host; a code-host runner has none of it, so the workflow would sweep nothing.
  Deferred to a follow-up that first decides where the workspace state lives.
- "Merge decision already recorded" is the merge policy itself: `wuwei merge check` clears
  only under the owner's recorded `merge.auto` and the 4.6 preconditions (cruise `merge`
  class). Anything it refuses is queued for the owner's merge decision in the morning. No
  new decision lookup.
- "Reminders" are repeat review pings: after a post, `pr_actions.observe` restarts the
  review window, so a PR still unreviewed a window later is `review_stale` again and the
  next sweep pings again. Overdue-action nudges stay with the listener.
- Owner-only scheduling: the issue says printed for a host terminal and confirmed on a card,
  so in a session the command returns the card and the command; the owner installs it. A
  standing process that merges and posts as the owner is the owner's to start.
- The headless sweep never runs beside a live planner: the session's shepherd owns PRs while
  a planner is registered and not stale (`heartbeat._planner`), which avoids double action.
- Events carry the evidence (comment text included) because the morning plan renders from
  events, which only CLI producers write; `overnight.md` is the readable copy and nothing
  trusts it.
- Dedup on (state, outcome) per PR: a second comment in an already queued state is not added
  overnight; `wuwei pr act` reads it fresh in the morning (ponytail ceiling).
- No `tests/test_invariants.py` exists on this base, so no invariant row is added.
