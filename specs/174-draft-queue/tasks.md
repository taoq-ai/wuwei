# Tasks: Owner draft queue

## Setup

- [X] T001 Read repository policy and existing outward/state/voice/cockpit flows; write specs/174-draft-queue/spec.md and plan.md.

## US1: Queue approve-tier replies

- [X] T002 [US1] Write and run failing queue creation, invalid policy/security and producer-only tests in tests/test_drafts.py and tests/test_state_allowlist.py.
- [X] T003 [US1] Implement queue creation and listing in cli/wuwei/drafts.py, cli/wuwei/commands/drafts.py, cli/wuwei/registry.py, cli/wuwei/state.py and cli/wuwei/commands/event.py.

## US2: Owner decisions

- [X] T004 [US2] Write and run failing approval, edit, drop, lint/error/repeat/concurrency and host-only guard tests in tests/test_drafts.py.
- [X] T005 [US2] Implement decisions using the shared state writer, editor adapter and security/voice lint in cli/wuwei/drafts.py and cli/wuwei/commands/drafts.py; extend cli/wuwei/guards/protect_state.py.

## US3: Visibility and metrics

- [X] T006 [US3] Write and run failing metrics, cockpit queue and escaped rendering tests in tests/test_drafts.py and tests/test_dashboard.py.
- [X] T007 [US3] Implement per-audience voice metrics and read-only cockpit in cli/wuwei/metrics.py, cli/wuwei/commands/dashboard.py and templates/dashboard.html.

## Integration checks

- [X] T008 [US3] Run failing draft signal routing and event-inventory tests in tests/test_signal_status.py; update the obsolete no-event expectation in tests/test_profiles.py.
- [X] T009 [US3] Route draft events to the Decisions lane in cli/wuwei/signal.py, nudging creation and failures while keeping completed decisions silent.

## Polish

- [X] T010 Document commands, assumptions and retry limits in docs/site/reference.md; run full suite and hygiene checks; complete specs/174-draft-queue/tasks.md.

## Review fixes

- [X] T011 Fix review F1: reproduce draft and MCP interpreter bypasses, then refuse non-CLI interpreter owner actions in cli/wuwei/guards/protect_state.py.
- [X] T012 Fix review F2: reproduce an editor-added newline counting as an edit, then normalize one trailing newline for single-field drafts whose original text had none.

## Dependencies and strategy

US1 is the queue MVP. US2 depends on US1; US3 depends on completed decisions. Execute serially so each behavior's red test precedes implementation. Metrics and cockpit tests can be authored independently once US2 passes. No parallel agents required.

## Verification

Full suite after review fixes: `5388 passed, 5 skipped in 131.80s (0:02:11)`. F1's three new bypass cases failed before the fix; all seven entrypoint cases then passed. F2's editor-newline regression failed before the fix and then passed. Final diff whitespace check passed. Review findings for Python module invocation variants, DM audience lint and Linear destination metadata are covered by regression tests.
