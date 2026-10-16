# Feature Specification: one plugin path and version read in ws, one git helper in guards, and two dead or one-caller definitions go

**Feature branch**: `claude/free-lines-3`
**Item**: free-lines-3, tier full, goal G-2
**Input**: `cli/wuwei` holds 3,000 of 3,000 lines on main e34586d, so #1085's fix and the door
fixes cannot land.

## The promise in my words

Four edits free 14 runtime lines and change no behaviour:

1. `verdict.CONFIDENCE` has no reader in `cli/` or `tests/`. It goes.
2. `Path(__file__).resolve().parents[2]` is written four times (`__main__.PLUGIN`, `hook.PLUGIN`,
   `setup.PLUGIN`, `guards.PR_STANDARD`) and `plugin.json`'s version is read three times
   (`__main__.version`, `guards.bash`, `setup.init`). `ws` gains `PLUGIN` and `version()`; the
   others use them, and `__main__` drops its unused `pathlib` import.
3. `guards.origin` and `guards.current_branch` share one `_git(cwd, *args)` helper with the same
   5 s timeout, answering `''` on `OSError` or `SubprocessError`.
4. `hook._confidence` has one caller, `hook.subagent_stop`, which reads the match in place.

The runtime drops from 3,000 to 2,986 lines. No CLI flag, output, config key or guard route
changes. Moving `replay.py` and `wuwei evidence --record` into `scripts/` stays out: it removes a
documented flag.

The acceptance scenarios, restated:

1. After the change the runtime is 2,987 lines or fewer and the whole suite passes, the
   vendored-drift test included after re-vendoring.
2. Under `cli/wuwei`, `Path(__file__).resolve().parents[2]` appears once (in `ws.py`),
   `plugin.json` is read once, and no module defines `CONFIDENCE` or `_confidence`.
3. In a scratch git repository with origin `https://github.com/o/r.git` on branch `i-1-x`,
   `guards.origin` answers `o/r` and `guards.current_branch` answers `i-1-x`; with a cwd that is
   not a directory both answer `''`.
4. A seat report ending `Confidence: High (reason)` records `confidence: high` on `seat.stopped`;
   with no Confidence line it records null, as on main.
5. `wuwei --version`, `wuwei agents build` and the first PR-create note give main's version and
   PR standard text.

## Clarifications

### Session 2026-10-16

- Q: Does the inlined confidence read still answer null with no match? A: Yes. It is
  `(m := re.search(...)) and m[1].lower()`, which is `None` when the search finds nothing. The
  `or ''` guard went because `last_text` always returns a string (`transcript` starts `found` at
  `''` and assigns only strings).
- Q: Does `setup.init` read the version the same way? A: It read without an explicit encoding;
  `ws.version()` reads as UTF-8. `plugin.json` is ASCII, so the recorded value is the same.
- Q: Does the vendored copy still find its own plugin root? A: Yes. `ws.py` sits at the same depth
  (`<root>/cli/wuwei/ws.py`) as the modules that held the path, so `parents[2]` names the same
  root, `.claude/wuwei` in a vendored copy. `test_init_cloud_vendors_the_plugin_into_the_repository`
  runs the vendored `--version`.
- Q: Should the size budget test tighten to 2,987? A: No. The freed lines are room for the next
  items; acceptance 1 is held by the line count at the head and the 3,000 budget test.

## User scenarios

### US1: the runtime has room for the next fixes (P1)

Acceptance 1 and 2. Tests: `tests/test_setup.py::test_the_runtime_holds_its_size_budget`,
`tests/test_setup.py::test_one_module_holds_the_plugin_path_and_its_version_and_dead_definitions_are_gone`,
`tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from`.

### US2: the doors read origin and branch as before (P1)

Acceptance 3. Tests:
`tests/test_guards.py::test_origin_and_branch_read_a_real_repository_and_answer_blank_on_a_bad_cwd`,
`tests/test_guards.py::test_origin_and_branch_answer_blank_when_git_cannot_run`.

### US3: seat confidence is recorded as before (P1)

Acceptance 4. Test: `tests/test_hook.py::test_a_seat_records_its_confidence_or_null`.

### US4: version and PR standard text are unchanged (P1)

Acceptance 5. Tests: `tests/test_setup.py::test_version_is_the_plugin_version`,
`tests/test_guards.py::test_the_pr_standard_note_is_the_charter_with_the_plugin_version`,
`tests/test_setup.py::test_the_generated_agents_match_the_charters` (and `bin/wuwei agents build`).

## Requirements

- FR-001: `verdict.py` defines no `CONFIDENCE`.
- FR-002: `ws.py` defines `PLUGIN` and `version()`; `__main__`, `hook`, `setup` and
  `guards.PR_STANDARD` use them; no other module computes the plugin root or reads `plugin.json`.
- FR-003: `guards._git(cwd, *args)` runs `git -C cwd ...` with a 5 s timeout and answers `''` on
  `OSError` or `SubprocessError`; `origin` and `current_branch` call it.
- FR-004: `hook.py` defines no `_confidence`; `subagent_stop` records the same value.
- FR-005: `.claude/wuwei/` is rewritten by `setup.vendor('.')`.
- FR-006: No CLI flag, output, config key or guard route changes.

## How this fails

1. The vendored copy resolves `ws.PLUGIN` to the wrong root and session start, `--version` or
   `agents check` read the wrong tree. Guarded: `ws.py` has the same depth; the vendored
   `--version` test runs the copy.
2. `_git` drops the timeout or lets an error escape, so a hung or missing git blocks or crashes
   every Bash call through the doors. Guarded: a test raises `OSError` and `TimeoutExpired` from
   `subprocess.run` and expects `''` from both readers; a `return None` mutant is killed.
3. The inlined confidence read changes its result (case, null, or a crash on an empty report), so
   the ledger's seat confidence drifts. Guarded: a parametrised test for `High` and for no line; a
   mutant without `.lower()` is killed.

## Assumptions

- Tier full because `guards.py` and `hook.py` hold the doors, as for free-lines-2. Overturned if
  the owner rates a behaviour-neutral change lower.
- `ws` is the home for the plugin path because every module already imports it. Cheap to move.

## Success criteria

- SC-001: The suite passes at the head.
- SC-002: `cli/wuwei/` holds 2,986 lines.

## Rollback

Revert the commit. No data, config or CLI output changes.
