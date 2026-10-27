# Tasks

## Setup

- [x] T001 Read approved item, policy, local catalog and schema; record decisions in specs/1261-codex-model-policy/research.md.

## US1: role defaults

- [x] T002 [US1] Add failing generated-role, override and doctor tests in tests/test_codex.py and tests/test_models.py.
- [x] T003 [US1] Generate mapped defaults with owner/tier precedence in cli/wuwei/agents.py and cli/wuwei/setup.py; run focused tests green.

## US2: dispatch visibility

- [x] T004 [US2] Rebase onto pushed 1254 and add failing native metadata/report tests in tests/test_models.py.
- [x] T005 [US2] Preserve resolution and requested fork policy in cli/wuwei/hook.py and expose labels in cli/wuwei/report.py; run focused tests green.

## Verification

- [ ] T006 Update docs/site/concepts/models.md and docs/site/concepts/codex.md; regenerate vendor copies through cli/wuwei/setup.py.
- [ ] T007 Run focused and serialized full checks, runtime count and routes; record evidence in specs/1261-codex-model-policy/analysis.md and PR body.

Dependencies: T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007. No parallel agents: hook ownership is serialized after 1254. US1 is the MVP; US2 completes the approved promise.
