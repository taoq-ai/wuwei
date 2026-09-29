# Tasks: Prompt canary and honeytoken

## Setup

- [X] T001 Read repository rules and integration paths; create spec and plan in specs/105-canary/.

## US1: Workspace instruction markers

- [X] T002 [US1] Add failing init, path, generation and protection tests in tests/test_canary.py.
- [X] T003 [US1] Implement security material and workspace generation in cli/wuwei/security.py, commands/init.py, commands/agents.py and guards/protect_state.py.
- [X] T004 [US1] Test seat instruction selection in tests/test_canary.py before integrating cli/wuwei/brief.py and adapters/runtime/.

## US2: Outbound refusal

- [X] T005 [US2] Add failing lint, guard, port, reservation and failure tests in tests/test_canary.py.
- [X] T006 [US2] Integrate security before outward policy in cli/wuwei/outward.py and reserve producers in state.py and commands/event.py.

## US3: Trace detection and redaction

- [X] T007 [US3] Add failing fetched-content, decoy-read, redaction, scope and error tests in tests/test_canary.py.
- [X] T008 [US3] Integrate detection and recursive redaction in cli/wuwei/guards/traces.py using cli/wuwei/security.py.

## Verification

- [X] T009 Review scope, trust, error paths and generated-file hygiene; run full pytest and record results in specs/105-canary/tasks.md.

## Review fixes

- [X] T010 [F1] Add failing override-refresh tests for briefs and upgrade, then regenerate secured workspace instructions on both paths while preserving dry-run behavior and markers.
- [X] T011 [F2] Add failing response-detection tests for Python, security.json and MCP reads, then detect honeytokens in every tool response while retaining path-based detection.

## Post-rebase review fixes

- [X] T012 [F1] Retarget canary tests to check_call and check_tier under both profiles, assert exactly one redacted page, check both guards outside workspace scope, and derive generated files from source charters and skills.
- [X] T013 [F2] Document security.required and missing-material fail-closed behavior in docs/site/configuration.md.
- [X] T014 [F3] Reproduce duplicate literal gh pages at the hook boundary under both profiles, then leave gh_outbound responsible only for file-backed bodies; verify both forms page once.
- [X] T015 [F4] Reproduce init through a symlinked parent, then compare honeytoken and generated-instruction paths against the resolved workspace directory; verify security loads through the unresolved root.

## Dependencies and execution

Execute T001 through T009 in order. Each test task must fail for the intended
missing behavior before its implementation. Implementation is sequential; an independent agent reviews the completed changes.
US1 supplies material used by US2 and US3. US2 and US3 can be validated independently
after US1. The full issue, not a partial MVP, is the delivery target.

## Verification evidence

- Tests were written and observed failing before each behavior was implemented.
- Independent security review and its delta review were completed. Regression
  tests cover shell comment bodies, API-mode ambiguity, instruction-read alerts,
  read aliases, input redirection and sibling subshell directory handling.
- Final full suite with the task-specified interpreter:
  `3839 passed, 3 skipped in 33.23s`.
- Review fixes F1 and F2 each had failing regressions before implementation;
  all 72 canary tests pass, including the five new regression cases.
- The three skipped checks are the existing load-sensitive latency benchmarks.
- `git diff --check` and changed-file typography/local-path checks passed.
- Changes remain in the working tree; no commit, push or gh command was run.
- Post-rebase review: reproduced the ten canary/documentation failures, then
  observed the new hook regression fail on duplicate pages in both profiles and
  the new symlinked-parent init regression fail before correcting runtime code.
- Post-rebase targeted suite: `84 passed in 1.07s`. Full suite with the
  task-specified interpreter: `3952 passed, 2 skipped in 39.88s`.
  The two skips were the existing load-sensitive latency benchmarks.
