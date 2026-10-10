# Tasks: the same doctor answer from either install

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process and use the `ws` fixture of `tests/test_doctor.py` (patched
`integrity.PLUGIN`, pointer naming the patched launcher, fakes for every adapter) and the `day`
fixture and `brief` helper of `tests/test_brief.py`. Neutral fixtures only; paths come from
`tmp_path`. Run the touched test files after each pair, then the full suite
(`python -m pytest -q`).

## Phase 0: prerequisite

- [X] T000 Merge `origin/main` into the worktree. Confirm `integrity.recorded` exists in
  `cli/wuwei/integrity.py` (#601). If not, add it as `plan.md` shows and note it under Deferred.
  Grep the suite for `doctor.run(` and `['doctor'` and confirm none would hand over (plan.md,
  Test notes).

## Phase 1: hand-over (FR-001, FR-003, US1)

- [X] T001 Test in `tests/test_doctor.py`, `test_doctor_hands_over_to_the_pointer`: a second
  plugin directory `other` built like the fixture's (stub `bin/wuwei`, `hooks/hooks.json`,
  `.claude-plugin/plugin.json`, `MANIFEST.sha256.sig`); the pointer keeps naming
  `ws.plugin / 'bin/wuwei'`; `integrity.PLUGIN` patched to `other`; `os.execve` patched to raise
  a test exception with `(path, argv, env)`. For each options namespace, `doctor.run(args)`
  raises it with `path == str(ws.plugin / 'bin/wuwei')`, `argv` equal to
  `[path, 'doctor', ...]` with the same options (`--json`; `--fix`; `--fix --widget`;
  `--fix --apply calibrate`; `--section pr-flow`), and
  `env['WUWEI_DOCTOR_FROM'] == str(other / 'bin/wuwei')`, other variables kept
  (`WUWEI_WORKSPACE` present).
- [X] T002 Test in `tests/test_doctor.py`, `test_doctor_reports_here_without_a_hand_over`
  (parametrized; `os.execve` patched to fail the test if called; `doctor.run` with `json=True`
  returns and prints one JSON document with no `invoked` row): the pointer names the running
  launcher; the pointer names it through a symlinked directory; the pointer is missing; it names
  a file that does not exist; it names a file without the execute bit; `WUWEI_DOCTOR_FROM` is
  already set; a `confirm` callback is passed; there is no workspace (`WUWEI_WORKSPACE` unset,
  cwd `tmp_path`).
- [X] T003 Test in `tests/test_doctor.py`, `test_failed_hand_over_reports_here_with_a_warn_row`:
  `os.execve` patched to raise `OSError(8, 'Exec format error')`; `doctor.run` with `json=True`
  returns 1 and its rows hold one `invoked` row, status `warn`, value naming the pointer,
  `OSError` and the running launcher, without the text `Exec format error`, fix
  `<pointer> doctor`; all other rows equal `doctor.diagnose()`.
- [X] T004 Smoke test in `tests/test_doctor.py`, `test_hand_over_runs_the_pointer_launcher`
  (one real process, the only one): a workspace in `tmp_path` with `.wuwei/` and
  `.wuwei/executable` naming an executable `/bin/sh` stub in `tmp_path` that prints
  `$WUWEI_DOCTOR_FROM|$*`; run `[sys.executable, '-P', '-m', 'wuwei', 'doctor', '--json']` with
  `PYTHONPATH` set to the repository's `cli`, `WUWEI_WORKSPACE` set to the workspace and cwd the
  workspace. The output is `<repository>/bin/wuwei|doctor --json` and the exit code is the
  stub's (0). It fails before T005: doctor runs here and prints its own JSON.
- [X] T005 Implement `FROM`, `_hand_over` and the `run` change in
  `cli/wuwei/commands/doctor.py` (plan.md, doctor.py items 1, 2 and 4).

## Phase 2: the invoked row and the same findings (FR-002, US1, SC-001)

- [X] T006 Test in `tests/test_doctor.py`, `test_either_copy_prints_the_same_findings`: with
  `integrity.PLUGIN` at `ws.plugin` (the pointer's copy), the verdict's `plugin` set to a third
  path (write `.wuwei/integrity/verdict.json` with `integrity._record`, keeping `exit`,
  `fingerprint` and `reason` from `fakes.integrity.seed`), `direct = doctor.diagnose()`; then
  `WUWEI_DOCTOR_FROM` set to `other / 'bin/wuwei'`, `handed = doctor.diagnose()`. Assert the
  rows of `handed` without `invoked` equal `direct`, and exactly one `invoked` row, section
  `install`, status `ok`, value naming `other/bin/wuwei`, `ws.plugin/bin/wuwei` and the third
  path; `doctor.outcome(handed) == doctor.outcome(direct)`. Then the verdict without `plugin`:
  the value says `unknown`. Then `WUWEI_DOCTOR_FROM` equal to the running launcher: no
  `invoked` row. Then T001's hand-over from `other` names the same pointer launcher, so both
  copies reach the same rows.
- [X] T007 Implement `_invoked` and its call at the end of `_install` in
  `cli/wuwei/commands/doctor.py` (plan.md, doctor.py item 3).

## Phase 3: the seat brief (FR-004, US2, SC-002)

- [X] T008 Test in `tests/test_brief.py`, `test_every_brief_names_the_doctor_and_the_install_rule`:
  a builder brief (`brief(monkeypatch, 'body', 'builder', 'X', 'b1')`) and a sentinel brief
  (`'sentinel-arch'` with `--worktree tree`, as `test_stamped_header_and_fresh_pr` writes it):
  the header (text before the first blank line) of each contains `brief.DOCTOR`, and
  `brief.DOCTOR` contains `.wuwei/executable`, `doctor`, `owner` and `Next:`.
- [X] T009 Implement `DOCTOR` and its `header.append` after the `Scratch:` line in
  `cli/wuwei/brief.py`.

## Phase 4: docs and suite (FR-005, SC-003)

- [X] T010 Add the sentences of plan.md to the Doctor section of `docs/site/reference.md`.
- [X] T011 Run `tests/test_reasons.py`, `tests/test_tone.py`, `tests/test_docs.py`,
  `tests/test_integrity.py` (`test_core_never_imports_subprocess`), then the full suite. Check
  every file written for em-dashes, emojis and absolute local paths.

## Phase 5: review fixes

- [X] T012 Test then move the exec behind the host port: `hand_over(target, argv, env)` in
  `cli/wuwei/registry.py`, `adapters/host/local.py` (os.execve; a failed exec returns exit 2 and
  the exception class) and `adapters/host/none.py` (record_none); doctor skips the hand-over
  when `adapters.host` is `none` (review F1).
- [X] T013 Test then restrict `integrity.recorded` to a pointer file that is not a symlink naming
  an absolute `.../bin/wuwei`; cases `relative path`, `not a launcher`, `symlinked pointer` in
  `test_doctor_reports_here_without_a_hand_over` (review F2).
- [X] T014 Test then add the `hooks copy` warn row in `_invoked` whenever the verdict's `plugin`
  differs from the reporting copy, handed over or not (review F3).
