# Feature Specification: A card answer confirms the record command without the session id in the environment

**Feature Branch**: `599-decide-card`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #599: fix(records): a card answer is the confirmation for wuwei
decide and every record command even when the session id is not in the environment: the
planner's asked topics in state decide, the widget's record command carries the card hash,
and doctor says when SessionStart could not export the session id.

Standing rules (unchanged): a card answer is the confirmation (#357, #529); below strict a
guard is a warning or a card, never a new wall (#530); the next step is a command the CLI
returns (#551). A host terminal keeps its y/N; strict still refuses the session path; seats
never record (I8).

## Root cause

Reproduced on the branch base (`6627e24`, read-only, in a scratch copy of the tree with the
`tests/test_card_confirms.py` fixtures): the planner `planner-1` asked D-1 on a card and the
record gate stored `D-1` and `D-1=<sha256 of the answer>` in
`state.sessions.planner-1.gate_asked`. `wuwei decide D-1 "cap = 5"` with `WUWEI_SESSION_ID`
unset and a non-terminal stdin called `integrity._host_confirm` once and exited 1 with
`decision: owner confirmation declined; rerun bin/wuwei decide <id> <option> in a host
terminal and answer y`. The same call with `WUWEI_SESSION_ID=planner-1` recorded with no
prompt.

The path, with lines on the base:

- The hook lets the command through: `protect_state._gate_edits`
  (`cli/wuwei/guards/protect_state.py:192-198`) reads the session id from the hook payload,
  and `D-1` is in the planner's asked set (`:278`).
- The CLI does not: `decision.owner_confirm` (`cli/wuwei/decision.py:500-507`) asks
  `sessions.gate_topics(root, sessions.current())`. `sessions.current()`
  (`cli/wuwei/sessions.py:22-25`) reads only `WUWEI_SESSION_ID`, which `sessions.export`
  (`cli/wuwei/sessions.py:180-186`) appends to `CLAUDE_ENV_FILE` at SessionStart
  (`cli/wuwei/guards/lifecycle.py:61-63`). When the harness has no env file, or does not
  carry it into Bash, the variable is absent.
- `gate_topics` returns no topics for a missing session id before any state read
  (`cli/wuwei/sessions.py:31-32`), so `owner_confirm` falls to `integrity._host_confirm`
  (`cli/wuwei/integrity.py:323-341`), which prompts on the terminal and reads a decline.

`sessions.card_answered` (`cli/wuwei/sessions.py:48-50`) has the same dependency, so `config
set --from-card` and `calibrate --answer` miss the card the same way; `decision undo` and
`mcp decide` reach `owner_confirm` too. `drafts approve` does not: it reads the planner from
state (`cli/wuwei/drafts.py:315`). Nothing records whether SessionStart could export the id,
so the degradation is silent.

The environment variable was never a trust boundary: any same-uid process can set it to the
planner id it reads from `state.json`. The boundary is the hook, which reads the session id
from the payload and refuses record commands from seats and other sessions (spec 9.1, I8).

## User Scenarios and Testing

### User Story 1: The planner records a card answer without a prompt (Priority: P1)

The owner answers a decision card in the planner session; the planner runs the widget's
record command and the outcome is recorded, with no y/N and no host-terminal line.

**Independent Test**: `tests/test_card_confirms.py`, in process, `WUWEI_SESSION_ID` unset,
`sys.stdin` not a terminal, `integrity._host_confirm` failing when called.

**Acceptance Scenarios**:

1. **Given** a planner session that asked D-1 on a card and the owner's answer, **When**
   `wuwei decide D-1 "<label>"` runs without `WUWEI_SESSION_ID` and without a TTY on stdin,
   **Then** the record has `Decided-by: owner`, its Notes line says `in the planner
   session`, and nothing prompts.
2. **Given** the same day, **When** the widget's record command `wuwei decide D-1 "<label>"
   --card <hash>` runs (any stdin, with or without the variable), **Then** it records the
   same way without a prompt.
3. **Given** a decision card for a config value, **When** `wuwei config set --from-card D-n`
   or `wuwei calibrate --answer` runs without `WUWEI_SESSION_ID` and without a TTY, **Then**
   the answer writes its config key as it does with the variable set.
4. **Given** the pending MCP registry decision asked on a card, **When** `wuwei decide <id>
   proceed` or `wuwei mcp decide <id> proceed` runs without the variable and without a TTY,
   **Then** it records with no prompt.

### User Story 2: The host terminal, strict, seats and changed records keep their rules (Priority: P1)

**Independent Test**: `tests/test_card_confirms.py` and `tests/test_invariants.py`.

**Acceptance Scenarios**:

1. **Given** a host terminal (stdin a TTY, no `WUWEI_SESSION_ID`) and a decision not asked
   on a card, **When** `wuwei decide D-1 <option>` runs, **Then** the y/N prompt is asked.
   A TTY caller without `--card` keeps the prompt even for an asked decision.
2. **Given** strict, **When** the planner runs `bin/wuwei decide D-1 <option> --card
   <hash>`, **Then** the hook refuses it and prints the command for a host terminal (I8,
   unchanged); **and When** the CLI runs it anyway, **Then** nothing is recorded, nothing
   prompts, and it exits 1 naming `bin/wuwei decide D-1 <option>` in a host terminal.
3. **Given** a seat (a payload with `agent_id`, or a seat session with `WUWEI_SEAT_ROLE` set
   and its own session id), **When** it runs `bin/wuwei decide D-1 <option> --card <hash>`
   for an asked D-1, **Then** `protect_state` refuses it before the CLI runs.
4. **Given** D-1 asked on a card and its record edited afterwards (Question or Options
   changed), **When** the old record command `wuwei decide D-1 "<label>" --card <old hash>`
   runs, **Then** nothing is recorded, nothing prompts, and it exits 1 naming `bin/wuwei
   decision show D-1 --widget` to ask the card again.
5. **Given** `--card <hash>` for a decision the planner never asked, below strict, **Then**
   exit 1 naming `bin/wuwei decision show D-1 --widget`; no prompt.

### User Story 3: A missing session id is visible (Priority: P2)

**Independent Test**: `tests/test_sessions.py`, `tests/test_doctor.py`.

**Acceptance Scenarios**:

1. **Given** SessionStart without `CLAUDE_ENV_FILE`, **When** the hook records the session,
   **Then** its `session.seen` payload carries `env_file: false`; with the file it carries
   `env_file: true`; other hooks' rows carry no `env_file`.
2. **Given** today's last flagged SessionStart had no `CLAUDE_ENV_FILE`, **When** `wuwei
   doctor` runs, **Then** the Day section has one `session id` row with status warn saying
   SessionStart could not export the session id; with the file, or with no flagged event, it
   is ok.

### User Story 4: The planner reruns with --card, never a host-terminal line (Priority: P2)

**Independent Test**: `tests/test_card_confirms.py`, `tests/test_guide.py`,
`tests/test_charters.py`.

**Acceptance Scenarios**:

1. **Given** a decision record, **When** `wuwei decision show D-n --widget` prints it,
   **Then** its record command is `wuwei decide D-n "<label>" --card <hash>`, the hash being
   the card hash of that record.
2. **Given** the planner skill card bullet and `wuwei guide`, **When** read, **Then** each
   says: a decision record command that exits non-zero on the confirmation is run again as
   the `record` command `wuwei decision show D-n --widget` prints (`wuwei decide D-n
   "<label>" --card <hash>`), without asking the card again; below strict the planner never
   shows the owner a host-terminal command for a card the owner answered.

### Edge Cases

- No planner registered today: the state fallback finds none, so a TTY-less caller gets no
  topics and reaches `_host_confirm` as today; with `--card` it exits 1 with the card hint.
- A non-planner `WUWEI_SESSION_ID` is set: it is used as today (no fallback); a session that
  is not the planner gets no topics.
- A widget printed before this change has no `--card`: its record command still passes on
  the id in `gate_asked` (the state fallback covers the missing variable).
- `decision undo` keeps its own record command and identifier (`card_topic(id, 'Undo')`);
  the state fallback covers it without `--card`.
- `wuwei mcp decide` keeps its own widget record command; the state fallback covers it.
- A SessionStart event written before this change has no `env_file` key: doctor reads only
  events that carry it and is ok when none does.
- A `--card` value that is not a hash of the record (a typo, any other text): the same exit
  1 and hint as a changed record.

## Requirements

### Functional Requirements

- **FR-001**: `sessions.caller(root, card=False)` returns `current()` when set; otherwise,
  when stdin is not a TTY or `card` is true, today's `planner_session_id` from state; else
  None. `current()` is unchanged.
- **FR-002**: `sessions.card_answered` and `decision.owner_confirm` resolve the session with
  `caller` instead of `current()`. `gate_topics` is unchanged, so strict still yields no
  topics and the hook path is untouched.
- **FR-003**: `decision.card_hash(identifier, fields)`: the first 12 hex characters of the
  #529 `sessions.card_topic` hash of the record's `Question` and `Options` fields. It names
  the card the owner saw.
- **FR-004**: `decision.RECORD` is `wuwei decide {id} "<label>" --card {card}`;
  `record_widget` formats it with `card=card_hash(identifier, fields)`. Record templates
  without `{card}` (`mcp.RECORD`, `CONFIG_RECORD`) are unchanged.
- **FR-005**: `owner_confirm(root, identifier, digest, prompt, card=None, fields=None)`: with
  a `card` that is not `card_hash(identifier, fields)`, return `''`; then a matching asked
  topic returns `in the planner session`; with a `card` and no match return `''` without
  prompting; otherwise `_host_confirm` as today.
- **FR-006**: `wuwei decide` takes `--card <hash>`. `owner_outcome` and `mcp.decide` pass it
  with the record's fields to `owner_confirm`. With `--card` and no confirmation the exit is
  1 with one reason naming `bin/wuwei decision show D-n --widget` and, under strict, the
  host-terminal command.
- **FR-007**: `sessions.export` returns whether `CLAUDE_ENV_FILE` was set; SessionStart puts
  it on its `session.seen` payload as `env_file`. No new read, write, import or event on the
  hook path.
- **FR-008**: doctor's Day section has one `session id` row from the last of today's
  `session.seen` events that carries `env_file`: ok when true or absent, warn when false.
- **FR-009**: The planner skill card bullet and the guide's Records and questions paragraph
  carry the rerun rule of User Story 4; `docs/site/reference.md` shows `--card <hash>`.
- **FR-010**: Design 9.2 gains rows I29 and I30, and `tests/test_invariants.py` their
  checks: I29, a decision record command for a card the planner asked never prompts below
  strict, with and without `WUWEI_SESSION_ID`, and never records from the card under
  strict; I30, a `--card` record command confirms only the card of the record as it stands.

### Key Entities

- `state.sessions.<id>.gate_asked`: topics the planner's cards asked (`D-n` and
  `D-n=<sha256 of the answer>`), written only by the record gate. Unchanged.
- Card hash: 12 hex characters derived from the record's `Question` and `Options`; carried
  only in the widget's record command, stored nowhere.
- `session.seen` payload: gains `env_file` (bool) on SessionStart rows only.

## Success Criteria

- **SC-001**: The five acceptance scenarios of the issue pass as in-process tests.
- **SC-002**: I29 and I30 hold on every case; I29 fails when the CLI reads the session only
  from the environment, I30 fails when the card hash is ignored.
- **SC-003**: The full suite passes; `tests/test_invariants.py::test_invariants_hold` stays
  within its CPU budget.

## Assumptions

- The hash is the card's, not the answer's. The widget is printed before the owner answers,
  so it cannot carry the answer hash the record gate stores (`D-n=<sha256 of the answer>`).
  What it can carry is a hash of what the card shows, the record's `Question` and `Options`,
  computed with the #529 `card_topic` hashing. The match on it binds the answer to the
  record the owner saw: a record edited after the card no longer confirms from that card.
  The id match in `gate_asked` stays the proof that the planner asked it.
- "An id in `gate_asked` without a hash match still passes for records asked before this
  change" is read as: a record command without `--card` (every widget printed before this
  change) passes on the id alone. A `--card` hash that names another version of the record
  does not pass; its next step is the card again, which is a card, not a wall (#530).
- The hash is not a secret: a seat could compute it. It is a version check, not a trust
  boundary; the hook is (I8).
- A caller with no TTY on stdin and no `WUWEI_SESSION_ID` is treated as the planner for the
  asked topics. A seat cannot reach this: the hook refuses record commands from seats and
  non-planner sessions before the CLI runs (I8, and a new explicit test).
- `drafts approve` already reads the planner from state; no change.
- `consolidate` answers (`wuwei memory forget F-n apply|keep`) never used `owner_confirm` or
  a card: the hook keeps `memory forget` owner-only and `consolidation.forget` always asks
  y/N. A card path needs the record gate to store F-n topics and the hook to pass them, a
  change on a hook path the notes rule out. Deferred.
- The doctor row is a warn, not a fail: nothing is refused, and record commands work without
  the variable after this change.
- I25 to I28 belong to #603 to #606 and I31 to I35 are taken on main; this item uses I29 and
  I30.
- The branch base (`6627e24`, 0.23.0) predates main 0.24.1. Line numbers above are on the
  base. Main changed `CONFIG_RECORD` (#600), the doctor Day section and
  `tests/test_invariants.py` (#627); the builder works against current main.

## Deferred

- Card-confirmed consolidate answers (`memory forget`): the record gate stores the asked
  F-n, `protect_state` passes it to the planner, `consolidation.forget` checks the card. Its
  own issue.
