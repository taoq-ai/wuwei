# Tasks: Memory index and payload

**Input**: `specs/030-memory-index/spec.md` and `plan.md`.

## Phase 1: Index

- [X] T001 [US1] Write failing tests for note and past day ordering, body-only line change, and byte stability in `tests/test_memory.py`; run and confirm failure.
- [X] T002 [US1] Implement index rendering, atomic write and CLI registration; run T001 tests.
- [X] T003 [US1] Write failing tests for invalid notes, max note overflow, config validation and operational errors; run and confirm failure.
- [X] T004 [US1] Implement finding statuses and `memory.max_notes`; run T003 tests.

## Phase 2: Payload

- [X] T005 [US2] Write failing tests for spine, index, today's state, sizes and missing sources; run and confirm failure.
- [X] T006 [US2] Implement payload function and CLI registration; run T005 tests.

## Phase 3: Verification

- [X] T007 Run the full issue interpreter test command; inspect written files for em-dashes and emojis.
- [X] T008 Write and run failing review regression tests for invalid UTF-8 notes, symlinked day paths, missing notes and config, invalid slugs, day sorting and index mode.
- [X] T009 Fix index and payload behavior, reuse the note slug rule, and extract the shared atomic writer without changing note create semantics.
- [X] T010 Write and run failing tests for an undecodable report and payload without a promote line.
- [X] T011 Treat an undecodable report as an index finding and remove ledger reading and rendering from payload.

## Dependencies

T001 before T002; T003 before T004; T005 before T006; T008 before T009; T010 before T011; T007 after all behavior tasks.

## Deferred

SessionStart hook is issue #15. Archiving, the last promote line and its ledger contract are issue #81.
