# Feature Specification: the owner answers in the session, never in a terminal

**Feature Branch**: `b3-decision-framework` (feature directory `specs/831-owner-answers-in-session/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #831, an owner-requested change inside batch 3 of the #789 deletion pass:
"feat(owner): the owner answers in the session, never in a terminal: every host prompt becomes
a recorded card answer".

## Context

Owner, 2026-10-11: WUWEI helps with autonomy and nothing runs in a terminal. Today some owner
steps still need one:

- `integrity._host_confirm` opens `/dev/tty` and reads a y/N answer. An agent's Bash has no
  terminal, so the step fails closed with "this is an owner action: run it in a host terminal".
  Seven call sites in code that stays use it: `plan set <item> spec=skipped` and
  `plan set <item> owner_merge=false` (both #800, one helper), `commands/config.offer`
  (`config set`, `config add-repo`, `config promote`), `integrity reconfirm`, `state recover`,
  `seat stop` under strict, `doctor --fix` and `telemetry send`.
- Dozens of refusal and help texts in code that stays tell the owner to run something "in a
  host terminal", most of them "the owner sets X with bin/wuwei config set in a host terminal".

The session already has the parts for an in-session answer. The planner asks an
AskUserQuestion card. The PostToolUse hook `guards/decision.record_gate` records the owner's
reply as a hashed topic (`sessions.card_topic`, #529). The decision, draft and config-from-card
commands read that topic back (`sessions.gate_topics`, `card_answered`, and the Send check in
`drafts approve` from #800). This part adds one card, the Owner step card, and one helper that
every remaining terminal caller uses instead of the terminal.

Parts 10 (#815) and 11 (#816) of this batch are built after this part. Parts 12 to 23 come in
later batches. Callers in code those parts delete are left to them and listed in plan.md.

## User Scenarios and Testing

### User Story 1: an owner step is a card in the session (Priority: P1)

The planner runs an owner step, for example `bin/wuwei plan set A spec=skipped --reason "docs
only"`. Without the owner's answer the command exits 1, changes nothing, and its reason names
the Owner step card: the exact command, the header `Owner step`, and the widget JSON to pass to
AskUserQuestion. The planner asks it. The owner answers `Yes`. The hook records the answer. The
planner runs the same command again and it proceeds.

**Independent Test**: in a workspace, `plan.set_spec('A', 'spec=skipped', 'x', root)` raises a
`StateError` whose text contains `Owner step: bin/wuwei plan set A spec=skipped --reason x` and
no "host terminal". After `record_gate` sees that question answered `Yes` in a main session,
the same call succeeds.

**Acceptance Scenarios**:

1. **Given** no recorded answer, **When** any converted owner step runs (plan set
   spec=skipped, plan set owner_merge=false, config set, config add-repo, config promote,
   integrity reconfirm, state recover, seat stop under strict, doctor --fix, telemetry send),
   **Then** it exits 1, writes nothing, sends nothing, and its reason names that step's card.
2. **Given** the owner answered `Yes` on that step's card today, **When** the step runs again,
   **Then** it proceeds exactly as a confirmed terminal prompt did.
3. **Given** the owner answered `No`, or answered the card of another step (another item, key,
   digest or snapshot), **When** the step runs, **Then** it refuses as in scenario 1.
4. **Given** today's `state.json` is unreadable, **When** the planner asks the
   `bin/wuwei state recover` card and the owner answers `Yes`, **Then** the hook records the
   answer without reading state, and `state recover` restores the snapshot.

### User Story 2: only the owner answers (Priority: P1)

An answer counts only when the hook recorded it from the owner's reply to AskUserQuestion in a
main session of the workspace.

**Independent Test**: a `record_gate` payload with `agent_id` (a seat's question) records
nothing; `wuwei event gate.asked '{...}'` is refused as a reserved kind; a Bash tool call
`bin/wuwei hook PostToolUse < payload.json` is refused by the state guard; a planner `Write` to
`events.jsonl` is refused as today.

**Acceptance Scenarios**:

1. **Given** a seat (subagent) asks an Owner step card, **When** the hook runs, **Then**
   nothing is recorded and the step still refuses.
2. **Given** the planner runs `bin/wuwei hook <event>` through the Bash tool, **When** the
   PreToolUse state guard runs, **Then** it refuses: hooks run from Claude Code, never from a
   tool call.
3. **Given** the planner tries to write the topic itself (`wuwei event gate.asked`, `state
   set`, a file write to `events.jsonl` or `state.json`), **Then** each is refused as today.

### User Story 3: no text sends the owner to a terminal (Priority: P1)

No string in the CLI tells the owner to run something in a host terminal, except text in code a
later #789 part deletes, which a list in the test names with its part.

**Independent Test**: `tests/test_reasons.py::test_no_text_sends_the_owner_to_a_terminal`
walks every string constant under `cli/wuwei` and fails on `host terminal`, `/dev/tty` or `on
the host` outside the LEFT list. Every LEFT row must still match, so the part that deletes the
code must delete its row.

**Acceptance Scenarios**:

1. **Given** the converted code, **When** the test runs, **Then** it passes with LEFT rows only
   for code parts 10 to 23 delete.
2. **Given** a later part deletes code a LEFT row names, **When** the test runs, **Then** the
   stale row fails it until the row goes.

## Edge Cases

- A command whose arguments hold a secret or a newline: the recorded topic is a hash of the
  question and the reply, so no command text reaches the event log; a changed argument is a new
  card.
- Day rollover between the answer and the rerun: answers are read from today's event log, so
  the step asks again after midnight.
- The same step run twice on one day: the answer still counts. Each converted step is
  idempotent or bound by its token to a digest of what it changes (config diff, snapshot,
  fingerprint, fix batch, telemetry body), so a rerun applies the same thing or nothing.
- Strict posture: the Owner step card counts under every posture. Strict used to mean "a card
  is not a confirmation, use the terminal"; with no terminal that leaves the owner no path. The
  legacy cards in code later parts delete (decision, drafts, calibrate) keep their strict rule
  until those parts delete them.
- `seat stop` outside strict keeps today's rule (the planner session may stop a seat); only its
  text loses "or a host terminal".

## Requirements

### Functional Requirements

- **FR-001**: `sessions.needs_owner(root, command, detail, token='')` returns None when today's
  event log holds a `gate.asked` event whose topics contain
  `card_topic('Owner step', question + '\nYes')`, where `question` is
  `'Owner step: ' + command`, plus ` (token)` when a token is given. Otherwise it returns one
  refusal line that names the card and carries the widget JSON (`question`,
  `header: Owner step`, options `Yes` described by `detail` and `No`, `multiSelect: false`,
  `record`: the command).
- **FR-002**: `guards/decision.record_gate` records every answered Owner step question from a
  main session (no `agent_id`) as a `gate.asked` event with the hashed topic, before and
  independent of any state read, so it works while `state.json` is unreadable.
  `check_question` lets an Owner step question through without a record citation.
- **FR-003**: Every remaining `_host_confirm` call site in code that stays calls `needs_owner`
  instead and refuses with its reason (exit 1) when it is not None: plan set spec=skipped and
  owner_merge=false, `config.offer` (config set, add-repo, promote, and setup's own offer),
  integrity reconfirm, state recover, seat stop under strict, doctor --fix, telemetry send.
- **FR-004**: `config set` drops its session and strict branches (the redirect to calibrate
  questions or a decision record, and "run it in a host terminal"); in or out of a session it
  goes through `offer` and its Owner step card. `--from-card D-n` stays until part 14.
- **FR-005**: The PreToolUse state guard refuses a Bash command that runs `wuwei hook`.
- **FR-006**: Every "host terminal", "/dev/tty" and "on the host" text in code that stays is
  rewritten to name the command (which asks its own card) or the card, never a terminal.
- **FR-007**: A test fails on any such text outside a LEFT list of (file, substring, part)
  rows, and on any LEFT row that no longer matches.
- **FR-008**: The planner charter says how to answer an Owner step refusal; design 9.1 records
  the rule; the generated agents are rebuilt.

### Key Entities

- **Owner step card**: one AskUserQuestion question, header `Owner step`, question
  `Owner step: <command>[ (<token>)]`, options `Yes` and `No`, `record` the command to rerun.
- **Owner answer**: a `gate.asked` event (a reserved kind only the PostToolUse hook writes)
  whose topics hold `card_topic('Owner step', question + '\n' + reply)`.

## Success Criteria

- **SC-001**: No converted step opens `/dev/tty`; each refuses without its answer and proceeds
  with it (one test per call site).
- **SC-002**: The terminal-text test passes with LEFT rows only for code later parts delete.
- **SC-003**: A seat's answer, a forged event and a Bash `wuwei hook` call never make a step
  proceed.
- **SC-004**: No test is loosened. Tests that pinned a terminal prompt for a converted step
  now pin the card; tests of left callers are unchanged.

## Assumptions

1. Owner answers are recorded from any main session of the workspace, not only today's planner
   session. A main session's AskUserQuestion is answered by the person at the keyboard, which
   is the owner; the existing gate and decision topics keep their planner-only rule. This is
   what lets `state recover` work while `state.json` (which names the planner) is unreadable.
2. The answer is read from `events.jsonl`, not from `state.json` session rows: the event log is
   append-only, `gate.asked` is a reserved kind only the hook writes, and the file is protected
   from tool writes.
3. The hook reads the answer only from `tool_response.answers`, never from `tool_input`.
   Claude Code fills `tool_response` from the owner's reply.
4. The boundary is the same as the terminal prompt it replaces (design 9.1): friction against
   the planner and seats, not proof against a process running as the owner's user. A seat that
   pipes a forged payload into the hook through an opaque interpreter is outside it.
5. No answer is consumed (see Edge Cases).
6. `integrity._host_confirm` and `HOST_TERMINAL` stay, with their tests, while a left caller
   uses them; the part that deletes the last left caller (part 18, the MCP registry gate)
   deletes them.
7. The merge owner path is left to part 11 (#816), which rewrites `merge.check` and adds the
   owner block. Its plan currently routes owner merges and deploys to a host terminal; that
   part must use `needs_owner` instead (plan.md, Handoff).
8. No config key is retired.
9. The design spec and charter edits are part of the owner-requested change and follow the
   #789 pass's rule for amendments.
