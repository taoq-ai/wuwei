# Implementation Plan: Live cockpit owner surfaces

**Branch**: `178-cockpit-live` | **Date**: 2026-09-29 | **Spec**: `specs/178-cockpit-live/spec.md`

## Summary

Map the existing PR state producer into cockpit rows, read the latest producer-recorded briefing path, show pending CLI commands, and read reply and calendar timing in the status snapshot.

## Technical Context

**Language/Version**: Python 3.11+ and existing browser JavaScript  
**Primary Dependencies**: Python stdlib and existing ports  
**Storage**: Daily state and pack files  
**Testing**: pytest with in-process fake ports  
**Target Platform**: Local WUWEI workspace  
**Project Type**: CLI and loopback cockpit  
**Constraints**: Three-state exits; no network in tests; no new runtime dependencies

## Constitution Check

- Reuse existing state, PR, calendar, and briefing producers.
- Test each behavior before implementation.
- Fail closed on invalid producer records and unreadable files.

## Project Structure

- `cli/wuwei/commands/dashboard.py`: cockpit mapping and pack read.
- `cli/wuwei/commands/status.py`: reply and calendar status inputs.
- `templates/dashboard.html`: action commands and drafts display.
- `tests/test_dashboard.py`, `tests/test_signal_status.py`: regression scenarios.

## Deferred

- Draft creation and approval lifecycle belong to #174.
- Person reply obligation population belongs to its upstream producer.
