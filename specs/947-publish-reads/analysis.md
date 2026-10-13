# Specification analysis: #947

Reviewed spec.md, plan.md and tasks.md before implementation on 2026-10-13.

## Findings

No CRITICAL or HIGH findings. No unresolved ambiguity, duplication or unmapped work.

| Requirement | Tasks | Coverage |
|-------------|-------|----------|
| FR-001 | T003, T004, T007 | Named Vercel reads and alias |
| FR-002 | T003, T004, T007 | GET-only, no fields/input |
| FR-003 | T003, T004, T005, T007 | Writes, explicit denies and compounds |
| FR-004 | T005, T006, T007 | Card wording and binding |

Four requirements, eight tasks, 100% requirement coverage. T001/T002 supply mandated artifacts; T008 supplies final review. No constitution violations: task-specific testing instructions take precedence; design interpretation is explicit in Assumptions. No new dependency, state or external call. Next: requirements checklist review, then test-first implementation.

## Implementation evidence

Test-first regression run on tests/test_edges.py selected the new publish cases. Reads failed because they returned owner cards, and the card assertion failed because its description lacked exact-command wording:

```text
14 failed, 36 passed, 236 deselected in 0.34s
```

After the initial shared fix, the full edge file passed:

```text
286 passed in 2.43s
```

Affected test discovery used `rg -l '\bedges\b|check_deploy' tests --glob '*.py'` and source import/caller searches. The selected files include all direct imports and additional hook, mutation, enforcement and doctor coverage.


The first affected-file run passed before review fixes:

```text
2024 passed in 65.46s (0:01:05)
```

## Adversarial review and one fix round

Independent correctness, security and simplicity review found two actionable implementation issues:

- HIGH: unparsed short clusters such as `-iXDELETE`, `-ifref=main` and `-iFref=main` could use the new GET exemption. Resolved by keeping residual unparsed short clusters owner-only. Spaced `-i -X GET` remains supported; no parser expansion.
- MEDIUM: a safe GET for an environment named `rerun` or `rerun-failed-jobs` fell through to the workflow rule. Resolved by returning clean immediately after the deployment/environment read predicate passes.

Both were reproduced before the fix round:

```text
8 failed, 39 passed, 247 deselected in 0.71s
```

The same explicit affected-file selection passed after these changes. No changes were made to the owner design, approval identity, state lifecycle or dependencies.


## Final verification

Using the task-specified interpreter from the worktree root:

```sh
python -m pytest -q -p no:cacheprovider tests/test_guard_mutation.py tests/test_canary.py tests/test_outward.py tests/test_e2e_day.py tests/test_dispatch.py tests/test_enforce.py tests/test_invariants.py tests/test_merge.py tests/test_doctor.py tests/test_hooks.py tests/test_edges.py
```

```text
2032 passed in 56.58s
```

The independent delta review found no remaining blocking correctness, security or simplicity findings. The fix round addressed both review findings. Requirements checklists pass, all tasks are complete, and git diff --check is clean. Artifact checks found no absolute local paths or prohibited punctuation in feature documents. Branch remains 947-publish-reads; the owner design file is unchanged. No extension hooks are configured. Work remains uncommitted; no commit, push, stash or gh commands were run. Nothing remains unfinished for this issue.


## Review follow-up analysis

Read the external #947 findings in full before starting. F1 is HIGH: GH_VALUED omits --preview and api() returns clean for multiple operands before examining deployment/environment paths. F3 is confirmed: the safe-read predicate does not inspect headers. The implementation plan resolves both at the shared scanner/api classifier, without changing owner identity or host permissions.

Coverage: FR-002/FR-003 map to T010 (preview and ambiguous targets) and T011 (override headers); T012 covers all imports plus signal status. F2 and F4 are explicitly owner decisions in spec Assumptions; the design conflict and proposed wording are documented. F5 needs no action. No CRITICAL/HIGH artifact gaps remain; F1 implementation remediation is required by T010. This follow-up is explicitly authorized despite the prior fix round.


### Follow-up test-first evidence

F1: preview writes and ambiguous deployment/environment operands returned clean before the fix. Spaced and equals preview GETs are retained as positive controls.

```text
10 failed, 51 passed, 247 deselected in 0.46s
61 passed, 247 deselected in 0.33s
```

F3: four header forms across both endpoint types returned clean before the fix. Ordinary Accept headers remain reads.

```text
8 failed, 55 passed, 255 deselected in 1.64s
63 passed, 255 deselected in 0.99s
```

Each finding was reproduced before its implementation change. All tests classify fixture commands without executing them.


### Follow-up final verification and disposition

Using the task-specified interpreter with explicit files:

```sh
python -m pytest -q -p no:cacheprovider tests/test_guard_mutation.py tests/test_canary.py tests/test_outward.py tests/test_e2e_day.py tests/test_dispatch.py tests/test_enforce.py tests/test_invariants.py tests/test_merge.py tests/test_doctor.py tests/test_hooks.py tests/test_edges.py tests/test_signal_status.py
```

```text
2153 passed in 39.33s
```

- F1 HIGH fixed: --preview consumes its value in spaced and equals forms through GH_VALUED; multiple operands including a deployment/environment path require a card.
- F2 unchanged by instruction: host Vercel denies and init migration are owner decisions. Hook acceptance does not remove the host deny; the Vercel MCP route remains available. Recorded in spec Assumptions.
- F3 fixed: -H/--header values containing override, case-insensitively, cannot qualify as reads. Ordinary headers remain allowed.
- F4 unchanged by instruction: owner design section 4.7 conflicts with the read exemption. Conflict and proposed owner wording are recorded in spec Assumptions for the PR.
- F5 no action: GET does not dispatch or rerun, and writes still require approval.

Independent delta review found no remaining blockers. All affected test imports were covered, plus signal status. git diff --check passed; an AST comparison confirmed PERMISSIONS_DENY is unchanged; init and the owner design have no diff. Branch remains 947-publish-reads. Feature artifacts contain no absolute local paths or prohibited punctuation. All follow-up tasks are complete. Changes remain uncommitted. Owner decisions F2 and F4 remain outstanding intentionally.
