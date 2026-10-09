# Tasks: one reviewer for a docs-only item

Test first: each test task runs and fails for the expected reason before its implementation
task. Diffs come from the fake VCS through the `tiered` helper in `tests/test_dispatch.py`
(neutral paths only); no test reaches git or the network. Run the touched test files, then
the full suite.

## Phase 1: the docs-only tier (FR-001, FR-002, FR-003; US1.1, US1.4, US1.5, US2, US3)

- [X] T001 Tests in `tests/test_dispatch.py`: rewrite
  `test_issue_acceptance_docs_only_light_floor_runs_quality_only` as the #622 acceptance:
  `docs/guide.md` at the default floor `standard` records tier light, roles `['goal']`,
  reasons `['docs-only: 1 reviewer (goal)']`, and the action's one command is
  `wuwei brief goal A goal-A --gate ...`; one `gate.tiered` event, one diff read.
- [X] T002 Tests in `tests/test_dispatch.py`, parametrized: `specs/622-x/spec.md` and
  `docs/prereg.md` give `['quality']`; `README.md` plus `docs/a.md` gives `['goal']`; a
  400-line `docs/big.md` gives one gate.
- [X] T003 Tests in `tests/test_dispatch.py`, parametrized, all at `floor='standard'` (the
  shipped default; the `tiered` helper defaults to `light`), each records the three roles:
  `src/app.py`; `docs/guide.md` with each lead flag; with track FULL;
  plus `cli/wuwei/guards/pr.py` (trust path); plus `uv.lock` (never-auto); plus `logo.png`
  binary; `charters/lead.md`; `AGENTS.md`; `docs/guide.md` at floor `full`. The empty diff
  stays light with `['quality']`.
- [X] T004 Test in `tests/test_dispatch.py`: lead tier `full` on `docs/guide.md` records
  light, one role, reasons containing `lead tier full overridden: docs-only` and
  `docs-only: 1 reviewer (goal)`. Move
  `test_issue_acceptance_lead_tier_raises_and_cannot_lower` to `src/app.py` (still full).
- [X] T005 Test in `tests/test_pace.py`: `docs/guide.md` under `pace careful` records
  standard with three roles and no docs-only reason; move
  `test_steady_records_are_unchanged` and `test_careful_raises_light_to_standard` to
  `src/app.py`.
- [X] T006 Implement `GATE_ROLES`, the document constants, `_docs_role` and the `tier()`
  changes in `cli/wuwei/dispatch.py` (plan, Design). T001 to T005 pass.

## Phase 2: a goal gate runs end to end (FR-004, FR-005, FR-006; US1.2, US1.3, US1.6)

- [X] T007 Tests in `tests/test_dispatch.py`: with a recorded `{'tier': 'light', 'roles':
  ['goal'], ...}`, receiving `arch` or `quality` is refused (not in the gate set); a goal
  PASS gives `raise`; a goal FIX gives `fix` for `['goal']`, and after the move to delta the
  action asks for `['goal']` only. `test_malformed_recorded_gate_set_fails_closed` gains
  `['goal', 'arch']` and `['security']` as still refused.
- [X] T008 Implement the `gate_set` validation in `cli/wuwei/dispatch.py`. T007 passes.
- [X] T009 Test in `tests/test_brief.py`: `brief goal X g --gate --worktree tree` writes a
  brief whose header names the `sentinel-goal` charter.
- [X] T010 Implement the `GATE_ROLES` mapping in `cli/wuwei/commands/brief.py`. T009 passes.

## Phase 3: the report (FR-007; US4)

- [X] T011 Test in `tests/test_report_retro.py`: item A tiered docs-only with one
  `sentinel-goal` seat and item B tiered standard with three sentinel seats give
  `## Review seats` lines `- A: 1 reviewer seat (goal); tier light: docs-only: 1 reviewer
  (goal)` and `- B: 3 reviewer seats (arch, quality, security); tier standard: <reasons>`;
  `test_report_levels` keeps its section list (no tiered item, no section).
- [X] T012 Implement `seat_lines` and the section in `cli/wuwei/report.py`. T011 passes.

## Phase 4: invariant I34 (FR-008)

- [X] T013 Test in `tests/test_invariants.py`: add `i34`, `READS['I34'] = ()` and the
  `INVARIANTS` entry; add the I34 row to the 9.2 table in
  `docs/specs/2026-09-24-wuwei-design.md`. Prove it bites: temporarily make `_docs_role`
  ignore `computed` (or ignore `AGENT_DOCS`) and see `test_invariants_hold` fail with an
  I34 line, then restore.
- [X] T014 Run `tests/test_invariants.py`; it passes on the Phase 1 code.

## Phase 5: fixtures, docs and charters (FR-009)

- [X] T015 Update `tests/test_process_depth.py` `test_builder_brief_names_its_depth`: the
  `floor='standard'` half uses `cli/wuwei/report.py`. Fix any other test whose
  `docs/guide.md` fixture meant "a small code diff" by moving it to `src/app.py`.
- [X] T016 Update `charters/_common.md` rule 4 (bump 1.7.0) and `charters/lead.md` rule 5
  (bump 1.5.0); run `bin/wuwei agents build` to regenerate `agents/*.md`.
- [X] T017 Update `docs/site/concepts.md` (Review tiers), `docs/site/reference.md` (lead
  `tier`), `docs/site/configuration.md` (`light_max_lines`, `floor`) and `README.md` line 30.
- [X] T018 Run the full suite (`python -m pytest -q`); check every written file for
  em-dashes, emojis and absolute local paths.

## Phase 6: review fixes

- [X] T019 (F1) Rebase onto main 8ea4f8f, which adds I26 and I27 (#603): renumber this
  invariant to I34, keep #603 rule 4 in `charters/lead.md` and regenerate `agents/*.md`.
- [X] T020 (F2) Test in `tests/test_dispatch.py`: `docs/conf.py`, `specs/x/plan.py`,
  `docs/site/index.html`, `CMakeLists.txt` and `src/stopwords.txt` keep three gates. A path is
  a document only when it ends in `.md` or `.rst`, or in `.txt` under `docs/` or `specs/`.
