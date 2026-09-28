# Implementation Plan: CLI entry point

**Branch**: `002-cli-entry` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Use argparse for parsing, pkgutil.iter_modules and importlib for command discovery,
and a single dispatcher for exit validation and fail-closed diagnostics. Reuse the
existing plugin manifest and pytest configuration. No command registry or dependency added.

## Technical Context

- Language: Python 3.11+ and POSIX sh.
- Runtime dependencies: standard library only.
- Storage: existing `.claude-plugin/plugin.json`, read relative to the package.
- Testing: pytest, temporary fixture command modules, subprocesses without site packages.
- Platform: macOS and Linux with python3 on PATH.
- Scope: CLI foundation only; no persistent state or performance target.

## Constitution Check

Pre-design and post-design: PASS. Runtime is stdlib-only, exit handling has one owner,
all behavior gets failing tests first, no abstraction or external operation is introduced.
The supplied non-interactive spec-kit process governs this work. Extension hooks are skipped.

## Project Structure

- `cli/wuwei/__init__.py`: package marker.
- `cli/wuwei/exits.py`: CLEAN, FINDINGS, UNRUN constants.
- `cli/wuwei/__main__.py`: parser, manifest version, discovery, execution boundary.
- `cli/wuwei/commands/__init__.py`: command package and registration contract.
- `bin/wuwei`: executable POSIX shim resolving its directory, unsetting PYTHONEXECUTABLE,
  and using `python3 -I -P` for isolated startup and the Python 3.11+ gate.
  Prepend the explicit cli and plugin root arguments to sys.path, remove those arguments,
  and dispatch with runpy.run_module, using exec to preserve Python's exit status.
- `tests/test_cli.py`: entry point, discovery, return contract, and failure tests.
- `tests/test_stdlib.py`: AST import audit over cli and optional adapters.
- `specs/002-cli-entry/`: spec, plan, tasks, quality checklist, and command contract.

## Design Decisions

`main(argv=None)` builds the parser and dynamically imports command modules. Each module
exposes `register(subparsers)` and calls `set_defaults(func=handler)` on its parser.
Parsing stays outside the command exception boundary so argparse retains its normal exits.
Command execution catches BaseException to prevent SystemExit(0) from bypassing the contract.
An empty exception message falls back to its class name. Invalid results raise ValueError.
Setup exceptions also return UNRUN with a startup diagnostic. Version reads the manifest
rather than duplicating release metadata. Integer subclasses are accepted except bool.

No research or data-model artifact is needed: all choices are bound by the issue and there
is no new data model. The external command interface is documented in contracts/cli.md.

## Validation Strategy

Run each new behavior test to red before implementing it, then run the relevant group to
green. Fixture modules live only in temporary test directories. Test all valid exit statuses,
exception reasons, invalid values, usage, version, and shim argument forwarding. Use an AST
scan and a temporary forbidden-import mutation to prove dependency enforcement works.
Run the complete suite with the supplied interpreter and inspect changed files for banned
characters and whitespace errors. Leave all work uncommitted.
