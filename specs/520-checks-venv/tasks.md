# Tasks: a fast check that names a per-worktree virtualenv runs in a fresh item worktree

Test first: each test task is written, run and seen to fail for the expected reason before its
implementation task. Fixtures are neutral (repository `example/project` or `app`, item `A` or
`X`), built under `tmp_path`; a stub interpreter is a `#!/bin/sh` script made executable, never
a real virtualenv. Run `python -m pytest -q` from the repository root.

## Phase 1: config (FR-001)

- [X] T001 Test in `tests/test_workspace.py`: a config without `[checks]` loads with
  `config['checks'] == {'python': '', 'bootstrap': ''}`; `[checks] python = 1` is a config
  error naming `checks.python`; `[checks] pyhton = "x"` is an unknown-key warning.
- [X] T002 Implement in `cli/wuwei/workspace.py`: `"checks"` in `SCHEMA`, bump
  `CONFIG_CACHE_VERSION`; add the commented `# [checks]` example to
  `templates/workspace/config.toml`.

## Phase 2: the shared helper (FR-002)

- [X] T003 Test in `tests/test_fast_checks.py` (table over `fast_checks.interpreter` with a
  main directory and a worktree directory under `tmp_path`, stub files created per case):
  `python3 -m pytest -q` gives `None`; `.venv/bin/python -m pytest -q` with the file in both
  gives the worktree path, `worktree`; only in main gives the main path, `main worktree`;
  in neither gives the worktree path, `missing`; a broken symlink in the worktree and a file in
  main gives `main worktree`; `checks.python` set to an absolute stub path under `tmp_path` gives that path,
  `checks.python`, even when the worktree has one; `checks.python = "envs/py/bin/python"`
  resolves under main; `node_modules/.bin/jest` with `checks.python` set and the file only in
  main gives `main worktree`.
- [X] T004 Implement `RELATIVE` and `interpreter(command, worktree, repo, root, config)` in
  `cli/wuwei/fast_checks.py`.

## Phase 3: run and record (FR-003, US1, US2)

- [X] T005 Test in `tests/test_fast_checks.py` (US1 scenario 1, the issue's first
  acceptance): `workspace_case` with `fast_checks = [".venv/bin/python -m pytest -q"]`, the
  main worktree `root/repo` holding an executable stub `.venv/bin/python` that exits 0, an
  item worktree `root/worktrees/A` without `.venv`, a build record for `A` in `check` status on
  that worktree, the real `adapters/checks/local.py` for `checks` (fake vcs for the rest):
  `main(['build', 'check', 'A']) == 0` and the record for the configured command has
  `exit == 0` and `interpreter == str(root / 'repo/.venv/bin/python')`. Without the fix it
  exits 1 with `No such file or directory`.
- [X] T006 Test in `tests/test_fast_checks.py` (US2, the issue's second acceptance): with
  `[checks] python` pointing at a stub outside both worktrees and a stub that exits 1 in each
  worktree's `.venv`, `fast-checks` on the main worktree and on the item worktree both exit 0
  and both records carry the configured path; a path containing a space still runs (quoting).
- [X] T007 Test in `tests/test_fast_checks.py` (US1 scenarios 2 and 3, edge): with the stub in
  the worktree itself, the fake checks runner receives the command unchanged and the record
  carries the worktree path; with no stub anywhere the runner receives the command unchanged
  and the record carries `interpreter: None`; the existing
  `test_recorder_runs_configured_check_and_records_derived_evidence` keeps its exact record
  (no `interpreter` key for `unit`).
- [X] T008 Implement in `cli/wuwei/fast_checks.py` (`record`, lines 36-47): resolve, rewrite
  for `checks.python` and `main worktree`, add `interpreter` only for relative-interpreter
  commands.

## Phase 4: worktree add (FR-004, US3)

- [X] T009 Test in `tests/test_worktree_command.py` (US3 scenario 1, the issue's third
  acceptance): a real git repository initialised in `tmp_path` (one commit, no clone of this
  repository), configured with `fast_checks = [".venv/bin/python -m pytest -q"]` and
  `[checks] bootstrap` that appends a line to a counter file and writes an executable stub
  `.venv/bin/python`; `main(['worktree', 'add', 'X']) == 0`, the counter has exactly one line,
  `worktrees/X/.venv/bin/python` exists, and `fast-checks` in `worktrees/X` records
  `interpreter == str(tree / '.venv/bin/python')` with exit 0.
- [X] T010 Test in `tests/test_worktree_command.py` (US3 scenarios 2 and 3): a checks port
  that returns `Result(1)` for the bootstrap (the local adapter maps any non-zero exit to 1)
  leaves exit 0, the JSON on stdout, and exactly one stderr line starting
  `wuwei worktree warning: checks.bootstrap exited 1`; a port returning `Result(2, reason=...)`
  gives one line with `exited 2` and the reason; with no bootstrap and the stub only in
  the main worktree, stderr has one `wuwei worktree warning:` line naming the main worktree's
  `.venv/bin/python` and `[checks] bootstrap`; with `fast_checks = ["python3 -m pytest -q"]`
  stderr has no warning. Use the fake vcs fixture with a fake `checks` port where real git is
  not needed.
- [X] T011 Implement in `cli/wuwei/commands/worktree.py` (after `create_worktree`, line 34):
  bootstrap through the checks port, else the per-check warning.

## Phase 5: doctor (FR-005, US3 scenario 4)

- [X] T012 Test in `tests/test_doctor.py` with the `ws` fixture: `fast_checks =
  [".venv/bin/python -m pytest -q"]` and a stub in `repo/.venv/bin/python` gives an `ok`
  `acme/widget check interpreter` row naming the path; without the stub a `warn` row whose fix
  names `[checks] python` and `[checks] bootstrap`; the default `ruff check .` repository has
  no such row (existing row list at line 295 unchanged).
- [X] T013 Implement in `cli/wuwei/commands/doctor.py` (after the `fast_checks` row, line
  331).

## Phase 6: builder brief (FR-006, US4)

- [X] T014 Test in `tests/test_brief.py` with the `day` fixture: a builder brief with a
  worktree whose repository's fast check is `.venv/bin/python -m pytest -q` and a stub only in
  the main worktree has one header line
  `Check interpreter: .venv/bin/python -m pytest -q runs with <main path> (main worktree)`;
  a gate brief and a builder brief for `python3 -m pytest -q` have none.
- [X] T015 Implement in `cli/wuwei/brief.py` (after the specmode line, 374-378).

## Phase 7: docs (FR-007)

- [X] T016 Run `tests/test_docs.py::test_configuration_names_every_config_section`; it fails
  after T002 until `[checks]` is listed.
- [X] T017 Implement in `docs/site/configuration.md`: `[checks]` in the Sections table,
  `checks.python` and `checks.bootstrap` rows, the extended `repos.fast_checks` row.

## Phase 8: verify

- [X] T018 Run `python -m pytest -q`; all pass. Check the changed files for em-dashes, emojis
  and absolute local paths.
