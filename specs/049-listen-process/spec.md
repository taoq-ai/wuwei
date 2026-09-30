# Feature Specification: `wuwei listen` process, inbox and service templates

**Feature Branch**: `049-listen-process`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #49, feat(listener). Design sections 15.1 and 15.2. Wave G (M5-lite):
one inbound channel (Slack DMs polled with urllib, #50), no responder role, no webhook
source, no routines, no budget governor. Depends on #48 (merged, ce6c7cf).

## Root cause (read on main, ce6c7cf)

This is a new process, not a regression. What exists today and why it does not cover the
issue:

- There is no `listen` command: `bin/wuwei listen` exits with argparse's
  `invalid choice: 'listen'`. Commands are discovered from `cli/wuwei/commands/`
  (`cli/wuwei/__main__.py:44-52`) and none is named `listen`.
- #48 shipped the pieces a listener needs but no caller: the `inbound.poll(since)` port
  (`cli/wuwei/registry.py:17`), `adapters/inbound/none.py`, and `inbox.store`
  (`cli/wuwei/inbox.py:18-41`), the only writer of `.wuwei/inbox/inbox.jsonl`. `store`
  appends every event it is given: it has no dedup by id (a retried batch is stored
  twice), and nothing persists a cursor per source (#48 spec, Deferred: "Dedup by id,
  cursor per source, poll loop: #49").
- The watch already has every other part of a supervised process, written for the watch
  only:
  - clock line and health: `watch.health` (`cli/wuwei/watch.py:45-65`) reads only
    `watch: clock` events, only `config['watch']['dead_seconds']`, and only the watch
    unit; its messages say `watch`.
  - unit path: `workspace.watch_unit` (`cli/wuwei/workspace.py:289-296`) returns one
    label per workspace, so a second service would collide with the watch unit.
  - service install: `cli/wuwei/commands/watch.py:26-78` renders
    `templates/wuwei-watch.plist` and `templates/wuwei-watch.service`, whose command is the
    literal word `watch` (`ProgramArguments`, `ExecStart`).
  - singleton lock, SIGTERM and SIGINT handling and the sleep loop: `watch.run`
    (`cli/wuwei/watch.py:426-466`), bound to `.wuwei/watch.lock`, `watch.tick` and the
    watch's read-failure limit.
  - planner wake: the marker written inside `watch.poll` (`cli/wuwei/watch.py:354-374`,
    closure `mark`) and read by `watch.wake` (`cli/wuwei/watch.py:469-493`) holds PR refs
    only; `wake` raises `empty planner wake marker` when it has none (line 479), so an
    inbox batch cannot wake the planner.
  - session start: `lifecycle.session_start` (`cli/wuwei/guards/lifecycle.py:34`) asks
    for the watch's health only.

The notes for this issue name no dry-run failure; the probe above (`bin/wuwei listen` on
main) is the reproduction.

## User Scenarios & Testing

### User Story 1 - Inbound events land in the inbox exactly once, across restarts (Priority: P1)

The owner runs `wuwei listen` (by hand or as a service). Every poll interval it asks the
configured inbound source for events after that source's cursor, stores the new ones in
the inbox, and advances the cursor. Killing and restarting it never loses an event and
never stores one twice.

**Independent Test**: `python -m pytest -q tests/test_listen.py -k "restart or dedup or cursor"`.

**Acceptance Scenarios**:

1. Given a restart mid-batch (the process dies after some events of a batch were stored
   and before the cursor was saved), when the listener runs again, then every event of the
   batch is in the inbox exactly once and the cursor ends at the batch's last event.
2. Given a poll that returns an event already in the inbox (same source and id), then it
   is not stored again.
3. Given a batch was stored, when the next poll runs, then it asks the source for events
   after the last event's `ts`, and the cursor survives a process restart.
4. Given the source or the store fails (exit 2), then the cursor does not move and the
   tick reports exit 2 with the reason; the next tick retries the same range.

### User Story 2 - New events wake the planner, unless the kill switch is off (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_listen.py -k "wake or responder"`.

**Acceptance Scenarios**:

1. Given `responder.enabled = false`, when new events arrive, then no responder run is
   launched (no planner wake marker is written) and the events are still stored.
2. Given `responder.enabled = true` (the default) and a new batch was stored, then the
   planner wake marker names the inbox, session start shows the notice, and the
   registered planner's Stop hook consumes it once, exactly like a PR wake.
3. Given a restart between writing the wake and recording that it was written, then the
   planner is not woken a second time for the same events.
4. Given a PR wake is pending and unseen, when an inbox wake is marked (or the reverse),
   then one marker carries both and neither is lost.

### User Story 3 - A dead listener is reported at session start (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_listen.py -k health`.

**Acceptance Scenarios**:

1. Given no `listen: clock` line for 5 minutes (today's latest clock is 300 s old or
   more), then the next session start reports `listen dead` and exits 1.
2. Given the listener unit is installed and there is no clock line today, then session
   start reports `listen dead`.
3. Given no unit installed and no clock line today (the listener is off, the normal case
   for most workspaces), then session start says nothing about the listener.
4. Given a fresh clock line, then session start says nothing about the listener.

### User Story 4 - Service install, clean shutdown, one listener per workspace (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_listen.py -k "install or shutdown or singleton"`.

**Acceptance Scenarios**:

1. `wuwei listen install --dry-run` prints a launchd or systemd unit that runs
   `bin/wuwei listen` in the workspace, under a label distinct from the watch unit, and
   writes and calls nothing.
2. `wuwei listen install` and `wuwei listen uninstall` write, load, stop and remove that
   unit through the existing service adapter, exactly like the watch.
3. SIGTERM or SIGINT lets the running tick finish, then the process exits 0.
4. A second listener in the same workspace exits 2 while the first holds the lock.
5. A seat cannot run `wuwei listen uninstall` inside a workspace (an uninstalled listener
   reads as off, which would hide a dead listener).
6. With `adapters.inbound = "none"` (the default), `wuwei listen`, `listen --once` and
   `listen install` exit 2 with the reason; nothing is polled.

### Edge Cases

- An empty poll (`Result(0, [])`) leaves the cursor unchanged and writes no wake.
- A batch in which every event is a duplicate still advances the cursor to its last `ts`.
- Two events in one batch with the same source and id: only the first is stored.
- A corrupt inbox line or a corrupt cursor file is exit 2 with the reason; nothing is
  stored and the cursor does not move.
- The clock line is written before polling, so a slow or failing source never makes a
  live process look dead; a failing source is exit 2 in the log, not a dead listener.
- Day rollover: the clock due time and the wake marker follow the watch's existing
  rollover rules (`previous(root)`); the cursor and the woken count live outside the day
  directory and are unaffected.
- `wuwei listen uninstall` with nothing installed exits 0.

## Requirements

### Functional Requirements

- **FR-001**: `wuwei listen` MUST run a loop that, every tick, writes a `listen: clock`
  line when one is due, polls the configured inbound adapter with that source's cursor,
  stores the returned events through `inbox.store`, then advances the cursor. It sleeps
  `min(listen.poll_seconds, 120)` between ticks. `--once` runs one tick and returns its
  exit code: 0 nothing new, 1 new events stored, 2 could not run.
- **FR-002**: `inbox.store` MUST drop events whose `(source, id)` is already in the inbox
  or earlier in the same batch, before redaction and before any write, and return the
  number of events it stored. This is the only dedup; no caller filters.
- **FR-003**: The cursor per source MUST persist in `.wuwei/inbox/cursor.json` and move
  only after `inbox.store` returned exit 0 or 1 for that batch. The next cursor is the
  `ts` of the last event the source returned.
- **FR-004**: When `responder.enabled` is true and the inbox holds more events than the
  last wake covered, the listener MUST mark the planner wake through the same helper the
  PR poll uses, then record the covered count. When it is false, it MUST NOT mark a wake;
  events are still stored.
- **FR-005**: The planner wake marker MUST accept an inbox count alongside PR refs;
  `watch.wake` reports either or both; a pending unseen marker merges PR refs and keeps
  the higher inbox count.
- **FR-006**: Clock health MUST be one function for the watch and the listener, with the
  off, dead and installed rules of #210 unchanged for the watch. The listener's deadline
  is `listen.dead_seconds` (default 300).
- **FR-007**: Session start MUST report the listener's health when it is dead (exit 1)
  or unmeasured (exit 2) and say nothing when it is off or alive.
- **FR-008**: `wuwei listen install [--dry-run]` and `wuwei listen uninstall` MUST reuse
  the watch installer, templates and service adapter; the unit runs `bin/wuwei listen`
  under a label distinct from the watch's.
- **FR-009**: One listener per workspace (lock `.wuwei/listen.lock`); SIGTERM and SIGINT
  stop it cleanly after the current tick, through the same loop the watch uses.
- **FR-010**: `wuwei listen uninstall` MUST be an owner action refused to agent tools
  inside a workspace, like `watch uninstall`.
- **FR-011**: `listen: clock` and `listen: wake` MUST be reserved to the listener (the
  event command names its producer) and classified silent.
- **FR-012**: The existing watch behaviour, its unit label, its templates' rendered
  output and every existing test MUST not change.

### Key Entities

- **Cursor file** `.wuwei/inbox/cursor.json`: `{"cursors": {"<source>": "<ts>"},
  "woken": <int>}`. `source` is the configured `adapters.inbound` name; `woken` is the
  number of inbox lines the last planner wake covered. Protected by the state guard with
  the rest of `.wuwei/inbox/` (#48).
- **Planner wake marker** (day state `watch.wake`): `{"at", "prs": [...], "inbox": <int>}`;
  `inbox` is optional, the number of inbox lines the wake covers.
- **Clock line**: event `listen: clock`; the due time lives in day state
  `watch.listen_clock_at`.
- **Config**: `listen.poll_seconds` (60), `listen.dead_seconds` (300),
  `responder.enabled` (true).

## Success Criteria

- **SC-001**: The three acceptance scenarios of the issue each have one test that fails
  on main and passes after the change.
- **SC-002**: No new module duplicates the watch's lock, signal, health, unit or install
  code; the listener core is one small module plus a thin command.
- **SC-003**: The full suite passes with no existing test changed, except the rows that
  enumerate owner actions, host terminal commands and config defaults.

## Assumptions

- **No responder run in this wave.** The notes (binding) replace "launch a headless
  responder run" with "wake the planner": a new batch sets the planner wake marker
  (`watch.wake`), which session start shows and the registered planner's Stop hook
  consumes; with no live planner session the marker stays pending for #65. "No responder
  run is launched" in the acceptance therefore means "no wake marker is written".
- **No webhook port.** #48 deferred `inbound.receive` to the first webhook adapter and
  wave G has none (Slack is polled). The listener polls only; the local webhook port
  arrives with WhatsApp.
- **No dead-man ping, routines, budget or quiet hours** (15.8): outside the issue scope
  and excluded from wave G.
- **One inbound source per workspace.** Config selects one `adapters.inbound`; the cursor
  file is keyed by that name so a second source later needs no format change.
- **Poll contract.** `poll(since)` returns events oldest first; `since` is `""` on the
  first poll. The next cursor is the last returned event's `ts`, even when every event was
  a duplicate. #50 (Slack) must honour this order.
- **"Processed" means stored and covered by a wake.** A restart mid-batch is safe
  because the cursor moves only after the store and `store` dedups by `(source, id)`; the
  wake is derived each tick from the inbox length against `woken`, so a crash between
  store and wake wakes on the next tick, and a crash between wake and recording `woken`
  finds the marker already covering that count and does not re-wake.
- **Kill switch backlog.** While `responder.enabled = false`, `woken` does not advance;
  when the owner turns it back on, the next tick wakes the planner once for everything
  stored meanwhile (nothing is silently dropped).
- **The inbox is never truncated.** `woken` is a line count; rotation is not in scope.
- **Clock interval is a constant.** The listener writes its clock every 120 s (module
  constant); with the 300 s deadline a live listener is never reported dead. Only the
  poll interval (spec: "default 60 s") and the deadline (acceptance: 5 minutes) are
  config.
- **`adapters.inbound = "none"` refuses to run.** Polling `none` would record an
  `adapter: none` event every minute and, under a service manager, restart every 30 s.
  The command exits 2 with the reason before the loop and before install.
- **A failing source keeps the process up.** A tick whose poll or store fails prints the
  reason and returns 2; the loop continues (the clock stays fresh). Surfacing repeated
  poll failures to the cockpit is deferred.
- **Listener health at session start only.** The acceptance names session start; the
  status line, nudges and sweep keep reporting the watch only.
- **Inbox location** stays `.wuwei/inbox/inbox.jsonl` (#48); the cursor file sits next to
  it so the existing state guard rule for `.wuwei/inbox/` protects it.
- **Unit label.** The watch keeps `wuwei-<hash>` so installed watch units stay valid; the
  listener uses `wuwei-listen-<hash>`.

## Deferred

- Webhook port and `inbound.receive`: first webhook adapter (not wave G).
- Slack inbound adapter: #50.
- Headless responder or planner sessions started from an inbox batch: #65.
- Dead-man ping to an external monitor (15.8).
- Listener health in `status --line`, `nudges` and the cockpit; a read-failure limit like
  the watch's `watch blind`.
