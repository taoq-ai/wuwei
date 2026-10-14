# Implementation Plan: Safer defaults and finite duties

**Branch**: `995-defaults-duties` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

## Summary

Extend trust path defaults, suppress terminal PR pings, read acknowledgements from earlier day state, and verify the existing zero memory default with a 30 percent owner override.

## Technical Context

**Language/Version**: Python 3.11+
**Dependencies**: stdlib runtime, pytest tests
**Storage**: Existing config and day state files
**Testing**: Explicit pytest files with the issue interpreter
**Platform**: Developer workstations

## Constitution Check

- Stdlib runtime and existing adapters: pass.
- Three-state errors: unreadable history fails closed.
- Single writer: acknowledgement writes stay in the existing state writer.
- Test first: one red test before each behavior change.
- Simplicity: reuse config, glob matcher, duty derivation and day readers.

## Project Structure

Changes use `cli/wuwei/workspace.py`, `cli/wuwei/derive.py`, `cli/wuwei/obligations.py`, existing callers and their tests, including the loop's duty oracle.

## Design

Trust path defaults gain patterns for the five sensitive families; the existing matcher prints the path and rule in a brief. Duty derivation checks PR state before adding a ping. The acknowledgement reader overlays current day records on earlier day records, then existing fingerprint and host reply checks validate them. The existing zero memory default remains in place; owner settings override it.
