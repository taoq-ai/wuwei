# Tasks: a scratch analysis.md is an ordinary write for WUWEI, and the builder knows why Claude Code refuses it

Test first: each test task runs and fails for the expected reason before its implementation
task. T001 pins behaviour the guard already has, so its red run comes from a temporary name
match (T002), reverted before the green run. Run only the touched test files, then the full
suite.

## Phase 1: the spec guard decides by path (FR-001, FR-002, US1, US2.1)

- [X] T001 Test in `tests/test_spec_mode.py`:
  `test_spec_guard_decides_by_path_not_by_file_name` (#649), after
  `test_pre_tool_use_refuses_source_edits_until_the_spec`, reusing `ws`, `item`, `write`,
  `hook`, `kinds` and `FIXTURES` (plan.md steps 1 to 5): a Write and an Edit of
  `tmp_path / 'scratch/analysis.md'` exit 0 with empty stdout and stderr and no `spec.*` or
  `hook.*` event; in the worktree before the steps, `scratch/analysis.md` and
  `scratch/notes.txt` exit 2 with equal stderr naming `specify first`;
  `specs/001-a/analysis.md` exits 0; with the fixture minus `specs/001-a/analysis.md`, a Write
  of `src/app.py` exits 2 and stderr names `bin/wuwei spec analysis a`; with the full fixture,
  `scratch/analysis.md` exits 0.
- [X] T002 Red check in `cli/wuwei/guards/spec.py`: add a temporary
  `if Path(path).name == 'analysis.md': return 1, 'x'` in `check_edit`, run T001, see it fail
  on the outside-worktree case (exit 2), then remove the line so the file is unchanged. Run
  T001 green. Record both runs in the handoff. No lasting change to this file (FR-001).

## Phase 2: the builder charter names the real check (FR-003, US2.2)

- [X] T003 Test in `tests/test_charters.py`:
  `test_builder_names_claude_codes_report_file_check` asserts `charter_text()["builder.md"]`
  contains `wuwei spec analysis <item>` and `in any directory`. Red: the second anchor is
  missing.
- [X] T004 Edit `charters/builder.md`: replace the "A subagent cannot write spec-kit's
  `analysis.md`" sentence with the plan.md wording and bump `version: 1.2.0` to `1.2.1`.
- [X] T005 Regenerate `agents/builder.md` with `bin/wuwei agents build`; run
  `tests/test_agents.py` and `tests/test_charters.py` green (no drift, no `BLOCKING` match).

## Phase 3: docs (FR-004)

- [X] T006 Edit `docs/site/configuration.md` line 119 to the plan.md wording; run
  `tests/test_docs.py` green.

## Phase 4: verify

- [ ] T007 Run `python -m pytest -q` from the worktree root; everything passes. Check the
  changed files for em-dashes, emojis and absolute local paths.
