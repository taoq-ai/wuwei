# Implementation Plan: Passive kanban dashboard

**Branch**: `028-kanban-dashboard` | **Date**: 2026-09-28 | **Spec**: `specs/028-kanban-dashboard/spec.md`

## Summary

Port the reference dashboard's passive fetch and interval refresh into a single-file kanban page. `wuwei dashboard` serves the page and board metadata from memory on loopback. The page polls state and events, which the server reads live from the day directory.

## Technical Context

- Runtime: Python 3.11+ standard library; inline HTML, CSS and JavaScript.
- Existing interfaces: `workspace.day_dir`, `state.read_state`, `state.PHASES`, command auto-discovery, state transition event payload.
- Testing: pytest with the issue interpreter; command and HTTP handler tests plus a Node render test when Node is installed.

## Constitution Check

- The dashboard reads state and events. The command keeps the page and board metadata in memory and never writes day files.
- It uses the existing state writer and event shape. No new dependency or service is added.
- Test each behavior red before code. Exit 2 prints operational errors. No engagement details ship.

## Project Structure

- `cli/wuwei/state.py`: phase ordering source shared with the board metadata.
- `cli/wuwei/commands/dashboard.py`: command and restricted local server.
- `templates/dashboard.html`: inline passive board, poll and render.
- `tests/test_dashboard.py`: command, handler and rendered board tests.

The existing state and event schema provides the data model. The command and page contract is small enough to state in the spec, so no separate research, data model, contracts or quickstart files are needed.
