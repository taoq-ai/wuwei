# Implementation Plan: a review-driven commit status reads as review, not CI

**Branch**: `claude/1067-review-status` | **Spec**: `specs/1067-review-status/spec.md`

## Summary

Follow a commit status's `target_url` run id to the run's workflow path, and compare it with the
workflow paths the repository runs on `pull_request_review`. A match turns the status into a
review gap instead of a CI gap.

## Technical Context

Python 3.11 stdlib, the gh CLI over REST only (GraphQL is refused in cloud sessions). Tests use
`tests/conftest.py`'s FakeGh. Runtime budget 3,000 lines, already full: lines come out of
`evidence.py` and `gh.py` only (other builders hold `guards.py` and `setup.py`).

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: the classification reads the host; no new command.
- III. An auditor: no new door; the merge door refuses through the existing safety-gap path.
- V. Test first: the new tests ran red before the change.
- VI. Budgets: five config keys unchanged; runtime held at 3,000 by freeing equal lines.

## Design

- `gh.pr`: each status carries `url` (its `target_url`).
- `gh.workflow_paths(repo, query)`: `repos/<repo>/actions/runs<query>`; the default query lists the
  last 100 `pull_request_review` runs, `/<id>` reads one run.
- `evidence.review_contexts(root, repo, rollup)`: unsettled statuses whose `target_url` names a run
  in this repository; the review path list is cached a day (`review-<owner>__<repo>`); each candidate
  run is read once; any read failure returns an empty set.
- `evidence.ci_gaps(rollup, review)`: review contexts become `waiting on review:` or
  `change request outstanding:` gaps, the rest stays CI.

## Lines freed

`DAY` constant, the inner `import datetime` in `budget`, `_upper` in gh.py, `spec_engine`'s inner
function, `item_for`'s early return, `review_duty`'s two refusals in one test, `verdicts`'
duplicated append, the gaps preamble, the reviewer list, and the comment-thread fallback loop. Each is
behaviour-preserving and covered by existing tests.

## Rollback

Revert the PR. No state, config or ledger format changes; the `review-*` cache files expire
after a day and nothing else reads them.
