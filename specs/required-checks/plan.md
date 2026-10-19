# Implementation Plan: a required status check that never ran on the head is a gap

**Branch**: `fix/required-checks` | **Spec**: `specs/required-checks/spec.md`

## Summary

`gh.required_checks` reads the contexts the base branch requires from branch protection and the
rulesets; `evidence.gaps` keeps that answer 15 minutes per repository and branch and names each
required context with no run on the head. `gh.pr` carries `mergeable_state`, and a blocked PR with
no other safety gap gets a gap that says so.

## Technical Context

Python 3.11 stdlib. Tests in `tests/test_evidence.py` through the fake host in `tests/conftest.py`,
which now answers the branch read (`protection`, by branch, or a raised `GhError`) and the rules
read (`rulesets`, by branch) in the shapes read live on `taoq-ai/wuwei`. Runtime 3,208 lines at
89e7064e; this item may add 10.

## Constitution Check

- I. Stdlib only: `hashlib` (already imported) for the cache key.
- II. Evidence over steps: the gap names the check; it says nothing about how to start it.
- III. An auditor: no new door. The merge door reads one more safety gap; an unreadable read fails
  closed, as a door that cannot read its evidence must.
- V. Test first: the new tests ran red on 89e7064e's runtime (21 failed, 285 passed in
  `tests/test_evidence.py`, `tests/test_replay.py` and `tests/test_status_perf.py`) and green at the
  head (306 passed).
- VI. Budgets: no config key; runtime 3,218 lines (+10, the item's budget), after moving `SHA` and
  `PR_TTL` into the constants block (-4).
- VII. Security first: a required check that never ran can no longer read as a pass.

## Design

- `gh.rules` reads every page (`pages`, 100 per page); `setup.doctor` keeps reading it.
- `gh.required_checks(repo, branch)`: `GET repos/{r}/branches/{b}` `protection.required_status_checks.contexts`
  plus the `required_status_checks` rules' contexts, `dict.fromkeys` for once each in order. Any error
  or a missing key raises.
- `evidence.gaps`, after CI not started: key `required-<owner>__<repo>-<sha256(base)[:16]>`, through
  `_cached` with `PR_TTL`; `_cached` writes only a returned value, so a raised read is read again. A
  context is run when a check run's name or a status's context equals it. The `except` takes
  `GhError`, `KeyError`, `TypeError` and `AttributeError` and adds the waiting gap; other errors keep
  reaching the outer `evidence unreadable`.
- The blocked gap is added after every other gap, just before the merged return, when
  `mergeableState == 'blocked'` and `blocking(found)` is empty.
- The PR warm cache (#1161) keeps the PR with its `mergeableState`; it holds only while the head and
  update time hold and CI had settled, so a review that clears GitHub's hold moves the update time and
  is read again.

## Lines

`cli/wuwei/*.py` 3,208 at 89e7064e to 3,218 at the head (`for f in cli/wuwei/*.py; do cat $f; done | wc -l`):
gh.py +5; evidence.py +5 (9 new lines, 4 fewer from moving `SHA` and `PR_TTL` into the constants block).

## Route differential (AGENTS.md)

`specs/required-checks/route_diff.py` runs all 257 routes of `tests/fixtures/routes.json` (sha256
`9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0`) through `hook.handle` at main
and at the head, under a host with no protection and one whose main requires `test (3.11)`, with PR 5
otherwise complete. 514 cases: with no protection none moves; with `test (3.11)` required 23 move,
every one a merge route of o/r#5 (15 `gh api` PUT spellings on `merge`, one on `ccr/auto_merge`, and 7 `gh pr merge`
forms, `--auto` included) from allowed with `merge.checked` to refused with `- required check not run
at aaaaaaa: test (3.11)`. No refusal names another PR or repository.

## Mutants

`specs/required-checks/mutants.py` applies each mutant to both copies (`cli/wuwei/` and
`.claude/wuwei/cli/wuwei/`) in a fresh `git archive` copy, one at a time, and counts a kill only on a
FAILED test. Results are in the PR body.
