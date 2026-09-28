# Implementation Plan: Read-only cockpit lanes

**Branch**: `093-cockpit-lanes` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing dashboard with a read-only JSON snapshot for decisions, people, PR references, attention, and briefing text. Render it with the existing escaped template and preserve the HTTP boundary.

## Technical Context

**Language/Version**: Python 3.11+, browser JavaScript
**Primary Dependencies**: Python stdlib only at runtime
**Storage**: Existing day files, read-only
**Testing**: pytest and existing Node render harness
**Target Platform**: Loopback browser
**Project Type**: CLI-served web page
**Constraints**: No POST, no state writes, exact Host, escaped fields

## Constitution Check

- Stdlib runtime: pass.
- Three-state behavior: unreadable snapshot reports unmeasured.
- One writer: no new writer.
- Test first: tests precede each implementation.
- Security: no page-derived authority or approvals.

## Project Structure

- `cli/wuwei/commands/dashboard.py`: snapshot and HTTP read path.
- `templates/dashboard.html`: lane rendering.
- `tests/test_dashboard.py`: in-process HTTP and Node rendering tests.

## Design

Serve `/cockpit.json` from current day state, D- and C- records, and the shared status snapshot. The PR row is sourced from `raised_prs` and `claimed_prs`; unavailable action fields are unmeasured. The briefing view reads one designated pack file if present. Keep the existing board and file routes. All POST methods return refusal.
