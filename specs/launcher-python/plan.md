# Implementation Plan: the hook launcher finds a Python 3.11 or later

**Branch**: `leone/launcher-python` | **Spec**: `specs/launcher-python/spec.md`

## Summary

`bin/wuwei` probes candidates with `-V` and runs the first at 3.11 or later; `bin/wuwei.cmd` does
the same for cmd.exe; `hooks/hooks.json` names the `.cmd` in `commandWindows`; the doctor names the
interpreter.

## Technical Context

POSIX sh and cmd.exe batch; Python 3.11 stdlib. Tests in `tests/test_launcher.py` with shim
interpreters written by code. Runtime budget 3,600 lines; main is at 3,399.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no door changes; the fail-closed bootstrap is unchanged and shared by AST.
- V. Test first: the new tests ran red (18 failed, 1 passed) before the change.
- VI. Budgets: no config key; runtime +2 lines.

## Design

- `fits` in sh runs `"$@" -V`, strips `Python `, and matches 3.11 to 3.19, 3.20 and up, or 4 and
  up with a `case` glob. A miss appends the interpreter and its version, or "not found", to `tried`.
- The `.cmd` reads `-V` with `for /f` through `call`, so a quoted path with spaces works, and
  compares major and minor with `set /a`. The bootstrap is the sh code as one `exec` literal with
  `\x22` for each double quote, so cmd.exe sees no quote, percent or caret inside it.
- `hook.pre_tool` stores `sys.executable` and the version beside the hook-seen stamp; the doctor
  appends it to the hooks row, and its python row names `sys.executable`.
