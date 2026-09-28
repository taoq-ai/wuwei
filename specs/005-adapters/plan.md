# Implementation Plan: Adapters

**Branch**: `005-adapters` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Use plain modules in `adapters/<kind>/none.py`, a single operation-name mapping in
`cli/wuwei/registry.py`, and a tiny shared result dataclass. Reuse `state.append_event`
and workspace discovery. No ABC, Protocol, external dependencies or subprocess calls.

## Technical Context

- Python 3.11+, standard library only; pytest for development.
- POSIX CLI plugin; existing append-only JSONL event storage with writer locking.
- Five adapter kinds and fifteen operations. Directory scans are small and uncached.
- Existing main-derived code supplies config schema, source-line helper, init and state.

## Constitution Check

Before and after design: pass. Runtime is stdlib-only; absent operations fail closed;
state remains the single event writer; tests precede implementations; event arguments
are omitted to protect secrets. Plain modules satisfy the explicit issue interface without
adding an abstraction. No git commits, pushes, network or extension hooks.

## Project Structure and Decisions

- `cli/wuwei/registry.py`: INTERFACES, Result, known(kind), load(kind, config), shared
  none-call recorder. Validate kind and scanned names before loading the discovered file by absolute path,
  independent of ambient Python package lookup. Reserved runtime
  claude is accepted by config check only; loading it fails explicitly until #26.
- `adapters/{tracker,chat,review_bot,runtime,scanner}/none.py`: explicit functions with
  section 8 positional parameters and optional keyword-only root. Namespace packages
  need no empty initializer files.
- `cli/wuwei/workspace.py`: after existing schema validation, validate repo requirements,
  uniqueness and installed adapter names. Reuse `_key_line`, tracking array-table indices
  so later repository diagnostics point to the correct entry.
- `cli/wuwei/commands/init.py`: recognizable tempfile prefix.
- `pyproject.toml`, `bin/wuwei`: include plugin root on import path.
- `tests/test_adapters.py`: all operation signatures, results, event payloads, I/O failure,
  discovery and import safety; shell entry point probe from outside plugin root.
- `tests/test_workspace.py`: unknown adapter diagnostics, required and unique repos, staging
  prefix; update former arbitrary adapter names to installed names.
- `tests/test_stdlib.py`: retain adapter tree coverage and allow the local adapters package.

## Validation Strategy

For each story write failing tests, run with the user-specified interpreter, implement,
then rerun. Keep failures and green summaries in tasks.md. Finish with the full suite,
`git diff --check`, and a scan of changed files for prohibited characters.

## Deferred

Runtime integrations remain #26. No extra design artifacts are needed: result, event and
module contracts are fully captured above and in the spec.
