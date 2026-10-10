# Feature Specification: the fast-check timeout is per repository in config and the error names the limit

**Feature Branch**: `724-check-timeout`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #724 (owner, 2026-10-10, item 50): the fast-check timeout is
hardcoded at 300 s in the local checks adapter; a repository whose tests run longer can never
pass, and the error only says "could not run: TimeoutExpired". Deliver:
`repos.<n>.check_timeout_seconds` (default 300, read by the checks port); calibration measures
the first run and proposes the value when the run is near the limit; the error reads
"fast check `<cmd>` exceeded <n> s (repos.<n>.check_timeout_seconds); raise it with
bin/wuwei config set or split the check".

## Root cause

Reproduced read-only, in process, by loading `adapters/checks/local.py` with `subprocess.run`
stubbed to raise `TimeoutExpired` (no workspace needed, nothing runs):

```text
Result(exit=2, data=None, reason='fast check could not run: TimeoutExpired') {'timeout': 300}
```

- `adapters/checks/local.py:26`, `run`: `subprocess.run([...], timeout=300, ...)`. The limit
  is a literal; the checks port (`cli/wuwei/registry.py:22`, `'checks': {'run': ('path',
  'command')}`) has no way to pass another one, and the repository config
  (`cli/wuwei/workspace.py:70` to `82`, the `repos` schema) has no key for it.
- `adapters/checks/local.py:39` to `40`: `TimeoutExpired` is a `SubprocessError`, so it falls
  into the generic branch and the reason is only the exception class name. It names neither
  the command, the limit nor the setting.
- Every caller of the port inherits the 300 s cap: `cli/wuwei/fast_checks.py:92`
  (`fast_checks.record`: `wuwei fast-checks`, `build check`, the rebase in `pr act`, and
  `repos.tests` at careful and fast pace), `cli/wuwei/calibrate.py:168` (`classify`, under
  `calibrate --measure` and `config promote --measure`) and
  `cli/wuwei/commands/worktree.py:63` (`checks.bootstrap` on `worktree add`).
- Calibration measures each test runner (`calibrate.py:165` to `176`) but only compares the
  time with `calibrate.fast_check_seconds`; it never looks at the port's limit, so a run that
  timed out or nearly did is reported as `exit 2: fast check could not run: TimeoutExpired`
  with no proposal.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: How does the setting reach the adapter: the adapter reads config, or the caller passes
  it? A: The caller passes it. The checks port gains a `timeout` parameter
  (`run(path, command, timeout, root)`); each caller already holds the repository's config
  row and passes `repo['check_timeout_seconds']`. An adapter that looked the repository up
  from a worktree path would duplicate `commit_push.context`.
- Q: What does `<n>` in the message print? A: The literal `repos.<n>.check_timeout_seconds`,
  as other messages in the code base name a repository key (`repos.<n>.path`). The adapter
  does not know the repository index, and the owner finds it with
  `bin/wuwei config show repos`.
- Q: What does "near the limit" mean, and what value is proposed? A: A measured run that took
  at least 80 % of the limit (a run that timed out took the whole limit). The proposal is
  twice the current limit: one rule covers a run that finished close to the limit and one
  that was cut off, whose real length is unknown.
- Q: Does `checks.bootstrap` use the setting? A: Yes. It runs through the same port in the
  same repository's worktree, and with the new message it would otherwise name a setting that
  does not apply to it.
- Q: Is the timeout exit 2 or exit 1? A: Exit 2 (could not run), as today: the check was not
  measured, so it is never evidence.

## User Scenarios and Testing

### User Story 1 - a slow suite can pass when the owner raises the limit (Priority: P1)

The owner's repository has a test suite that runs ten minutes. They set
`repos.0.check_timeout_seconds = 900`; `wuwei fast-checks` (and every path that records fast
checks) lets the run finish and records it.

**Why this priority**: today such a repository can never pass a fast check.

**Independent Test**: config with `check_timeout_seconds = 900`; `fast_checks.record` with a
fake checks port asserts it receives `timeout=900`; the local adapter with `subprocess.run`
stubbed (a 600 s command: raises `TimeoutExpired` only when `timeout < 600`) returns exit 0.

**Acceptance Scenarios**:

1. **Given** `check_timeout_seconds = 900`, **When** a 600 s check runs, **Then** it passes
   (exit 0) and its record is exit 0.
2. **Given** no `check_timeout_seconds`, **When** a check runs, **Then** the limit is 300 s,
   as today.

### User Story 2 - the error says what to change (Priority: P1)

A check runs past its limit. The reason the owner sees names the command, the limit and the
setting, and what to do.

**Independent Test**: the local adapter with `subprocess.run` stubbed to raise
`TimeoutExpired`.

**Acceptance Scenarios**:

1. **Given** a check that takes longer than the configured limit, **When** it runs, **Then**
   the result is exit 2 and the reason is exactly
   ``fast check `<cmd>` exceeded <limit> s (repos.<n>.check_timeout_seconds); raise it with
   bin/wuwei config set or split the check``, with the command and the limit filled in.
2. **Given** any other run failure (missing shell, empty command), **Then** the reason is
   unchanged (`fast check could not run: <ExceptionName>`).

### User Story 3 - calibration proposes the limit (Priority: P2)

`bin/wuwei calibrate --measure` runs each detected test runner once. When a run takes at least
80 % of the repository's limit, or times out, the config proposal adds
`check_timeout_seconds = <twice the limit>` for that repository, and the report's note on
the check says it was near the limit.

**Independent Test**: `main('calibrate', '--measure')` with the fake checks port and the
monotonic clock stubbed, as the existing measure tests do.

**Acceptance Scenarios**:

1. **Given** a repository with no `check_timeout_seconds` and a measured run of 290 s,
   **When** `calibrate --measure` runs, **Then** the proposed diff adds
   `check_timeout_seconds = 600` under that repository.
2. **Given** a measured run of 75 s, **Then** no `check_timeout_seconds` is proposed.
3. **Given** the runner is called, **Then** it receives the repository's limit as `timeout`.

### Edge Cases

- `check_timeout_seconds = 0` or negative: refused by config validation (minimum 1), like
  every other `*_seconds` key.
- A repository that already sets `check_timeout_seconds` and still runs near it: the report
  lists it under "config differs; edit by hand" (existing `proposal` behaviour for a present
  key); calibration never rewrites an owner value.
- Several commands in one repository: one limit per command run (the setting is per
  repository, applied to each command), and calibration proposes from the slowest run.
- Calibration without `--measure`: nothing runs, nothing is proposed (unchanged).
- The none checks adapter: takes the new parameter and stays unmeasured (unchanged).

## Requirements

### Functional Requirements

- **FR-001**: The `repos` config schema has `check_timeout_seconds`, an integer, default 300,
  minimum 1.
- **FR-002**: The checks port operation is `run(path, command, timeout, root)`; the local
  adapter passes `timeout` to the process; the none adapter accepts and ignores it.
- **FR-003**: `fast_checks.record`, `calibrate.survey` (through `classify`) and
  `worktree add`'s bootstrap pass the repository's `check_timeout_seconds` to the port.
- **FR-004**: A timed-out check returns exit 2 with the reason in User Story 2 scenario 1.
- **FR-005**: `calibrate --measure` proposes `repos.<i>.check_timeout_seconds = 2 * limit`
  when the slowest measured run of the repository took at least 80 % of its limit, through
  the existing additive `proposal`; the near-limit check's report note says so.
- **FR-006**: `docs/site/configuration.md` documents `repos.check_timeout_seconds` and the
  calibration proposal, and no longer says the measure run is capped at a fixed 300 seconds.

### Key Entities

- **`repos.<n>.check_timeout_seconds`**: integer seconds, default 300, minimum 1; the limit
  for one run of one check command in that repository.

## Success Criteria

- **SC-001**: With `check_timeout_seconds = 900`, a 600 s check records exit 0.
- **SC-002**: A timed-out check's reason contains the command, the limit and
  `repos.<n>.check_timeout_seconds`.
- **SC-003**: A measured run of at least 80 % of the limit yields a config proposal raising
  the limit; a short run yields none.
- **SC-004**: With no new key set, every existing check behaves as before (300 s).

## Assumptions

- The orchestrator notes file named for this issue (`notes/724-full.md`) does not exist; the
  issue text is the whole input. No dry-run workspace was named, so the failure was reproduced
  in process against the adapter with `subprocess.run` stubbed.
- The workflow harness relayed an owner request about another item (item 63: owner commands
  depend on the current folder). This feature is issue #724 (item 50) only; item 63 is a
  separate issue and not part of this feature.
- "Measures the first run" means the existing `calibrate --measure` run (and
  `config promote --measure`, which measures again); no new measurement is added to
  `fast-checks` or `build check`.
- "Near the limit" is 80 % and the proposal is twice the limit; both are constants in
  `calibrate.py`, not config (constitution V: no config for a value that never changes).
- The proposal is made whether or not the command ends up a fast check: the limit also
  governs `repos.tests` and owner-set checks, and a CI-only runner that is near the limit
  will hit it when the owner adds it.
- The design spec (`docs/specs/2026-09-24-wuwei-design.md`) has no checks port signature or
  300 s figure to amend; only the owner docs change.
- The command in the message is the one the port ran; for a check whose interpreter
  `fast_checks.record` rewrote (#520), that is the rewritten command.
