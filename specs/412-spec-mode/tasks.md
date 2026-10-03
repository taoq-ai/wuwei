# Tasks: Specification mode

Input: specs/412-spec-mode/spec.md and plan.md. Test first: each test task runs red (for the
stated reason) before its implementation task. Run tests with `python -m pytest -q <file>`
from the repository root; the full suite at the end. Mark `[X]` as each task finishes.

## Phase 1: Config (FR-001)

- [X] T001 [US5] Test in tests/test_spec_mode.py: an empty config loads `spec` as `{"engine": "speckit", "mode": "strict", "skip_tiers": ["light"]}`; `engine = "kiro"`, `mode = "loud"` and `skip_tiers = ["tiny"]` each raise ConfigError naming the key; the template's `[spec]` loads to the defaults. Red: KeyError `spec`.
- [X] T002 [US5] Add `SCHEMA["spec"]` in cli/wuwei/workspace.py, bump `CONFIG_CACHE_VERSION` to 2, add the commented `[spec]` section to templates/workspace/config.toml.

## Phase 2: Helper tables and rules (FR-002)

- [X] T003 [P] [US4] Create fixtures tests/fixtures/spec/speckit/specs/001-a/ (spec.md with `## Clarifications`, plan.md, tasks.md all checked, analysis.md with a LOW row only, checklists/requirements.md all checked), tests/fixtures/spec/superpowers/docs/superpowers/{specs/2026-10-03-a-design.md,plans/2026-10-03-a.md all checked}, tests/fixtures/spec/openspec/openspec/changes/archive/2026-10-03-a/ (proposal.md, specs/cli/spec.md, tasks.md all checked, validation.json valid). Neutral content only.
- [X] T004 [US1] [US4] Tests in tests/test_spec_mode.py for `specmode.status`, parametrized per engine over a copy of its fixture in `tmp_path`: complete set gives None with `build=True`; deleting each artifact in turn makes its step the gap; without `build` the implementation row and later rows never gap; an unchecked task gaps `implement` only with `build=True`; analysis.md with a `| HIGH |` row gaps `analyze` while prose `CRITICAL issues: 0` does not; `## Clarifications` missing gaps `clarify`; two matching directories (`specs/001-a`, `specs/002-a`) gap the first step naming both; invalid UTF-8 and malformed validation.json are not done and name the file; item `ENG-7` is found as `specs/003-eng-7`; OpenSpec before archive (`openspec/changes/a/`) gaps `archive` only with `build=True`. Red: no module `wuwei.specmode`.
- [X] T005 [US1] [US4] Create cli/wuwei/specmode.py with `INSTALL`, `MARKER`, `OWN`, `LOCATION`, `STEPS`, `IMPLEMENT`, the `RULES` functions and `status`, `done`, `own`.
- [X] T006 [US2] [US3] Tests in tests/test_spec_mode.py for `mode` (off for engine none or mode off; advisory for advisory, and for strict under `security.posture = "observe"`), `skip` (override skipped, override required beats a light tier, light tier skips, `computed = "standard"` voids a tier skip, no tier needs a spec) and `once` (a second identical call appends nothing; a different step appends). Red: AttributeError.
- [X] T007 [US2] [US3] Implement `mode`, `label`, `skip` and `once` in cli/wuwei/specmode.py.
- [X] T008 [US1] [US2] [US3] Tests for `specmode.check` in tests/test_spec_mode.py: strict gap returns exit 1 with `specify first: /speckit.specify` and, with no `.specify/` in the tree, the spec-kit install line; skipped returns 0 and writes one `spec.skipped` across two calls; advisory returns 0 and writes one `spec.warned` across two calls; off writes nothing; a lead-tier skip with `build=True` reads `row['gates']['computed']` and, with no gates record, calls a monkeypatched `dispatch.tier` once. Red: AttributeError.
- [X] T009 [US1] [US2] [US3] Implement `check` and `record` in cli/wuwei/specmode.py.

## Phase 3: Hooks (FR-003)

- [X] T010 [US1] Tests in tests/test_spec_mode.py driving `wuwei.commands.hook.run` with PreToolUse payloads (a workspace with today's state recording item A at phase implement with `worktree` = a temporary repository): an Edit of `src/app.py` refused with `specify first: /speckit.specify` and a `hook.refusal` event; an Edit of `specs/001-a/spec.md` passes; after the complete spec-kit set the Edit passes; a Write in the workspace root and a Write in an unrecorded repository pass. Red: no guard refuses.
- [X] T011 [US1] Tests in tests/test_spec_mode.py: PostToolUse Write of each artifact in order writes exactly one `spec.step` (item, engine, step, path) per step, a repeated Write writes none, a PostToolUse Bash with `cwd` in the worktree records a step whose file appeared, and a PostToolUse in a skipped item writes no `spec.step`.
- [X] T012 [US1] Tests in tests/test_spec_mode.py: SubagentStop of a `wuwei:builder` seat (seat reservation, brief reference transcript as in tests/test_agent_launch.py) whose last message lacks `specs/001-a` is refused naming it; with the name it passes; with `stop_hook_active` it passes; a sentinel stop is not checked.
- [X] T013 [US6] Test in tests/test_hooks.py (fresh interpreter, the `test_hook_imports_no_unused_stdlib` launcher pattern): PreToolUse bash, PreToolUse Write in the workspace root and PostToolUse Bash in a workspace leave `wuwei.specmode` out of `sys.modules`; a Write in a recorded item worktree loads it. Red: the item case fails (no guard).
- [X] T014 [US1] [US6] Create cli/wuwei/guards/spec.py (`_item`, `check_edit`, `check_record`, `check_stop`, `GUARDS`); add `MODULES['spec']` and `AREAS['spec'] = None` in cli/wuwei/guards/__init__.py. T010 to T013 and `tests/test_hooks.py::test_import_map_matches_guard_tables` pass.
- [X] T015 [US1] Add `PROBES` rows for the three spec checks in tests/test_guard_mutation.py (a refused Edit, a recorded event, a refused stop); run it and see each probe red with its check disabled.

## Phase 4: Build loop and backstop (FR-004)

- [X] T016 [US1] [US2] Tests in tests/test_build.py: with green fast checks and no spec, `complete_checks` keeps the item at `implement`, returns 1 and the continue feedback starts `spec:` naming `specify`; with the complete set and all tasks checked it moves to `gate`; `stuck_after` repeats of the same gap park the item; a light lead tier whose monkeypatched `dispatch.tier` computes `standard` gets the gap; `[spec] mode = "advisory"` moves to `gate` and writes one `spec.warned`. Red: the item moves to gate.
- [X] T017 [US1] [US2] Call `specmode.check(..., build=True, where='gates')` in `complete_checks` in cli/wuwei/commands/build.py before the move.
- [X] T018 [US1] Test in tests/test_dispatch.py: an item at `gate` (set by `state.transition`) with stopped builder and no spec makes `dispatch.next_step` raise `Refused` naming the step; with the complete set it returns the gates action. Red: gates returned.
- [X] T019 [US1] Call `specmode.check(..., build=True, where='dispatch')` after the tier block in `next_step` in cli/wuwei/dispatch.py.

## Phase 5: Owner action (FR-005)

- [X] T020 [US2] Tests in tests/test_plan.py: `plan set A spec=skipped --reason "typo fix"` exits 0, writes `items.A.spec = {"value": "skipped", "reason": "typo fix"}` and one `spec.override`; `spec=required` with no reason exits 0; `spec=skipped` with no reason exits 2 and writes nothing; `spec=maybe` and `tier=light` exit 2; unknown item exits 1. Tests in tests/test_protect_state.py: Bash `wuwei plan set A spec=skipped --reason x` from an agent tool is refused with the owner reason; `wuwei plan approve ...` is not. Tests in tests/test_state.py: `state set items.A.spec ...` names `wuwei plan set`; tests in tests/test_owner_actions.py or the event test: `wuwei event spec.override {}` exits 1 naming its producer. Red: unknown action `set`.
- [X] T021 [US2] Implement `set_spec` in cli/wuwei/plan.py, the `set` subparser and dispatch in cli/wuwei/commands/plan.py, `('plan', 'set')` in cli/wuwei/guards/protect_state.py, `'spec'` in `state._producer_error`, the four kinds in `EVENT_PRODUCERS` in cli/wuwei/commands/event.py.

## Phase 6: Briefs, orientation, report (FR-006)

- [X] T022 [US5] Tests in tests/test_brief.py: a builder brief for a STANDARD item has one `Spec: speckit strict` line naming `/speckit.specify` and `create-new-feature.sh --json --short-name a`; for a skipped item `Spec: skipped (lead tier light)`; a gate brief names the feature directory; `engine = "none"` adds no line. Test in tests/test_next.py: the orientation block has `Spec: speckit strict`, and `Spec: speckit advisory` under observe posture. Test in tests/test_report_retro.py: a day with one `spec.warned` lists it under `## Spec warnings`; a day without has no such heading. Red: lines missing.
- [X] T023 [US5] Implement `brief_line` in cli/wuwei/specmode.py and call it in `write` in cli/wuwei/brief.py; add the `spec` argument to `orientation` in cli/wuwei/commands/next.py and pass `specmode.label(config)` in cli/wuwei/guards/lifecycle.py; add the `## Spec warnings` block in cli/wuwei/report.py. Update any whole-header or whole-block expectations in existing tests by the one new line only.

## Phase 7: Presence (FR-007)

- [X] T024 [US5] Tests in tests/test_doctor.py: a configured repository without `.specify/` under default `[spec]` has a `<name> spec` fail row whose fix is `INSTALL['speckit']`; with `.specify/` ok; `engine = "none"` ok; `engine = "superpowers"` with a plugins file listing `superpowers@superpowers-marketplace` ok, without it fail, with the file unreadable unmeasured. Tests in tests/test_spec_mode.py for `present` and `detect` (openspec found and speckit not: `openspec`; nothing found: `speckit`; both: `speckit`). Red: no row.
- [X] T025 [US5] Implement `present` and `detect` in cli/wuwei/specmode.py and the row in the repository loop of cli/wuwei/commands/doctor.py.
- [X] T026 [US5] Tests in tests/test_interview.py: `question('spec')` exists with four choices setting `spec.engine`; `effects('spec', 'OpenSpec') == {'spec.engine': 'openspec'}`; `ask(['spec'], [], first={'spec': 'OpenSpec'})` prints OpenSpec as choice 1 and `1` picks it. Test in tests/test_setup.py: setup over a repository with `openspec/` asks the spec question with OpenSpec first and the proposal sets `spec.engine = "openspec"`. Red: unknown question.
- [X] T027 [US5] Add the `spec` row to `QUESTIONS` and the `first` parameter to `ask` in cli/wuwei/interview.py; pass the detected engine's label from cli/wuwei/commands/setup.py.

## Phase 8: Fixture days (FR-009)

- [X] T028 [US6] Tests in tests/test_e2e_day.py: in `test_scripted_day`, a PreToolUse Write of `memory/demo.py` after the builder brief and before the build is refused with `specify first: /speckit.specify`; after the day, exactly one `spec.step` per spec-kit step for A and the item merges. New `test_light_item_skips_spec`: candidate A with `tier: light` builds and reaches the gates with one `spec.skipped` and no `spec.step`. Test in tests/test_headless_e2e.py: `validate` without a `spec.skipped` event for A is a finding; `fixture_plan` writes `tier: light`. Red: no refusal, no events.
- [X] T029 [US6] Update tests/fakes/day.py (`Runtime.dispatch` builder branch writes and commits the spec-kit set through the hooks, last message names `specs/001-a`, `Day.plan` takes an optional tier) and scripts/headless_e2e.py (`fixture_plan` tier, `validate` requirement).
- [X] T030 Run `python -m pytest -q`. For each failing test that is not about spec mode and moves an item to the gates without artifacts, add `[spec]` `engine = "none"` to that test's workspace config; change no assertion. Rerun until green.

## Phase 9: Text (FR-008)

- [X] T031 [US5] Tests in tests/test_docs.py: `GLOSSARY` gains `('Spec engine', r'spec engines?')` and `('Strict mode', r'strict mode')` in concepts.md order; `test_configuration_names_every_config_section` now requires `[spec]`; a check that charters/builder.md names `Spec:` and `plan set`, charters/lead.md names `skip_tiers`. Red: missing entries.
- [X] T032 [US5] Write docs/site/concepts.md glossary entries, docs/site/configuration.md `[spec]`, docs/site/daily.md paragraph, docs/site/agent.md step and refusal bullet; charters/builder.md, charters/lead.md, charters/planner.md, skills/wuwei-plan/SKILL.md lines (bump charter versions if required); regenerate agents/ with `python3 -P -m wuwei agents build` and confirm `agents check` is clean.

## Phase 10: Verify

- [X] T033 Run `python -m pytest -q` (full suite green) and `python -m pytest -q tests/test_hooks.py` (the #346 tests unchanged and green).
- [X] T034 Run the plan's grep: step names, artifact names and `skip_tiers` appear in cli/wuwei only in specmode.py, workspace.py (schema) and interview.py (choice effects). Check every changed file for em-dashes, emojis and absolute local paths.
