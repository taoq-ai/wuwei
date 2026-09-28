# Implementation Plan: Optional SwiftBar indicator

**Branch**: `094-swiftbar` | **Date**: 2026-09-28 | **Spec**: `specs/094-swiftbar/spec.md`

## Summary

Ship one SwiftBar plugin template that reads the existing workspace executable pointer and calls `status --json`. Parse the snapshot with Python 3.11 standard library and render SwiftBar text. Add `wuwei init --menu-bar` as read-only installation guidance on macOS. A menu_bar port would have only one implementation now, so defer it.

## Technical Context

- Runtime: shell script and Python 3.11 standard library.
- Existing interfaces: `.wuwei/executable`, `bin/wuwei`, and `status --json`.
- Verification: pytest fixture-driven plugin process tests and CLI guidance tests.

## Constitution Check

- No new dependency or state writer. Status is read-only.
- A failed measurement prints an unknown mark and exits 2 with a reason.
- Each behavior gets a failing test before its implementation.

## Project Structure

- `templates/swiftbar/wuwei.1m.sh`: optional plugin.
- `cli/wuwei/commands/init.py`: read-only setup guidance.
- `tests/test_swiftbar.py`: fixture rendering and setup tests.

The existing status schema is the data contract. No separate research, data model, contracts, or quickstart file adds useful information.
