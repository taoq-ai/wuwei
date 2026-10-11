# Tasks: a CI-fix item's briefs list every step of the failing job, and its gate verdicts cite each

**Input**: `specs/733-ci-fix-every-step/spec.md`, `specs/733-ci-fix-every-step/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Run tests with `python -m pytest -q` from the repository root.

A shared fixture text for every test file below (copy it, or import it from
`tests/test_calibrate.py`): `.github/workflows/ci.yml` with `on: [pull_request]` and one job
`lint` (`name: Lint`) whose steps are `- uses: actions/checkout@v4`, `- name: Ruff` /
`run: ruff check .`, and `- name: Types` / `run: |` followed by `pip install mypy` and
`mypy cli`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Foundational - the workflow reader knows steps (blocks US1 and US2)

- [X] T001 [P] [US1] In `tests/test_calibrate.py`, add a test: `calibrate._workflow(CI)` gives
  the `lint` job `steps` equal to three dicts in file order: the checkout step with `run`
  `None`, `{'name': 'Ruff', 'run': 'ruff check .', 'line': <its dash line>}` and
  `{'name': 'Types', 'run': 'pip install mypy\nmypy cli', 'line': <its dash line>}`; the
  job's `runs` is `[('ruff check .', <run line>)]` with no `'|'` entry; a `run: >-` block and
  a step whose first key is `run:` (`- run: make test`) parse the same way. Run it; it fails
  (no `steps` key, and `runs` carries `'|'`).
- [X] T002 [US1] In `cli/wuwei/calibrate.py` `_workflow`, record `job['steps']` and fix the
  single-line run regex to `r'-?\s*run:\s*([^\s|>].*)'` (plan Design 1). T001 passes; the
  rest of `tests/test_calibrate.py` passes unchanged.

## Phase 2: User Story 1 - the briefs list every step (P1)

### Tests first

- [X] T003 [P] [US1] In `tests/test_brief.py`, add unit tests for the three helpers on a
  `tmp_path` worktree holding the fixture workflow:
  - `brief.ci_jobs` returns `['.github/workflows/ci.yml#lint']` for "fix the lint job",
    "CI job `lint` is red", "the Lint job" and the feedback line
    `Lint: failure https://example.test/run/1` (also `Lint (3.11): timed_out url`); returns
    `[]` for "write the test first", "lint: fix the import order" (prose after a colon is not a
    red conclusion), a job name absent from the workflow, and a worktree with no
    `.github/workflows`.
  - `brief.ci_steps(['.github/workflows/ci.yml#lint'], tree)` returns two steps numbered 1 and
    2 with labels `lint / Ruff` and `lint / Types`, sources `.github/workflows/ci.yml:<line>`
    and the full commands, and `missing == []`; with an extra ref
    `.github/workflows/ci.yml#gone` that ref is in `missing`; with the workflow replaced by a
    symlink it raises `ValueError` naming `.github/workflows/ci.yml`.
  - `brief.ci_block` returns `''` for `[]`, and for the lint ref the exact text in plan
    Design 2 (first line, `CI step 1: lint / Ruff (...)`, the indented command lines), with no
    blank line and a trailing newline.
  Run them; they fail (no such functions).
- [X] T004 [P] [US1] In `tests/test_brief.py`, add brief-write tests in the `day` fixture with
  the fixture workflow under `day[0] / 'tree'`:
  - Spec US1 scenario 1: set `items.X.title` to "fix the lint job"; `brief builder X b1
    --worktree tree` writes a brief containing `CI step 1: lint / Ruff` and
    `CI step 2: lint / Types` after the body, and `items.X.ci_jobs ==
    ['.github/workflows/ci.yml#lint']`; then a gate brief (`brief quality X g1 --gate
    --worktree tree` with the `GATE_BODY` text, item title cleared) lists both steps from the
    record alone.
  - Spec US1 scenario 3: an item whose title and body name no job writes a brief equal to the
    one written before this change (assert no `CI step` text and no `ci_jobs` key).
  - Edge case: a gate brief whose body already contains the block (the second-opinion copy)
    carries `CI step 1:` once.
  Run them; they fail (no block, no key).
- [X] T005 [P] [US1] In `tests/test_dispatch.py`, add two tests with the fixture workflow in the
  item worktree from `built(root)`:
  - Spec US1 scenario 2: `build.open_fix('A', 'Lint: failure https://example.test/1',
    root=root)` records `items.A.ci_jobs == ['.github/workflows/ci.yml#lint']` and the
    returned action's prompt contains `CI step 1: lint / Ruff` and `CI step 2: lint / Types`.
  - In the `test_delta_offers_one_continuation_of_the_stopped_seat` setup with
    `items.A.ci_jobs` recorded, the delta continue action's `feedback` ends with the block and
    `prompt == launch['prompt'] + '\n\n' + feedback` still holds.
  Run them; they fail.
- [X] T006 [P] [US1] In `tests/test_plan.py` (beside the test at line 509), add: a generic
  `state.write_state` setting `items.<item>.ci_jobs` raises `StateError` matching
  `reserved; written by wuwei brief`. Run it; it fails (the message says "its dedicated
  command").

### Implementation

- [X] T007 [US1] In `cli/wuwei/brief.py`, add `RED`, `ci_jobs`, `ci_steps` and `ci_block`
  (plan Design 2). T003 passes.
- [X] T008 [US1] In `cli/wuwei/brief.py` `write`, record `ci_jobs` and append the block (plan
  Design 3). T004 passes; every other `tests/test_brief.py` test passes unchanged.
- [X] T009 [US1] In `cli/wuwei/commands/build.py` `open_fix` and `cli/wuwei/dispatch.py`
  `_seats` and `opinion`, record the jobs and append the block (plan Design 4 and 5). T005
  passes.
- [X] T010 [US1] In `cli/wuwei/state.py` `_producer_error`, name the producer of `ci_jobs`
  (plan Design 7). T006 passes.

## Phase 3: User Story 2 - a verdict citing one step is refused (P1)

### Tests first

- [X] T011 [P] [US2] In `tests/test_verdict.py`, add a parametrized `verdict.lint` test with
  `steps=[(1, 'lint / Ruff'), (2, 'lint / Types')]` on the module's valid verdict texts:
  - spec US2 scenario 1: rows for step 1 only: exit 1, the message names `CI step 2
    (lint / Types)` and `CI step <n>: PASS|FAIL|NOT RUN`;
  - scenario 2: `CI step 1: PASS ruff check . exited 0` and `CI step 2: NOT RUN needs a
    service` (and the same as bullets): exit 0;
  - scenario 3: `Verdict: PASS` with `CI step 2: FAIL mypy reported 3 errors`: exit 1;
  - scenario 4: two `CI step 1:` rows: exit 1;
  - a row with a status but no evidence (`CI step 1: PASS`): counts as missing, exit 1;
  - light (`light=True`): scenario 1 still exits 1;
  - scenario 5: the same texts with `steps=()` lint exactly as before the change.
  Run it; it fails (`lint` takes no `steps`).
- [X] T012 [P] [US2] In `tests/test_verdict.py`, beside
  `test_lint_file_reads_the_docs_value_at_lint_time`, add a `lint_file` test: a day state
  with seat `quality-1` on item `A` whose `worktree` is a `tmp_path` tree holding the fixture
  workflow; a gate file citing only step 1 lints 0 while `A` records no `ci_jobs`, then 1
  naming `CI step 2` once `ci_jobs` is recorded; `gate-unknown-1.md` lints 0; with the
  workflow replaced by a symlink the result is exit 2 naming the file (spec US2 scenario 6).
  Run it; it fails.

### Implementation

- [X] T013 [US2] In `cli/wuwei/verdict.py`, add `FORMAT['CI step']`, `CI_ROW`, `ci_rows`, the
  `steps` parameter of `lint` and the `ci_steps` reader used by `lint_file` (plan Design 6).
  T011 and T012 pass; the rest of `tests/test_verdict.py` passes unchanged.

## Phase 4: User Story 3 - charters, agents, docs and the invariant (P2)

- [X] T014 [P] [US3] In `tests/test_invariants.py`, add `i60` (pattern of `i46`): with the two
  steps, `verdict.lint` exits 0 for rows on both, 1 for step 1 only, 1 for PASS with a FAIL
  row, 1 for a duplicate row, and 0 for step 1 only with `steps=()`. Register `'I60': i60`
  at the end of `INVARIANTS`, `'I60': ()` at the end of the reads map, and a `BROKEN` entry
  `'ci step rows off'` patching `wuwei.verdict.ci_rows` to `lambda *args: []`. Run
  `test_table_matches_the_checks`; it fails (no I60 row in the design table).
- [X] T015 [US3] Edit `charters/builder.md` (step 9) and `charters/sentinel-goal.md` (step 1)
  with the sentences in plan Design 8, then run `bin/wuwei agents build` and confirm the diff
  under `agents/` is those two lines plus the `CI step` row in every
  `agents/sentinel-*.md` Verdict format section. `tests/test_agents.py` and I44 pass.
- [X] T016 [US3] In `docs/specs/2026-09-24-wuwei-design.md` 9.2, append the row
  `| I60 | A CI-fix item's gate verdict is accepted only with one result row per run step of
  each job the item records, and never as PASS with a failing step; an item that records no
  job lints as before | `verdict.lint` on two steps with rows for both, one, a duplicate and a
  FAIL under PASS, and on one row with no steps | #733; the steps come from
  `items.<item>.ci_jobs` and the worktree's workflow through `brief.ci_steps` |`. In
  `docs/site/reference.md`, add to "The lint rules" (line 367): "For an item that fixes a CI
  job, one `CI step <n>: PASS|FAIL|NOT RUN <evidence>` row per step the brief lists, at every
  depth; a PASS verdict carries no `FAIL` row." T014 passes, mutation included.

## Phase 5: Polish

- [X] T017 Run `python -m pytest -q`; everything passes. Check every file written for
  em-dashes and emojis and remove any. Confirm no absolute local path landed in a file.
- [X] T018 Review fix: in `tests/test_calibrate.py`, add a job whose `steps:` list sits at its
  key's indent; it fails. In `cli/wuwei/calibrate.py` `_workflow`, read a dash line at the
  key's indent as a step while `steps` is open. Split the two long charter sentences so
  `tests/test_tone.py` passes.

## Dependencies

- T001 before T002; T002 before T007 (the helpers read `steps`).
- T003 before T007; T004 before T008; T005 before T009; T006 before T010.
- T007 before T008, T009 and T013 (`verdict.ci_steps` calls `brief.ci_steps`).
- T011 and T012 before T013; T013 before T014's mutation can bite; T015 after T013 (agents
  render `FORMAT`); T016 after T014.
