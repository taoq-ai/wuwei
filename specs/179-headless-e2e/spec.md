# Feature Specification: Real Claude Code headless day

**Feature Branch**: `179-headless-e2e`
**Created**: 2026-09-29
**Status**: Draft
**Input**: Issue #179, design sections 5.2 and 10.

## User Scenarios & Testing

### US1: Exercise the installed plugin (P1)

As a maintainer, I need a bounded real headless day to detect broken seat launch
contracts and lifecycle wiring before release.

Acceptance scenarios:
1. Given valid credentials, the job builds and signs a scratch plugin, invokes the
   plan skill, runs one item through a real builder, gates and close, and passes
   only when recorded events, state and hook exits demonstrate completion.
2. Given broken seat launch or hook wiring, the job fails even if Claude says it
   succeeded.
3. Given expired OAuth, absent tools, timeouts or malformed evidence, the runner
   exits 2 with an explicit unmeasured reason. Expired OAuth names login recovery.

### US2: Skip predictably and run locally (P1)

1. Given no API key in CI, the job skips with a message and spends nothing.
2. Given a local Claude login, the owner can opt into the same bounded test using
   the documented command without an API key.

## Requirements

- FR-001: Use the built plugin in a scratch HOME and workspace; preserve the checkout.
- FR-002: Exercise the existing plan skill, shared launch prompt, step build loop,
  real subagent hooks, gate receipts, retro and day close.
- FR-003: Assert on structured workspace evidence and actual hook exits, never
  model prose. Missing evidence must fail.
- FR-004: Limit turns, dollar budget and wall time; do not retry paid sessions.
- FR-005: Keep ordinary pytest offline, with fakes for the external boundary and
  mutation coverage for missing launch/hook evidence.
- FR-006: Do not introduce trusted production state or workspace configuration.

## Success Criteria

- SC-001: A credentialed run completes within a five-minute session deadline and
  a three-dollar model budget, or reports a bounded failure.
- SC-002: Missing launch, stop, skill, gate or close evidence always fails validation.
- SC-003: An uncredentialed CI run reports its skip without invoking Claude.

## Assumptions

- Match skill-evals: paid CI runs only on pushes to main, never pull requests.
- The scripted owner approves a supplied one-item proposal. Discovery and the
  interactive morning questions are outside this test; the plan skill still runs.
- The item verifies the existing demo README and fast checks without changing
  tracked code. Three real sentinel seats exercise the pre-PR gates.
- Park the unpublished fixture item after gates. No remote PR, tracker or chat
  action is required; the offline scripted-day suite covers the PR lifecycle.
- Local OAuth credentials may be copied into the temporary HOME only with the
  explicit local-login option, and are deleted with that directory.

## Deferred

Remote PR creation, merge and fix rounds remain covered by the existing replay
suite. This issue adds no remote service fixtures or production policy changes.
