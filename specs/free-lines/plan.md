# Implementation Plan: the manifest signing code moves out of the runtime into the release script

**Branch**: `claude/free-lines` | **Spec**: `specs/free-lines/spec.md`

## Summary

Move the body of `cli/wuwei/integrity.py` into `scripts/build-release.py`, delete the module,
re-vendor `.claude/`, and add `tests/test_release.py` that builds and signs a release.

## Technical Context

Python 3.11 stdlib, pytest, `ssh-keygen` for signing. The runtime is at 2,999 of 3,000 lines.

## Constitution Check

- I. Stdlib only: yes; the script imports only the standard library.
- II. Evidence over steps: the test verifies the signed archive itself.
- III. An auditor: no new door.
- V. Test first: the new tests ran red (the module still existed; the script had no `inventory`).
- VI. Budgets: runtime falls from 2,999 to 2,939; no config key.

## Design

- `scripts/build-release.py`: the constants `KEY`, `MANIFEST`, `EXCLUDED`, `NAMESPACE` and the four
  functions, copied verbatim, then `build()` calling them directly. The `sys.path` insert and the
  `from wuwei import integrity` line go. `measure(plugin)` takes the stage explicitly.
- `tests/test_release.py`: loads the script with `importlib`. A fixture copies the shipped tree to
  a temporary root with a throwaway public key in `keys/`, sets the script's `ROOT`, and builds.
  Tests: verify the archive's manifest with `ssh-keygen -Y verify` and compare it with the shipped
  files; tamper `README.md` and expect `changed: README.md`; a symlink raises; no runtime module is
  or imports integrity.
- `.claude/`: rewritten by `setup.vendor('.')`.

## Rollback

Revert the commit. The workflow reads only `scripts/build-release.py`, and the old script imports
the restored module.
