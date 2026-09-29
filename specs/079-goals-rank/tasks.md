# Tasks: Goals, discovery and rank

## Goal format and protection

- [X] T001 [US1] Add failing goal parser and guard tests in tests/test_goals_rank.py
- [X] T002 [US1] Implement goal parser and guard protection in cli/wuwei/goals.py and cli/wuwei/guards/protect_state.py

## Ranking and plan lint

- [X] T003 [US1] Add failing rank, CLI and plan lint tests in tests/test_goals_rank.py
- [X] T004 [US1] Implement rank, command and plan lint in cli/wuwei/rank.py, cli/wuwei/commands/rank.py and cli/wuwei/plan.py

## Discovery and autostart

- [X] T005 [US2] Add failing discovery and source measurement tests in tests/test_goals_rank.py
- [X] T006 [US2] Implement discovery and command in cli/wuwei/discovery.py and cli/wuwei/commands/discover.py
- [X] T007 [US3] Add failing autostart tests in tests/test_goals_rank.py
- [X] T008 [US3] Implement autostart decision in cli/wuwei/discovery.py

## Integration

- [X] T009 [US2] Add failing morning and sweep integration tests in tests/test_goals_rank.py
- [X] T010 [US2] Wire discovery into cli/wuwei/plan.py and cli/wuwei/watch.py
- [X] T011 Run existing config documentation test in tests/test_docs.py against new keys
- [X] T012 Add config keys and documentation in cli/wuwei/workspace.py, templates/workspace/config.toml and docs/site/configuration.md
- [X] T013 Run full pytest and scan changed files for em-dashes, emojis and absolute paths
