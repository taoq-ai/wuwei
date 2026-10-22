# Tasks: the hook launcher finds a Python 3.11 or later

## Phase 1: Tests first

- [x] T001 Reproduce the report: a 3.9 `python3` shim alone on PATH makes main's launcher print "Unknown option: -P" and exit 2
- [x] T002 [US1] Acceptance 1 and 3 under sh, dash and bash; an old WUWEI_PYTHON falls through (tests/test_launcher.py)
- [x] T003 [US2] Acceptance 2 and no interpreter at all (tests/test_launcher.py)
- [x] T004 [US3] Acceptance 4 with a `py` shim; the `.cmd` bootstrap, order and fail-closed run; hooks.json `commandWindows` (tests/test_launcher.py)
- [x] T005 [US4] The doctor names the interpreter (tests/test_launcher.py)
- [x] T006 Run the new tests red

## Phase 2: Implementation

- [x] T007 Interpreter selection in `bin/wuwei`
- [x] T008 `bin/wuwei.cmd`, `commandWindows` in `hooks/hooks.json`, `*.cmd -text` in `.gitattributes`
- [x] T009 The interpreter in `hook.pre_tool` and `setup.doctor`
- [x] T010 Run the new tests green

## Phase 3: Docs and checks

- [x] T011 docs/design.md, docs/site/getting-started.md, docs/site/concepts/codex.md, README.md
- [x] T012 Re-vendor `.claude/` with setup.vendor('.')
- [x] T013 `sh -n`, `dash -n`, `bash -n`; the full suite once
