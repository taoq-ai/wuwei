# Implementation Plan: 077 merge policy

## Context and constitution check

Python 3.11+, stdlib runtime, pytest only in tests. Existing ports own subprocesses.
Existing PR guard supplies normalization and workspace scope. Existing obligations supply
reply/visibility evaluation. Existing watch schedules post-merge polling. No new daemon.
All behaviours start with a failing test. No commit, push, network or real forge commands.

## Design

1. Extend the code-host read contract with PR files, ruleset-aware protection and outcome
   evidence. Preserve full SHA pins and validate error bodies, pagination and identifiers.
2. Add `wuwei.merge.check` returning a Result with evidence. It reads config, linked item,
   cycle events, actual gate files, code-host requirements, obligations and bot ports.
3. Add `wuwei merge [check] <pr>` and replace the PR guard's placeholder. Raw merge tools
   call check but refuse a successful result with directions to the dedicated CLI writer.
4. Keep the journal in the reserved `merges` day-state namespace. Scan day records for
   caps, unresolved intents and breakers. Use a workspace merge lock for command/watch
   serialization and the existing atomic state/event writers inside it.
5. The watch reconciles intents and actual merge commits, follows base checks, records
   undo entries and trips a persistent repository breaker before attempting a revert PR.
6. Compare mature auto-merge outcomes with the baseline note; unreadable outcomes return 2.

## Validation

In-process fakes and transport replay cover policy tables, head races, malformed results,
classic/ruleset unions, trust reservation, concurrency, day rollover and post-merge recovery.
Reuse the existing external-boundary smoke test. Run the full specified pytest command.

## Source-port decisions

Preserve ping-gate refusal order: dirty, behind, resolvable required checks, required
checks present and passing, all checks non-failing/non-pending, bot score and reviewed head.
Use configured policy defaults and adapter selection instead of repository/login literals.
Do not silently discard protection failures or apply an engagement-specific fallback.
