# Tasks: decision titles, rationale, consequence, reasoning and lenses

**Input**: `specs/475-decision-lens/` (spec.md, plan.md, data-model.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. No absolute local paths, emojis or em-dashes in any file.
Neutral fixtures only.

## Phase 1: Foundation (classes, lens config, parsed fields)

- [X] T001 Test, `tests/test_decision.py`: `test_class_after_question_is_its_own_field`
  (a record with `Class: re-plan` after `Question:` evaluates and `fields['Class'] ==
  're-plan'`; `Class: desing` raises naming `Class`). Extend `test_class_levels` with
  `design`, `boundary`, `refactor` at 0. Update `tests/test_brief.py:412` to the owner list
  with the three new classes after `dependency-bump`. Run `python -m pytest -q
  tests/test_decision.py -k "class" tests/test_brief.py -k mandate` (fails: Question
  expected one line; unknown classes).
- [X] T002 Implement plan Design 1 in `cli/wuwei/decision.py` (CLASSES, ENGINEERING,
  LENSES, OPTIONAL, `lens_table`, parser and one-line and class checks) and the three
  classes in `cli/wuwei/telemetry.py` `CLASSES`. Rerun T001 and `python -m pytest -q
  tests/test_telemetry.py`; pass.
- [X] T003 Test, `tests/test_workspace.py`: `test_decision_lenses_config` (default `{}`; a
  `[decisions.lenses]` table loads; a name `bad name` or `9x` is refused naming
  `decisions.lenses.<name>`). Test, `tests/test_decision.py`: `test_lens_table` (defaults;
  added name appended; `YAGNI = ""` dropped). Run `python -m pytest -q tests/test_workspace.py
  tests/test_decision.py -k lens` (fails: unknown key decisions.lenses).
- [X] T004 Implement plan Design 8 in `cli/wuwei/workspace.py` (schema, name check,
  `CONFIG_CACHE_VERSION = 6`). Rerun T003; pass.

## Phase 2: US1, the new-record check (P1)

- [X] T005 Test, `tests/test_decision.py`: rewrite `VALID` (and `FIVE`) to the new shape
  (data-model.md: `Class: design`, four-column Options, `Lenses:` with the four default
  lenses, `Reasoning:`); keep the old text as `LEGACY`. Add
  `test_explained_record_fields`, parametrized over removing or breaking: `Class:`, the
  `Title` column, one `Rationale` cell, one `Consequence` cell, `Reasoning:`, a two-line
  `Reasoning:`, the `Lenses:` table, the `YAGNI` row, one lens cell, an extra `Speed` lens
  row, a duplicate title, a 41-character title, a title with `"`; each `lint` exits 1 and
  the message contains the field name (and the lens or title). Add
  `test_legacy_record_still_evaluates` (`evaluate(LEGACY)` passes; `lint(LEGACY)` exits 1
  naming `Options` or `Class`; `decision.write(LEGACY, root)` raises). Add
  `test_prioritisation_record_needs_no_lens` (`Class: re-plan`, no `Lenses:`; lint 0; spec
  US3 scenario 4). Add `test_custom_lens_is_required` (workspace config with `company-rule`
  added: `lint_file` on VALID exits 1 naming `company-rule`; with the row added, 0; with
  `YAGNI = ""`, the `YAGNI` row is refused as unknown). Run `python -m pytest -q
  tests/test_decision.py -k "explained or legacy or prioritisation or custom_lens"` (fails:
  evaluate takes no lenses; four-column Options refused as `expected columns Option,
  Description`).
- [X] T006 Implement plan Design 2 (`options`, `_scored`) and Design 3 (`evaluate(text,
  lenses=None)`, `lint`, `lint_file`, `write`) in `cli/wuwei/decision.py`. Rerun T005; pass.
- [X] T007 Test: run `python -m pytest -q tests/test_decision.py tests/test_why.py
  tests/test_remote.py tests/test_control_plane.py tests/test_doctor.py
  tests/test_dashboard.py tests/test_consolidation.py tests/test_interview.py` and list the
  failures that come from fixtures going through `lint`, the question guard or `write`
  (expected: they still use `| Option | Description |`).
- [X] T008 Implement: move those fixtures to the new shape (non-engineering class, so no
  `Lenses:` unless the test is about lenses); leave fixtures read only through
  `evaluate(text)` legacy. Replace the `table(fields['Options'], ['Option', 'Description'],
  'Options')` copies with `decision.options(fields)` in `cli/wuwei/commands/decision.py`,
  `cli/wuwei/control_plane.py`, `cli/wuwei/interview.py`, `cli/wuwei/consolidation.py`
  (plan Design 2). Rerun T007; pass.

## Phase 3: US1, CLI-written records (FR-011)

- [X] T009 Test: in one existing test per generator, assert the written record passes
  `decision.lint(text)` with exit 0: `tests/test_watch.py` (scanner critical sequence),
  `tests/test_plan.py` (day close carry and park), `tests/test_pr_actions.py` (scope thread),
  `tests/test_mcp.py` (registry findings and proceed-unmeasured), `tests/test_build.py`
  (build park), `tests/test_report_retro.py` (hard rule), `tests/test_remote.py` (denial).
  Run those files (fails: `write` refuses the old shape, or the lint assertion fails).
- [X] T010 Implement plan Design 7 in `cli/wuwei/scanner.py`, `cli/wuwei/plan.py`,
  `cli/wuwei/pr_actions.py`, `cli/wuwei/mcp.py` (both records), `cli/wuwei/commands/build.py`,
  `cli/wuwei/retro.py`, `cli/wuwei/remote.py`. Rerun T009; pass.

## Phase 4: US2, the Ask card (P1)

- [X] T011 Test, `tests/test_decision.py`: rewrite `test_decision_widget_passes_the_question_guard`
  and `test_decision_show_widget` for the new card: labels are titles, the first ends in
  ` (Recommended)`; descriptions are rationale, consequence and four `<lens>: <line>`
  lines; the question ends with the first sentence of `Reasoning`; `record ==
  'wuwei decide D-3 "<label>"'`; the card still passes the question guard; FIVE shows four
  options. Add `test_widget_trims_by_verbosity` (brief: first sentence of a two-sentence
  rationale; full: both sentences) and `test_custom_lens_on_the_card` (config
  `company-rule`: every option's description has a `company-rule:` line). Run `python -m
  pytest -q tests/test_decision.py -k widget` (fails: labels are option ids).
- [X] T012 Implement plan Design 4 (`lens_lines`, `first`, `RECORD`, `record_widget`) in
  `cli/wuwei/decision.py` and Design 6 `show --widget` in `cli/wuwei/commands/decision.py`.
  Rerun T011; pass.
- [X] T013 Test, `tests/test_decision.py`: `test_decide_accepts_a_title_label`
  (`owner_outcome` with `"Implement fix (Recommended)"`, with `"implement fix"` and with
  `A` each record option `A`; `"Nope"` exits 1 with the existing not-in-the-record
  message). `tests/test_mcp.py`: the widget's `record` is `wuwei mcp decide <id>
  "<label>"`, the proceed option still carries the findings lines, and `mcp.decide` with the
  proceed title records `proceed`. Run `python -m pytest -q tests/test_decision.py -k
  title_label tests/test_mcp.py -k widget` (fails: option not in the record).
- [X] T014 Implement plan Design 4 `option_id` in `cli/wuwei/decision.py` and Design 5 in
  `cli/wuwei/commands/decision.py` and `cli/wuwei/mcp.py`. Rerun T013; pass.

## Phase 5: US4, `decision show` and the DM (P2)

- [X] T015 Test, `tests/test_decision.py`: update `test_present_brief` and
  `test_present_standard` (brief: each option line has its title, score and consequence; the
  Recommended line ends with the reasoning; standard adds `Rationale:` and the lens lines);
  add `test_present_legacy_unchanged` (LEGACY prints the same lines as on main). Check
  `tests/test_control_plane.py` DM brief text the same way. Run `python -m pytest -q
  tests/test_decision.py -k present tests/test_control_plane.py` (fails: no consequence in
  the brief text).
- [X] T016 Implement plan Design 4 `present` in `cli/wuwei/decision.py`. Rerun T015; pass.

## Phase 6: Template (FR-010)

- [X] T017 Test, `tests/test_decision.py`: the `template()` helper output lints `OK: A
  (80)`, contains `Class: design`, one `Lenses:` row per default lens and the HTML comment
  with each question; inside a workspace with `company-rule` configured it also has that
  row. Run `python -m pytest -q tests/test_decision.py -k template` (fails: no `Class:`).
- [X] T018 Implement plan Design 6 `template` in `cli/wuwei/commands/decision.py`. Rerun
  T017; pass.

## Phase 7: US5, charters, skill, docs, design spec (P2)

- [X] T019 Test, `tests/test_charters.py`: add rows to the existing phrase table: `_common.md`
  has `Option | Title | Rationale | Consequence`, `Reasoning:` and `Lenses:`; `lead.md`,
  `sentinel-arch.md` and `builder.md` each name the `design` class and say the lens lines
  are mandatory. Run `python -m pytest -q tests/test_charters.py` (fails: phrases missing).
  Built as a separate `test_decision_lens_charters`: the `RULES` table requires one home per
  anchor and `test_charter_sentences_have_one_home` forbids a shared sentence, so the three
  role charters word their line differently.
- [X] T020 Implement plan Design 10 charter lines in `charters/_common.md`,
  `charters/lead.md`, `charters/sentinel-arch.md`, `charters/builder.md`; run `bin/wuwei
  agents build` then `bin/wuwei agents check` from the repository root (outside a
  workspace) to regenerate `agents/*.md`. Rerun T019 and `python -m pytest -q
  tests/test_agents*.py`; pass.
- [X] T021 Test: run `python -m pytest -q tests/test_docs.py` after adding the
  `decisions.lenses` key (fails if the docs test requires every config key in
  `docs/site/configuration.md`); otherwise add an assertion there that
  `configuration.md` has a `decisions.lenses` row and `concepts.md` has `### Lens`.
- [X] T022 Implement plan Design 10 text in `docs/site/configuration.md`,
  `docs/site/concepts.md`, `skills/wuwei-plan/SKILL.md` and
  `docs/specs/2026-09-24-wuwei-design.md` (5.8 and 5.8.1). Rerun T021; pass.

## Phase 8: Polish

- [X] T023 Run the full suite, `python -m pytest -q`; pass (including
  `tests/test_reasons.py` for the new refusal texts). Check every changed file for
  em-dashes, emojis and absolute local paths; remove any.
