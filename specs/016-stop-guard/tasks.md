# Tasks: day-close Stop guard

## Setup

- [X] T001 Read source harness, spec and reused code; write specs/016-stop-guard/spec.md and plan.md.

## US1: retro and close evidence

- [X] T002 [US1] Write failing source P7 and retro tables in tests/test_stop.py.
- [X] T003 [US1] Write failing history and merged evidence contracts in tests/test_vcs.py, tests/test_code_host.py and tests/test_adapters.py.
- [X] T004 [US1] Extend adapters/vcs/git.py, adapters/code_host/github.py, cli/wuwei/registry.py and tests/fakes/vcs.py.
- [X] T005 [US1] Implement ordered checks in cli/wuwei/closing.py and config in cli/wuwei/workspace.py.

## US2: owned PR anchor

- [X] T006 [US2] Write failing action deadlines and disposition verification tests in tests/test_stop.py.
- [X] T007 [US2] Add action consumer and verified disposition producer in cli/wuwei/pr_actions.py and cli/wuwei/commands/pr.py; defer action production to #120.

## US3: scoped Stop and close entry point

- [X] T008 [US3] Write failing guard/CLI, retry, scope, mutation and reserved-writer tests in tests/test_stop.py.
- [X] T009 [US3] Implement cli/wuwei/guards/stop.py and cli/wuwei/commands/close.py; reserve producer namespaces in cli/wuwei/state.py and cli/wuwei/commands/event.py.

## Verification

- [X] T010 Confirm and fix initial review regressions in tests/test_stop.py, cli/wuwei/closing.py, cli/wuwei/pr_actions.py and cli/wuwei/guards/stop.py.

- [X] T011 Run full pytest suite; inspect changed files for hygiene; finish specs/016-stop-guard/tasks.md.

## Adversarial review fix round

- [X] T012 [F1] Require owner-routed decisions without seat outcomes and refuse raw disposition markers across all PreToolUse tools. Regress Bash comment/API calls and Write/Edit body files before implementation.
- [X] T013 [F2] Remove synthetic watch actions and cross-day action inheritance. Missing actions allow turn end; explicit overdue actions and close dispositions remain enforced. Regress waiting and midnight cases before implementation.
- [X] T014 [F3] Remove consolidation checks, CLI option, baseline config and initial-commit traversal. Regress close without a Git repository before implementation.
- [X] T015 [F4] Use the shipped memory changelog path. Fail default-config and landed-retro tests before implementation.
- [X] T016 [F5] Preserve Git-returned paths containing wildcard characters or leading hyphens. Regress recorded Git output before implementation.
- [X] T017 [F6] Remove the speculative day_close payload flag. Regress ignored payload flags and persistent close requests before implementation.
- [X] T018 Run the requested full pytest command and inspect the final diff after all six fixes.

## Dependencies and strategy

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010 -> T011.
US1 is independently testable with fake vcs evidence; US2 with fake code-host evidence;
US3 integrates both. Execute serially to keep failing-first evidence clear. No parallel
agents needed. MVP is US1; complete all three stories for issue acceptance.

## Initial evidence (superseded by this fix round)

- Full suite: 4042 passed, 3 skipped in 38.57s. Three timing checks skipped under host load.
- Source P7, acceptance refusals, ports, scope, retries, forged dispositions and planner handoff covered.
- A later adversarial review raised F1 through F6, addressed in T012 through T017.
- Diff whitespace, changed-file characters and new absolute machine paths: clean.

## Fix-round evidence

- F1 through F6: each regression failed before its fix and passed afterward.
- Requested interpreter, full suite: 4057 passed, 3 skipped in 38.45s. Three timing checks skipped under host load.
- Final diff whitespace and new-file style checks passed. Changes remain uncommitted.
