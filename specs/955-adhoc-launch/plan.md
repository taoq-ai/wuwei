# Implementation Plan: Ad-hoc launch

## Technical Context

Python 3.11+, stdlib runtime, pytest development dependency. Existing Agent
hook, JSON day state and private Markdown files. No new module or dependency.

## Root Cause

`cli/wuwei/guards/agent_launch.py:90-103` routes a missing marker to a refusal
under enforcement. The permissive fallback at lines 106-148 only keeps a
redacted first line and bypasses the normal launch checks. Prompt matching
in `cli/wuwei/brief.py:238-247` only considers legacy role=adhoc records.

## Design

Reuse `_check`'s shared runtime, memory, gate and locked capacity checks for
inline metadata derived from the prompt, role and inferred item. Save the raw
prompt only after validation in a private day brief file and bind the seat
with its digest. Preserve the actual role so live-seat accounting and existing
recovery continue to apply. Do not start or advance routed build records for
these seats. Extract the existing protected-path check in brief.py for reuse.
Extend existing prompt binding to typed seats for trace and stop handling.
Explicit references retain their full validation path.

## Constitution Check

PASS: stdlib only, three exits, atomic state/file writers, test first, shared
checks, no new subsystem. Prompt bodies stay out of events. User instructions
require explicit affected test files instead of the bare full suite. Existing
worktree is used; no commit, push, stash, gh or design-document edit.

## Sequence and Validation

1. Add the field-case and guard/recovery regression tests before runtime edits.
2. Observe expected missing-brief refusals with the assigned pytest interpreter.
3. Implement in agent_launch.py and brief.py; adapt obsolete refusal tests.
4. Run all test files importing changed modules, plus seat recovery, traces and
   guard integration tests, with fake adapters and no network.
5. Review correctness, security and simplicity, resolve blocking findings,
   record exact test summaries and leave all changes uncommitted.

## Authorized review follow-up

Root causes located before the follow-up runtime edits:
- dispatch.receive admitted a stopped matching seat without checking its
  prompt_sha256 provenance at cli/wuwei/dispatch.py:1479.
- The #901 condition explicitly exempted ad-hoc builders at
  cli/wuwei/guards/agent_launch.py:243 before this follow-up.
- _named_item searched free prompt prose at
  cli/wuwei/guards/agent_launch.py:70.
- transcript_reference searched every user message at cli/wuwei/brief.py:198.
- _unbriefed accepted planner from ROLES, and _check and _adhoc did not reject
  callers with agent_id at cli/wuwei/guards/agent_launch.py:80,159,108.


1. Reproduce HIGH-1 in tests/test_dispatch.py and refuse prompt_sha256 seats
   at dispatch.receive, before reading or recording a verdict.
2. Reproduce HIGH-2 in tests/test_agent_launch.py and route item-bound ad-hoc
   builders through the existing #901 refusal under the reservation lock.
3. Reproduce MEDIUM-3 and limit _named_item to name, description and Item: lines.
4. Reproduce LOW-1 and LOW-4: first-prompt binding in the shared transcript
   reference helper, no ad-hoc nested seats, no planner role.
5. Correct the #937 history claim, then run every test importing a changed
   module plus tests/test_signal_status.py with explicit file arguments.

## Round 2 root causes and plan

- agent_launch.py:70-80 collapses multiple named items to None; the locked
  #901 check at line 251 then admits an ambiguous builder as unbound. Return
  all matches and inspect them in the shared reservation.
- agent_launch.py:124 refuses agent_id on the untyped #676 path. Remove that
  duplicate check; retain the typed check at line 185.
- brief.py:245-261 matches only digest, role and session. Reject pending
  cross-item collisions in the shared launch reservation, before private writes.
- dispatch.py:1082 counts prompt sentinels as gate evidence. Exclude them from
  the gate batch count and its running-seat trigger.
- agent_launch.py:297 uses brief-only worktree advice. Give prompt launches
  their own next-step message.

Write and run regression tests for each case, implement the smallest shared
changes, then run every importer of the five requested modules explicitly.
