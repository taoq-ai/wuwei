# Feature Specification: the owner's session is never blocked by work

**Feature Branch**: `477-session-available`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #477, "fix(plan): the owner's session is never blocked by work: seats
and long commands run in the background, the planner stays available, and a test rejects
blocking instructions in skills and charters". Owner, 2026-10-04, first real items on
0.15.0: "the agents are holding the main session instead of running in the background, so I
can't talk to the planner while something is in progress" and "the main session should be
available at all times, all the work happens in the background."

## Root cause (read on main, 0e22fac)

The notes name no dry-run workspace for this issue. The causes below are read from the code
on main and confirmed with a read-only in-process probe in a temporary workspace (two
running builder seats, a third item whose builder stopped and whose fast checks run); each
is pinned by a failing test in tasks.md before it changes. The issue cites plan skill lines
38, 40 and 54; #474 (merged as 0e22fac) moved them to 41, 43 and 57.

1. The plan skill tells the planner to block. `skills/wuwei-plan/SKILL.md:41` says "wait for
   the turn to return in the planner session" after an Agent launch; `:25` says "When the
   turn returns, do each item's next step"; `:49` says "After each Agent or measured check
   returns"; `:57` says "Wait for all required verdicts before a fix or PR raise", which the
   planner reads as "block until".
2. The fast checks run in the foreground. `skills/wuwei-plan/SKILL.md:43` says "execute the
   returned `command` through Bash", with no background mode. A configured suite takes
   minutes (`adapters/checks/local.py:26` allows 300 s per command).
3. The steward launch has no background instruction. `skills/wuwei-report/SKILL.md:12` and
   `skills/wuwei-retro/SKILL.md:12` say "launch that steward with Agent exactly as returned".
4. Nothing records a fast check in flight. `wuwei build check <item>`
   (`cli/wuwei/commands/build.py:383-397`) leaves the build record at status `check` from the
   builder's stop until the result, so "checks are waiting to run" and "checks are running"
   look the same. The probe: with item C's check running, `wuwei next` printed
   `build: C is in implement; run the build loop and do the step it returns. Run: wuwei
   build next C` (`cli/wuwei/commands/next.py:77-93`), and `build next C` returns the same
   `check` action (`build.py:126-128`). A planner that follows `next` runs the suite a second
   time while the first still runs.
5. The board does not say what is running. `next` names running seats by name only
   (`next.py:113-123`, "Seats running: b-1, b-2"), with no role, item or start time, and
   never a check. `status --line` prints only counts (`cli/wuwei/commands/status.py:345-348`,
   probe: `seats 2 of CAP 3 (unplanned 2)`).
6. No rule says the owner's session stays available: neither the constitution, the design
   doc (5.2), the planner charter nor `docs/site/agent.md`.

## User Scenarios & Testing

### User Story 1 - Seats run in the background and the planner stays available (Priority: P1)

The plan skill launches and continues every seat with Agent in the background (the harness
default) and moves on to the next ready action or the owner's message. `wuwei build next
<item>` and `wuwei dispatch next <item>` are called when a seat's completion notification
arrives, never polled (`build next` still exits 2 while the seat runs). The fix round and the
PR raise start only once every required verdict is received. The report and retro skills
launch the steward with Agent in the background. The planner ends each turn with the board in
one line (`wuwei status --line`). The planner charter says the planner stays available to the
owner while seats run and answers from the board, never by resuming or interrupting a seat.
Owner questions through AskUserQuestion are the one thing that waits.

**Why this priority**: this is the owner's complaint.

**Independent Test**: `python -m pytest -q tests/test_charters.py -k blocking` and
`python -m pytest -q tests/test_headless_e2e.py`.

**Acceptance Scenarios**:

1. **Given** a builder launched by the planner, **Then** the planner's next turn is available
   to the owner before the builder stops, and the seat's stop is recorded by SubagentStop as
   today. Measured on the headless fixture day: a planner `Stop` hook falls between the
   builder's Agent PreToolUse and its SubagentStop.
2. **Given** the plan, report and retro skills, the charters, the generated agents and
   `docs/site/agent.md`, **Then** none tells the planner to wait for an Agent call, a turn, a
   seat or the verdicts, to run a command through Bash without the background mode, or to
   launch with Agent without "in the background".

### User Story 2 - Fast checks run in the background and are visible while they run (Priority: P1)

The plan skill runs the `check` action's command through Bash in the background and calls
`wuwei build next <item>` when its notification arrives. `wuwei build check <item>` records
the check in flight (start time and process id) on the build record before it runs the
checks, and clears it with the result. While that process is alive, `build next <item>` and
a second `build check <item>` exit 2 naming the running check and its start time, and `wuwei
next` does not send the planner to the build loop for that item. A check whose process died
(killed session, crash) is not in flight: the action is `check` again, as today.

**Why this priority**: a suite of minutes is the longest foreground command in the day, and
without the record a background check runs twice.

**Independent Test**: `python -m pytest -q tests/test_build_next.py -k in_flight`.

**Acceptance Scenarios**:

1. **Given** fast checks that take a minute, **Then** the owner can speak to the planner while
   they run and `build next` follows their result. Measured on the headless fixture day: a
   planner `Stop` hook falls between the Bash PreToolUse that runs `build check A` and that
   command's exit.
2. **Given** a build at `check` whose `build check` process is alive, **When** `build next
   <item>` or `build check <item>` runs, **Then** it exits 2 naming the running check and its
   start time; **When** that process has exited without a result, **Then** `build next`
   returns the `check` action and `build check` runs.
3. **Given** `build check` completes (pass, failure feedback or park), **Then** the build
   record carries no in-flight marker.

### User Story 3 - The board names what is running (Priority: P1)

`wuwei next` and `wuwei status --line` name the running seats with role, item and start time,
and the fast checks in flight, so "what is happening" is answered without touching them. A
second-opinion run (`wuwei dispatch opinion`) already records a running seat with its start
time, so it appears as a seat.

**Independent Test**: `python -m pytest -q tests/test_next.py tests/test_signal_status.py -k running`.

**Acceptance Scenarios**:

1. **Given** `wuwei next` while two seats and a check run (and nothing else is due), **Then**
   the output names all three with start times, for example `Running: builder A 09:10,
   builder B 09:20, checks C 09:25`.
2. **Given** the same day, **Then** `status --line` carries `running builder A 09:10, builder
   B 09:20, checks C 09:25` and `status --json` carries the same rows under `running`.
3. **Given** nothing runs, **Then** `status --line` has no `running` part.
4. **Given** a seat without a recorded start, **Then** it shows `start unrecorded`.

### User Story 4 - The principle is written down and a test keeps it (Priority: P2)

The constitution and the design doc (5.2) gain one rule: the owner's session is never blocked
by work. Seats run in the background; any command that can run longer than a few seconds
(fast checks, `dispatch opinion`, `steward run`, calibration) runs in the background; the
planner's turn ends with the board in one line and the owner can speak at any time; owner
questions are the one thing that waits. `docs/site/agent.md` carries the rule. A text test
reads every skill and charter and fails on a blocking instruction.

**Independent Test**: `python -m pytest -q tests/test_charters.py -k blocking`.

**Acceptance Scenarios**:

1. **Given** the skill and charter texts, **Then** the test fails if a blocking instruction is
   reintroduced (each old sentence of Root cause 1 to 3, used as a sample, matches) and
   passes on the background phrasing.
2. **Given** the constitution, the design doc, the planner charter and agent.md, **Then** each
   states the rule.

### Edge Cases

- The check process is killed or the session closes mid-check: the pid is dead, so `next` and
  `build next` treat the check as not running and the planner reruns `build check`, which
  overwrites the marker.
- `build check` exits 2 on an error before the result (HEAD moved, adapter failure): the
  marker stays but its process has exited, so it is not in flight.
- Pid reuse after a crash: a stale marker whose pid now belongs to another live process reads
  as in flight until that process exits. Accepted ceiling (Assumptions).
- The SubagentStop reuse path (`build.stopped` completes the checks from evidence the
  builder recorded) never sets a marker; clearing is a no-op there.
- The Codex loop (`wuwei build <item> <brief> <worktree>`) calls `check` in its own process;
  the marker carries that process's pid and clears the same way.
- The shepherd charter's pinned sentence `"before X" blocks until X is met` (a merge
  precondition, `tests/test_charters.py` RULES) is not a session wait; the pattern matches
  `block until` only, never `blocks until`.

## Requirements

### Functional Requirements

- **FR-001**: The plan skill MUST say that every seat launch and continue goes to Agent in the
  background, that the planner continues with the next ready action or the owner's message,
  that `build next` and `dispatch next` follow a completion notification and are never
  polled, that the `check` command runs through Bash in the background, that the fix round
  and the PR raise start only once every required verdict is received, that `wuwei steward
  run` runs in the background, and that each turn ends with `wuwei status --line` in one line.
- **FR-002**: The report and retro skills MUST launch the steward with Agent in the
  background.
- **FR-003**: The planner charter MUST say the planner stays available to the owner while
  seats and background commands run and answers from the board, never by resuming or
  interrupting a seat; `agents/planner.md` MUST be regenerated and the charter version
  bumped.
- **FR-004**: `wuwei build check <item>` MUST record `check: {started_at, pid}` on the build
  record (event `build.check_started`, silent, producer `wuwei build check`) before running
  the checks and MUST leave no marker once it records a result.
- **FR-005**: `wuwei build next <item>` and `wuwei build check <item>` MUST exit 2 with the
  start time and the next step while a live check marker exists.
- **FR-006**: One shared helper MUST list what runs (running seats, live checks) as
  `(started_at, role, item)` rows, oldest first, and one MUST format them; `next` and
  `status` MUST both use them.
- **FR-007**: `wuwei next` MUST skip an item with a live check when choosing the build step,
  and its `wait` rows MUST name every running seat and live check with role, item and start
  time.
- **FR-008**: `status --line` MUST add a `running ...` part when something runs, and `status
  --json` MUST carry `running`.
- **FR-009**: The constitution (Constraints) and the design doc (5.2) MUST state the rule;
  `docs/site/agent.md` MUST carry it; `docs/site/reference.md` MUST describe the new status
  part.
- **FR-010**: A text test MUST fail on a blocking instruction in `skills/*/SKILL.md`,
  `charters/*.md`, `agents/*.md` and `docs/site/agent.md`, and pass on the background
  phrasing.
- **FR-011**: The headless fixture day MUST assert a planner turn between the builder's launch
  and its stop and between the check's launch and its result; its fast check MUST take a few
  seconds so the assertion measures something.

### Key Entities

- Build record (day state `builds.<item>`, producer `wuwei build`): gains an optional
  `check: {"started_at": <ISO time>, "pid": <int>}` while `build check` runs.
- In-flight row: `(started_at or "", role, item)`; role is the seat role (`builder`,
  `sentinel-arch`, a second-opinion role) or `checks` for fast checks.

## Success Criteria

- **SC-001**: The four Acceptance scenarios of issue #477 pass: US1 scenario 1 and US2
  scenario 1 as headless validator assertions with offline mutation tests, US3 scenario 1 as
  a `next` test, US1 scenario 2 and US4 scenario 1 as the text test.
- **SC-002**: The full suite passes with `python -m pytest -q`.
- **SC-003**: No new command, config key, state key, module or dependency. One new event
  kind, `build.check_started`, silent and reserved to `wuwei build check`.

## Assumptions

- #473 is a precondition, not part of this item: a background seat hands back without
  `last_assistant_message`, and the SubagentStop guard must read the transcript before
  background seats can be the default. This item changes no SubagentStop code. The notes say
  it lands after #473 merges; the headless assertions are measured on the opt-in paid run,
  which needs #473.
- "Background" for Agent is the harness default; the skill says so and the planner does not
  pass a foreground flag. For Bash it is the tool's background mode, whose exit arrives as a
  notification.
- The only CLI change is the fast-check marker and the board text. `dispatch opinion` already
  records a running seat with `started_at` (`cli/wuwei/dispatch.py:531-535`), so it shows as
  a seat; `steward run` returns quickly and its seat is recorded at launch; `calibrate`
  measures in setup in a host terminal. None needs a new record.
- Liveness by pid (`os.kill(pid, 0)`, stdlib) is enough: the marker only steers `next`,
  `build next` and the board, never a guard or a metric, so it is not trusted state in the
  sense of the pre-flight rule. Pid reuse can make a dead check read as running until the
  reusing process exits; accepted, with a `ponytail:` comment naming the upgrade (a start
  token compared with the process start time).
- `wuwei next` lists what runs on its `wait` rows only; when another step is due it names
  that step, and `status --line` always carries the running part. This keeps `next` one row
  (its ponytail note) and satisfies Acceptance 3, which has nothing else due.
- Start times print as `HH:MM` cut from the recorded ISO time, in the offset it was recorded
  with; the date is today's. One format serves `next` and the status line.
- A marker whose pid is the current process is never in flight: the CLI is one process per
  call, so a check that raised in this process is over. This keeps in-process tests and the
  Codex loop (which runs `check` in its own process) from reading their own finished check
  as running, without a clear-on-error write.
- The text test is a regex over the files, not a parser. Its patterns: `wait for` followed by
  the Agent, a turn, a seat, a builder, a sentinel, a check or the verdicts; `block until`;
  `foreground`; `turn returns`; `through Bash` or `with Bash` not followed by `in the
  background`; `with Agent` not followed by `in the background`. Writers keep `in the
  background` directly after `Bash` or `Agent`.
- The design doc is amended by its owner only (constitution, Governance); the owner asked for
  this rule in the issue, so the item adds it as an owner-dated paragraph in 5.2. The
  constitution amendment needs a dated line in the merge commit message; this item leaves
  changes uncommitted, so the merger adds it.
- #476 will generate `docs/site/agent.md` from tables. Until it lands, this item edits the
  hand-written page with one paragraph; when #476 lands, its generator carries the rule. #474
  and #476 edit the plan skill in parallel; this item changes only the sentences named in
  Root cause 1 to 3 and adds two sentences, so the drain can union them.
- The headless fixture's fast check becomes `sleep 5 && test -s README.md`, long enough for
  the planner to end a turn between launch and result, short enough for the 300-second
  bound.

## Deferred

- None filed. A pid-reuse-proof marker is noted in the `ponytail:` comment, not deferred work.
