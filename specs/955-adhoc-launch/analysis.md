# Analysis: #955

## Pre-implementation consistency review

| Finding | Severity | Resolution |
| --- | --- | --- |
| Legacy ad-hoc fallback bypasses launch checks | HIGH | Resolved in plan: use the shared typed reservation checks. |
| Legacy role=adhoc cannot record a verdict through seat stop | HIGH | Resolved in plan: preserve actual WUWEI role and existing recovery. |
| Design 4.1 requires the missing-brief refusal | HIGH | Issue explicitly changes this behavior; proposed wording recorded in spec Assumptions. Owner design stays untouched. |

No open CRITICAL or HIGH findings. No unresolved clarification or duplication.

| Requirement | Tasks |
| --- | --- |
| FR-001 | T003, T004 |
| FR-002 | T003, T004 |
| FR-003 | T005, T006 |
| FR-004 | T007, T008, T009 |
| FR-005 | T003, T009 |
| FR-006 | T005, T006 |

Coverage: 6/6 requirements; 10 tasks. No unmapped implementation tasks.
Constitution: stdlib, fail closed, shared checks, private prompt, atomic writes
and test-first covered. Explicit affected tests follow the issue's instructions.

## Implementation review and resolutions

The independent correctness/security/simplicity review found four blockers:
committed protected-path evidence was missing, stopped prompt seats lost their
identity, identical prompts could cross roles, and unscoped builder recovery
assumed a plan item. Regression tests reproduced these before fixes. The
shared repository/path evidence now includes committed diffs; prompt matching
includes role and session and retains stopped identity; missing items have no
spec worktree. Original-day stops resolve uniquely or remain unmatched.

The delta review confirmed those fixes and identified name collisions with
preexisting brief files or evidence left by failed event writes. The allocation
design now considers both seats and files under the same reservation lock,
preserving evidence without trying to roll back a potentially durable event.
Tests reproduce both collisions and verify successful retry. Concurrent ad-hoc
builders also consume CAP, and an untyped stop cannot consume a typed seat.
These changes complete the consolidated fix round; no open blocking finding.

## Initial implementation verification evidence

Field-case red run, before implementation:
`12 failed, 122 deselected in 1.01s`

The first broad run exposed two obsolete missing-marker assertions in dispatch
and mutation tests. Both now exercise the new registration contract and retain
an unavailable-day guard probe. Focused verification after those updates:
`497 passed in 6.77s`

Tests use the assigned pipeline interpreter, `-q -p no:cacheprovider`, explicit
file arguments, fake adapters and temporary workspaces. An AST import inventory
cross-checks the grep search for brief, agent_launch, traces and guards.spec;
the final set includes all 23 direct-import test files plus protection and
seat-command coverage. No network or real GitHub call is required.

The owner design is unchanged. `git diff --check` passes. Added content has no
absolute local paths or em-dashes. All changes remain uncommitted on the
original branch.

## History correction

The prior claim that #937 was absent is withdrawn. Commit a30d25fb, which
includes #937, is an ancestor of HEAD. The existing plain-final payload
regression is in tests/test_handback.py. No missing-#937 limitation is asserted.

Initial implementation verification, all 25 explicit affected test files:
`2587 passed in 198.47s (0:03:18)`

## Follow-up analysis before implementation

The owner requested HIGH-1, HIGH-2, MEDIUM-3, LOW-1, LOW-4 and LOW-6 fixes.
Their design conflicts are resolved in spec Assumptions and the authorized
design reconsideration. Implementation findings remain open until tests pass.

| Requirement | Tasks | Planned resolution |
| --- | --- | --- |
| FR-007 | T011 | Reject prompt-backed gate receipts at the shared receive function. |
| FR-008 | T012, T013 | Preserve #901; require explicit item identification. |
| FR-009 | T014, T015 | First-prompt binding; reject nested seats and planner role. |
| History and validation | T016 | Correct #937 ancestry and run affected-file tests. |

No unresolved specification-level CRITICAL or HIGH conflicts remain. Runtime
HIGH findings are tracked by T011 and T012. No new module or dependency.

## Follow-up implementation review

| Finding | Resolution | Regression evidence |
| --- | --- | --- |
| HIGH-1 | receive rejects seats carrying prompt_sha256 before reading a verdict. | A prompt-backed sentinel and valid verdict leave gate state unchanged. |
| HIGH-2 | The locked #901 check includes every item-bound ad-hoc builder. | Missing, ready and running build records all refuse; existing concurrent unbound CAP coverage remains. |
| MEDIUM-3 | Only name, description and exact Item: lines identify items. | Free prose, quoted labels, ambiguity and explicit identifiers are covered. |
| L1 | The shared transcript reference helper reads only the first prompt. | A later reference cannot redirect traces, seat_of or SubagentStop. |
| L4 | Typed and untyped ad-hoc launches reject agent_id; typed roles exclude planner. | Nested typed, nested untyped and planner cases reserve nothing. |
| L6 | #937 ancestry is confirmed and the prior absence claim withdrawn. | a30d25fb is an ancestor of HEAD; existing handback tests are in the required run. |

Before runtime edits the regression run reproduced the expected failures:
`11 failed, 4 passed, 474 deselected in 2.95s`

After the minimal shared-path fixes:
`15 passed, 474 deselected in 0.79s`

The first four-file check found four obsolete free-text item assumptions:
`4 failed, 698 passed in 20.00s`

The affected tests now use explicit descriptions for scoped guard probes and
expect an unbound item for free prose. No runtime behavior was weakened to
satisfy these assertions.

Cross-artifact review: 9 requirements mapped across 16 tasks; FR-001 through
FR-006 retain their original coverage, FR-007 maps to T011, FR-008 to T012 and
T013, FR-009 to T014 and T015. T016 verifies history, docs and affected tests.
No unmapped implementation tasks, unresolved ambiguity or new subsystem.
No open CRITICAL or HIGH findings remain after the targeted regressions pass.
L2, L3 and L5 remain outside the requested corrections and are recorded under
Deferred in spec.md. The owner design remains unchanged; proposed wording is
recorded under Assumptions and the review-driven reconsideration.

The first 39-file run completed with:
`1 failed, 3406 passed in 267.30s (0:04:27)`

The failure was tests/test_reasons.py's required-next-step check on the new
planner and nested-seat refusal messages. It reproduced before the wording
fix. The messages now name the existing planner session or the seat report
as the next step. The same explicit 39-file set is rerun after that fix.

Final follow-up verification:
`3407 passed in 253.09s (0:04:13)`

The 39 explicit files include every direct importer of brief, dispatch,
guards.agent_launch, guards.spec and guards.traces, plus signal status,
protected-state and seat-command coverage. The rg search was cross-checked
with an AST import inventory, including dynamic module-name literals. All
T011-T016 tasks are complete. No requested correction remains unfinished.
The remaining unselected low findings are explicitly deferred in the spec.

Explicit final test-file inventory:

```text
tests/test_admit_context.py
tests/test_agent_launch.py
tests/test_brief.py
tests/test_build.py
tests/test_build_next.py
tests/test_canary.py
tests/test_dispatch.py
tests/test_enforce.py
tests/test_guard_mutation.py
tests/test_handback.py
tests/test_hooks.py
tests/test_launch_contract.py
tests/test_linear_loop.py
tests/test_loop.py
tests/test_main_broken.py
tests/test_merge.py
tests/test_metrics.py
tests/test_next.py
tests/test_one_action.py
tests/test_parallel_dispatch.py
tests/test_plan.py
tests/test_post_pr.py
tests/test_pr_actions.py
tests/test_process_depth.py
tests/test_protect_state.py
tests/test_reasons.py
tests/test_reconcile.py
tests/test_runtime.py
tests/test_seat_command_forms.py
tests/test_shepherd.py
tests/test_signal_status.py
tests/test_spec_mode.py
tests/test_templates_errors.py
tests/test_tone.py
tests/test_traces.py
tests/test_traces_seats_only.py
tests/test_tracker.py
tests/test_worktree_command.py
tests/test_ziran.py
```

## Round 2 pre-implementation analysis

HIGH-1 maps to FR-010/T017: preserve all named items under the reservation lock.
MEDIUM-2 maps to FR-009/T018: restore untyped #676 behavior. Low findings map
to FR-011 through FR-013/T019-T020. T021 verifies the affected importers.
No specification-level CRITICAL or HIGH conflict remains; the reported runtime
failures remain open until red/green regressions and importer tests pass.
The binding limitation is explicit: description is absent from transcripts, so
refuse cross-item pending collisions and require item-specific prompt text.

## Round 2 regression evidence

Before runtime edits:
`14 failed, 185 deselected in 15.07s`

After the shared-path fixes:
`14 passed, 185 deselected in 2.30s`

All failures were the expected behavior assertions: eight ambiguous builder
launches were admitted, both nested untyped roles refused, cross-item prompts
were admitted, missing-worktree advice named brief flags, and two gate batch
schedules were wrong. The collision test also retries with Item: Y and verifies
the Y agent traces first without binding X.

The round 1 L4 resolution above is superseded: only typed WUWEI launches refuse
nesting; general-purpose and Explore preserve #676. HIGH-1 is closed by the
locked all-match check and both field cases with missing/running build records.
No new module, dependency or state field was introduced. Gate batching excludes
prompt seats both from the count and from the running-gate trigger.

## Round 2 final verification

`3879 passed in 450.33s (0:07:30)`

The 41 explicit test files below cover every direct importer of brief, dispatch,
guards.agent_launch, guards.spec and guards.traces, cross-checked by rg and AST
imports/module literals, plus touched tests and recovery/guard integration.
The assigned interpreter ran pytest with -q -p no:cacheprovider and explicit
file arguments. Tests used fake adapters and temporary workspaces.

```text
tests/test_admit_context.py
tests/test_agent_launch.py
tests/test_brief.py
tests/test_build.py
tests/test_build_next.py
tests/test_canary.py
tests/test_dispatch.py
tests/test_enforce.py
tests/test_guard_mutation.py
tests/test_handback.py
tests/test_hooks.py
tests/test_launch_contract.py
tests/test_linear_loop.py
tests/test_loop.py
tests/test_main_broken.py
tests/test_merge.py
tests/test_metrics.py
tests/test_next.py
tests/test_one_action.py
tests/test_parallel_dispatch.py
tests/test_plan.py
tests/test_post_pr.py
tests/test_pr_actions.py
tests/test_process_depth.py
tests/test_protect_state.py
tests/test_reasons.py
tests/test_reconcile.py
tests/test_runtime.py
tests/test_seat_command_forms.py
tests/test_shepherd.py
tests/test_signal_status.py
tests/test_spec_mode.py
tests/test_templates_errors.py
tests/test_tone.py
tests/test_traces.py
tests/test_traces_seats_only.py
tests/test_tracker.py
tests/test_verdict.py
tests/test_workspace.py
tests/test_worktree_command.py
tests/test_ziran.py
```

T017-T021 are complete. All requested round 2 findings are resolved; no open
CRITICAL or HIGH finding remains. Earlier unselected L2, L3 and L5 remain
recorded under Deferred. The collision remedy deliberately refuses pending
cross-item prompts because the transcript cannot recover launch metadata; an
Item: line distinguishes the retry and its trace binding is regression-tested.

Final diff check passes. Added text contains no absolute local paths or
em-dashes. The owner design is untouched and all changes remain uncommitted
on 955-adhoc-launch.
