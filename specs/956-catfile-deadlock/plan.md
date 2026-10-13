# Implementation Plan: Prevent git cat-file batch deadlock

**Branch**: `956-catfile-deadlock` | **Date**: 2026-10-13 | **Spec**: `spec.md`

## Summary

For `_run` calls with `input`, write bytes to `tempfile.TemporaryFile`, rewind, and pass the file as `stdin` to `subprocess.run`. Keep existing capture, timeout, and result handling. `read_tree` remains the only caller supplying input.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Standard library and git
**Storage**: Temporary file for one subprocess call
**Testing**: pytest with explicit test files and the provided interpreter
**Target Platform**: macOS and other supported POSIX hosts
**Project Type**: Claude Code plugin adapter
**Constraints**: No network, no new runtime dependency, 30 second subprocess timeout
**Scale/Scope**: One adapter function and its tests

## Constitution Check

Stdlib only, one shared implementation, test first, existing exit 2 error path, no new module. All pass. The design spec remains owner-only.

## Project Structure

- `adapters/vcs/git.py`: shared `_run` subprocess path.
- `tests/test_vcs.py`: large real git regression and existing adapter checks.
- `specs/956-catfile-deadlock/`: feature artifacts.

## Verification

Run the new regression before production code and observe the expected failure. Then run every test file importing `adapters.vcs.git` using the specified interpreter, explicit files, and `-p no:cacheprovider`.
