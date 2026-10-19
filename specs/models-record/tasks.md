# Tasks: agent files carry the table's model and effort, the hook advises on a departure and records what ran, and the report shows outcomes by model and effort

## Phase 1: Tests first

- [x] T001 [US1] Agent files carry the table's default model and effort; `MODELS` is gone (tests/test_models.py)
- [x] T002 [US1] `TABLE` equals the planner table at every tier on and off the paths (tests/test_models.py)
- [x] T003 [US2] A departure is advised with the table's setting and the reason line; a fit gets nothing (tests/test_models.py)
- [x] T004 [US2] Reason line, Haiku floor, owner rows, cached raise, `Item:` lines, both variables, Codex spawn (tests/test_models.py)
- [x] T005 [US3] `seat.started` and `attest` (joined by agent id) carry model and effort; unreadable fields are `unrecorded` or `unmeasured` (tests/test_models.py)
- [x] T006 [US3] A transcript payload with `model` and `effort` (tests/fixtures/payloads/claude-agent-post-model-effort.json, README provenance)
- [x] T007 [US4] The `models` key is set, kept, written as TOML and not retired; malformed values dropped (tests/test_models.py)
- [x] T008 [US5] The doctor names each variable; Learning shows each seat by model and effort (tests/test_models.py)
- [x] T009 Run red on main's code (3d2eb29) with the head's three test files and the new fixture: 37 failed, 162 passed (`pytest -q tests/test_models.py tests/test_hook.py tests/test_ledger.py`); fix round 1 on the previous head's code (e0351a1): `tests/test_models.py` 7 failed, 45 passed

## Phase 2: Implementation

- [x] T010 `TABLE`, `PATHS`, `CONFLICT`; `render` writes `model:` and `effort:` (cli/wuwei/agents.py)
- [x] T011 `asked` and `advise`; `pre_tool` returns the note for an Agent launch (cli/wuwei/hook.py)
- [x] T012 The record fields on `seat.started` and `attest` (cli/wuwei/hook.py)
- [x] T013 The `models` key (cli/wuwei/ws.py)
- [x] T014 The doctor rows (cli/wuwei/setup.py)
- [x] T015 The Learning lines and traced escapes (cli/wuwei/report.py)
- [x] T016 Five keys to six: README.md, docs/site/reference.md, cli/wuwei/ws.py, cli/wuwei/__main__.py, tests/test_ledger.py
- [x] T017 planner.md rules 1, 4 and 7; models.md; design.md; `bin/wuwei agents build`; `setup.vendor('.')`

## Phase 3: Checks

- [x] T018 Full suite green
- [x] T019 Route corpus and payload differential at main and head with the corpus sha256 (specs/models-record/route_diff.py)
- [x] T020 40 mutants (M1 to M41; M17 went with the `seat.stopped` effort), each applied to both copies of `cli/` by re-vendoring `.claude/`, in fresh copies: 40 killed, each by a test in tests/test_models.py, 0 survived (specs/models-record/mutants.py)
- [x] T021 Malformed launch inputs never refuse and never raise (tests/test_models.py)

## Fix round 2

- [x] T022 Merge main (5fe8347); the one conflict is the import line in hook.py (agents and view)
- [x] T023 The doctor's variable rows are `note` rows and keep the exit code (tests/test_models.py, cli/wuwei/setup.py)
- [x] T024 A malformed `models` row naming Haiku for a gate brings the floor note (tests/test_models.py, cli/wuwei/hook.py)
- [x] T025 Docs: README.md, docs/site/concepts/models.md
- [x] T026 Mutants on the merged tree: 44 (M1 to M45, M17 gone; M42 to M45 new), 44 killed, 0 survived. M7 survived the first run,
  since the floor now reads the raw rows; a role-row test kills it (specs/models-record/mutants.py)
- [x] T027 Route differential at main 5fe8347 and the head, corpus sha256 9e099867 (specs/models-record/route_diff.py)
