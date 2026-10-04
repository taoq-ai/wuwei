# Feature Specification: A hand-back without last_assistant_message is read from the transcript and never leaves a seat running, traces redact only secrets, and a failed span records a gap event

**Feature Branch**: `473-handback-traces`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #473, "fix(seats): a hand-back without last_assistant_message is read
from the transcript and never leaves a seat running, traces redact only secrets, and a failed
span records a gap event", with the owner's addition of 2026-10-04 (every background seat
hands back this way; a recovery command for a stuck seat). Builds on #166 (SubagentStop lint
scoped to the seat's own verdict), #287 (heartbeat), #352 (traces for seats only), #362
(reason shape), #346 (hook import and latency budget). Owner's first real items on v0.15.0.

## Evidence (read-only, on `main` at 963a839)

**1. The background hand-back.** Seats launched in the background finish through the
harness's structured hand-back. Recorded subagent transcripts on the owner's machine (128 of
them end this way) show the shape: the last assistant entry is

```json
{"type": "assistant", "message": {"role": "assistant", "content": [
  {"type": "tool_use", "id": "toolu_...", "name": "SubagentHandback",
   "input": {"message": "<the seat's report>"}}], "stop_reason": null}}
```

followed by one user entry carrying the `tool_result` (`{"success":true,"message":"Report
delivered to your caller."}`) with `"toolEndsTurn": true`. The entry has no text block, and
the SubagentStop payload carries no `last_assistant_message`. A foreground seat (the lead)
ends on an assistant entry with a text block and its payload carries the message.

Reproduced with the `seat` fixture of `tests/test_build_next.py` (launch a builder, append the
hand-back entry and its tool result to the agent transcript, call `agent_launch.stop` with no
`last_assistant_message`): the guard returns `(2, 'build result could not be recorded:
SubagentStop omitted builder result; ...')`, the seat and the build stay `running`, and no
event follows `seat launched`. Root cause:

- `cli/wuwei/commands/build.py` lines 283 to 285 (`stopped`): a missing
  `last_assistant_message` raises before anything is recorded.
- `cli/wuwei/commands/build.py` lines 286 to 295: the transcript walk joins only `text`
  blocks of the last assistant entry, so a hand-back reads as an empty message and would not
  match even if the payload carried the report.
- `cli/wuwei/guards/agent_launch.py` lines 255 to 263 (`stop`): the exception is turned into
  exit 2 and the seat is never released, so it stays `running` until the reservation timeout.
- The other SubagentStop readers of the message fail the same way for a background seat:
  `cli/wuwei/guards/verdict.py` line 116 (`check_retro`, `required_text`),
  `cli/wuwei/guards/decision.py` line 225 (`check_stop`), `cli/wuwei/guards/spec.py` line 89
  (`check_stop` reads an empty string, so the builder's spec artifacts are never named).

**2. Trace redaction.** `cli/wuwei/redact.py` lines 103 to 107 (`redact`) replace the whole
string with `[REDACTED]` when any `SECRET` or phone pattern matches anywhere in it, and two
patterns match ordinary commands: line 55 matches `--json <anything>` and `-d <anything>`
(`gh pr view 12 --json state,title,body`, `gh pr list --json number,title` and
`git branch -d old-branch` all become `[REDACTED]`), and line 54 matches any `--body`,
`--message` or `--text` flag, so `gh pr create --title x --body "..."` loses its tool and
subcommand. Lines 101 and 102 replace the whole `git commit -m` and `gh pr comment --body`
match, command words included, with the body marker.

**3. Silent span failures.** `cli/wuwei/guards/traces.py` lines 123 to 131 (`check`) record a
failed span as `hook.post_tool_use_error` with the reason only (no span kind, no session);
nothing counts it in `status --line` or `doctor`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A background seat's hand-back is its result (Priority: P1)

A builder or sentinel launched in the background ends with a SubagentHandback. The
SubagentStop hook reads the report from the agent transcript, records the seat's result
exactly as it does for a foreground seat whose payload carries the message, and the seat
stops. The planner never has to resume a seat to ask for its report as plain text.

**Why this priority**: every background seat hands back this way, so without it no
background seat ever stops and the day stalls at the first build.

**Independent Test**: run the scripted day of `tests/fakes/day.py` twice, once with the
plain-text ending and once with the recorded hand-back shape and no `last_assistant_message`;
the seat statuses, the build result text and the seat events match.

**Acceptance Scenarios**:

1. **Given** a SubagentStop payload without `last_assistant_message` and an agent transcript
   ending in a structured hand-back, **When** the hook runs, **Then** the report is read from
   the transcript, the seat stops, and the events match the plain-text case.
2. **Given** the same payload with `last_assistant_message` present, **When** the hook runs,
   **Then** behaviour is unchanged (the message is used; a message that differs from the
   transcript's last turn is still refused as today).
3. **Given** `last_assistant_message` set to an empty string and a transcript whose last
   assistant entry is text, **When** the hook runs, **Then** that text is used.

---

### User Story 2 - An unreadable transcript never leaves a seat running (Priority: P1)

When the message is missing and the transcript cannot be read (missing file, undecodable
last entry, no assistant entry), the hook stops the seat with status `unmeasured`, records a
`seat stopped` event naming the reason, and exits 2 with a reason that names the recovery
command.

**Why this priority**: a seat left `running` holds a CAP slot and blocks `build next`,
`dispatch next` and the gate until the reservation timeout.

**Independent Test**: the `seat` fixture with a transcript path that does not exist.

**Acceptance Scenarios**:

1. **Given** an unreadable transcript and no message, **When** the hook runs, **Then** the
   seat's status is `unmeasured` with the reason, one `seat stopped` event carries
   `status: unmeasured` and the reason, `wuwei next` no longer reports the seat as running,
   and `status --line` exits 0.

---

### User Story 3 - The owner recovers a stuck seat (Priority: P1)

A seat with no process and no stop (its transcript ends in a hand-back but no stop was
recorded), or a seat the hook stopped as `unmeasured`, is named by `wuwei next`, `doctor` and
the heartbeat with the command that recovers it:

- `wuwei seat stop <name> --verdict <file>` reads the report from the file, runs the verdict
  lint (sentinel roles), and records the stop and the result through the same SubagentStop
  guards the hook runs.
- `wuwei seat stop <name> --unmeasured "<reason>"` stops it as unmeasured so the day can move;
  a builder's running build parks with that reason.

Under `strict` both are owner actions in a host terminal (y/N at the terminal). Under
`observe` and `guarded` the planner session may run them.

**Why this priority**: the owner's report ends with "I'll look into the CLI for a way to
recover a stuck seat"; today there is none.

**Independent Test**: a running builder seat whose recorded transcript ends in a hand-back;
`wuwei next` names `wuwei seat stop <name> --verdict <file>`; running that command records
the build result and stops the seat.

**Acceptance Scenarios**:

1. **Given** a running seat whose transcript ends in a hand-back, **When** the heartbeat
   ticks, **Then** its `seats` probe fails naming the seat and the command, within that tick.
2. **Given** the same seat, **When** `wuwei next` runs, **Then** the row names
   `wuwei seat stop <name> --verdict <file>`; `doctor` lists the seat in a `stuck seats` row.
3. **Given** `wuwei seat stop <name> --verdict <file>` for a builder, **Then** the build
   records the file's text as its result, the seat is `stopped`, and the events match a hook
   stop.
4. **Given** `wuwei seat stop <name> --verdict <file>` for a sentinel and a file that fails
   the verdict lint, **Then** exit 1 with the lint finding and the seat stays as it was.
5. **Given** `wuwei seat stop <name> --unmeasured "<reason>"`, **Then** the seat is
   `unmeasured` with the reason and `by: owner`, a builder's build is `parked` with the
   reason, and the seat is no longer listed as stuck.
6. **Given** `strict` and no host terminal, **Then** exit 2 naming the host terminal and
   nothing changes; **given** `guarded` and a session that is not the planner, **Then**
   exit 1 and nothing changes.

---

### User Story 4 - Traces keep ordinary commands readable (Priority: P2)

The trace recorder redacts credential-shaped values only. Tool names, subcommands and paths
before the first credential stay; message bodies keep their command words and lose their
text.

**Why this priority**: the investigation of the stuck seat had to read the raw transcript
because the trace rows said `[REDACTED]`.

**Independent Test**: a corpus test over `wuwei.redact.redact`.

**Acceptance Scenarios**:

1. **Given** the redaction corpus, **When** each entry is redacted, **Then** twenty ordinary
   commands (gh, git, pytest, curl without tokens) pass through unchanged and none of the ten
   secret shapes survives.
2. **Given** `gh pr comment 12 --body "looks good"`, **Then** the output starts with
   `gh pr comment 12 --body ` followed by the body marker.

---

### User Story 5 - A span that cannot be written says so (Priority: P2)

A trace span that cannot be written (lock, disk, malformed payload) records one `traces.gap`
event with the reason, the span kind and the session. `status --line` shows `traces: N gaps`
and `doctor` shows a `traces` row. The recorder never raises into the hook.

**Why this priority**: a silent gap reads as a complete trace.

**Independent Test**: patch `state.append_jsonl` to raise and run the PostToolUse hook.

**Acceptance Scenarios**:

1. **Given** a trace write that raises, **When** the PostToolUse hook runs, **Then** one
   `traces.gap` event, exit 0, `status --line` contains `traces: 1 gaps`, and the doctor
   `traces` row warns with the count.

### Edge Cases

- The transcript's last line is torn (written while the seat still runs): the hook treats
  it as unreadable (User Story 2); the stuck check treats it as no evidence of an end.
- A seat hands back and then continues (the stop was blocked): its last assistant entry is
  no longer the hand-back, so it is not stuck.
- A stuck seat with no recorded transcript (it made no tool call): not detected; the
  existing reservation timeout still reports it.
- `wuwei seat stop` for a seat that is `stopped`, unknown, or `unmeasured` by the owner:
  exit 1 naming its status, nothing changes.
- A reason for `--unmeasured` that is empty or spans lines: exit 2, nothing changes.
- A non-WUWEI subagent (Explore) without a message: no transcript read, no import beyond
  today's.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SubagentStop hook MUST, for a WUWEI seat whose payload has no non-blank
  `last_assistant_message`, read the agent transcript's last assistant entry and use its text
  blocks joined by newlines, or a SubagentHandback's `input.message`, as the message for
  every SubagentStop guard.
- **FR-002**: One shared helper in `cli/wuwei/brief.py` MUST read the last assistant turn;
  `build.stopped` and the hook use it, and the builder completion binding (`[line index,
  sha256]`) is unchanged.
- **FR-003**: When neither the payload nor the transcript yields the message for a running
  seat, the seat MUST be stopped with status `unmeasured`, a `reason`, and a
  `seat stopped` event `{name, status: unmeasured, reason}`; the hook exits 2 with a reason
  that names `wuwei seat stop`.
- **FR-004**: The traces recorder MUST record a subagent seat's agent transcript path on the
  seat (`transcript`) when it binds the trace session.
- **FR-005**: `brief.stuck(data)` MUST list seats needing recovery: running seats whose
  recorded transcript's last assistant entry is a SubagentHandback, and seats `unmeasured`
  by the hook (not by the owner).
- **FR-006**: The heartbeat MUST have a `seats` probe that fails with the stuck seat names
  and the recovery command; `wuwei next` MUST return a `stuck` row naming
  `wuwei seat stop <name> --verdict <file>` before item rows; `doctor` MUST show a
  `stuck seats` row with the command.
- **FR-007**: `wuwei seat stop <name> --verdict <file> | --unmeasured "<reason>"` MUST exist
  as in User Story 3; `--verdict` runs the registered SubagentStop guards on a payload whose
  message is the file text; `--unmeasured` reuses the unmeasured stop and parks a running
  build.
- **FR-008**: Under `strict` the command MUST confirm y/N at the host terminal and exit 2
  without one; under `observe` and `guarded` it MUST run from a host terminal (no session)
  or today's planner session and exit 1 from any other session.
- **FR-009**: `wuwei.redact.redact` MUST, for the trace recorder (`prefix=True`), keep the text
  before the first credential match and replace the rest with `[REDACTED]` (other callers keep
  replacing the whole string); `--json` and `-d` count only with a quoted, brace or
  `@` value; body markers keep their command words and are not themselves matched.
- **FR-010**: A span write failure MUST append one `traces.gap` event `{reason, span,
  session}` in place of `hook.post_tool_use_error`; the hook's exit stays as today.
- **FR-011**: `status --line` MUST add `traces: N gaps` when today has N > 0 gap events;
  `doctor` MUST show a `traces` row (ok with none, warn with the count).
- **FR-012**: `traces.gap` MUST be reserved to `wuwei hook PostToolUse` in the event
  command's producers; `seat stopped` adds the owner command as a producer.
- **FR-013**: Every new reason string MUST name a next step (#362).

### Key Entities

- **Seat record** (day state `seats.<name>`): gains `status: unmeasured`, `reason`,
  `by: owner` (owner recovery only) and `transcript` (agent transcript path, set by traces).
- **`seat stopped` event**: payload gains `status` and `reason` on an unmeasured stop, and
  `by: owner` from the command.
- **`traces.gap` event**: `{reason, span, session}`; a nudge.

## Success Criteria *(mandatory)*

- **SC-001**: A background seat's stop records the same seat status, build result and seat
  events as a foreground stop, in a test over the recorded hand-back shape.
- **SC-002**: No SubagentStop leaves a WUWEI seat `running`.
- **SC-003**: Twenty ordinary commands survive redaction unchanged; ten secret shapes do not.
- **SC-004**: Every failed span write is one `traces.gap` event, counted in `status --line`
  and `doctor`.
- **SC-005**: The full suite passes, including the #346 import pins and the #362 reason test.

## Assumptions

- A1: The recorded frame names the report field `input.message` on a `SubagentHandback`
  tool use; the issue's "`result` text" means this frame. Only this shape and text blocks
  are read; other tool uses (StructuredOutput, which workflow agents use) are not seat
  endings.
- A2: The issue says `transcript_path`; the subagent's own transcript is
  `agent_transcript_path`, which `build.stopped` and `stopping_seat` already read.
  `transcript_path` is the parent session's.
- A3: "`seat.stopped` event" means the existing `seat stopped` kind with `status` and
  `reason` added, not a new kind.
- A4: "Runs the verdict lint on that" is the existing SubagentStop guards fed the read text
  (`check_retro`, `decision.check_stop`, `spec.check_stop`, the sentinel gate lint, the
  builder result); the hook fills the payload once so `guards/decision.py`, which #471
  changes in parallel, is not edited.
- A5: "No process" for a Claude seat is positive evidence that it ended: its recorded agent
  transcript's last assistant entry is the hand-back. A seat with no recorded transcript is
  not detected; the reservation timeout still covers it.
- A6: The hook does not park a builder it stops as unmeasured; the owner decides with
  `seat stop --verdict` (records the result, the build is still `running`) or
  `--unmeasured` (parks it).
- A7: `status --line` has no seat part today; "shows no running seat" is checked through
  day state and `wuwei next` (no `wait` row for the seat) with `status --line` exiting 0.
- A8: The owner-action table in `guards/protect_state.py` is not touched (#471 changes it in
  parallel, and its records floor would refuse the command in every posture, against the
  issue's observe and guarded rule). The command enforces its own posture rule; a seat
  shares the planner's session id, so under observe and guarded a seat could run it too
  (spec 9.1: a seat runs as the owner).
- A9: A span-write failure keeps today's exit (0 without security material, 2 with it,
  #135); "exit 0 as today" describes a workspace without `security.json`.
- A10: Redaction drops everything from the first credential match on (tool, subcommand and
  earlier paths kept), a deliberate simplification over per-value redaction; message bodies
  stay private (design 15.5).
- A11: `hook.post_tool_use_error` is renamed to `traces.gap`; nothing outside the traces
  guard and its tests reads the old kind.
- A12: A stop the hook refuses for another reason (an agent id that differs from the resumed
  builder, a build that changed under a resumed iteration, a message that differs from the
  transcript) leaves the seat as it was, as today: releasing it would let a replayed stop free
  a live seat. SC-002 covers the hand-back and the unreadable report.
