# Implementation Plan: Shared GitHub hold

**Branch**: `994-github-hold` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

## Summary

Use the existing workspace atomic writer and file lock for one hold record. Check it at the GitHub transport boundary before every `gh` subprocess. Write it on the first refusal and clear it on expiry. Preserve the existing cached listing refresh in `next` and `pr wait`; route PR state consumers through it where practical. Keep complete review and thread reads so a hold only defers them.

## Technical Context

- Python 3.11+, standard library runtime, pytest development tests.
- Workspace files and the existing GitHub adapter and PR listing are the storage and ports.
- Rate-limited and corrupt input exits are 2 with a safe reason.

## Constitution Check

- Test before implementation for each behavior.
- No subprocess in core; GitHub transport stays in its adapter.
- Workspace state writes are atomic; trust keys are reserved from seat writes.
- No new dependency, service or config value.

## Files

- `adapters/code_host/github.py`, `adapters/_http.py`: transport hold and refusal wording.
- `cli/wuwei/workspace.py`: workspace hold storage.
- `cli/wuwei/commands/config.py`, `cli/wuwei/commands/doctor.py`: pass workspace context to diagnostic GitHub reads.
- `cli/wuwei/watch.py`, `cli/wuwei/pr_actions.py`, `cli/wuwei/derive.py`: cached PR state, action verification and skipped shepherd duty handling.
- `tests/test_code_host.py`, `tests/test_pr_actions.py`, `tests/test_pr_wait.py`, `tests/test_derive.py`: regression tests.
