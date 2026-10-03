# Feature Specification: session orientation (`wuwei next`, SessionStart block, agent guide)

**Feature Branch**: `358-session-orientation`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #358, "wuwei next names the next step from the day's state, SessionStart orients the session with it, and the plugin ships an agent-facing guide to the whole flow"

## Problem and root cause

Owner, 2026-10-03, after three stops on the first day: a session in a WUWEI workspace does
not know what WUWEI is, which commands to run or in which order.

Reproduced on `main` (read-only, a fresh `wuwei init` workspace in scratch, then
`lifecycle.session_start({'cwd': <workspace>})`): the injected context starts with
`Active constraints:` and holds memory, today's raw state, the payload size and
`watch off`. It never says what WUWEI is, that `/wuwei:wuwei-plan` starts the day, or what
to run next. `python3 -P -m wuwei next` exits 2 with `invalid choice: 'next'`.

Root cause: `cli/wuwei/guards/lifecycle.py::session_start` (lines 31-87) composes the
context from the posture line (`SHADOW_LINE`, line 41, observe only), the session registry,
`memory.session_payload` (line 50), watch and listen health, the wake notice and phone
answers (lines 70-71). Nothing in the CLI derives "where the day stands and what comes
next" from the day's files; that knowledge is spread over the four skills, `daily.md` and
individual refusal reasons. The repository `AGENTS.md` is for contributors, `agents/*.md`
are seat charters and `docs/site/` is written for the owner, so no shipped document
explains the flow to an agent with no prior context.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `wuwei next` names the one next step (Priority: P1)

Any session (or the owner) runs `wuwei next` and gets one line: the day's state, the step,
and the exact command or skill to run. `--json` prints the same as `{state, step, command}`.

**Why this priority**: it is the single derivation everything else (SessionStart, the
skills, the docs) points at.

**Independent Test**: build a workspace in each day state in `tmp_path` and call the
command in process; assert the printed line and the JSON.

**Acceptance Scenarios** (issue Acceptance 1):

1. **Given** no workspace above the current directory, **When** `wuwei next` runs, **Then**
   it exits 0 with state `no-workspace` and command `bin/wuwei setup --shadow`.
2. **Given** a workspace with no repositories or no approved calibration
   (`.wuwei/calibration.json` absent), **Then** state `setup`, command `bin/wuwei setup`.
3. **Given** a calibrated workspace with no `plan.md` today, **Then** state `plan`, command
   `/wuwei:wuwei-plan`.
4. **Given** today's `plan.md` exists and the gate is not approved, **Then** state `gate`,
   the step names the Morning gate questions on `days/<date>/plan.md`, command
   `/wuwei:wuwei-plan`.
5. **Given** the gate is approved and a decision in today's ledger has no owner outcome,
   **Then** state `decision`, command `wuwei decision show <id>`.
6. **Given** an approved item in `planned` and fewer items in a build phase than CAP,
   **Then** state `dispatch`, command `wuwei worktree add <item>`, and the step names the
   brief and `build next` that follow. With CAP full the planned item is skipped.
7. **Given** an approved item in `spec`, `implement` or `fix` with no running seat,
   **Then** state `build`, command `wuwei build next <item>`.
8. **Given** an approved item in `gate` or `delta` with no running seat, **Then** state
   `verdicts`, command `wuwei dispatch next <item>`.
9. **Given** an approved item in `raised` with no running seat, **Then** state `pr`,
   command `wuwei pr act <pr ref>`.
10. **Given** every remaining item has a running seat, **Then** state `wait`, the step
    names the running seats, command `wuwei status --line`.
11. **Given** nothing above applies and today's watch is dead or the heartbeat is
    degraded, **Then** state `doctor`, command `wuwei doctor`.
12. **Given** every approved item is `merged`, `parked` or `escalated`, **Then** state
    `close`, command `/wuwei:wuwei-report`; once `report.md` exists and close was
    requested, state `closed`, command `wuwei close`.
13. **Given** any state above, **When** `--json` is passed, **Then** stdout is one JSON
    object with exactly the keys `state`, `step`, `command`.
14. **Given** an unreadable `config.toml` or `state.json`, **Then** exit 2, state
    `unmeasured`, the reason in the step and on stderr, command `wuwei doctor`.

### User Story 2 - SessionStart orients the session (Priority: P1)

Every Claude Code session that starts inside a workspace gets a short orientation block at
the top of its injected context: what WUWEI is, the day loop, the posture, the `wuwei next`
line, the entry point and the path to the agent guide.

**Why this priority**: it is what the owner asked for; a session learns the flow without
the owner naming a command.

**Independent Test**: pipe a recorded SessionStart payload through `hook.run` and assert on
`additionalContext`.

**Acceptance Scenarios** (issue Acceptance 2, 3, 4):

1. **Given** SessionStart in a workspace, **Then** `additionalContext` starts with the
   orientation header, contains a `Next: ` line equal to the `wuwei next` row and the
   absolute path of the shipped `docs/site/agent.md`, and `Active constraints:` appears
   on a line with index below 25.
2. **Given** an integrity guard message at SessionStart (for example a development
   checkout's owner-confirmed line), **Then** the orientation block is still first.
3. **Given** SessionStart outside a workspace, **Then** nothing is printed and the exit is 0
   (#323 regression).
4. **Given** a fresh calibrated workspace with no plan today (the session would be told only
   "start the day"), **Then** the injected text names `/wuwei:wuwei-plan` as the way to
   start the day, both in the entry line and in the `Next:` line.
5. **Given** a session whose environment carries `WUWEI_SEAT_ROLE=<role>` naming a shipped
   charter, **Then** the entry line points at `charters/<role>.md` instead of
   `/wuwei:wuwei-plan`; everything else in the block is the same.
6. **Given** the observe posture, **Then** the posture line is the existing `SHADOW_LINE`
   text (existing `tests/test_shadow.py` keeps passing); `guarded` and `strict` get one
   line each saying what blocks.

### User Story 3 - the plugin ships an agent-facing guide (Priority: P2)

`docs/site/agent.md` explains WUWEI to an agent with zero context: what it is, the roles,
the day in order with the command per step, what the hooks refuse and the accepted command
forms, where each record lives and which command writes it, how the owner answers, and the
first-day path.

**Independent Test**: docs tests on the file's presence, front matter, links, required
phrases and length.

**Acceptance Scenarios** (issue Acceptance 5):

1. **Given** the docs coverage tests, **Then** `bin/wuwei next` is a row of the commands
   table in `reference.md` and `agent.html` is linked from `index.md` and `daily.md`.
2. **Given** `agent.md`, **Then** it starts with the site front matter, names
   `wuwei next` and `/wuwei:wuwei-plan`, names each role (planner, lead, builder, gate
   sentinels, shepherd, steward), is at most 100 lines and has no em dash or emoji.
3. **Given** the four skills, **Then** each opens with the `wuwei next` instruction.
4. **Given** the README quick start, **Then** it says the session orients itself on start.

### Edge Cases

- Approved item missing from `items`: skipped, never a crash.
- Several items due: the first approved item (plan order) whose step is due wins; one row.
- A planned item while CAP is full and another item is building: the building item's step
  or `wait` is returned, not the planned one.
- `WUWEI_SEAT_ROLE` set to a name with no shipped charter: treated as an interactive
  session (no path is built from it).
- `wuwei next` failing inside SessionStart: the orientation still prints, with
  `Next: unmeasured: <reason>`, and the lifecycle exit is 2 (fail closed, reason shown).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new command `wuwei next [--json]` prints one row derived only from
  `config.toml`, `.wuwei/calibration.json`, today's `plan.md`, `report.md` and
  `state.json`, and today's `events.jsonl` (health). It writes nothing, spawns no
  subprocess and calls no adapter.
- **FR-002**: The row is chosen by the first matching state in this order: `no-workspace`,
  `setup`, `plan`, `gate`, `decision`, item states (`build`, `verdicts`, `pr`, `dispatch`,
  in approved-item order), `wait`, `doctor`, `close`, `closed`.
- **FR-003**: Exit 0 whenever a row is named (including `no-workspace`); exit 2 with the
  reason when an input cannot be read. It never exits 1.
- **FR-004**: `lifecycle.session_start` puts the orientation block first in its lines; the
  block replaces the standalone `SHADOW_LINE` (which becomes the observe posture line).
- **FR-005**: The hook's SessionStart output places the lifecycle orientation block first in
  `additionalContext` whatever other SessionStart guards returned.
- **FR-006**: The orientation block is under 25 lines, built in process from constants plus
  the `wuwei next` row and the plugin root path; no subprocess.
- **FR-007**: `docs/site/agent.md` ships in the plugin (the release archive already copies
  `docs/`).
- **FR-008**: Each of the four skills opens with: run `wuwei next` first and follow the step
  it names; run the steps below when it names this skill or the owner asked for it.
- **FR-009**: Owner docs link the guide: `index.md` and `daily.md` link `agent.html` as
  "what the session knows"; `daily.md` "Re-anchoring" describes the orientation block
  before `Active constraints:`; the README quick start says the session orients itself.
- **FR-010**: No new state key, event kind or file is written. Nothing is trusted from the
  row (it is display only), so no reservation is needed.

### Key Entities

- **Next row**: `{state, step, command}`; `state` is one of the names in FR-002 or
  `unmeasured`; `step` is one sentence; `command` is a CLI command (`wuwei ...` for the
  session, `bin/wuwei ...` for the owner's host terminal) or a skill (`/wuwei:wuwei-plan`,
  `/wuwei:wuwei-report`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the 14 scenarios of User Story 1 passes as an in-process test.
- **SC-002**: SessionStart in a workspace yields the orientation first with
  `Active constraints:` before line 25; outside a workspace it yields nothing.
- **SC-003**: The full suite passes, including `test_reference_lists_every_cli_command`,
  `test_site_pages_and_links` and the hook latency tests.

## Assumptions

- No dry-run workspace was named in the notes; the failure was reproduced on a fresh
  `wuwei init` workspace in scratch.
- Precedence (FR-002) is a design choice the issue leaves open: owner decisions come right
  after the gate because the owner is present and parked items wait on them; health
  (`doctor`) comes after item work so a session that cannot run `doctor --fix` (host
  confirmation) is not stuck on it all day.
- `wuwei next` does not run `wuwei doctor` or `closing.check`: both call adapters and
  subprocesses, which the SessionStart latency budget (#346) rules out. "Doctor warnings"
  are read from what the day already records (watch dead, heartbeat degraded via
  `status.scan`); "closable" is read from item phases. `wuwei close` itself still names
  anything owed.
- The step for a `planned` item is `wuwei worktree add <item>`, not `dispatch next`
  (which refuses phase `planned`); the step text names the brief and `build next` that
  follow, as in the plan skill's Item dispatch section.
- The `gate` state command is `/wuwei:wuwei-plan` (resume at the morning gate), not
  `wuwei plan approve`, so a session never approves without the owner's answers.
- Seats are detected only by the existing `WUWEI_SEAT_ROLE` environment variable (set for
  headless seats; Agent subagents fire no SessionStart). It selects display text only, so a
  forged value grants nothing.
- "Host terminal only under strict" in the issue does not match the code: owner-only
  commands (`decision outcome`, `drafts approve`, `mcp decide`, `config set`) require a
  host terminal in every posture. `agent.md` states the code's behaviour.
- The four skills hold no list of the day order, so FR-008 adds the line and deletes
  nothing; existing phrases pinned by tests stay.
- Feeding `--json` into the board (`wuwei_board`) and the DM is not in the Acceptance
  section; the JSON shape is the interface they will read. Deferred.
- No skill eval fixture is added: the "start the day" acceptance is a transcript-level test
  over the injected text (the issue allows either), which is deterministic.
