# Tasks: models-table

## Phase 1: Tests first

- [x] T001 [US1] Table row per allowlisted seat with a model and an effort; lookups on Haiku 5.5 low
- [x] T002 [US1] Ladder, Opus 5.5 max fallback, diversity rule, precedence order, effort variable, `Model reason:`
- [x] T003 [US2] Every source on the models page links a document and a read date
- [x] T004 [US3] `team.md`, `codex.md` and `design.md` section 3 link the table and name no `MODELS`; `codex.md` says unmeasured
- [x] T005 [US4] Steward reads by seat, model and effort; the watch skill offers Sonnet 5.5 medium, not a default
- [x] T006 [US3] Codex mapping per step, unmeasured, not OpenAI guidance, `ultra` named
- [x] T007 Red run: `6 failed, 79 passed` on `git archive origin/main` with the head's test file

## Phase 2: Text

- [x] T008 [US1] `charters/planner.md` "Model and effort"
- [x] T009 [US2] `docs/site/concepts/models.md`, `mkdocs.yml` nav, `docs/site/concepts/index.md` row
- [x] T010 [US3] `team.md`, `codex.md`, `docs/design.md` section 3
- [x] T011 [US4] `charters/steward.md` rule 6, `skills/wuwei-watch/SKILL.md`
- [x] T012 [US3] Codex facts re-read at openai/codex 8c07694 and the mapping added

## Phase 3: Build

- [x] T013 `bin/wuwei agents build`; `setup.vendor('.')`
- [x] T014 Full suite: `pytest -q` gives `1690 passed, 2 skipped`; runtime 2,976 lines
