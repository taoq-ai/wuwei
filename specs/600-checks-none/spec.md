# Feature Specification: No fast checks is a state, not a wall

**Feature Branch**: `600-checks-none`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #600: fix(checks): an empty fast-check list is a state, not a wall:
items build with checks none and merge at green CI, calibration proposes checks from the
repository or none under mandate, config cards carry list values in a Value row, and a
config record is two-way.

Owner, 2026-10-09, first day on 0.23.0 in autonomous mode, on a repository that holds a
paper (Markdown and a plan, no code): a card reached the owner reading "Which fast checks
gate every change in repo:<name>? All four planned items are refused at dispatch because
repos.0.fast_checks is empty." Owner: "Again."

Builds on #328 (calibrate fast checks), #529 (the card answer is the confirmation;
`config set --from-card`), #530 (no wall below strict), #544 (classes), #551 (the CLI owns
the path), #557 (measured reversibility), #579 (pace reads the fast checks) and #494 (the
config list writer). Design references: 4.1 (push before the fast checks passed), 5.2
(Records, #529; Pace, #579), 5.8 (decision framework), 9.2 (safety invariants).

## Root cause

Line numbers are on the worktree base, `main` at 6627e24.

1. The wall. `cli/wuwei/commands/build.py:85-92` (`_repo`) raises `worktree has no
   configured fast checks` whenever `repo['fast_checks']` is empty, under every posture.
   `build.next_action` (`build.py:146`) calls it, and `dispatch.launch_set`
   (`cli/wuwei/dispatch.py:349-353`, `371`, `391`) turns the ValueError into
   `{'action': 'refused'}` for every briefed item of that repository. Nothing else refuses
   an empty list: `fast_checks.commands` (`cli/wuwei/fast_checks.py:34-55`) returns `[]`,
   `fast_checks.record` records `{}` and returns 0, `build.check` and
   `build.complete_checks` (`build.py:330-410`) accept zero results, and the push evidence
   rule `commit_push.fast_evidence` (`cli/wuwei/guards/commit_push.py:147-167`) loops over
   no checks and returns `(0, '')`. The one refusal is a #530 violation under observe and
   guarded.
2. Calibration detects nothing for a paper. `cli/wuwei/calibrate.py:92-133` (`toolchain`)
   reads `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod` and, only without a
   language, Makefile `test`, `lint` and `check` targets. It reads no `latexmk` or
   `markdownlint` configuration and no workflow `run:` step (`_workflow`,
   `calibrate.py:175-245`, keeps job names only). With nothing found, `calibrate` proposes
   nothing and nothing says "none" is the answer; a proposal reaches config only through
   `config promote` in a host terminal (`cli/wuwei/commands/config.py:265-282`).
3. A config card cannot carry a list. The #529 flow matches the answered option's title as
   `KEY = VALUE` (`cli/wuwei/commands/setup.py:151-193`, `assignment` and `_from_card`), and
   the new-record lint caps a title at 40 characters without a quote
   (`cli/wuwei/decision.py:156-158`). `repos.0.fast_checks = ["python3 -m pytest -q"]` fails
   both limits, so the record is rejected before it can be asked.
4. A config record is routed as Strategic. `cli/wuwei/undo.py:17-21` (`KIND`) maps `other`
   to no action kind, so `undo.measured` (`undo.py:70-90`) has no undo for it and nothing
   corrects a door the seat wrote as `one-way`; `decision.cisr`
   (`cli/wuwei/decision.py:364-372`) then classes a one-way, workspace-wide record as
   Strategic. Separately, `commands/decision.py:91-133` (`mandate`) takes a two-way config
   record under autonomous and records a mandate outcome, after which
   `config set --from-card` still refuses (it needs the owner's answer on the card,
   `setup.py:181-186`): the planner loops between the two.

## User Scenarios and Testing

### User Story 1: Items build in a repository with no fast checks (Priority: P1)

A repository with `fast_checks = []` (none configured) is buildable below strict. Its items
launch, build, pass `build check` with no local checks, run the gates, push and raise a PR
whose body says `checks: none configured`; the shepherd merges at green required checks as
always. Under strict the launch asks once per repository.

**Why this priority**: it is the wall the owner hit; every other story improves what
happens around it.

**Independent Test**: a fixture workspace with one repository `acme/paper` whose
`fast_checks = []`, a planned item with a logged builder brief and worktree; call
`build.next_action` and `dispatch.launch_set` in-process.

**Acceptance Scenarios**:

1. **Given** a repository with `fast_checks = []` under autonomous and observe (and under
   guarded), **When** `dispatch next --all` runs, **Then** the briefed planned items get
   `launch` entries, no entry is `refused`, the build record has `commands == []`, the
   `build.started` event payload carries `checks: "none configured"`, and no card is
   asked.
2. **Given** that build, **When** the builder stops and `build check` runs, **Then** the
   item moves to `gate` with no check run.
3. **Given** a builder brief for an item in that repository, **Then** its header carries
   `Fast checks: none configured; CI and the gates are the evidence. Write "checks: none
   configured" in the PR body.` and no pace `Checks:` line contradicts it.
4. **Given** a push from that worktree, **Then** `commit_push.fast_evidence` returns
   `(0, '')` (pinned, unchanged).
5. **Given** posture strict and no owner answer on the repository's fast-checks card,
   **When** `build next` runs, **Then** it exits 2 naming `wuwei calibrate --questions
   --repo acme/paper`; **Given** the owner answered that card (any option), **Then** the
   launch proceeds.

### User Story 2: Status and doctor name the state (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a repository with `fast_checks = []`, **When** the owner runs `wuwei status`
   (full) or `wuwei doctor`, **Then** each shows `fast checks: none configured; CI and the
   gates are the evidence` for that repository; the doctor row is `ok`, not `warn`.
2. **Given** a repository with fast checks, **Then** neither output carries that line.

### User Story 3: Calibration proposes from the repository's contents (Priority: P1)

`calibrate --questions` (which `wuwei next` runs every day) proposes the fast checks of each
repository whose list is empty and that has no fast-checks record on a live day. The
proposal is detection, never invention: a Makefile `test`, `check` or `lint` target,
`pyproject.toml` or `package.json` scripts (as today), a `latexmk` or `markdownlint`
configuration, or, when none of those is found, the command of a `.github/workflows` test
step. With nothing found it recommends `none` and says why. The proposal is a Routine
decision record (class `approach`, two-way, high confidence, Value rows, a Previous line).
Under autonomous (below strict) the CLI takes it under the mandate, writes the value and
the record's outcome, and the digest lists it; under supervised (and strict) it is routed
to the owner and printed as a card whose record command is `wuwei config set --from-card
D-n`.

**Acceptance Scenarios**:

1. **Given** autonomous mode, observe, and a repository with `fast_checks = []` whose
   checkout has a Makefile with a `test:` target, **When** `calibrate --questions` runs,
   **Then** it writes one decision record recommending `make test` (option title
   `Detected`, Value row `repos.0.fast_checks = ["make test"]`), records it decided by
   `mandate` (record Outcome and Decided-by, `decision_outcomes`), writes
   `fast_checks = ["make test"]` to config with one `config.set` event naming the card,
   prints one stderr line naming the record and the value, prints no widget for it, and
   exits 0.
2. **Given** the same with no detectable runner, **Then** the record recommends `None`
   (Value row `repos.0.fast_checks = []`), its Context names the reason (no Makefile target,
   no pyproject.toml or package.json check, no latexmk or markdownlint configuration and no
   CI test step), and config is unchanged.
3. **Given** supervised mode, **Then** the record is routed to the owner (`decision_routes`)
   and the printed widget list carries its card with record command `wuwei config set
   --from-card D-n`; config is unchanged.
4. **Given** a fast-checks record for the repository already exists on a live day, or the
   list is not empty, **Then** `calibrate --questions` writes no new record.
5. **Given** a checkout with `.markdownlint.json`, **Then** `toolchain` yields fast check
   `markdownlint .` (a lint, so fast); with `.latexmkrc`, `latexmk` (a runner, unmeasured);
   with no local finding and a workflow on `pull_request` whose `test` job runs
   `python3 -m pytest -q`, that command.

### User Story 4: Config cards carry values, not titles (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a decision record whose options are titled `Detected`, `None` and `Defer`
   and whose `Value:` table holds `| A | repos.0.fast_checks = ["make test", "markdownlint ."] |`
   and `| B | repos.0.fast_checks = [] |`, **When** it is linted as a new record, **Then**
   it passes; a Value row naming an unknown option, an undeclared key or a value that is
   not TOML is rejected with the reason.
2. **Given** that card routed and answered `Detected` in the planner session (below
   strict), **When** the planner runs `wuwei config set --from-card D-1`, **Then** config
   holds the list, no host prompt runs, the owner outcome and one `config.set` event are
   recorded. `config set repos.0.fast_checks '["make test", "markdownlint ."]' --from-card
   D-1` (key and value given) writes the same; a key or value that differs from the
   answered option's Value row writes nothing and exits 1.
3. **Given** `decision show D-1 --widget` on a config card (Value rows or #529 titles),
   **Then** its record command is `wuwei config set --from-card D-1`.
4. **Given** a #529 card whose titles read `cap = 5`, **Then** both `config set cap 5
   --from-card D-1` and `config set --from-card D-1` work (the first unchanged).
5. **Given** a config card answered with an option that sets nothing (`Defer`, or a #529
   `Keep the current cap`), **When** the planner runs `config set --from-card D-1`,
   **Then** it records the owner outcome, writes no config, prints `No config.toml
   changes` and exits 0 (today it refuses, so a Keep answer cannot be recorded).

### User Story 5: A config record is two-way (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a record that sets `repos.0.fast_checks` through its Value rows, carries
   `Previous: repos.0.fast_checks = []`, and says `Reversibility: one-way` and
   `Class: other`, **When** `decision lint` runs, **Then** it passes and reports the door
   it will store (`Reversibility: two-way, not one-way: a config write that records its
   previous value is undone by config set (#600)`); **When** `decision route` runs,
   **Then** the stored record reads `Reversibility: two-way` and `Class: approach` with a
   Notes line, and the route is not Strategic (the card is Routine).
2. **Given** the same record with `Class: design`, **Then** the class stays `design` and the
   door is corrected to two-way.
3. **Given** a config record without a `Previous:` line, **Then** neither door nor class is
   changed (no evidence of the undo).
4. **Given** autonomous mode and a config record (Value rows or #529 titles), **When**
   `decision route` runs, **Then** it routes to the owner instead of taking it under the
   mandate, because a config value is the owner's answer (#529); `decision show --widget`
   then prints its card.

### Edge Cases

- A fast-check command containing `|` cannot sit in a Value cell (table separator); the
  lint rejects the row; the owner sets such a value in a host terminal.
- `fast_checks = []` with `repos.tests` set: at careful pace the checks run `repos.tests`
  (#579), so `fast_checks.commands` is not empty and the none line is not written; the
  none state is decided by `fast_checks.commands` returning `[]`.
- A missing checkout during `calibrate --questions`: no proposal for that repository and
  one stderr line naming it; the other widgets still print.
- The mandate write fails (config changed, layout error): exit 2 with the reason; the
  record and its mandate outcome stay, the next run does not re-propose (the record
  exists), and the owner sets the value on a card or in a host terminal.

## Requirements

### Functional Requirements

- **FR-001**: `build._repo` MUST NOT refuse an empty `fast_checks` below strict. Under
  strict it refuses until the owner has answered the repository's fast-checks record (an
  owner outcome in that day's state, never a seat-writable file), naming
  `wuwei calibrate --questions --repo <name>`.
- **FR-002**: A build with no checks MUST record `commands: []` and carry
  `checks: "none configured"` on its `build.started` event; `build check` completes it to
  `gate`.
- **FR-003**: The builder brief of an item whose `fast_checks.commands(...)` is empty MUST
  carry the none line instructing `checks: none configured` in the PR body, in place of
  the pace `Checks:` line.
- **FR-004**: `wuwei status` (full, not `--line`) and `wuwei doctor` MUST name
  `fast checks: none configured; CI and the gates are the evidence` per such repository;
  the doctor row status is `ok`.
- **FR-005**: `calibrate.toolchain` MUST detect `markdownlint` configuration
  (`markdownlint .`, a lint) and `latexmk` configuration (`latexmk`), and, when no local
  finding exists, a single-line `run:` command of a test, check or lint step in a workflow
  triggered on `pull_request` or `push`. Detected values pass the existing `SAFE` and
  instruction-like filters of `profile`.
- **FR-006**: `calibrate --questions` with no question ids MUST write one fast-checks
  decision record per selected repository with an empty list and no record on a live day,
  recommend the detected commands or `none` with the reason, take it under the mandate
  and write the value under autonomous below strict, and route it to the owner with its
  card otherwise.
- **FR-007**: A decision record MAY carry `Value:` (a table `| Option | Value |`, each cell
  `<dotted key> = <TOML value>`) and `Previous:` (one line, `<dotted key> = <TOML value>`).
  The new-record lint MUST check that each Value row names an option and a declared key
  with a parsable value.
- **FR-008**: `config set --from-card D-n` MUST read the key and value from the answered
  option's Value row, falling back to its #529 title; KEY and VALUE become optional with
  `--from-card` and, when given, must equal the answered assignment. An answered option
  that sets nothing records the owner outcome and writes nothing. The widget record
  command for any config card is `wuwei config set --from-card D-n`.
- **FR-009**: A record that sets a config key (Value rows or #529 titles) and carries a
  `Previous:` line for that key MUST be measured two-way by `undo.measured` (kind
  `config`); `undo.correct` at first route MUST rewrite a one-way or unsure door to two-way
  and a missing or `other` class to `approach`, with a Notes line; `decision lint` reports
  the door it will store.
- **FR-010**: `mandate` MUST NOT take a record that sets a config key; it routes to the
  owner (#529). The calibrate path is the CLI's own producer and does not pass through it.
- **FR-011**: Invariant rows I25 to I27 in design 9.2 and `tests/test_invariants.py`:
  I25 an empty fast-check list never refuses a launch below strict; I26 a config card with a
  list value records without a prompt below strict; I27 a config record is never Strategic
  on its own. I22's note names the config-write kind.
- **FR-012**: Nothing new on a hook path: `protect_state`, `commit_push`, the PR guard and
  `fast_checks.record` keep their behaviour; no new refusal under observe or guarded.

### Key Entities

- **Fast-checks record**: a decision record with Question
  `Which fast checks gate every change in repo:<name>?`, Class `approach`, Value rows for
  `repos.<n>.fast_checks`, `Previous: repos.<n>.fast_checks = []`, two-way, high confidence.
- **Value row**: one row of the optional `Value:` table, `| <option> | <key> = <TOML> |`.

## Success Criteria

- **SC-001**: In a workspace whose repository has no fast checks, `dispatch next --all`
  returns no `refused` entry under observe and guarded.
- **SC-002**: The owner's day from the issue produces zero fast-checks cards under
  autonomous, and one Routine card per repository under supervised.
- **SC-003**: A config record written by a seat with `one-way`, `other` and a Previous line
  is stored two-way and `approach` after its first route.

## Assumptions

- "Asks once per repository" under strict is the fast-checks card: the strict launch refuses
  until the owner answered it, and an answered card (any option) clears that repository.
  Strict keeps its refusal by constitution VII.
- "Recorded on the item" is the build record (`commands: []`) plus the
  `checks: "none configured"` field on `build.started`; the PR body line is the builder's,
  instructed by its brief (tests assert the brief, never model prose).
- The card recommends what the repository declares (detection), measured or not: a Makefile
  `test` target is recommended although `classify` calls it unmeasured. A slow runner taken
  under the mandate is two-way and is replaced on a card or with `calibrate --measure` and
  `config promote`. A `ponytail:` comment names the ceiling.
- The proposal runs only from `calibrate --questions` without ids (the daily `wuwei next`
  row); named ids keep today's behaviour.
- "Already proposed" is a fast-checks record for the repository on a live day
  (`watch.days`); an archived day is not read, so a repository may be proposed again after
  its record is archived. A `ponytail:` comment names the ceiling and the upgrade (a memory
  file such as `memory/targets.json`).
- A Previous line is the evidence that the record carries the previous value; the CLI
  writes it for its own records, and the `config set` session hint prints the exact line
  with the current value (rendered by `configtext.dumps`). The config-write undo is the same
  `config set` with the previous value, so it needs no rehearsal; I22's note says so.
- The option titles are `Detected` (the detected commands; not `Recommended`, because the
  widget already appends ` (Recommended)` to the recommended title), `None` (`[]`) and `Defer`
  (no Value row, nothing written; the record format requires a Do nothing, Defer or Keep
  row). When nothing is detected the options are `None` (recommended) and `Defer`.
  `Custom` is not an option: the widget's Other answer goes to a new card or a host
  terminal.
- `markdownlint .` (markdownlint-cli) and `latexmk` (reads its rc file) are the commands for
  those configurations; markdownlint is a lint and counts as fast.
- Under supervised the calibrate card is routed with `route_owner`; under strict the
  owner's answer is recorded in a host terminal as today.
- A mandate-taken config record never writes config through `config set --from-card`; only
  the owner's answer does (I8 unchanged).
- Invariant ids I25 to I27 assume no parallel item took them; a merge renumbers.

## Deferred

- A durable "proposed" marker across archived days (memory file), if re-proposals after an
  archive prove noisy.
- A `Custom` option with free-text values on decision cards.
