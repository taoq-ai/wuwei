# Feature Specification: the reference-adapter replay test is isolated under the parallel run

**Feature Branch**: `776-replay-isolation`

**Created**: 2026-10-10

**Status**: Draft

**Input**: GitHub issue #776: since #685 (parallel suite) the 3.11 job fails on
`tests/test_reference_adapters.py::test_linear_replay` about one run in four with no related
change in the PR, and the test passes locally every time. Find the shared state, isolate it,
keep every assertion, and record the cause in one line in the test.

## Root cause (read on main at f2567cb, reproduced read-only)

The shared state is a process-wide memo in the Linear tracker adapter, not a recording path
or a port:

1. `adapters/tracker/linear.py:8` declares `_state_ids = {}`, a module-level map from a
   Linear team id to its workflow state names. `transition` (`linear.py:62`) queries
   `workflowStates` only when the team is not already in the map and stores the result at
   `linear.py:74`. Every test in one xdist worker shares this one dict.
2. `tests/test_linear_loop.py:41` (`test_linear_transition_resolves_team_state_once`) calls
   `linear._state_ids.clear()` and then fills `_state_ids['team-1']`, and never restores it.
   `tests/test_linear_loop.py:59` (`test_linear_transition_resolves_name_starting_with_state`)
   clears the map again and leaves only `team-2`.
3. `tests/test_reference_adapters.py:69` (`test_linear_replay`) replays six recorded
   responses in a fixed order that assumes the map is empty: the fourth is the
   `workflowStates` page for `team-1`. When `team-1` is already in the map, `transition`
   skips that query, the `workflowStates` payload is handed to `_updated`, which reads
   `['issueUpdate']`, and the call returns `exit=2, reason='linear.transition: could not run:
   KeyError'`; the assertion at `tests/test_reference_adapters.py:78` fails.
4. In a serial run the files run in name order, so the second loop test clears `team-1`
   before `test_linear_replay` runs and the suite passes every time. Under
   `-n auto --dist loadgroup` (`.github/workflows/tests.yml:27`) the two loop tests and the
   replay test are spread across workers; when the worker that runs `test_linear_replay`
   ran the first loop test but not the second, it fails. That is the one run in four.

`test_linear_replay` is also a writer: it leaves `team-1` in the map after it passes, so any
later test in the same worker that replays a `workflowStates` page for `team-1` would fail
the same way. `tests/test_tracker_adapters.py:86-87` already isolates the memo with
`monkeypatch.setattr(adapter, '_state_ids', {})`, which pytest restores after the test.

Reproduction (one process, no xdist, deterministic):

```
python -m pytest -q -p no:xdist \
  tests/test_linear_loop.py::test_linear_transition_resolves_team_state_once \
  tests/test_reference_adapters.py::test_linear_replay
```

gives `1 failed, 1 passed` with the `KeyError` above. Both files together in name order pass
(`56 passed`).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Isolate with the `xdist_group` marker? A: No. The tests do not need to share a worker;
  they need not to share the memo. A group would hide the leak and slow the run.
- Q: Clear the memo in the adapter, or drop it? A: No. The memo is production behaviour
  (one `workflowStates` read per team per process) with its own test
  (`test_linear_transition_resolves_team_state_once`). Only tests change.
- Q: A conftest autouse fixture that resets the memo for every test? A: No. Three tests
  touch the memo through real `transition` calls; each isolating itself with the idiom
  `tests/test_tracker_adapters.py:87` already uses is a smaller diff than a fixture that
  imports the Linear adapter into every test of the suite.
- Q: Which tests change? A: `test_linear_replay` (the victim, also a writer) and the two
  loop tests (the writers that leak today). Each replaces the memo with an empty dict
  through `monkeypatch`, so pytest restores the original after the test.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The replay test passes whatever ran before it in its worker (Priority: P1)

A contributor opens a pull request with no change near the Linear adapter. The parallel CI
job runs the suite and `test_linear_replay` passes on whichever worker it lands, so the
contributor never re-runs a red job that their change did not cause.

**Why this priority**: a flaky required job costs every pull request a re-run and trains
people to ignore red.

**Independent Test**: run the memo-filling loop test and then `test_linear_replay` in one
process; the replay test passes.

**Acceptance Scenarios**:

1. **Given** a worker that already ran
   `test_linear_transition_resolves_team_state_once` (so the Linear state memo holds
   `team-1`), **When** `test_linear_replay` runs next in that worker, **Then** it passes with
   the same six recorded calls and the same assertions as today.
2. **Given** the suite, **When** CI runs it in parallel ten consecutive times
   (`-n auto --dist loadgroup`), **Then** `test_linear_replay` passes every time and its
   assertion set is unchanged.

### User Story 2 - Tests that fill the memo leave it as they found it (Priority: P2)

A contributor adds a new Linear replay test. Tests that call the real `transition` do not
leave team states behind, so the new test does not inherit a memo from an unrelated file.

**Why this priority**: removes the root cause for the next test, not only this one.

**Independent Test**: run one of the three tests and then `test_linear_replay` in one
process; the replay test passes, and running the loop test first no longer reproduces the
failure even before the replay test isolates itself.

**Acceptance Scenarios**:

1. **Given** `test_linear_transition_resolves_team_state_once`,
   `test_linear_transition_resolves_name_starting_with_state` or `test_linear_replay` has
   run, **When** the next test in that worker reads `linear._state_ids`, **Then** it is the
   same dict with the same contents as before the test ran.
2. **Given** the two loop tests, **When** they run, **Then** their existing assertions still
   hold (the team's states are read once across two transitions; a state name starting
   with `state` resolves).

### Edge Cases

- The memo already holds a different team (`team-2`) when `test_linear_replay` runs: the
  replay starts from an empty memo and passes.
- `test_linear_replay` runs twice in one worker (a rerun plugin or a retry): the second run
  starts from an empty memo and passes.
- `tests/test_tracker_adapters.py::test_tracker_port_contract[linear]` already isolates the
  memo and stays unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `test_linear_replay` MUST run against an empty Linear state memo regardless of
  what ran before it in its process, and MUST leave the memo as it found it.
- **FR-002**: `test_linear_replay` MUST keep its assertion set unchanged: the same six
  recorded responses in the same order, the same `exit == 0` checks on `claim`, `transition`
  and `history`, and the same history data, call count, URL, credential header and
  variables assertions.
- **FR-003**: `test_linear_replay` MUST carry a one-line comment naming the cause (the
  process-wide `_state_ids` memo in the Linear adapter, shared by the tests in one worker)
  and this issue number.
- **FR-004**: The two tests in `tests/test_linear_loop.py` that call the real `transition`
  MUST start from an empty memo and restore the original memo after they run, with their
  assertions unchanged.
- **FR-005**: No production code changes: `adapters/tracker/linear.py` keeps its memo and
  its behaviour.
- **FR-006**: No `xdist_group` marker and no change to `pyproject.toml`, `tests/conftest.py`
  or the CI workflow.

### Key Entities

- **Linear state memo**: `adapters/tracker/linear.py` `_state_ids`, team id to
  `{state name: state id}`, one per process.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The reproduction command above passes (`2 passed`) after the change and fails
  before it.
- **SC-002**: Ten consecutive parallel CI runs pass `test_linear_replay`.
- **SC-003**: The full suite passes with `python -m pytest -q` and with
  `python -m pytest -q -n auto --dist loadgroup`.
- **SC-004**: The diff touches only `tests/test_reference_adapters.py` and
  `tests/test_linear_loop.py` (plus this feature directory) and removes no assertion.

## Assumptions

- No orchestrator notes exist for #776 (`notes/776-full.md` is absent); the spec follows the
  issue text and the reproduction above.
- The memo is the only shared state behind the flake: the other adapters the replay file
  exercises (`adapters/_http.py`, `adapters/chat/slack.py`, `adapters/review_bot/greptile.py`,
  `adapters/inbound/slack.py`) hold no module-level cache, the recordings are read once into
  a module constant that no test writes, and `tests/conftest.py` already clears the
  environment variables the replay tests read.
- The "one run in four" rate is the chance that xdist places the first loop test and
  `test_linear_replay` on the same worker without the second loop test between them; the
  exact rate is not measured and does not change the fix.
- SC-002 is verified on CI after merge; locally the deterministic reproduction stands in for
  it.
- The constitution's guard-invariant rule does not apply: no guard or decision rule changes.
