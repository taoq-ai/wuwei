# Preserve seat results and recover committed builds

**Branch**: `937-seat-results` | **Issues**: #937, #930 | **Date**: 2026-10-13
**Status**: Field follow-up implemented and verified

## User scenarios

1. In default permission mode, a builder finishes with plain final text. Its stop
   hook arrives while the transcript ends in a thinking row. The final text row
   lands shortly afterward; the hook records that matching completion once.
2. The planner continues a stopped builder through SendMessage. No Agent launch
   hook runs. Its same-agent final report closes the ready/continue round, through
   either SubagentStop or the planner's seat stop --verdict.
3. A completed seat left clean descendant commits without a result. Build next
   and build check measure that work through checks and gates, without inventing
   result text or usage. Explicit reconcile requires the same completion evidence.
4. The item records spec work in one worktree, but its PR work is in another.
   Reconcile names both worktrees and HEADs on an Owner step card. Only an answer
   bound to that evidence rebinds the same-repository work and reruns checks/gates.

## Requirements and success criteria

- FR-001 / SC-001: Accept the field-supported SubagentStop fields: agent_id,
  agent_type, agent_transcript_path, last_assistant_message, session_id, cwd and
  permission_mode. Re-read for about two seconds on a text mismatch, then refuse
  with the actual mismatch reason. Never substitute the parent transcript.
- FR-002 / SC-002: A new completion from the recorded agent on ready/continue
  closes its continued round. Foreign agents and repeated completions cannot
  record another round. Preserve atomic result/usage recording and guard lint.
- FR-003 / SC-003: A matching hand-back tool_result with toolEndsTurn=true and
  no is_error proves completion; toolUseResult is unnecessary. A later user turn
  resumes the task. Unknown completion never receives an automatic stop offer.
- FR-004 / SC-004: Record failed result capture as a gap. The builder reports a
  refused hand-back tool under Gap and uses its final text as its report. Do not
  classify arbitrary Blocked prose with regexes. Preserve genuine owner blockers.
- FR-005 / SC-005: Only completed builders with clean descendant HEADs can recover
  to checks. Missing results stay absent, failed checks remain actionable, and
  explicit reconcile cannot bypass completion evidence.
- FR-006 / SC-006: Accept the same recorded worktree. For another tree, require
  a linked worktree of the same repository, no other item's binding, no live or
  unknown-completion seat, and the existing Owner step approval. Bind approval
  to both paths/HEADs and the current item/build. Concurrent seat or item changes
  refuse. Rebinding discards old build evidence and requires fresh checks/gates.
- FR-007 / SC-007: Stale launch records cannot route an old agent's blocker to the
  owner. A resultless blocker requires a matching bound seat that actually ran.

## Entities and constraints

Reuse existing seats, builds, transcripts, worktree records and Owner step events.
No new runtime module, dependency or service. Keep completion, identity, check,
owner-decision and concurrent-write protections. Recovery advises --verdict.

## Assumptions and design reconsideration

- The owner explicitly authorized this field-review revision after the earlier
  approach failed. Its invented payload aliases and prose patterns missed the
  actual transcript timing and SendMessage lifecycle. They are deleted.
- The real payload shape is inferred by the review from field events and source
  behavior; no raw hook payload was captured. Fixtures carry those supported
  fields and real terminal-result structure with neutral identifiers and paths.
- A rejected stop can leave a task alive. An unmeasured seat alone proves nothing,
  including during explicit reconcile. A stopped seat or terminal hand-back is
  required. Clean Git state alone is not task completion.
- Rebinding uses sessions.needs_owner, the existing Owner step mechanism. It is
  never implicit. Its card explicitly discards the old build record, including
  old result/check evidence, before creating the selected tree's build record.
  Neither worktree's files or commits are removed; gates must run again.
- No live owner workspace is changed by this development task. Field timing is
  reproduced deterministically with a patched reader; tests use local fixtures.
- Combined #937/#930 scope, autonomous recommendations, explicit test files and
  uncommitted changes follow the owner's instructions. #938/#941 are excluded.
- Proposed design clarification: final text is the hand-back even if a hand-back
  tool is refused, consistent with design 5.2/5.3. The owner-only design is untouched.

## Clarifications

All questions are resolved by the recommendations above, as instructed. Historical
implementation claims and red/green evidence remain in analysis.md.

## Round 2 reconsideration

The owner authorized this revision after fresh-context review. The prior timing
fix assumed each read saw complete JSON, and manual continuation reused a free-file
recovery path with a synthetic agent binding. Replace both assumptions: retry
ValueError within the same two-second deadline, including the initial read; manual
continued reports must come from the recorded transcript with a new completion.
A supplied verdict file is refused. No new module or transport is needed.

The stale-stop LOW remains deferred: existing manual results can have synthetic
completion indices, and no persisted SendMessage delivery time exists. A user-row
heuristic would not reliably prove feedback delivery; adding that tracking exceeds
the requested few-line fix. The separate planner-main-thread authorization issue
also stays deferred, since the user prohibited filing GitHub issues in this task.

Rebind still enters implement deliberately: reconcile invokes build checks only
from planned/build phases; retaining raised/delta would skip measuring the selected
worktree. This is required for the existing fresh-check/gate contract. An absent
old worktree can be named as missing in the approval card; the selected tree still
must pass configured-repository validation, and appearance of the old tree after
approval invalidates the evidence.
