# Feature Specification: Scripted delivery day

**Feature Branch**: `037-e2e-day`
**Created**: 2026-09-29
**Status**: Draft
**Input**: Issue #37, test(e2e): scripted day with record-and-replay adapters

## User Scenarios & Testing

### User Story 1: Replay a delivery day on every PR (Priority: P1)

A maintainer runs the default test suite and gets deterministic evidence that the
planner, seats, gates, shepherd and close guards work together without external services.

**Independent Test**: Run the scripted day test with pytest.

**Acceptance Scenarios**:

1. Given a temporary workspace and demo repository, when a plan is proposed and
   approved, then ranking and the morning gate precede build seat launch.
2. Given a stopped builder, when sentinels produce verdicts, then one quality FIX
   triggers one fix round and only its delta gate before PR raise.
3. Given a raised PR, when recorded review evidence changes, then shepherding
   observes the changes and close refuses outstanding work until it is settled.
4. Given captured seat retros, when retro and report run and obligations are clear,
   then the planner Stop guard permits close.
5. Given an agent-surface item without ZIRAN, when its security gate is received,
   then exit 2 reports unmeasured and no trusted PASS is recorded.
6. Given owner-confirmed plugin content, when a new unconfirmed fingerprint is
   measured, then PreToolUse denies even an otherwise harmless tool call.

### Edge Cases

- Premature gate, raise and close attempts must fail without fabricating evidence.
- Unrelated shell syntax remains allowed with healthy integrity evidence.
- External network or tool execution must fail the test instead of escaping replay.

## Requirements

- **FR-001**: Exercise existing plan, rank, build, dispatch, verdict, PR, retro,
  report and Stop producers and guards in process wherever possible.
- **FR-002**: Use existing fake adapters and code-host recordings, with scripted
  seats writing briefs, verdicts, transcripts and retro artifacts as real seats do.
- **FR-003**: Keep workspace and demo repository under pytest tmp_path. Git runs
  only through the VCS adapter. No network, real gh, model runtime or ZIRAN.
- **FR-004**: Assert structured events, state, files and exit codes, never model prose.
- **FR-005**: Collect in the default pytest suite on every PR; target under 20 seconds.
- **FR-006**: Preserve fail-closed integrity and scanner boundaries, without mocking guards.

## Success Criteria

- **SC-001**: The scripted day passes in the existing PR CI pytest job.
- **SC-002**: The scripted day completes in under 20 seconds on the development test run.
- **SC-003**: Exactly one fix round and one delta review appear in measured state/events.
- **SC-004**: The full suite passes without new skips or expected failures unless a named
  upstream gap makes a step impossible.

## Assumptions

- In-process CLI main calls are appropriate for orchestration; subprocess CLI calls,
  if needed, use sys.executable with -P. Existing smoke tests cover CLI bootstrapping.
- The ordinary day changes a source file; the no-ZIRAN agent-surface case is a separate
  fail-closed scenario because an unmeasured gate cannot legitimately raise a PR.
- Scripted owner confirmations and recorded code-host updates are test inputs, not
  new runtime trust anchors. The test does not send messages or create remote PRs.
- Existing VCS workspace history operations can initialize the local demo repository;
  recorded VCS responses supply remote and review metadata unavailable offline.
  Demo source lives at memory/demo.py to reuse the existing writer allowlist.
- Merge completion is a scripted code-host observation; automatic merge policy and
  remote branch pushes remain covered by their existing adapter contract tests.

## Deferred

None identified during specification.
