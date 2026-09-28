# Implementation Plan: Signal classification and status line

**Branch**: `092-status-line` | **Date**: 2026-09-28 | **Spec**: `spec.md`

## Summary

Add a pure event classifier, one read-only status snapshot and two renderings. Print owner setup guidance at init.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Standard library
**Storage**: Existing day state and event JSONL
**Testing**: pytest
**Target Platform**: Claude Code plugin CLI
**Project Type**: CLI
**Performance Goals**: status line p95 CPU under 50 ms
**Constraints**: No writes from status or classification; three-state exits
**Scale/Scope**: Today's events and items

## Constitution Check

Stdlib only at runtime, fail closed, one classifier function, test first, read-only status and no owner settings writes. Design uses existing readers and `state.BUILD_PHASES`. These checks remain satisfied after design.

## Project Structure

`cli/wuwei/signal.py` owns the pure classifier. `cli/wuwei/commands/signal.py` and `cli/wuwei/commands/status.py` expose commands. `cli/wuwei/commands/init.py` prints setup guidance. `tests/test_signal_status.py` and the existing benchmark cover behavior.

## Data flow

The classifier accepts a parsed event and state and returns tier and lane. Status reads the validated state once, classifies each event record, counts build phases, selects earliest optional due times, and renders line or JSON. A state read failure produces exit 2.
