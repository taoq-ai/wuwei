# Tasks: Agent generation from charters

## Foundation

- [X] T001 Read issue #19 charters, design, constitution and CLI patterns; write `specs/020-agent-generation/spec.md` and `plan.md`.

## US1: Build role agents

- [X] T002 [US1] Write failing `tests/test_agents.py` for nine generated agents, complete explicit tool lists, shared body order and atomic build; run red.
- [X] T003 [US1] Add `agents/allowlist.json` and role rationale in `agents/README.md`.
- [X] T004 [US1] Implement `wuwei agents build` in `cli/wuwei/commands/agents.py` using the shared atomic writer; generate `agents/<role>.md`.

## US2: Detect drift

- [X] T005 [US2] Write failing `tests/test_agents.py` for clean, changed, missing and extra files, and unreadable or malformed sources; run red.
- [X] T006 [US2] Implement `wuwei agents check` and a golden pytest assertion against checked-in agents.

## Verification

- [X] T007 Run the full requested pytest suite, scan authored files for em dashes and emoji, and inspect the diff.

## Dependencies

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007.

## Verification results

- Build test red: import failed because the agents command did not exist.
- Drift golden test red: all nine generated role files were absent.
- Version-only drift test red: stripped frontmatter hid a charter version edit.
- Focused agent suite: 10 passed.
- Full suite: 2917 passed in 30.46s with the requested interpreter.
- `bin/wuwei agents check` returned 0 after generation.
