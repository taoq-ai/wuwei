# Implementation Plan: #952 housekeeping

## Technical Context
Python 3.11 stdlib. Existing watch day readers, host adapter, next dispatch, lifecycle
hook, close and report paths. No new runtime module or dependency.

## Constitution Check
Pass: one shared rule, atomic existing event writer, local cached state, owner cards,
no daemon, no owner design edits, test first. OS subprocesses stay in the host adapter.
Explicit test-file selection follows the implementation-seat instruction.

## Research and Design
Root cause: commands/next.py:284 hands out an untracked pr wait; resolve at :340
also hands out run entries without process ownership. guards/lifecycle.py:58 checks
only prior-day seat reservations. commands/close.py:67 proceeds to steward without
process cleanup. Existing watch.py owns cross-day event reads and fits this check.
A new subsystem or shell PID capture would duplicate lifecycle and lose launch identity.

## Implementation
1. Reproduce the merged wait, duplicate, hung-init orphan, PID reuse and lifecycle cases in tests/test_housekeeping.py.
2. Add host process-table and verified termination operations; fake both in tests.
3. Add watch background registration, findings and cleanup using events.jsonl, cached prs.json, seat transcripts and terminal item worktrees.
4. Wrap only PR waits and timers, validate their exact argv at runtime, and keep other commands direct. Use fast process checks in next and SessionStart, full cwd checks only on explicit inspection. List historical seats without clock overrides; record failed cleanup once.
5. Run tests importing changed modules with explicit file arguments; inspect correctness/security and simplicity, then a delta review if needed.

## Validation
Fake process tables and signals only. Assert identity checks before both signals,
three-state exits, exact owner commands, recovery commands and close ordering.
No network, no real GitHub, no real process termination.

## Round 2 plan
Root causes before changes: commands/next.py:301 reoffers waits without live ownership;
watch.py:260 and :285 send historical noise to every caller; protect_state.py:27 has
partial wrapper parsing; next.py:104 and watch.py:134 retain dead item/purpose inputs;
lifecycle.py:37 prints unresolved commands; watch.py:165 calls host none during reads;
watch.py:274 includes external tree roots and has no daily listing receipt.
1. Port four-round field reproduction and tests for FR-008 through FR-012; observe failures.
2. Return live wait identities through the shared scan, scope owner findings, and skip host none on fast reads.
3. Drop dead wrapper inputs and guard unwrap; share pure wrapper formatting with orientation.
4. Constrain orphan cwd to workspace and record daily general-orphan listings using existing events.
5. Run explicit impacted files and record exact summaries and production diff size.

## Round 3 plan
1. Extend close retry coverage for host none and failed ps/lsof inspection; verify unmeasured rows stay visible and closing.check still decides the exit. Cover current failures versus historical failed-reap receipts.
2. Record session id and day in background; limit live-wait suppression and oldest-wait selection to that scope. Reproduce other-session and prior-day waits against today's open PR, then verify obsolete cleanup and replacement waits.
3. Reject housekeeping positional arguments before side effects, including combined flags.
4. Run all test files importing any changed module, plus hooks, close files and signal status with the prescribed interpreter and explicit paths.
