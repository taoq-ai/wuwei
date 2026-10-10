# Tasks: the analysis step checks each assumption against the governing document

**Input**: `specs/664-analysis-governing/spec.md`, `specs/664-analysis-governing/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: The governing reference and the table check (shared spot)

### Tests first

- [X] T001 [US1] In `tests/test_spec_mode.py`, add a test for `specmode.governing`: a
  `tmp_path` worktree with `docs/prereg.md` holding `# Pre`, `## Pre-registration` (two
  lines of text), `### Sample`, `## Analysis`. Assert: `governing(tree, {})` is None; the
  row `{'governed_by': 'docs/prereg.md#Pre-registration'}` returns the reference, the
  heading's line number, the line before `## Analysis`, and text that includes `### Sample`
  and excludes `## Analysis`; `'docs/prereg.md'` alone returns the whole file; a design-like
  file with `### 5.1 Roles` and `### 5.10 Spec` resolves `#5.1` to the first and `#5.10` to
  the second. Run it; it fails (`governing` does not exist).
- [X] T002 [US1] In `tests/test_spec_mode.py`, extend T001 with the spec line route and its
  precedence: a `specs/001-a/spec.md` with `Governing: docs/prereg.md#Analysis` resolves
  through `governing(tree, {}, Path('specs/001-a'))`; with the row also set, the row's
  reference wins. Run it; it fails.
- [X] T003 [US1] In `tests/test_spec_mode.py`, parametrize the refusals of `governing`
  (`ValueError`, reason checked): a missing file, a missing heading (`no heading`), an
  absolute path, `../outside.md` (a real file outside the worktree), an empty name
  (`#Pre-registration`). Run it; it fails.
- [X] T004 [US1] In `tests/test_spec_mode.py`, add a test for `specmode.governed(report,
  spec_text)` with a spec holding two `## Assumptions` bullets: a report with a
  `## Governing` table of two valid rows returns None (mix `agrees` and `not covered`, one
  citation a range `docs/prereg.md:3-5`); no `## Governing` section, one valid row, a row
  verdict `maybe`, and a row whose Line cell has no `<path>:<n>` each return a gap naming
  what is missing; a spec with no assumptions still needs one row. Run it; it fails.

### Implementation

- [X] T005 [US1] In `cli/wuwei/specmode.py`, add `GOVERNING`, `VERDICTS` and
  `governing(tree, row, location=None)` as `plan.md` Design says, with the `ponytail:`
  comment on fenced code blocks. T001 to T003 pass.
- [X] T006 [US1] In `cli/wuwei/specmode.py`, add `governed(report, spec_text)`, importing
  `docs._sections` inside the function. T004 passes.

## Phase 2: `wuwei spec analysis` refuses a governed report without the table

### Tests first

- [X] T007 [US1] In `tests/test_spec_mode.py`, next to `test_spec_analysis_refusals`, add a
  test with the `ws`, `item` and `unanalysed` fixtures: write `docs/prereg.md` in the item
  worktree, set `governed_by` on item `A` in the day state, and run `analysis(...)` with the
  fixture `REPORT` (no table). Assert exit 2, empty stdout, no `analysis.md`, and stderr
  naming `docs/prereg.md#Pre-registration`, the line range and `## Governing`. Then append a
  valid table with one row per assumption in the fixture `spec.md` (add an `## Assumptions`
  bullet to the copied spec if it has none) and assert exit 0 and the saved text (scenarios
  2 to 4). Run it; the first assertion fails (exit 0).
- [X] T008 [US1] In the same file, add the spec line route: no `governed_by` on the item,
  `Governing: docs/prereg.md#Pre-registration` in the copied `spec.md`, report without the
  table, exit 2 (scenario 5); and a `governed_by` naming a missing heading, exit 2 with
  `no heading` (edge case). Run it; it fails.
- [X] T009 [US2] In the same file, assert the ungoverned path is unchanged: the existing
  `test_spec_analysis_writes_the_report` keeps passing untouched (no edit), and add one
  assertion that a report without a `## Governing` section is saved when neither the row
  nor `spec.md` names a document. Run it; it passes before and after (guard test).

### Implementation

- [X] T010 [US1] In `cli/wuwei/commands/spec.py` `write`, after the empty-report check,
  call `specmode.governing(tree, items[name], location)` and, when found,
  `specmode.governed(text, spec.md text)`; raise `ValueError` with the reason from
  `plan.md` Design. T007 and T008 pass, T009 still passes.

## Phase 3: The builder brief carries the governing text; the gate brief names it

### Tests first

- [X] T011 [US1] In `tests/test_spec_mode.py`, add a test for `specmode.brief_block`:
  with the row's `governed_by` and the T001 document, the block starts with
  `\n## Governing document\n`, names the reference and `lines a-b`, says
  `/speckit.analyze` and `## Governing`, and ends with the section text only; it is `''`
  with no reference, with spec mode off, with engine `openspec`, and with the item skipped
  (`{'spec': {'value': 'skipped', 'reason': 'r'}}`). Run it; it fails.
- [X] T012 [US1] In `tests/test_spec_mode.py`, assert `brief_line(config(), 'A', row, tree,
  True)` for a governed item equals `Spec: speckit artifacts: specs/001-a; governed by
  <reference> (lines a-b): check the ## Governing table in analysis.md`, and the builder
  line (`gate=False`) and the ungoverned gate line are unchanged (scenario 6, US2). Run it;
  it fails.
- [X] T013 [US1] In `tests/test_brief.py`, next to
  `test_builder_and_gate_briefs_carry_the_spec_line`: set `governed_by` on item `X`, write
  the document in `tree`, write a builder brief, and assert the brief file ends with the
  block and the section text, and that its header (text before the first blank line) is
  unchanged; then a `governed_by` naming a missing file makes the brief command exit 2 with
  the reason and write no brief file. Add to the existing test an assertion that the
  ungoverned builder brief contains no `## Governing document` (US2). Run it; it fails.

### Implementation

- [X] T014 [US1] In `cli/wuwei/specmode.py`, add `brief_block(config, item, row, tree)` and
  the gate branch suffix in `brief_line`. T011 and T012 pass.
- [X] T015 [US1] In `cli/wuwei/brief.py` `write`, compute
  `specmode.brief_block(config, item, current, tree)` for `role == 'builder'` with a tree,
  before the state update, and append it after the body where `text` is joined. T013
  passes.

## Phase 4: The lead can name `governed_by` on the plan item

### Tests first

- [X] T016 [P] [US1] In `tests/test_plan.py`, next to
  `test_candidate_tier_is_copied_at_approve`: a candidate with `governed_by:
  'docs/prereg.md#Pre-registration'` is copied onto the item at `plan.approve`; a candidate
  with `governed_by: ''` or `3` is refused by `plan.propose` with `governed_by must be`;
  without the key the item has no `governed_by`. Run it; it fails.
- [X] T017 [P] [US1] In `tests/test_plan.py`, admit a discovery candidate carrying
  `governed_by` through `plan.add` (reuse the setup of the intraday tests) and assert it is
  copied. Run it; it fails.

### Implementation

- [X] T018 [US1] In `cli/wuwei/plan.py`, validate `governed_by` in `_proposal` next to the
  `paths` check, and widen the copied keys in `approve` (line 386) and `add` (line 489) to
  `('tier', 'governed_by')`. T016 and T017 pass.

## Phase 5: Charters, agents and docs

### Tests first

- [X] T019 [US1] In `tests/test_charters.py`, add a test that `builder.md` mentions
  `Governing:` and `## Governing`, `sentinel-goal.md` mentions `## Governing` and
  `conflicts`, and `lead.md` mentions `governed_by`. Run it; it fails.

### Implementation

- [X] T020 [US1] Edit `charters/builder.md` (step 1), `charters/sentinel-goal.md` (step 1)
  and `charters/lead.md` (step 4) with the sentences from `plan.md`; no em-dashes, no
  sentence repeated in another charter. T019 passes.
- [X] T021 [US1] Run `bin/wuwei agents build` from the repository root to regenerate
  `agents/builder.md`, `agents/sentinel-goal.md` and `agents/lead.md`; `bin/wuwei agents
  check` exits 0.
- [X] T022 [US1] Add the "Governing document (owner, 2026-10-10, #664)" paragraph to
  `docs/specs/2026-09-24-wuwei-design.md` 5.10 after the spec-kit step table; add the
  governed refusal to the `bin/wuwei spec` row of `docs/site/reference.md` (line 71) and
  one sentence to `docs/site/configuration.md` (line 119).

## Phase 6: Verification

- [X] T023 Run `python -m pytest -q` from the repository root with the task's interpreter;
  everything passes. Grep the changed files for em-dashes and emojis and remove any.

## Dependencies

- T005 and T006 before T010, T014; T014 before T015. Phase 4 is independent of Phases 2
  and 3 (T016 and T017 can run in parallel with them). Phase 5 after Phases 1 to 4.
