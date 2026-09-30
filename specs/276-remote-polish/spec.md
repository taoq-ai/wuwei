# Feature Specification: phone answers as one status segment, an ack for a refused-sender page, and the section 3 quote

**Feature Branch**: `276-remote-polish`
**Created**: 2026-10-01
**Status**: Ready for implementation
**Input**: Issue #276, fix(remote). References: `docs/site/remote.md` sections 3 and 7; #273
(remote visibility); the status line rule in #210 (single pass over the day events, hook
latency budget); owner actions #222 (the owner-action table) and #227 (host
confirmation). Design sections 5.9 (status line), 9.1 (threat model), 10.6 (latency
budget), 15.4 (remote operation). Evidence: the second remote dry run on main 80f3573
(2026-10-01, verdict yes, new findings 1 to 3).

## Root cause (read on main, 80f3573; reproduced read-only in the dry-run workspace)

- **Finding 1, the status line grows one sentence per phone answer.** `status.snapshot`
  collects every `decision.answered` reason (`cli/wuwei/commands/status.py:169`) and
  `status.line` appends each as its own part (`status.py:241`,
  `parts.extend(data['answered'])`). Each reason is about 75 characters. The DM `status`
  reply reuses `status.line` (`cli/wuwei/remote.py:265-268`). Reproduced in the dry-run
  workspace with four answered decisions: `status --line` is 392 characters,
  `WUWEI no plan yet | pages 2 | nudges 4 | watch off | sessions 3 | D-1 answered from the phone: option A, confirm with decision outcome D-1 A | ... | meeting unmeasured`.
  `nudges` (via `status.attention`) and SessionStart
  (`cli/wuwei/guards/lifecycle.py:65`, the `decision.answered` context lines) carry the
  same reasons and are the right place for the detail.
- **Finding 2, a refused-sender page with the right pin cannot be cleared.**
  `remote.handle` records `remote.refused {id, pin}` (`remote.py:226-230`);
  `signal.classify` pages it (`cli/wuwei/signal.py:57`). `status.scan` drops it only
  when the recorded pin differs from the current `control_plane.owner`
  (`status.py:73-77`) and keys every other refusal by its line number (`status.py:107`),
  so no event can remove it. No command records an owner acknowledgement. remote.md
  section 3 (lines 128-133) says a refusal while the pin is right "stays paged until the
  day ends". Reproduced at dry-run step 6g: editing the pin to another team and back
  moves `pages` 2, 0, 2.
- **Finding 3, section 3 quotes a truncated line.** `config check` prints
  `control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)`
  (`cli/wuwei/commands/config.py:68-70`; dry-run `steps.log` line 41). remote.md section 3
  (line 103) quotes only `control_plane.owner: missing`, and
  `tests/test_docs.py::test_remote_runbook_matches_the_code` (line 298) checks only that
  prefix, so the two can drift.

## User Scenarios & Testing

### User Story 1 - Phone answers take one status segment (Priority: P1)

The owner with several decisions answered from the DM sees a short status line in Claude
Code and in the DM `status` reply; the per-decision confirm commands stay in `nudges` and
at session start.

**Independent Test**: `python -m pytest -q tests/test_signal_status.py -k phone_answer`.

**Acceptance Scenarios**:

1. (Issue acceptance 1) Given four decisions routed to the owner and answered from the
   DM, when `status --line` runs, then it contains the part `phone answers 4`, contains
   no `answered from the phone` text, and is under 160 characters; `wuwei nudges` lists
   four `decision.answered` rows, each with the reason
   `D-n answered from the phone: option X, confirm with decision outcome D-n X`.
2. Given one answered decision, then the part is `phone answers 1`.
3. Given no answered decision, or every answered decision with an owner outcome, then
   the line has no `phone answers` part.
4. Given the DM `status` command, then the reply is the same line without the `WUWEI `
   prefix (unchanged mechanism), so it carries `phone answers N` too.
5. SessionStart context still carries one `D-n answered from the phone: ...` line per
   answered decision (unchanged).

### User Story 2 - The owner acknowledges a refused-sender page on the host (Priority: P1)

A refusal from the owner's user id with a wrong team (while the pin is right) pages. The
owner looks at it and clears it from a host terminal, without editing the pin and back.

**Independent Test**: `python -m pytest -q tests/test_remote.py -k ack`.

**Acceptance Scenarios**:

1. (Issue acceptance 2, first part) Given a `remote.refused` page today, when the owner
   runs `wuwei remote ack` on a host terminal and types the digest shown, then a
   `remote.acknowledged {ids: [<refused ids>]}` event is recorded, the command exits 0,
   and the page is gone from `wuwei nudges` and the `pages` count.
2. (Issue acceptance 2, second part) Given the same page and no terminal (`/dev/tty`
   cannot be opened), then `wuwei remote ack` exits 2, prints
   `wuwei remote: this is an owner action: run it in a host terminal` on stderr, records
   nothing, and the page stays.
3. Given the owner types something other than the digest, then it exits 1 with
   `remote ack: owner confirmation declined`, records nothing, and the page stays.
4. Given a refusal recorded after the acknowledgement, then that new refusal pages (an
   acknowledgement covers only the ids it lists).
5. Given no unacknowledged `remote.refused` event today, then `wuwei remote ack` prints
   `remote ack: no refused sender message today`, asks nothing, records nothing, and
   exits 0.
6. Given an agent tool call running `bin/wuwei remote ack` (or `python3 -P -m wuwei remote
   ack`) inside a workspace, then the PreToolUse guard refuses it as an owner action
   (exit 1 with the owner-action reason); outside a workspace it is allowed (0).
   Ordinary work such as `git remote -v` or `bin/wuwei steward ack <id>` is not refused.
7. Given `wuwei event remote.acknowledged`, then it is refused naming its producer
   `wuwei remote ack`.

### User Story 3 - Section 3 quotes the line as printed (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_docs.py tests/test_env_credentials.py -k "remote_runbook or pin"`.

**Acceptance Scenarios**:

1. (Issue acceptance 3) Given the docs test, then the `control_plane.owner` missing line
   that `config check` prints (one shared constant) appears verbatim in remote.md
   section 3.
2. Given `config check` with an inbound adapter and an empty pin, then the printed line is
   exactly that constant.

### Edge Cases

- Day rollover: `remote ack` reads today's events only (`remote._today`), like every
  remote record; yesterday's pages are already gone.
- A `remote.refused` event without an `id` keeps its line-number key and cannot be
  acknowledged; it clears at the day's end as before.
- A refusal already cleared by a pin edit (#273) is still listed by `remote ack` until
  acknowledged; acknowledging it changes nothing visible.
- `status --json` keeps `answered` as the list of reasons (unchanged contract); only the
  line changes.

## Requirements

### Functional Requirements

- **FR-001**: `status.line` MUST show answered decisions as one part `phone answers N`
  (N = `len(data['answered'])`), placed where the reasons were, and nothing when N is 0.
  `status.snapshot`, `status.scan`, `nudges` and SessionStart are unchanged by this FR.
- **FR-002**: A new owner action `wuwei remote ack` MUST list today's `remote.refused` ids
  not yet in any `remote.acknowledged` event, ask for host confirmation through
  `integrity._host_confirm` with a 12-character digest of those ids, and on confirmation
  append `remote.acknowledged {ids}`. Exit 0 on success or nothing to acknowledge, 1 when
  declined, 2 without a terminal or on any read error.
- **FR-003**: `status.scan` MUST key `remote.refused` rows by the event id (falling back
  to the line number) and drop the rows whose ids a later `remote.acknowledged` event
  lists, in the same single pass over the events (#210).
- **FR-004**: `remote.acknowledged` MUST be silent (`signal.SILENT`) and reserved
  (`EVENT_PRODUCERS`, producer `owner host wuwei remote ack`).
- **FR-005**: `('remote', 'ack')` MUST be in the owner-action table
  (`guards/protect_state._OWNER_ACTIONS`) so agent tools are refused it inside a
  workspace.
- **FR-006**: The printed `control_plane.owner` missing line MUST come from one constant
  that the docs test checks against remote.md section 3.
- **FR-007**: Docs: remote.md section 3 quotes the full missing line and says how
  `bin/wuwei remote ack` clears a refused page; section 7 says `status --line` shows
  `phone answers N` while `nudges` and session start show each answer with its confirm
  command. `configuration.md` (listener section closing paragraph), `reference.md` (host
  terminal actions table) and `concepts.md` (owner command list) name the new behaviour.

### Key Entities

- `remote.acknowledged {ids}`: the owner acknowledged these refused messages on the host.
- `remote.refused {id, pin}`: unchanged.

## Success Criteria

- **SC-001**: The dry-run state (four answered decisions) gives a status line under 160
  characters.
- **SC-002**: The three issue acceptance scenarios each have a test named
  `test_issue_acceptance_*`.
- **SC-003**: `status --line` stays one pass over `events.jsonl` (#210).
- **SC-004**: The full suite passes.

## Assumptions

- **The acknowledgement lists ids.** The event records exactly the refused ids the owner
  confirmed, so a refusal arriving during or after the confirmation keeps paging and no
  re-check after the prompt is needed.
- **The confirmation types a digest**, the host-terminal rule of `decision outcome`,
  `state recover` and `drafts approve`: a 12-character sha256 prefix of the
  newline-joined ids, as `state recover` uses. The prompt lists the ids (Slack
  channel/ts pairs, already stored in the events).
- **Nothing to acknowledge is exit 0**, not a finding: the command is idempotent and asks
  nothing when there is nothing to clear.
- **`status --json` keeps the `answered` list.** The issue scopes the change to the status
  line and the DM reply; the JSON is not length-limited and a consumer may use the
  reasons.
- **The part text is `phone answers N`**, verbatim from the issue, placed after the
  sessions part where the reasons were.
- **The acknowledgement is only as strong as the cooperative model**: a seat running as
  the owner could append to `events.jsonl` directly (design 9.1); the event is reserved
  against `wuwei event` and the command is refused to agent tools, the same level as
  `decision.escalated` (#273). Accepted.
- **No `wuwei remote` command group exists on main**; the new
  `cli/wuwei/commands/remote.py` holds only `ack`. `remote` and `ack` join the
  owner-action relevance words, so a command naming the CLI, `remote` and `ack` together
  is now parsed; the ordinary-work table tests guard against false refusals.
