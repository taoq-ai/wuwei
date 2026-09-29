# Tasks: Shepherd PR Actions

## Conflict resolution

- [X] T001 [US1] Write failing conflict step and completion tests in tests/test_pr_actions.py
- [X] T002 [US1] Implement guarded VCS rebase, checks, push and action recording in cli/wuwei/pr_actions.py and adapters/vcs/git.py

## Fix rounds

- [X] T003 [US2] Write failing CI and review fix tests in tests/test_pr_actions.py
- [X] T004 [US2] Implement feedback-driven build next fix rounds in cli/wuwei/pr_actions.py and cli/wuwei/commands/build.py

## Replies and decisions

- [X] T005 [US3] Write failing reply tier and decision tests in tests/test_pr_actions.py
- [X] T006 [US3] Implement replies and decisions in cli/wuwei/pr_actions.py

## Exit contract and verification

- [X] T007 Write failing unknown item CLI test in tests/test_build_next.py
- [X] T008 Correct unknown item exit in cli/wuwei/commands/build.py
- [X] T009 Run full pytest suite and inspect changed files

## Review fixes

- [X] T010 Require a PR-head lease for rebased pushes and distinguish rebase conflicts from refusals
- [X] T011 Require a composed review answer before sending or drafting a reply
- [X] T012 Reset the fix budget when a completed delta returns to raised
- [X] T013 Run the full pytest suite with deterministic promotion test dates
