# Tasks: --shadow means posture observe, and guards.mode retires

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names. Signatures, texts and placement are
in plan.md. Neutral fixture names only; no absolute local paths.

The trial config used below (call it TRIAL) is a workspace created in process with
`init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False))` (with
`WUWEI_WORKSPACE` removed), whose `config.toml` then gets `mode = "shadow"` inserted after
`[guards]` and `shadow_since = ""` replaced by `shadow_since = "2026-09-29"`; the
template's `posture = "guarded"` stays.

## Phase 1: Upgrade retires guards.mode (US1; FR-001, FR-002)

- [X] T001 In `tests/test_workspace.py`, add failing in-process tests:
  (a) TRIAL, `init.run(... upgrade=True, dry_run=True)` returns 0, stdout has exactly one
  line `Would upgrade config.toml: guards.mode = "shadow" becomes security.posture =
  "observe"`, and `config.toml` bytes are unchanged;
  (b) TRIAL, `upgrade=True, dry_run=False`: `tomllib` gives `security.posture ==
  'observe'`, no `mode` in `guards`, `shadow_since == '2026-09-29'`, `shadow_days == 7`;
  the raw text equals the input with only the `mode` line removed and the posture value
  changed (comment kept); a second upgrade prints `No workspace changes needed`;
  (c) `mode = "enforce"` instead: the dry run line is `Would upgrade config.toml: remove
  guards.mode = "enforce" (the default)` and the upgrade removes it with
  `security.posture` still `guarded`;
  (d) a config whose only posture setting is `[guards]\nmode = "shadow"` (no
  `[security]` table, e.g. the `previous_workspace` fixture plus that table): after the
  upgrade `security.posture == 'observe'`;
  (e) `security.posture = "strict"` plus `mode = "shadow"`: after the upgrade `observe`;
  (f) a layout the line edit does not reach, the quoted key `"mode" = "shadow"` under
  `[guards]`: upgrade returns 2, stderr has `cannot safely retire guards.mode`, and no
  file changed.
  Fails today: no rewrite line; (a) prints `No workspace changes needed`.
- [X] T002 In `cli/wuwei/commands/init.py`, add `_retired_mode` and call it in `upgrade`
  with its output lines and the `No workspace changes needed` condition (plan.md 4).
  T001 passes; run `tests/test_workspace.py`, `tests/test_config_transition.py`,
  `tests/test_setup.py`.

## Phase 2: One posture line with its source (US2; FR-003, FR-004)

- [X] T003 In `tests/test_posture.py`, add failing tests: `workspace.posture_source` of
  `load('')` is `'security.posture'` and of `load('[guards]\nmode = "shadow"\n')` is
  `'guards.mode = "shadow", deprecated; run doctor --fix'`; with `checked`, the config
  `[security]\nposture = "guarded"\n[guards]\nmode = "shadow"\n` prints
  `Posture: observe (from guards.mode = "shadow", deprecated; run doctor --fix)\n`,
  exactly one stdout line contains `deprecated`, no stdout line contains `guarded`, and
  the exit code equals `checked('', ...)`'s; `[security]\nposture = "observe"\n` prints
  `Posture: observe (from security.posture)\n` and no `deprecated`. Update
  `test_config_check_prints_posture` to the new header (plan.md "Tests that change").
  Fails today: no `posture_source`, header has no source, the deprecation is its own line.
- [X] T004 In `cli/wuwei/workspace.py` add `posture_source`; in
  `cli/wuwei/commands/config.py` `run`, print the one line and delete the deprecation
  block (plan.md 1, 2). T003 passes; run `tests/test_posture.py`,
  `tests/test_config_transition.py`.
- [X] T005 In `tests/test_doctor.py`, add a failing test with the `ws` fixture: config
  `CONFIG` with `[security]\nposture = "guarded"\n[guards]\nmode = "shadow"\nshadow_since
  = "2026-09-30"\n` before `[adapters]`; the `posture` row is `warn`, value
  `observe (from guards.mode = "shadow", deprecated; run doctor --fix)`, fix
  `wuwei init --upgrade`, `apply == 'init-upgrade'`. Then, with the real
  `init.upgrade` restored (keep a module-level reference taken before the fixture
  patches it), the `template` row is `warn`, `apply == 'init-upgrade'`, and its detail
  holds the `Would upgrade config.toml: guards.mode = "shadow" becomes security.posture =
  "observe"` line. Update `test_workspace_rows_healthy` and
  `test_workspace_calibration_and_shadow` as plan.md "Tests that change" says.
  Fails today: the posture row is `ok` with value `observe, 4 days left`, and the
  template row is `ok`.
- [X] T006 In `cli/wuwei/commands/doctor.py` `_calibration`, the posture row of plan.md 3.
  T005 passes; run `tests/test_doctor.py`.

## Phase 3: Template and setup --shadow (US3; FR-005)

- [X] T007 In `tests/test_docs.py` (next to the other template tests), add a failing test:
  the template text has no `guards.mode` and no line matching `^\s*mode\s*=`;
  `'mode' not in tomllib.loads(template)['guards']`; in the `[security]` section the first
  non-comment, non-blank line starts with `posture =`, and the comment lines before it
  include one starting `# observe:`, one `# guarded:` and one `# strict:`. In
  `tests/test_setup.py::test_one_command_three_repositories`, extend the #345 assertion:
  `'mode' not in tomllib.loads((project / '.wuwei/config.toml').read_text())['guards']`
  and `shadow_since == '2026-10-03'` (passes already; regression guard). In
  `tests/test_workspace.py`, `init --shadow` writes `security.posture == 'observe'` and
  today's `shadow_since`, and `init --posture strict` writes `strict`, both read with
  `tomllib` (keeps the `run` replace honest after the reorder).
  Fails today: `posture` is the second key and the profile comments are missing.
- [X] T008 In `templates/workspace/config.toml`, the `[security]` block of plan.md 5. T007
  passes; run `tests/test_docs.py`, `tests/test_workspace.py`, `tests/test_setup.py`,
  `tests/test_interview.py`, `tests/test_config_transition.py`,
  `tests/test_config_failure.py`.

## Phase 4: Docs (US4; FR-006)

- [X] T009 In `tests/test_docs.py`, add a failing test: the `guards.mode` row of
  `docs/site/configuration.md` contains `doctor --fix` and `init --upgrade`; the
  `security.posture` row contains `--shadow` and `guards.shadow_days`;
  `docs/site/security.md` contains `setup --shadow` and no longer contains
  `` `guards.mode = "shadow"` (`init --shadow`) counts as `observe` ``.
  Fails today: the rows and the sentence are the old ones.
- [X] T010 In `docs/site/configuration.md` and `docs/site/security.md`, the edits of
  plan.md 6. T009 passes; run `tests/test_docs.py`.

## Phase 5: Full suite

- [X] T011 Run `python -m pytest -q` from the repository root; everything passes. Check
  every file you wrote for em-dashes, emojis and absolute local paths.
