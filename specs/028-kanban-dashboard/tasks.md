# Tasks: Passive kanban dashboard

**Input**: `specs/028-kanban-dashboard/spec.md` and `plan.md`.

## Phase 1: Serve today's board

- [X] T001 [US2] Write failing tests for loopback serving, in-memory page and board metadata, no day writes, HTTP allowlist and Host refusal; run them and inspect the expected failures.
- [X] T002 [US2] Implement the serve-only command and restricted handler. Read state and events live per request; run T001 tests.

## Phase 2: Render the passive flow

- [X] T003 [US1] Replace static page checks with a Node render test for phase columns, other, and the escalated D-3 card with time in phase; run it.
- [X] T004 [US1] Escape CAP, remove the recent events list, and define build phases once in state; verify the render and phase tests.

## Phase 3: Hygiene and verification

- [X] T005 Replace the hard-coded test interpreter with `sys.executable -P` and add a git-tracked text path hygiene test.
- [X] T006 Run the full issue interpreter test command and inspect the diff.

## Dependencies

T001 precedes T002. T003 precedes T004. T006 follows both stories and T005.

## Deferred

Mandatory metadata and rank schema belong to the item intake or state writer issues.
