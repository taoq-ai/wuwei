# Tasks: Profiles

## Setup and foundation

- [X] T001 Read main's hook, scope and outward policy code and write specs/017-profiles/spec.md and plan.md.
- [X] T002 Write metadata and dispatcher profile matrix tests in tests/test_profiles.py; run and observe failure.
- [X] T003 Add validated default-false guard metadata in cli/wuwei/guards/__init__.py and profile handling in cli/wuwei/commands/hook.py.

## US1: Outward warnings (P1)

Independent check: an eligible message exceeding its length limit warns only in standard.

- [X] T004 [US1] Write tests for separate lint registration, warnings, errors, tiers and ports in tests/test_profiles.py; run and observe failure.
- [X] T005 [US1] Separate tier and lint checks in cli/wuwei/guards/outward.py and cli/wuwei/outward.py, reusing dispatcher profile handling for ports.

## US2: Other guards unchanged (P1)

Independent check: merge, approve and deployment refusals persist in standard.

- [X] T006 [US2] Add profile regression tables for real safety guards, mixed results, scope and irrelevant commands in tests/test_profiles.py before any required implementation adjustment.
- [X] T007 [US2] Confirm existing safety and scope helpers need no changes; if tests expose an integration gap, fix only profile handling in cli/wuwei/commands/hook.py.

## Validation

- [X] T008 Update specs/006-hooks-harness/contracts/hooks.md with metadata and warning semantics.
- [X] T009 Run the full pytest suite, inspect all changed files for hygiene, and complete specs/017-profiles/tasks.md.

## Review fixes

- [X] T010 Add a failing regression for `hook.warning` on relaxed lint, then record
  redacted reason and tool for hooks and direct ports with nudge signal tier.
- [X] T011 Move shared profile translation into `wuwei.guards` so library policy does
  not import a CLI command.
- [X] T012 Remove the unregistered combined outward guard and point tests at the
  registered tier or lint checks.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009.
US1 is the initial increment; US2 verifies its boundaries before completion. Sequential work
keeps each failing test ahead of its implementation. No parallel agent work is needed.

## Validation notes

Metadata/dispatcher tests initially failed on missing metadata and standard refusing lint;
after implementation 22 passed. Outward registration tests then failed on the absent
relaxable lint guard; after separation the focused suites passed. Existing safety and
scope behavior needed no runtime changes. Review regressions exposed misleading draft
wording in warnings and missing-profile error handling in direct calls; both were fixed
after observing failing tests. Profile tests reject unexpected port reads.

Final full suite: 3791 passed, 2 skipped in 34.79s. The existing load-aware rule
skipped two latency checks. Diff whitespace and authored-file hygiene checks passed.
Review fix run: 3791 passed, 3 skipped in 38.57s. The added skip was a load-aware
latency check.
