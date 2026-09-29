# Tasks: Shepherd PR flow

## Reviewer selection and raise

- [X] T001 [US1] Write failing reviewer ladder and two-author raise tests in tests/test_shepherd.py
- [X] T002 [US1] Add authorship VCS port and adapter in cli/wuwei/registry.py and adapters/vcs/git.py
- [X] T003 [US1] Implement reviewer selection and PR raise in cli/wuwei/shepherd.py and cli/wuwei/commands/pr.py

## Ping gate and channel post

- [X] T004 [US2] Write failing production ping refusal tests in tests/test_shepherd.py
- [X] T005 [US2] Implement fresh ping gate and channel post in cli/wuwei/shepherd.py and cli/wuwei/commands/pr.py
- [X] T006 [US2] Reserve post state and event kinds in cli/wuwei/state.py and cli/wuwei/commands/event.py

## Replies and ownership actions

- [X] T007 [US3] Write failing thread last-word and ownership dispatch tests in tests/test_shepherd.py
- [X] T008 [US3] Extend reply handling in cli/wuwei/obligations.py and cli/wuwei/commands/reply.py
- [X] T009 [US3] Execute supported PR ownership actions through cli/wuwei/pr_actions.py and cli/wuwei/commands/pr.py

## Verification

- [X] T010 Run the full pytest suite and check changed files for prohibited characters
