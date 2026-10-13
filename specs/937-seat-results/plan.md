# Implementation plan

**Branch**: `937-seat-results` | **Spec**: [spec.md](spec.md)

## Root causes confirmed before follow-up edits

- commands/build.py:552-558 read the transcript only once and mislabeled the
  thinking/text append race as an unreadable payload.
- guards/agent_launch.py:419 and commands/build.py:548 ignored already-stopped
  seats and non-running records, including SendMessage's ready/continue round.
- brief.py:313 required toolUseResult.success, absent from real successful results.
- Explicit reconcile bypassed completion evidence; the earlier path advice named
  the spec-only worktree even when the owner needed the distinct PR worktree.
- build.step's broad resultless branch consulted stale launch agent IDs.

## Changes

1. Reproduce the two field failures and manual stopped-seat refusal before fixes.
2. Bound transcript rereads to about two seconds. Keep persistent mismatch refusal.
3. Share continued-round eligibility between result capture and manual report
   recovery; preserve agent identity, completion deduplication and atomic writes.
4. Use real terminal-result evidence; delete aliases and prose classifiers.
5. Require completion for all reconcile paths. Reuse adopt_worktree validation,
   needs_owner cards and the atomic state writer for confirmed same-repo rebinds.
   The card names both paths/HEADs and the exact command; fresh checks/gates follow.
6. Limit resultless blocker escalation to a matching completed bound seat. Simplify
   recovery advice. Generate the builder agent from its updated charter.
7. Run explicit importer test files with the prescribed interpreter and record
   outcomes, remaining limitations and final diff size in analysis.md.

## Constitution and complexity

Stdlib Python 3.11+, existing modules and adapters only. No network in tests.
No owner design edits or commits. The owner authorized this reconsideration and
specified explicit test files instead of a bare full suite. One-time clean Git
recovery remains for work completed before its build record, without synthetic
seat results. Approval and state comparisons preserve trust boundaries.

## Round 2 plan

Root causes before edits: build.stopped invokes last_turn outside a ValueError
retry boundary; seat.run permits arbitrary files for a ready continuation and
stop_with_report creates a synthetic transcript with the build agent's identity.

1. Reproduce initial and mid-wait torn writes plus the foreign verdict-file path.
2. Move all transcript reads inside the bounded retry. Require the original bound
   transcript and new completion for manual continuation; retain all stop guards.
3. Fix missing-old-tree approval evidence, simplify the misleading eligibility
   call, and restore the hook import. Preserve implement to require checks.
4. Verify explicit importer tests, document deferred LOWs and leave work uncommitted.
