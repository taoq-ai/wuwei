# Tasks: a gate never edits a written verdict, each seat has its own scratch folder, and Codex jobs are not seats

## Phase 1: Evidence first

- [x] T001 Baseline suite on main: 462 passed
- [x] T002 Read `hook._verdict_problem` and `verdict.FORMAT` for the words to reuse

## Phase 2: Charters and docs

- [x] T003 [US2] `charters/_gate.md`: never edit a written verdict; next free `-2.md` (FR-001)
- [x] T004 `charters/_common.md`: scratch files under `<scratchpad>/<role>-<item>/` (FR-002)
- [x] T005 [US4] `charters/planner.md`: routes differential, attestation, codex-companion limit (FR-003)
- [x] T006 [US3] `docs/site/reference.md` verdict format as FORMAT (FR-004)
- [x] T007 [US4] `docs/site/concepts/codex.md` "Gates on Codex" (FR-004)

## Phase 3: Build and checks

- [x] T008 [US1] Drift tests red in a scratch copy with `agents/builder.md` held at main
- [x] T009 [US1] `bin/wuwei agents build` and `setup.vendor('.')` (FR-005)
- [x] T010 Full suite green; no file under `cli/` changed
- [x] T011 No emojis and no em dashes in the diff
