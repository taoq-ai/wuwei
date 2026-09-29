# Tasks: PR ownership loop

## Setup

- [X] T001 Read dependencies and create spec and plan in specs/120-pr-ownership/.

## US1: Fresh state and dispatch

- [X] T002 [US1] Write and run failing classification, dispatch, config and CLI tests in tests/test_pr_ownership.py.
- [X] T003 [US1] Implement fresh evidence classification and CLI in cli/wuwei/pr_actions.py, cli/wuwei/commands/pr.py and cli/wuwei/watch.py; document config in cli/wuwei/workspace.py and docs/site/configuration.md.

## US2: Deadlines, wake and Stop

- [X] T004 [US2] Write and run failing deadline, transition, signal, parking and Stop tests in tests/test_pr_ownership.py; migrate placeholder scenarios in tests/test_stop.py.
- [X] T005 [US2] Implement persistent action production, poll integration and Stop consumption in cli/wuwei/pr_actions.py and cli/wuwei/watch.py; classify events in cli/wuwei/signal.py.

## US3: Trusted state and body files

- [X] T006 [US3] Write and run failing reserved-event and body-file marker tests in tests/test_pr_ownership.py.
- [X] T007 [US3] Reserve events in cli/wuwei/commands/event.py and extend the shared body reader in cli/wuwei/security.py.

## Verification

- [X] T008 Run full pytest suite, review diff and hygiene, and finalize specs/120-pr-ownership/tasks.md.

## Dependencies and execution

T002 precedes T003, T004 precedes T005, T006 precedes T007. Execute slices sequentially
because they share the action producer. US1 is the smallest independently testable increment.
US3 could be developed independently, but no parallel agents are needed. T008 follows all slices.

## Verification result

Initial suite: 4351 passed, 3 skipped in 86.30s (0:01:26). The three skips were host-load
latency checks. Subsequent adversarial review identified F1, F2 and F3 below.

## Adversarial review fixes

- [X] T009 [US3] Reproduce F1 through PreToolUse with quoted and escaped disposition markers, then reject markers in parsed gh arguments in cli/wuwei/security.py.
- [X] T010 [US1] Reproduce F2 through classification and polling, then classify startup_failure as ci_red in cli/wuwei/pr_actions.py.
- [X] T011 [US2] Reproduce F3 with a changed head and unknown mergeability, then preserve the fresh snapshot and wake while reporting exit 2 in cli/wuwei/watch.py.
- [X] T012 Run the full suite with the pipeline interpreter and inspect the final diff. Leave changes uncommitted.

Each regression in tests/test_pr_ownership.py failed before its corresponding fix and
passed after it. Full suite with `python -m pytest -q`:
4359 passed, 3 skipped in 60.98s (0:01:00). The three skips are host-load latency checks.
Diff whitespace check passed. Changes remain uncommitted.

## Delta review fixes

- [X] T013 Fix H1 by replacing the local interpreter path with `python -m pytest -q`.
- [X] T014 Reproduce F4 through PreToolUse, then limit argv disposition checks to text writes; let the PR guard handle Bash markers and reuse API method/field parsing.
- [X] T015 Run the full suite and scan all authored files for local paths; leave changes uncommitted.

F4 regression table before the fix: 3 failed, 22 passed. After the fix, all 96 PR ownership
tests passed. Full suite with `python -m pytest -q`: 4384 passed, 3 skipped in 47.45s.
The three skips are host-load latency checks. Local-path scan of all 20 authored files
and diff whitespace check passed. Changes remain uncommitted.

## Security regression fix

- [X] T016 Reproduce F5 through PreToolUse, then exempt raw Bash disposition markers only when every normalized command is gh; preserve read-only searches and refuse non-gh and mixed scripts.
- [X] T017 Run the full suite with the pipeline interpreter and inspect the diff; leave changes uncommitted.

F5 regression table before the fix: 7 failed, 26 passed. After the fix, all 104 PR ownership
tests passed. Full suite with the pipeline interpreter and `python -m pytest -q`:
4392 passed, 3 skipped in 42.71s. The three skips are host-load latency checks.
Diff whitespace check passed. Changes remain uncommitted.
