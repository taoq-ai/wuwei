# Implementation Plan: codex.command doctor row

**Branch**: `871-codex-parallel` (batch) | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

One function in `doctor` says why an empty `codex.command` matters (`codex_gap`), one finds
the installed companion (`_companion`). `_host` appends the warn row; `plan.propose` and
`plan.gate_widget` append the reason to the seat-policy line.

## Technical Context

Python 3.11+ stdlib. Files: `cli/wuwei/commands/doctor.py`, `cli/wuwei/plan.py`. Tests:
`tests/test_doctor.py` (rows), `tests/test_plan.py` (seat-policy line).

## Constitution Check

- II: an unreadable plugins file is "no plugin", never an error row; the wanted conditions
  still raise the row.
- III: one function (`codex_gap`) for doctor and the gate.
- IV: failing tests first.
- V: reuses `scanner.mcp.plugins_file`; no new config key.

## Changes

1. `doctor.py`: `_companion(config)` reads `plugins_file`, returns the first existing
   `<installPath>/scripts/codex-companion.mjs` of a `codex@` entry, else None.
   `codex_gap(config, policy)` returns `'codex.command empty: runtime codex unavailable'`
   when the command is empty and Codex is wanted (runtime, second opinion, `budget.codex`,
   a policy runtime or alternate) or the companion exists, else ''. `_host` appends the row
   with today's seat policy when a day is open.
2. `plan.py`: `_policy(config, data)` renders the seat policy for the `Seat policy:` line in
   `propose` and the gate card's `seat policy` text, ending with ` (<gap>)` when
   `codex_gap(config, seat_policy)` is non-empty.
