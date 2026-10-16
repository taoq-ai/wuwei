# Implementation Plan: one plugin path and version read in ws, one git helper in guards, and two dead or one-caller definitions go

**Branch**: `claude/free-lines-3` | **Spec**: `specs/free-lines-3/spec.md`

## Summary

Drop `verdict.CONFIDENCE`, move the plugin root and the version read into `ws`, fold the two git
reads in `guards` into `_git`, inline `hook._confidence`, and re-vendor `.claude/`.

## Technical Context

Python 3.11 stdlib, pytest. The runtime is at 3,000 of 3,000 lines on main e34586d.

## Constitution Check

- I. Stdlib only: yes; no import added, one removed (`pathlib` in `__main__`).
- II. Evidence over steps: the doors still read origin and branch from git.
- III. An auditor: no new door, no route change; `tests/fixtures/routes.json` reads as recorded.
- V. Test first: the structural test and the session-start test (now reading `ws.PLUGIN`) ran red
  on main; the behaviour pins ran green on main and stay green after.
- VI. Budgets: runtime falls from 3,000 to 2,986; no config key.

## Design

- `cli/wuwei/verdict.py`: delete `CONFIDENCE`.
- `cli/wuwei/ws.py`: add `PLUGIN = Path(__file__).resolve().parents[2]` and `version()`.
- `cli/wuwei/__main__.py`: delete `PLUGIN`, `version()` and `from pathlib import Path`; use
  `ws.PLUGIN` and `ws.version()`.
- `cli/wuwei/hook.py`: delete `PLUGIN` and `_confidence`; use `ws.PLUGIN`; `subagent_stop` reads
  the confidence match in place.
- `cli/wuwei/setup.py`: delete `PLUGIN`; use `ws.PLUGIN` and `ws.version()`.
- `cli/wuwei/guards.py`: `PR_STANDARD = ws.PLUGIN / 'charters' / '_pr.md'`; the note uses
  `ws.version()`; add `_git(cwd, *args)` and rewrite `origin` and `current_branch` through it.
- Tests: `tests/test_setup.py` structural test; `tests/test_guards.py` origin and branch on a real
  repository, a bad cwd and a failing `subprocess.run`, and the full PR standard note text;
  `tests/test_hook.py` confidence high or null, and the session-start test reads `ws.PLUGIN`.
- `.claude/wuwei/`: rewritten with `setup.vendor('.')`.
