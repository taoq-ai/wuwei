# Feature Specification: decisions and health are visible on both ends

**Feature Branch**: `273-remote-visibility`
**Created**: 2026-10-01
**Status**: Ready for implementation
**Input**: Issue #273, fix(remote). Design sections 3.4, 5.4, 15.4, 15.9; builds on #57
(control plane), #65 (command vocabulary), #66 (remote guards), #260 (session registry),
#49/#50 (listener, Slack inbound), #55 (remote runbook). Depends on #272 (same chain).
Evidence: the operator dry run of `docs/site/remote.md` against a simulated Slack
(2026-09-30, main d555d10), findings F3, F4, F5, F6, F8 and F9.

## Root cause (read on main, 58f4889; reproduced read-only in the dry-run workspace)

- **F3, host decisions never reach the DM.** The only call to `control_plane.escalate` in
  `cli/` is inside a remote turn: `remote._turn` (`cli/wuwei/remote.py:340-344`) escalates
  only the ids that turn added (`new`, `remote.py:329`). `decision route`
  (`cli/wuwei/commands/decision.py:41`), `pr act` (`cli/wuwei/pr_actions.py:389`) and
  `remote.deny` all write the ledger through `decision.route_owner`
  (`cli/wuwei/decision.py:183-191`), and nothing reads the ledger to send. The listener
  tick (`cli/wuwei/listen.py:32-70`) handles inbox lines and never escalates. Dry run step
  7b: `decision route D-1` answered `owner`, the next `listen --once` sent nothing.
- **F4, phone answers are invisible on the host and can be stored twice.** `remote.handle`
  (`remote.py:232-242`) appends `decision.replied` for every parsed answer with no check
  for an earlier one. The dry-run events hold `decision.replied {D-1, A}` and then
  `{D-1, B}` one second apart (step 7d: "option A on D-1", then "drop it"). On the host,
  `status.scan` (`cli/wuwei/commands/status.py:122-129`) renders every unanswered route as
  `D-n pending owner decision`; `decision.replied` is in `signal.SILENT`
  (`cli/wuwei/signal.py:14`) and is read by nothing on the host. `nudges` in the dry-run
  workspace still says `D-1 pending owner decision`.
- **F9, a `remote.refused` page never clears.** `remote.handle` (`remote.py:216-218`)
  appends `remote.refused {id}`; `signal.classify` pages it (`signal.py:57`) and
  `status.scan` keys each one by line number (`status.py:99-105`), so nothing removes it.
  remote.md section 3 says "Editing the pin on the host is the re-confirmation", but the
  event does not record which pin it was checked against, so an edit changes nothing.
  Reproduced: `status --line` shows `pages 2` after the pin was fixed.
- **F8, stopped sessions count as live.** `remote.stop` (`remote.py:360-362`) sets
  `stopped` on the registry row; `sessions.rows` (`cli/wuwei/sessions.py:57-70`) drops the
  field and `status.snapshot` (`status.py:149-151`) counts every non-stale row.
  Reproduced: `sessions` lists 7 rows with no `stopped` field, 4 of them stopped, and
  `status --line` shows `sessions 7`.
- **F6, the status line has no listener.** `status.scan` collects `watch: clock` lines
  only (`status.py:48-49`) and computes watch health only (`status.py:106-115`); listener
  health is computed only in `lifecycle.session_start`
  (`cli/wuwei/guards/lifecycle.py:53-56`). Reproduced at a time when the latest
  `listen: clock` was 306 s old (dead at `listen.dead_seconds = 300`): `status --line` is
  `WUWEI no plan yet | pages 2 | nudges 4 | watch off | sessions 7 | meeting unmeasured`.
- **F5, `config check` is silent on the pin and the TOTP secret.**
  `commands/config.py:run` (`cli/wuwei/commands/config.py:19-65`) checks adapter
  credentials, `owner.name`, host protections and seat tokens only. Reproduced: no line
  mentions `control_plane.owner` or `WUWEI_TOTP_SECRET`. The pin format lives only in
  `remote.sender` (`remote.py:101`).

## User Scenarios & Testing

### User Story 1 - Every owner decision reaches the DM once (Priority: P1)

A decision routed to the owner on the host (`decision route`, `pr act`, a refused tool)
arrives in the owner DM the same way a decision from a remote `plan` turn does.

**Independent Test**: `python -m pytest -q tests/test_remote.py tests/test_listen.py -k escalat`.

**Acceptance Scenarios**:

1. (Issue acceptance 1, first part) Given a decision routed to the owner on the host and
   the listener running with the responder on and `SLACK_OWNER_DM_CHANNEL` set, when the
   next tick runs, then the owner DM receives the decision rendered by
   `control_plane.escalate` (summary and options, or ids only under
   `control_plane.content = "none"`) followed by the reply help line, and a
   `decision.escalated {id}` event is recorded.
2. Given the same decision still pending, when later ticks run, then it is not sent again.
3. Given a `plan` turn that raises a decision, then the decision is sent before the
   `Session ... turn ended` line as today, and the next tick does not send it again.
4. Given an escalation the outward lint refuses, then the DM receives
   `D-n is waiting in the workspace.` as today and the decision counts as sent.
5. Given a send that fails (exit 2), then no `decision.escalated` is recorded, the tick
   exits 2 with the reason printed, and the next tick retries.
6. Given `responder.enabled = false` or no `SLACK_OWNER_DM_CHANNEL`, then the tick sends
   nothing and records nothing.

### User Story 2 - A phone answer is visible on the host and never stored twice (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_remote.py tests/test_signal_status.py tests/test_listen.py -k "answer or replied"`.

**Acceptance Scenarios**:

1. (Issue acceptance 1, second part) Given `option A on D-1` from the DM for a pending
   decision, then `decision.replied {D-1, A}` is recorded and `wuwei nudges` lists
   `{tier: nudge, source: decision.answered, lane: Decisions, reason: "D-1 answered from
   the phone: option A, confirm with decision outcome D-1 A"}` in place of the
   `decision.pending` row.
2. Given the same state, then `status --line` carries the part
   `D-1 answered from the phone: option A, confirm with decision outcome D-1 A` and
   SessionStart's context contains the same line.
3. (Issue acceptance 1, third part) Given a recorded DM answer A for D-1, when a
   different answer arrives (`option B on D-1`, or `drop it` resolving to B), then no
   second `decision.replied` is recorded, no session is resumed, the handler returns 1 and
   the DM answers `Not recorded: D-1 already has option A from this DM. Record the outcome
   on the host to change it.`
4. Given a recorded answer A for D-1, when `option A on D-1` arrives again, then nothing
   is recorded or resumed and the DM repeats `Recorded D-1 option A. Confirm it on the
   host.` (exit 0).
5. Given `decision outcome D-1 <option>` on the host, then the answered row disappears
   like the pending row does today.

### User Story 3 - A refused-sender page clears when the pin is re-confirmed (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_remote.py tests/test_signal_status.py -k refused`.

**Acceptance Scenarios**:

1. Given a refused message, then `remote.refused` records `{id, pin}`, where `pin` is the
   `control_plane.owner` value the sender was checked against, and it pages as today.
2. Given `control_plane.owner` edited on the host to a different value, then that page no
   longer appears in `nudges` or the `pages` count.
3. Given the pin unchanged, then the page stays (until the day ends, as every page does).
4. Given a `remote.refused` event without a `pin` (written before this change), then it
   keeps paging.

### User Story 4 - Stopped sessions are not live (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_sessions.py tests/test_remote.py -k stop`.

**Acceptance Scenarios**:

1. Given a stopped remote session, then `wuwei sessions` lists it with a `stopped` field
   holding the stop timestamp; rows never stopped carry no `stopped` field.
2. (Issue acceptance 2) Given `stop all`, then `status --line` and `status --json` count
   only sessions that are neither stale nor stopped.

### User Story 5 - The status line carries the listener (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_listen.py -k status`.

**Acceptance Scenarios**:

1. (Issue acceptance 3) Given today's latest `listen: clock` older than
   `listen.dead_seconds`, or an installed listener unit with no clock line today, then
   `status --line` shows `listen dead` and `wuwei nudges` lists a page with source
   `listen: health` and the health reason.
2. Given unreadable listener health, then a `listen: health` nudge and `listen
   unmeasured`.
3. Given a fresh clock line, then no `listen` part and no row (alive, like the watch).
4. Given no clock line today and no unit, then `listen off` when `adapters.inbound` is not
   `none`, and no part at all when it is `none`; never a row.
5. `status --json` carries `listen` as `alive`, `off`, `dead`, `unmeasured`, or `none`
   (not configured and off).

### User Story 6 - `config check` reports the pin and the TOTP secret (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_env_credentials.py -k "control_plane or totp"`.

**Acceptance Scenarios**:

1. (Issue acceptance 4) Given `adapters.inbound` not `none` and an empty
   `control_plane.owner`, then `config check` prints a `Control plane:` section with
   `control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)`
   and exits 1.
2. Given a pin that does not match `<team>/<user>` (the same pattern `remote.sender`
   uses), then `control_plane.owner: invalid (expected <team id>/<user id>)`, exit 1.
3. Given a valid pin, then `control_plane.owner: set`; the value is never printed.
4. Given `WUWEI_TOTP_SECRET` set or unset, then `WUWEI_TOTP_SECRET: set` or
   `WUWEI_TOTP_SECRET: missing (confirm replies are the only second factor)`; neither is a
   finding, and the value is never printed.
5. Given `adapters.inbound = "none"`, then no `Control plane:` section and no change to
   the exit code.

### Edge Cases

- Day rollover: escalation dedup, first-answer lookup and refused pages read today's
  events only, like every other remote record (`remote._today`). A decision routed
  yesterday is not in today's ledger, so nothing is re-sent.
- Two `decision.replied` events for one id written before this change: the first one is
  the answer shown on the host and quoted in a refusal.
- `poll_replies` (`control_plane.py:104-129`) has no production caller; the listener is the
  only DM path, so the first-answer rule lives in `remote.handle`.
- The answered line is informational: it never changes the SessionStart exit code, and
  the outcome still needs `decision outcome` in a host terminal.

## Requirements

### Functional Requirements

- **FR-001**: One function in `remote.py` MUST send every owner-pending decision
  (`control_plane.pending`) that has no `decision.escalated` event today, through
  `control_plane.escalate` with the lint fallback line, recording `decision.escalated
  {id}` after each successful send. `remote._turn` and `listen.tick` MUST both use it.
- **FR-002**: `listen.tick` MUST call it after handling inbox lines when
  `responder.enabled` is true and `SLACK_OWNER_DM_CHANNEL` is set; an error there is
  printed as `listen escalate unmeasured: <reason>` and makes the tick exit 2.
- **FR-003**: `decision.escalated` MUST be silent (`signal.SILENT`) and reserved
  (`EVENT_PRODUCERS`, producer `wuwei listen`).
- **FR-004**: `remote.handle` MUST NOT append a second `decision.replied` for an id that
  has one today; a different option is refused with the first option quoted (exit 1), the
  same option repeats the `Recorded` line (exit 0); neither resumes a session.
- **FR-005**: `status.scan` MUST render an unanswered owner route that has a
  `decision.replied` today as source `decision.answered` with the reason
  `D-n answered from the phone: option X, confirm with decision outcome D-n X`, from the
  first reply, in the same single pass over the events.
- **FR-006**: `status.snapshot` MUST carry those reasons as `answered`; `status.line` MUST
  append each as a part; `lifecycle.session_start` MUST add each as a context line.
- **FR-007**: `remote.refused` MUST record the pin; `status.scan` MUST drop a refused event
  whose recorded pin differs from the current `control_plane.owner`.
- **FR-008**: `sessions.rows` MUST carry `stopped` when the registry row has it;
  `status.snapshot` MUST count rows that are neither stale nor stopped.
- **FR-009**: `status.scan` MUST compute listener health with the watch rule
  (`watch.health(root, clocks, name='listen')`, the unit check, dead page, unmeasured
  nudge) from the same single pass; `status.line` MUST show the listener as specified in
  User Story 5.
- **FR-010**: `config check` MUST report the pin and the TOTP secret as in User Story 6,
  with the pin pattern shared with `remote.sender`.
- **FR-011**: `docs/site/remote.md` sections 3, 4, 5, 6, 7 and 8 and
  `docs/site/configuration.md` MUST describe the new behaviour; section 7 MUST cover host
  decisions instead of excluding them, and section 3 MUST say that editing the pin clears
  the page.

### Key Entities

- `decision.escalated {id}`: evidence that the listener sent decision `id` to the owner DM
  today.
- `remote.refused {id, pin}`: a refused message and the pin it was checked against.
- `decision.replied {id, option}`: unchanged; now written at most once per id per day.

## Success Criteria

- **SC-001**: The dry-run sequence 7a to 7d (route D-1 on the host, `listen --once`,
  `option A on D-1`, `drop it`) sends D-1 to the DM, records one `decision.replied`, and
  refuses the second answer.
- **SC-002**: The four issue acceptance scenarios each have a test named
  `test_issue_acceptance_*`.
- **SC-003**: `status --line` stays one pass over `events.jsonl` (the #210 rule).
- **SC-004**: The full suite passes.

## Assumptions

- **Refused page clears on a pin edit, not by a new command.** The issue offers editing
  `control_plane.owner` or a `wuwei remote reconfirm` owner action. Editing the pin is what
  remote.md section 3 already calls the re-confirmation and needs no new command, owner
  terminal gate or reserved state; the refusal records the pin and the page clears when
  the current pin differs. A refusal while the pin is right (an impostor) stays paged for
  the rest of the day. `wuwei remote reconfirm` is deferred until that proves noisy.
- **No `control_plane.second_factor` key exists on main** (`workspace.SCHEMA` has only
  `content` and `owner`). The issue's "missing is a finding when second_factor is totp"
  has no key to test, and adding one would change the listener's factor rules beyond this
  issue. `config check` reports `WUWEI_TOTP_SECRET` set or missing as information, never
  a finding.
- **The Control plane section appears only when `adapters.inbound` is not `none`.** A
  workspace without a listener has no use for a pin; an empty pin there is not a finding.
- **`listen off` is hidden when `adapters.inbound = "none"`.** The issue writes
  `listen off | dead | ok`; the watch rule shows nothing when alive, so "ok" is read as
  "no part", exactly like the watch. Showing `listen off` to every workspace without a
  listener would add noise to every status line.
- **A dead listener also pages**, because the watch rule the issue asks to reuse pages a
  dead watch (#210 FR-007). SessionStart already exits 1 for it.
- **Escalation happens at the next listener tick** (at most `listen.poll_seconds` after
  the route), not inside `decision route` or `pr act`: the listener is the only process
  that sends to the DM, and one spot covers every producer of the ledger. The morning
  gate reaches the DM only through decisions it routes this way; its question widgets are
  the Remote Control path.
- **Escalation needs no pin.** The DM channel is the owner's own; answers still need the
  pin through `remote.handle`.
- **The first DM answer wins**; the host outcome (`decision outcome D-n X`) is how the
  owner changes their mind, as the issue says.
- **The answered line in the `status` DM reply** follows from reusing `status.line`; it is
  addressed to the owner and passes the outward lint like the rest of the line.
