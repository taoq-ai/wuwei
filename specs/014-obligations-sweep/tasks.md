# Tasks: PR obligations sweep

## Setup

- [X] T001 Read design, constitution, existing ports, state writer and source harness; write specs/014-obligations-sweep/spec.md and plan.md.

## US1: Reply evidence and obligations

- [X] T002 [US1] Add failing normalized actor and reviewer evidence tests in tests/test_code_host.py and tests/fixtures/code_host/recordings.json.
- [X] T003 [US1] Extend existing evidence normalization in adapters/code_host/github.py.
- [X] T004 [US1] Add failing absolute thread/comment/review obligation tables in tests/test_obligations.py.
- [X] T005 [US1] Implement reply evaluation in cli/wuwei/obligations.py.

## US2: Visibility

- [X] T006 [US2] Add failing requested-reviewer, posted mention and exact verdict tables in tests/test_obligations.py.
- [X] T007 [US2] Implement visibility evaluation in cli/wuwei/obligations.py.

## US3: Sweep and errors

- [X] T008 [US3] Add failing CLI union, closed PR, malformed evidence, API stdout errors and single-event tests in tests/test_obligations.py.
- [X] T009 [US3] Implement cli/wuwei/commands/sweep.py and aggregation in cli/wuwei/obligations.py.

## US1: Acknowledgement producer

- [X] T010 [US1] Add failing forged-ledger and successful/failed/edited-target reply tests in tests/test_obligations.py.
- [X] T011 [US1] Reserve reply_acks in cli/wuwei/state.py and implement cli/wuwei/commands/reply.py with dedicated producer in cli/wuwei/obligations.py.

## Verification

- [X] T012 Run full pytest suite, review changed source and tests, and check all files changed for machine paths, em-dashes and emojis; update specs/014-obligations-sweep/tasks.md.

## Dependencies and execution

T002 precedes T003. T004, T006 and T008 can be authored as independent tables before
T005, T007 and T009 implement their shared module. T010 precedes T011. T012 follows
all implementation. MVP is US1, but all stories are required for this delivery.

## Validation evidence

- Adapter evidence tests failed on absent reviewer and actor fields, then passed.
- 54 initial sweep cases failed on the missing command, then passed.
- Reserved-ledger, acknowledgement, malformed-reference continuation, stale reply
  ID and edited-reply regressions failed before their fixes.
- Initial implementation suite: `2613 passed in 21.43s`.
- Adversarial review subsequently identified F1-F6; remediation follows below.
- Changed-file whitespace, ASCII and machine-path checks passed. No commits or pushes.


## Adversarial review fixes

- [X] T013 [F1, F4] Reproduce forged channel evidence and state verdict bypasses; reserve channel_posts and read linted gate files at the current head using shared verdict vocabulary. Cover resolved quality-file lint requirements.
- [X] T014 [F2] Reproduce removal and empty-set history bypasses; make both PR lists append-only, record PR presence in state-write events, and fail closed on contradictory or unavailable empty-day history.
- [X] T015 [F3] Reproduce forged events and caller-selected identity; reserve both obligation event kinds, remove --me, and resolve one unambiguous configured code-host login.
- [X] T016 [F5] Reproduce extra review-author mention requirements; prefer requested reviewers and teams, with review authors only as the fallback.
- [X] T017 [F6] Move canonical repository and PR validation to cli/wuwei/references.py and reuse it in obligations and the GitHub adapter.
- [X] T018 Run the full suite with the requested interpreter and check final diff hygiene; leave all changes uncommitted.

T013-T016 each had failing regression tests before their correctness fixes. T017
is a refactor covered by the existing adapter and obligations suites. Targeted
state, verdict, adapter and obligations checks passed before final verification.


Final verification: `2652 passed in 24.90s` with the requested interpreter.
One prior run hit the existing PostToolUse 50 ms CPU latency threshold at 52.72 ms;
the unchanged full-suite rerun passed at 38.47 ms. No thresholds or tests were
relaxed. Diff whitespace and changed-file path/style checks passed. No commits.
