# Implementation Plan: Workspace

**Branch**: `003-workspace-init` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Add discovered init/config command modules. Keep discovery, clock, day paths and config
loading in `cli/wuwei/workspace.py`. Use one nested schema with typed defaults and a
recursive validator; report source locations with a documented best-effort text scan.
Copy `templates/workspace/` with shutil, refusing existing destinations.

## Technical Context

Python 3.11+, stdlib only: pathlib, datetime, os, shutil, re, tomllib. pytest for tests.
Storage is local files. No network or external tools. Existing CLI exception handling
maps unexpected failures to UNRUN; config validation maps to FINDINGS.

## Constitution Check

Pass before and after design: no runtime dependency, single shared implementation,
three-state exits, test first, no unrelated changes, no commits or pushes.

## Project Structure

- `cli/wuwei/workspace.py`: find_workspace(start=None), now(), day_dir(root=None), load_config(root=None), ConfigError.
- `cli/wuwei/commands/init.py`: register/run, copy skeleton with no overwrite.
- `cli/wuwei/commands/config.py`: register/check, findings printed to stderr.
- `templates/workspace/`: commented defaults and memory documents; gitkeeps in empty directories.
- `tests/test_workspace.py`: helper, config and real subprocess command tests.

## Implementation Strategy

US1 init skeleton first, US2 validation second, US3 location and clock integration third.
Each phase writes and runs failing tests before implementation. Final full suite, diff
review, and authored-text checks. Existing #2 command discovery and exits need no changes.
