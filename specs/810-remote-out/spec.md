# Feature Specification: delete the remote control plane, the listener and the inbox

**Feature Branch**: `810-remote-out`

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #810, part 7 of the #789 deletion pass: "Delete the remote control plane, the inbound listener and the inbox (design 15, M5): the `remote` and `listen` commands, the inbound adapters, their config tables and tests. The item loop never reaches them." Acceptance: no module, adapter, config key, doctor row, charter, skill or docs page refers to the control plane, the listener or the inbox; `init --upgrade` removes the retired keys; design spec section 15 is marked retired by #789 (owner, 2026-10-10).

## Context

Design 15 (M5) added a second long-running process next to the watch: `wuwei listen` polls
an inbound source (Slack) into `.wuwei/inbox/inbox.jsonl`, wakes the planner with
`inbox to line N`, and its responder turns owner DM messages into commands (`plan`, `ask`,
`status`, `report`, `stop`, `approve D-n`, `more D-n`, `undo D-n`) guarded by a pinned
sender, a TOTP second factor and a confirm window. It also DMs the owner on PR changes,
negotiation loops, cruise answers and owner-routed decisions, starts a headless shepherd seat
per mechanical PR action, and probes owned PRs every 30 s so the watch skips its own PR poll.
`wuwei remote ack` clears refused-sender pages.

None of it is on the item loop (brief, builder seat, gates, verdicts, fix rounds, `pr raise`,
merge). It is process machinery around the owner's attention, so it goes. The watch keeps
polling PRs on its own interval, as it already does when no listener runs. Claude Code Remote
Control (a Claude Code feature, not WUWEI code) still pushes the planner's question cards to
the phone; nothing here touches it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No listener, inbox or control plane in the CLI (Priority: P1)

The CLI has no `listen` or `remote` command, no inbound port, no inbox, no control plane and
no config for them.

**Why this priority**: it is the issue.

**Independent Test**: `wuwei --help --all` lists neither `listen` nor `remote`;
`registry.PARAMETERS` has no `inbound`; `workspace.SCHEMA` has no `listen`, `responder`,
`control_plane`, `adapters.inbound` or `shepherd.autostart`, and `owner.verbosity` has no
`dm`; the modules `wuwei.listen`, `wuwei.remote`, `wuwei.inbox`, `wuwei.control_plane` and the
package `adapters.inbound` do not import.

**Acceptance Scenarios**:

1. **Given** any workspace, **When** `wuwei listen` or `wuwei remote ack` runs, **Then** the
   parser refuses it as an unknown command.
2. **Given** a workspace, **When** `wuwei doctor` runs, **Then** there is no `listener` day
   row, no `listen-install` fix and no `claude` host row that names the listener.
3. **Given** a day, **When** `wuwei status --line` runs, **Then** the health group reads
   `watch <state>` with no `listen` part, and the attention group has no `phone answers`.
4. **Given** a SessionStart, **When** lifecycle reports health, **Then** it reports the watch
   only and prints no "answered from the phone" lines.

---

### User Story 2 - The watch owns PR polling (Priority: P1)

With no listener, the watch polls owned PRs every `pr.poll_seconds` unconditionally.

**Why this priority**: the only loop-adjacent job the listener held; losing it would leave PR
state stale.

**Independent Test**: `watch.tick` with `poll_at` due calls `poll_prs` even when a
`listen: clock` line exists today.

**Acceptance Scenarios**:

1. **Given** a due `poll_at` and a `listen: clock` event written today before the upgrade,
   **When** the watch ticks, **Then** it polls PRs.

---

### User Story 3 - Upgrade leaves nothing running or stale (Priority: P1)

An owner who had the listener installed upgrades with `init --upgrade`; the installed listener
service is stopped and removed, the retired config keys go (after #799), and today's state
written before the upgrade still reads.

**Why this priority**: a leftover launchd or systemd unit would restart `bin/wuwei listen`,
which no longer exists, in a loop.

**Independent Test**: with a `wuwei-listen-<hash>` unit file present, `init --upgrade` stops
and deletes it and prints one line; `--dry-run` prints "Would remove" and changes nothing.

**Acceptance Scenarios**:

1. **Given** an installed listener unit, **When** `init --upgrade` runs, **Then** the unit is
   stopped and removed and the output says `Removed the listener service (no longer shipped)`.
2. **Given** a planner wake marker written today with only an `inbox` count, **When**
   SessionStart reads the wake, **Then** it shows no wake and raises nothing.
3. **Given** a `config.toml` with `[listen]`, `[responder]`, `[control_plane]`,
   `adapters.inbound`, `shepherd.autostart` or `owner.verbosity.dm`, **When** `init --upgrade`
   runs after #799, **Then** those keys are removed (plan.md, "RETIRED at rebase").
4. **Given** a day file with an interview answer for `phone`, **When** setup or calibrate
   reads it, **Then** it loads (the id is retired, not unknown).

---

### User Story 4 - Setup connects Slack for sending only (Priority: P2)

`wuwei setup slack` keeps the bot token, the app DM channel and `adapters.chat = "slack"`, and
no longer pins a sender, writes a TOTP secret, sets an inbound adapter or installs a listener.

**Why this priority**: outward sends to the owner DM (digest, drafts) still use the chat port.

**Independent Test**: `setup slack` with token and channel typed writes both to `.wuwei/env`,
sets `adapters.chat = "slack"`, and installs no service.

---

### User Story 5 - Docs, charters and the design spec say it is gone (Priority: P2)

**Why this priority**: issue acceptance; lower than behaviour.

**Independent Test**: `grep -rniE "wuwei listen|listener|control.plane|inbox|inbound|remote
ack|TOTP|responder" charters skills hooks agents docs/site README.md templates` finds only the
outward mail vocabulary word `inbox` in `docs/site/security.md`. The design spec heading of
section 15 carries "(retired by #789, owner, 2026-10-10)".

---

### Edge Cases

- An events file written today before the upgrade holds `listen: clock`, `remote.*`,
  `decision.replied` or `inbox.redacted` lines: `signal.classify` gives a kind it no longer
  lists the default non-page tier; `status.scan` no longer reads them for health or answers.
  None of them pages.
- `.wuwei/inbox/` stays on disk (redacted owner messages); nothing reads or writes it. Part 24
  removes obsolete files.
- A session row with `role: remote` in today's state still reads; `sessions.registered`
  returns None for it.
- The `WUWEI_SEAT_ROLE == 'shepherd'` checks in merge, outward and the PR guard stay: they are
  refusals that stop a seat from merging or sending, not listener code.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Delete `cli/wuwei/control_plane.py`, `cli/wuwei/inbox.py`,
  `cli/wuwei/listen.py`, `cli/wuwei/remote.py`, `cli/wuwei/commands/listen.py`,
  `cli/wuwei/commands/remote.py` and `adapters/inbound/`; no module imports them.
- **FR-002**: `workspace.SCHEMA` drops `listen`, `responder`, `control_plane`,
  `adapters.inbound` and `shepherd.autostart`; `workspace.SURFACES` drops `dm`;
  `registry.PARAMETERS` drops `inbound`; `telemetry.ADAPTERS` drops `inbound`.
- **FR-003**: The template drops `[control_plane]`, the `dm` surface in the `owner.verbosity`
  comment and `shepherd.autostart`.
- **FR-004**: `watch.listening` is deleted; `watch.tick` polls PRs whenever `poll_at` is due.
- **FR-005**: `watch.mark_wake` drops the `inbox` keyword; `watch.wake` renders PRs and
  summaries only and treats a stored marker with no PRs and no summaries (a legacy inbox-only
  marker) as no wake, without raising.
- **FR-006**: `shepherd.pending`, `shepherd.headless` and `shepherd.HEADLESS` (with
  `_TRIAGE` and `_STOP`) are deleted; the runtime adapter function `claude.headless` (with
  `SESSION` and `TIMEOUT`) is deleted.
- **FR-007**: SessionStart (`guards/lifecycle.py`), the heartbeat `clocks` probe,
  `status.scan` and doctor report the watch clock only; the phone-answer row
  (`decision.answered` built from `decision.replied`) and its SessionStart lines go;
  `status.snapshot` drops `listen` and `answered`.
- **FR-008**: `status.scan` drops the `remote.refused` pin filter and the `remote.acknowledged`
  clearing; `signal` drops every `remote.*`, `listen: *`, `inbox.redacted`,
  `decision.replied`, `decision.escalated`, `pr.notified`, `negotiation.notified`,
  `decision.notified` and `shepherd.dispatched` kind it lists, the `remote.refused` page and
  the `shepherd.finished` branch; `commands/event.py` and `state.py` drop producer text that
  names `wuwei listen`, `wuwei remote` or the control plane.
- **FR-009**: `config check` drops the control-plane section, the inbound credential row and
  the pin finding; `env.CREDENTIALS` drops `WUWEI_TOTP_SECRET`.
- **FR-010**: `setup slack` keeps token, app DM channel and `adapters.chat`; it drops the pin,
  TOTP, inbound adapter, listener install and `_first_dm`.
- **FR-011**: `commands/decision.owner_outcome` drops the DM-only two-way refusal; `where`
  stays as the confirmation a caller already holds.
- **FR-012**: `sessions.ROLES` drops `remote`; `sessions.record` and `touch` drop `thread`.
- **FR-013**: `interview` moves `phone` to `interview.RETIRED`; `profiles` drops
  `control_plane.owner` from PRIVATE and the `shepherd.autostart` DENIED rule.
- **FR-014**: `init --upgrade` stops and removes an installed listener unit (`--dry-run`
  prints it); the retired keys are listed for `workspace.RETIRED` (#799).
- **FR-015**: `charters/_common.md` drops "or escalating through a control plane"; agents are
  rebuilt with `bin/wuwei agents build`.
- **FR-016**: `docs/site/remote.md` is deleted and every docs page, README and the mkdocs nav
  stop naming the listener, the inbox, the control plane, the inbound adapter, `remote ack`,
  TOTP and DM phone answers.
- **FR-017**: Design spec section 15's heading is marked "(retired by #789, owner,
  2026-10-10)" and the other passages that name the listener or the control plane are marked
  the same way; the constitution's long-running-process constraint names the watch only.

### Key Entities

- None added. Removed: the inbox line, the listen cursor, the sent-ids file, the `remote`
  session role, the `decision.replied` evidence.

## Success Criteria *(mandatory)*

- **SC-001**: The acceptance grep (US5) is empty apart from the named mail vocabulary word.
- **SC-002**: Every touched test file passes; no kept behaviour lost its test (the wake and
  SessionStart cases move to `tests/test_watch.py`).
- **SC-003**: The diff removes far more lines than it adds; no new module.

## Assumptions

- **Headless shepherd goes here.** `shepherd.pending` and `shepherd.headless` have one caller,
  the listener tick (`shepherd.autostart`), and their only tests live in
  `tests/test_listen.py`. They are listener machinery and go with it, with
  `shepherd.autostart` and the runtime `headless` function, whose only callers were the
  listener's remote turns and this seat. The CLI-only overnight shepherd (#511,
  `shepherd.loop`, `wuwei shepherd schedule`) is a different unit and stays for part 23.
- **Seat-role refusals stay.** The `WUWEI_SEAT_ROLE == 'shepherd'` checks in `merge.py`,
  `outward.py` and `guards/pr.py` stop a seat from merging or sending (b); they stay until the
  guard rewrite (parts 17 and 23).
- **Remote guards go with their surface.** The pinned sender, TOTP step, confirm window and
  memory floor in `remote.py` guarded the inbound command channel. With the channel gone
  there is nothing to guard; their mutation probes go with them.
- **`where` stays** in `owner_outcome` and `undo`: tests use it as the confirmation seam and
  part 14 deletes decide. Only the DM-only branch and the docstrings change.
- **Owner Slack user id.** `setup slack` derived `outbound.owner.slack.user` from the pinned
  sender. With no inbound read, the owner sets it with `bin/wuwei config set`; `setup slack`
  prints that command when the key is empty.
- **Leftover event kinds.** `classify` gives an unlisted kind its default non-page tier. A
  `listen: clock` or `remote.*` line written earlier on the upgrade day is therefore counted
  as a warning for that day only. After part 4 (#801) warnings are not shown on any surface,
  so no legacy tuple is added.
- **Retired keys.** The base has no `workspace.RETIRED` (#799 is not merged). The keys go
  under "RETIRED at rebase" in plan.md for the lead to add.
- **Docs.** The pass plan says edit docs only where a test forces it; the issue acceptance
  says no docs page refers to these units. The acceptance governs: sentence-level deletions,
  no rewrite (part 24 rewrites the site).
- **Design spec.** The constitution lets only the owner amend the design spec. #789 and the
  issue acceptance are the owner's instruction; each edit is marked
  "(retired by #789, owner, 2026-10-10)".
- **Parallel parts.** Parts 4 (#801, nudges) and 5 (#808, cockpit) edit `status.py`,
  `nudges.py`, `doctor.py` and the board; part 3 (#800) deletes the owner-action table in
  `protect_state.py`, `commands/__init__` WRITES and `__main__` GROUPS; part 1 (#798) deletes
  prose-pinning tests in `tests/test_docs.py`. Edits to code a merged part already removed are
  skipped at rebase.
