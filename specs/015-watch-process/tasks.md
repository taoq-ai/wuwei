# Tasks

## Setup
- [X] T001 Read source harnesses and existing contracts; write specs/015-watch-process/spec.md and plan.md.

## US1: Supervision
- [X] T002 [US1] Add failing day-PR selection tests in tests/test_watch.py.
- [X] T003 [US1] Use existing code_host reads for raised_prs + claimed_prs only; remove the added discovery port and its tests.
- [X] T004 [US1] Add failing clock, heartbeat, staleness and single-summary sweep tests in tests/test_watch.py.
- [X] T005 [US1] Implement watch cycle in cli/wuwei/watch.py and reuse cli/wuwei/obligations.py evaluation.

## US2: PR wake
- [X] T006 [US2] Add failing change, retry, restart, scheduling and trust tests in tests/test_watch.py.
- [X] T007 [US2] Implement snapshots and loop in cli/wuwei/watch.py, CLI in cli/wuwei/commands/watch.py and reserve producers in state.py and commands/event.py.

## US3: Lifecycle
- [X] T008 [US3] Add failing session, orphan, scope, wake and flush tables in tests/test_watch.py.
- [X] T009 [US3] Implement cli/wuwei/guards/lifecycle.py and lifecycle output in cli/wuwei/commands/hook.py.

## Validation
- [X] T010 Document configuration, wake and operation in specs/015-watch-process/contracts/watch.md; add templates/wuwei-watch.service and templates/wuwei-watch.plist.
- [X] T011 Run full suite, inspect scope and hygiene, update specs/015-watch-process/tasks.md with results.

Dependencies: T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010 -> T011.
Each story has an independent test selection in tests/test_watch.py. Serial execution
keeps the shared watch module consistent. The MVP is US1; all stories are required.

## Review fixes

- [X] T012 F1: SessionStart exits 0 for findings, errors and malformed input, preserving additionalContext; update hook tests and contract.
- [X] T013 F2: Call memory.lint(root) directly with list[str] findings; missing notes are unmeasured. Test the signature pending rebase and verify against the real function from local main.
- [X] T014 F3: Force a same-tick sweep for dead old health; cover restart after a 30-minute gap with 60-second ticks. Narrowed from nonzero health by D2.
- [X] T015 F4/F7: Accumulate pending PR wakes, block Stop once per unseen marker, reserve its acknowledgement and honour stop_hook_active. Read failures allow Stop. Record M5 idle-session launch boundary.
- [X] T016 F5: Isolate snapshot errors per PR, preserve its old fingerprint, record its reserved read-failed event and count only discovery failures toward the streak.
- [X] T017 F6: Remove live discovery adapter, registry entry, fake and tests; poll and sweep only raised and claimed day PRs.
- [X] T018 F8/F10/F11: Omit watch state from the memory payload, finish ticks on SIGTERM via threading.Event, and replace fixed policy config keys with constants.
- [ ] T019 F9 (optional, deferred): Combine all tick state saves and remove observation events. This requires restructuring shared poll/activity/sweep persistence, beyond a small review fix.
- [X] T020 Run the full specified pytest command and guard pre-flight checks after fixes.
- [X] T021 T1: Document all four watch and PR timing keys and defaults on the public configuration page; reproduce and resolve the docs regression.
- [X] T022 D1/D3: Test missing day state after midnight, allow an empty owned PR set to poll and continue the loop, and remove the discovered argument and its caller while retaining the sweep's empty-day evidence check.
- [X] T023 D4: Test planner-only wake consumption and generic-write refusals; add the plan session producer, reserved key/event, silent registration signal, skill registration and Stop session check. Keep SessionStart exit 0.
- [X] T024 D2: Test that unmeasured health keeps the sweep schedule; only dead health forces an early sweep.
- [X] T025 Run the full specified pytest command and inspect the final review-fix diff after rebase.

## Guard pre-flight

Applied design section 9.1 and the constitution: lifecycle relevance and workspace
scope precede reads; unrelated projects pass; existing shell and role guards stay
unchanged; generic state/event writes cannot forge wake acknowledgements. Hook
regressions cover exits, malformed input and context retention; watch regressions
cover Stop bypass, unreadable markers, duplicate delivery and an acknowledgement
race. All five feature requirements checklist entries remain checked.

## Verification result

Full specified pytest command after rebase and review fixes:
`3941 passed, 3 skipped in 41.64s`. The three performance checks were skipped by
the existing machine-load guard. Docs, midnight polling, planner registration and
isolation, sweep scheduling and signal-tier regressions were observed failing
before their fixes. Diff whitespace checks passed. Both sides of the rebase
unions in event kinds, signal tiers, reserved state, config schema and workspace
tests remain intact.

Changes remain uncommitted. No commits, pushes or gh commands were run.
