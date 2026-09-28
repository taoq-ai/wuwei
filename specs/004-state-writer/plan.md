# Implementation Plan: State writer

**Branch**: `004-state-writer` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Add one state module and thin argparse registrations. Reuse workspace.day_dir and
workspace.now. No runtime dependencies or additional clock/locator.

## Technical Context

Python 3.11+, stdlib json, tempfile, os, fcntl and pathlib. Tests use pytest and
real subprocesses with the task's interpreter. Storage is today's state.json and
events.jsonl. POSIX filesystem locking is an intentional platform limit.

## Constitution Check

Stdlib only; three-state exits; one writer module; tests before implementation;
no classes except a finding exception; no adapters or new infrastructure. PASS.

## Project Structure

- cli/wuwei/state.py: defaults, validation, read_state, write_state, append_event,
  get/set path and transition helpers.
- cli/wuwei/commands/state.py: state get/set/transition registration and exits.
- cli/wuwei/commands/event.py: event registration.
- tests/test_state.py: persistence, schema, lifecycle, concurrency and failures.

## Design

write_state accepts an updater callback, plus optional
workspace root and event metadata. It obtains a sidecar state.lock flock before
reading state and calling the updater. All mutations normalize defaults and validate
schema. Existing item phase changes use one transition dictionary, including
writer-managed resume_phase. Temp files live beside state.json and are replaced
with os.replace after flush and fsync; the directory is then fsynced where supported,
and cleanup runs on exceptions. The lock spans the event append too.

append_event takes the same state lock, then a shared internal helper serializes an object with kind, payload and workspace.now().isoformat()
into UTF-8 plus one newline, opens O_APPEND|O_CREAT|O_WRONLY, and uses exactly one
os.write. Short writes raise OSError. No retries that could split one event into
multiple appends. Serialization rejects non-finite JSON numbers before state changes.

The directory is resolved once per write and passed to read_state and the internal event helper
so midnight cannot switch files during an operation. Event ts still uses the clock
at append time.

read_state returns fresh defaults only on FileNotFoundError; corrupt JSON and I/O
errors propagate to the existing CLI error handler as exit 2. Schema violations and
illegal transitions use a ValueError subclass mapped to exit 1 by the state command.
Missing paths and malformed CLI JSON are exit 2. Reads never create the day directory.

## Validation Strategy

First add persistence/schema/atomicity/concurrency tests and observe failures, then
implement US1. Next add lifecycle table and resume tests, observe failures, and
implement US2. Finally test explicit events and short writes before US3. Run the
full requested pytest command, review the diff and scan authored files for banned
characters. All user stories run sequentially because they share one writer module.

## Limitations

One atomic file replacement plus one append is not a two-file transaction. Power-loss
recovery and Windows support are deferred. No WAL, recovery service or schema framework.
