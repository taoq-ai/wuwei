# Cross-artifact analysis

Reviewed spec, plan and tasks after task generation. FR-001/002 map to T002/003; FR-003 to T006/007; FR-004 to T004/005; FR-005 to T008/009; FR-006 to T010/011. Documentation and validation map to T012/013.

No open CRITICAL or HIGH findings. The old constitution VII conflicts with the explicit owner boundary; T012 applies the owner-authorized amendment. No new trusted state is introduced. Every behavior has a test task before implementation. Clarifications are recorded under Assumptions. The custom requirements review has seven satisfied criteria; implementation does not edit its markers.


## Implementation review

The test-first checks covered nudges and defaults, app versus infrastructure deployment,
merge eligibility, UUID matching, and complete versus incomplete unchanged fix handbacks.
Review regressions also cover compound commands with a later protected operation, protected
outbound body files (including after owner approval), malformed connector inputs, encoded
environment endpoints, and cloud operation names used as ordinary argument values.

The existing scope helpers, recorded verdict findings, build handback, head binding,
retry/park limits and security readers are reused. No trusted state or event producer was
added. Explicit enforcement tests opt in; default-mode tests assert visible nudges. Stop
and Codex runtime files are unchanged. The code path behind #987 now admits reasoned
unchanged fix heads. Local sources do not identify the specific #857/#982 refusals, so
those issue closures are not asserted from their titles. Real-day validation is deferred.


## First-build validation, superseded by the review below

All test files were supplied explicitly to the task-provided interpreter with
`-m pytest -q -p no:cacheprovider`; no bare-suite invocation was used.

`8177 passed, 1 xfailed in 537.19s (0:08:57)`

The final security fix preserves exactly one canary event per checked body while scanning
merge, approval and admin early-return paths before authorization. The focused security,
edge and enforcement run passed 549 tests before the full rerun. Review has no remaining
findings. Diff whitespace and changed-file hygiene checks pass; Stop is unchanged.
No commits, pushes, GitHub commands or real-day external actions were performed.

## Review fix round

The supplied FIX verdict supersedes the first-build review conclusion above. F1 through
F9 map to T014 through T020. Each behavior was reproduced by failing tests before its
implementation. The specification, plan and constitution now distinguish ordinary merge
eligibility from protected path cards and require the journaled merge path for owned PRs.

- F1: raw list and string canaries are scanned before shape validation; unrun send checks block.
- F2: owner_paths and never_auto_paths retain head-bound cards, including rename sources.
- F3/F4: Netlify colon commands, cloud mutation verbs, Fly scaling and gcloud security flags
  require cards; cloud option values are excluded from operation matching.
- F5: Vercel secret pulls stay in host deny rules and survive upgrade.
- F6/F8: repository administration uses owner cards, including combined body-scan findings.
  Environment writes have one card owner across the whole hook, avoiding duplicate approval.
- F7: deploy.workflows is removed from schema, template and calibration output, and retired
  for upgrade migration. Calibration observations of deploy workflows remain useful evidence.
- F9: raised and claimed PRs refuse raw merges with the requested bin/wuwei merge next step.
  Numeric, URL, branch, current-branch and explicit repository forms are covered. Other PRs
  and PR approval remain nudges. Existing worktree and ownership readers are reused.

The import-scoped run supplied 82 explicit files to the task interpreter with
`-m pytest -q -p no:cacheprovider`: `2 failed, 6803 passed, 1 xfailed in 474.68s (0:07:54)`.
Both failures were obsolete deploy.workflows expectations: the day-flow fixture and the
default-config assertion. Both are corrected. The final run repeated the affected files
and security, hook, merge, calibration, migration, documentation and invariant checks:

`2048 passed in 70.45s (0:01:10)`

All nine findings have regression coverage, with the relevant failures observed before
implementation. Diff whitespace checks pass. No additional runtime dependency, trusted
record producer, commit, push, gh command or external action was introduced.
