# Specification Analysis: #940

## Pre-implementation review

No CRITICAL or HIGH findings. No duplicate requirements, unowned tasks or unresolved ambiguities. The proposed design wording is confined to Assumptions, respecting owner ownership of the design document.

| Requirement | Tasks | Coverage |
| --- | --- | --- |
| FR-001 | T003, T004 | Field question and appended context |
| FR-002 | T005, T006 | Missing token and differing command diagnostics |
| FR-003 | T003, T005, T006 | Build and dispatch direct-card paths |
| FR-004 | T003, T007 | Seat exclusion, latest reply, consumption and terminal regressions |
| FR-005 | T004, T007 | Hash-only event compatibility |
| SC-001, SC-002, SC-003 | T007, T008 | Offline validation and review |

Constitution alignment: shared implementation, stdlib runtime, failing tests before code, owner-only design unchanged. Explicit-file tests replace a bare full-suite invocation as the user requires. No extension hook configuration is present.

## Validation results

Test-first reproduction before runtime changes:

```text
9 failed, 1 passed, 45 deselected in 4.75s
2 failed, 308 deselected in 0.63s
```

Failures showed the field question did not bind, ordinary refusals lacked a specific mismatch identity, and build/dispatch cards lacked a mismatch hint. The exact-card control passed.

The first post-fix focused run reached a mistaken test assertion: next JSON uses `why`, not `reason`. Corrected that assertion without changing runtime behavior.

Focused verification after correction:

```text
381 passed in 33.76s
```

Files: tests/test_card_confirms.py, tests/test_one_action.py, tests/test_dispatch.py, tests/test_answers.py, tests/test_sessions.py.

The importer/helper run used 51 additional explicit files, starting before the final recorder correction. It reported:

```text
3562 passed in 220.08s (0:03:40)
```

An AST audit confirms all 27 direct importer files are included across the 56 selected files. No bare suite invocation.


## Review and one fix round

Independent review found one P2 compatibility issue: the first token-shaped text could occur inside a quoted command argument, breaking exact tokenless cards. Added regressions for a quoted --reason with token-shaped text, both without a card token and with an actual token plus optional context. Before the correction:

```text
3 failed, 28 deselected in 0.14s
```

The correction uses stdlib shlex.split to skip candidates inside unfinished quotes. No custom shell parser or new module. The independent delta review found no blocking issues. Final focused validation after that correction:

```text
384 passed in 50.78s
```

The 20 remaining recorder consumers and hook tests were rerun after the correction:

```text
1706 passed in 119.95s (0:01:59)
```

Files: tests/test_build_next.py, tests/test_calibrate.py, tests/test_close_parked.py, tests/test_doctor.py, tests/test_e2e_day.py, tests/test_edges.py, tests/test_headless_e2e.py, tests/test_hooks.py, tests/test_integrity.py, tests/test_loop.py, tests/test_merge.py, tests/test_next.py, tests/test_parallel_dispatch.py, tests/test_path_day.py, tests/test_plan.py, tests/test_post_pr.py, tests/test_pr_actions.py, tests/test_spec_mode.py, tests/test_telemetry.py, tests/test_traces_seats_only.py.

sessions.py and dispatch.py did not change after their broader passing run. Every run used the task-specified interpreter, `-m pytest -q -p no:cacheprovider`, and explicit file arguments. Importers were collected with rg for sessions, dispatch, guards.answers, and the shared fake owner/day helpers; AST inspection confirmed direct import coverage.

## Completion

All implementation tasks completed. No open CRITICAL, HIGH or blocking review findings. git diff --check passes. The branch remains 940-card-token; changes are uncommitted. The owner-only design document and constitution are unchanged. No absolute local paths, emojis or em dashes were added to feature artifacts. Custom requirements review checkboxes remain reviewer-owned, as documented in that checklist; their semantics do not track implementation completion.

Limitations: generated 12-hex tokens support trailing context; other existing token forms retain exact matching. Previously recorded extended-question hashes cannot be migrated, so those need a new answer. No unfinished implementation work within #940.

## Review follow-up readiness

Owner-requested findings F1, F3 and the small newline portion of F2 map to T009, T010 and T011. The corrections retain the existing shared functions and hashed event schema. F1 strengthens fail-closed behavior; F3 affects diagnostics only; F2 adds a hint without a reply hash and cannot authorize. No open CRITICAL or HIGH planning findings. Test-first reproduction and T012 verification follow.


## Follow-up test-first results

Before runtime changes, both F1 reply orders incorrectly returned Yes, F3 reported a spent card as a mismatch, and both F2 token variants lacked a first-line hint:

```text
5 failed, 31 deselected in 0.84s
```

After the shared fixes:

```text
5 passed, 31 deselected in 0.68s
```

F1 now requires exactly one recognized reply. F3 scans diagnostic rows newest first and stops at the requested command's last owner.approved; a later mismatched answer remains visible and another command's approval does not clear it. F2 adds one first-line step topic with no reply hash, so it cannot approve either a tokenless or token-bearing expected card. Same-line tokenless context is deferred per the owner's limited scope.

Final explicit-file importer validation:

```text
3167 passed in 222.08s (0:03:42)
```

The 39 files include tests/test_card_confirms.py, tests/test_dispatch.py, tests/test_one_action.py, all eight direct sessions/guards.answers importers (confirmed by AST), and shared fake-owner/day consumers. Selection used rg for sessions, guards.answers, answers imports and the fake owner/day imports, followed by explicit file arguments with the task-specified interpreter and `-m pytest -q -p no:cacheprovider`.

Delta review: F1 fails closed for either contradictory reply order and allows a later unambiguous answer. F3 is bounded by the requested command's approval, not another command's, and still reports fresh mismatches. F2 preserves authorization and hash-only storage. No new runtime module or dependency. git diff --check passes; owner-only design and constitution remain unchanged. No commits, pushes, stashes or GitHub commands were run. All follow-up implementation tasks are complete; only same-line tokenless-context diagnosis remains deferred as authorized.
