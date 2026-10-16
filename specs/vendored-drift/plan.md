# Implementation Plan: the vendored plugin in .claude/ matches the tree it was copied from

**Branch**: `claude/vendored-drift` | **Spec**: `specs/vendored-drift/spec.md`

## Summary

Add a drift test that runs `setup.vendor()` into a temporary directory and compares it byte for
byte with the committed `.claude/`. Add the copy's `plugin.json` to release-please's extra files.
Re-vendor `.claude/` at the head.

## Technical Context

Python 3.11 stdlib, pytest. The runtime budget (3,000 lines in `cli/wuwei/`) is full, so all new
code lives in `tests/test_setup.py`.

## Constitution Check

- I. Stdlib only: yes, the test uses `tempfile` and `pathlib`.
- II. Evidence over steps: the test reads the committed tree, not a step log.
- III. An auditor: no new door.
- V. Test first: the drift and release-please tests ran red before the config change and re-vendor.
- VI. Budgets: no config key; runtime unchanged at 3,000.

## Design

- `tests/test_setup.py`: `_files(root)` maps relative paths to bytes, skipping `__pycache__` and
  `.pyc`. `vendored_drift(repository)` vendors into a temporary directory and returns the sorted
  paths that are missing or different, plus extra files under `wuwei/` and WUWEI's skill folders.
- Three tests: the real repository has no drift; a mutated fresh copy reports exactly the changed,
  missing and extra paths while project agents, project skills and `__pycache__` stay quiet; the
  release-please config bumps both plugin.json files and their versions match.
- `release-please-config.json`: a second `extra-files` entry for
  `.claude/wuwei/.claude-plugin/plugin.json`.
- `.claude/`: rewritten by `setup.vendor('.')` from the worktree root.
- `docs/adr/0001-cut-1.2.1-before-1068.md`: the owner's one-way release decision.

## Rollback

Revert the PR. The copy goes back to 1.1.0 and the test and config entry go away; nothing else
reads them.
