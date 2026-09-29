# Tasks: Workspace credentials

## Setup

- [X] T001 Reproduce dry-run evidence read-only and inspect existing entry points.
- [X] T002 Write spec.md, plan.md and reviewed requirements checklist.

## US1: Workspace authentication

- [X] T003 Write and run failing loader, Linear authentication, redaction, entry-point
  and provisioning tests in tests/test_env_credentials.py.
- [X] T004 Implement validated loading and provisioning in cli/wuwei/env.py,
  __main__.py, commands/hook.py and commands/init.py.
- [X] T005 Extend cli/wuwei/redact.py and state.py to remove loaded values from output
  and persisted events/traces, then pass US1 tests.

## US2: Credential diagnostics

- [X] T006 Write and run failing credential matrix and GitHub auth tests in
  tests/test_env_credentials.py.
- [X] T007 Implement config report, GitHub auth operation and registry contract;
  adapt existing workspace tests to fake auth.

## Polish

- [X] T008 Document credentials in docs/site/adapters.md and configuration.md.
- [X] T009 Run full pytest suite, inspect scope/security and repository hygiene,
  and record results in tasks.md.

## Review fixes

- [X] T010 Reproduce and fix protected env mutations using the shared state guard.
- [X] T011 Reproduce and fix hook credentials under a legacy workspace override.
- [X] T012 Complete one delta review; no unresolved blockers.
- [X] T013 Reproduce F1 credential inheritance in real Codex dispatch and fast-check
  subprocesses, then filter loaded names and known credentials at both boundaries
  while preserving ordinary environment variables and the fast-check GIT_ strip.
- [X] T014 Run the full pytest suite after F1 and record the result.

## Dependencies and Strategy

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009.
Run sequentially because entry points, diagnostics and redaction share state.
Independent read-only inspections can run together. Deliver file loading first,
then diagnostics, followed by the full regression suite. No commits or pushes.

## Validation Results

- First US1 run: 15 failures showing missing loading, provisioning and redaction.
- First US2 run: 11 failures showing absent credential and authentication diagnostics.
- Review regressions failed before fixes for env mutations and legacy overrides.
- Targeted final scope, hook and credential run: 739 passed.
- Final full suite: 5279 passed, 5 skipped in 104.47s (0:01:44).
- Git whitespace check and changed-file path/style hygiene checks passed.
- One review fix round and delta review completed with no unresolved blockers.
- Shared scope/relevance and reserved-path protections retained; no new trusted
  state keys, event producers, dependencies or configuration keys were introduced.
- No commits, pushes or live external adapter calls were made.
- F1 regression run before the fix: both Codex and fast-check cases failed because
  the child inherited fixture credentials. After the fix: 47 targeted tests passed.
- Full suite after F1 with the requested pipeline interpreter:
  5284 passed, 2 skipped in 97.57s (0:01:37).
