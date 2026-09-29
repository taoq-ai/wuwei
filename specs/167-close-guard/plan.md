# Implementation Plan: Refuse unresolved day close

## Summary

Extend the shared close reader for approved items, recorded dispositions, owner
questions and pushed branches. Keep the existing Stop scope and planner routing.
Replace build park prose with a lintable decision and recorded seat outcome.

## Technical Context

Python 3.11+, standard library runtime, pytest development tests. Existing state
writer, decision evaluator, PR reader and registry remain the boundaries. No new
configuration, dependency or guard registration.

## Constitution Check

Stdlib only; three-state exits; shared behavior; failing tests first; minimal
extension of the vcs port; no direct external tool calls from core. No exceptions.

## Design

- Add unresolved-work evaluation to cli/wuwei/closing.py, retaining all findings
  even when individual evidence reads fail. Reuse decision.evaluate/today_path,
  recorded seat outcomes, and pr_actions.evaluate for verified dispositions.
- Skip branch reads for already owned item PRs, including cleaned-up merged worktrees.
- Use current item.pr links and raised_prs/claimed_prs. Add vcs.pushed_branches
  to list remote-tracking branch names and use vcs.branch for the item's branch.
  Recordings and in-process fake cover the adapter; no network reads.
- Owner decision resolution requires existing external PR disposition evidence;
  seat-written Outcome text cannot authorize owner work.
- Build creates an unused D-<n> record, validates it, records its seat outcome
  and links it in the reserved build.parked event. Keep phase/status semantics.
- Tests use tests/test_stop.py fixtures, tests/test_build.py and adapter replay.

## Validation

Reproduction before changes: the supplied dry-run workspace had an approved
blocked item and close_requested=true; closing.check and the planner Stop both
returned (0, ''). Probe used read-only readers with state writers disabled.

Run targeted regression tables red, then green. Run the full suite using the
orchestrator-provided interpreter. Check diff whitespace and authored files for
machine-specific paths, em dashes and emojis.

## Deferred

General authenticated owner completion, remote fetch at close and unrelated
scanner-generated parks are separate work. No new artifact scaffolding is needed.

## Verification evidence

The same read-only dry-run probe now returns exit 1 naming both the blocked
approved item and the owner decision. Regression tests first reproduced the
missing refusals and invalid build record. Review additionally reproduced and
fixed phase-only merge bypass, invalid decision directories, resolved owner
decisions reopening after merge, and removed completed worktrees blocking close.

Final full-suite result: 5201 passed, 2 skipped in 81.62s (0:01:21).
Added-line and new-file hygiene and git diff whitespace checks passed.
