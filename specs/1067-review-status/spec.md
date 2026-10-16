# Feature Specification: a review-driven commit status reads as review, not CI

**Feature branch**: `claude/1067-review-status`
**Item**: 1067 (issue taoq-ai/wuwei#1067), tier full, goal G-2
**Input**: ai-stacks publishes its approval rule as the commit status `Review Gate`. WUWEI reads it as
CI: six PRs needing a reviewer show `CI running [waiting]`, and #3274 reads as a red build.

## The promise in my words

When a commit status at the head was posted by a workflow the repository runs on
`pull_request_review`, WUWEI names it as review work: pending is `waiting on review: <context>`,
failure is `change request outstanding: <context>`. Both are actionable safety gaps, so the team
acts and the merge stays refused. WUWEI learns which workflows are review-triggered from the code
host, never from config. It only asks when a head has a commit status, and caches the answer for a
day. If the host cannot answer, the status stays CI, which still holds the merge.

The acceptance scenarios, restated:

1. Check runs done, a pending status from a review-triggered workflow: one actionable
   `waiting on review: <context>` gap, no `CI running`.
2. That status failing while a change request stands: `change request outstanding: <context>`,
   no `CI failing`.
3. A failing status from an ordinary CI workflow: `CI failing: <context>`, as today.
4. A head with no commit status: no Actions call at all.
5. The Actions read fails: the status stays CI, never a pass.
6. Either review gap: the merge door refuses, with or without `--auto`.
7. Config keeps five keys; the runtime stays at 3,000 lines or fewer.

## Clarifications

### Session 2026-10-16

- Q: What ties a status to its workflow? A: The run id in the status's `target_url`
  (`https://github.com/<owner>/<repo>/actions/runs/<id>`). The context does not equal the workflow
  name (`Review Gate` vs `Review Gate Publisher`), so the context-match route is out (1067-probe).
- Q: Does the run's own event classify the status? A: No. A PR without a review has only
  `pull_request` runs of the workflow. WUWEI compares the run's workflow path with the paths seen
  in `repos/<repo>/actions/runs?event=pull_request_review` (1067-probe).
- Q: Which statuses trigger the read? A: Only unsettled ones (pending, failure, error) whose
  `target_url` names a run in the same repository. A success status yields no gap either way, so
  it never costs a call.
- Q: Does `failure` need a CHANGES_REQUESTED review to read as a change request? A: No. The
  status state decides, as the promise says; the review list is not consulted.

## User Scenarios & Testing

### User Story 1: a PR waiting on a reviewer says so (Priority: P1)

The planner reads `wuwei status` and sees that a PR needs a reviewer, not that CI is running.

**Independent test**: a PR whose check runs passed and whose `Review Gate` status is pending,
tied by `target_url` to a run of a review-triggered workflow, gives exactly
`waiting on review: Review Gate`, actionable, kind safety.

### User Story 2: a change request is not a red build (Priority: P1)

**Independent test**: the same status failing gives `change request outstanding: Review Gate`
and no `CI failing`.

### User Story 3: ordinary CI and unreadable hosts are unchanged (Priority: P1)

**Independent test**: a failing status tied to `ci.yml` (not review-triggered) gives
`CI failing: lint`; with the Actions read refused, the review status gives `CI running` or
`CI failing: Review Gate`; a head without statuses makes no `/actions/` call.

### Edge Cases

- A status whose `target_url` is empty, external, or another repository's run: CI, no call.
- A repository with no `pull_request_review` runs: the cached path list is empty, so no per-run
  read follows.
- A run JSON without `path`, or a reply that is not JSON: treated as unreadable, the status stays CI.

## Requirements

### Functional Requirements

- **FR-001**: `gh.pr` keeps each commit status's `target_url` in the rollup as `url`.
- **FR-002**: `gh.workflow_paths` reads the workflow paths of one run or of the last 100
  `pull_request_review` runs.
- **FR-003**: `evidence.review_contexts` returns the contexts of unsettled statuses tied to a
  review-triggered workflow; it caches the path list per repository for a day and makes no call
  when no status qualifies.
- **FR-004**: `evidence.ci_gaps` reports those contexts as `waiting on review:` or
  `change request outstanding:` and leaves them out of `CI running` and `CI failing`.
- **FR-005**: any failed or malformed Actions read leaves every status CI.

## Success Criteria

- **SC-001**: on ai-stacks #3300, #3291 and #3274 the live read gives `waiting on review: Review Gate`,
  `waiting on review: Review Gate` and `change request outstanding: Review Gate`.
- **SC-002**: the suite passes with the runtime at 3,000 lines and five config keys.

## Assumptions

- The workflow `path` in the runs list and in a single run match exactly (no `@ref` suffix); the
  probe and the live read show `.github/workflows/review-gate.yml` in both. A suffix would leave the
  status CI, the safe side.
- Only github.com `target_url`s are matched. A GitHub Enterprise host stays CI until a case shows up.
- A review-triggered workflow that has not run on any of the last 100 reviews is not recognised;
  its status stays CI. Overturned if a repository shows this in practice.

## How this fails

1. A workflow that is real CI but also listens on `pull_request_review` (a re-run on review) posts a
   failing status: it reads `change request outstanding`, sending the team to reviews instead of the
   build. The merge is still refused.
2. The day-old cache misses a newly added review workflow: its status reads as CI for up to a day.
3. A token without Actions read gets 403 on every evidence read with a status: each call costs a
   failed request and the status stays CI, as today.
