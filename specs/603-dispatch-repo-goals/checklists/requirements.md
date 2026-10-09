# Requirements Checklist: 603-dispatch-repo-goals

**Purpose**: Check that the requirements of `spec.md` are complete, clear and testable
before implementation.
**Created**: 2026-10-09

## Completeness

- [x] CHK001 Each of the two defects has a root cause with file and line, reproduced in a
  fixture (spec, Root cause).
- [x] CHK002 Every Acceptance line of #603 maps to a scenario: `--repo` with two
  repositories (US1.1), unchanged with one (US1.2), a fresh day reaches approval (US2.1),
  the invariant row (FR-011).
- [x] CHK003 The candidate without `repo` is specified for both outcomes: derived from
  `paths` (US1.3) and unresolved (US1.4, FR-004, FR-006).
- [x] CHK004 The sibling `worktree add` remediation lines are covered (FR-007).
- [x] CHK005 The lead is asked for `repo` in both places the item names (FR-008).

## Clarity

- [x] CHK006 "Paths fall under a repository" is defined (existence in the configured
  checkout; Assumptions).
- [x] CHK007 The choice between the item's two goals fixes is decided with its reasons
  (Design decision for defect 2).
- [x] CHK008 What approve reads in each case is stated: memory with goals, the draft
  without, `no goals` with neither (US2.2 to US2.4).

## Principles

- [x] CHK009 No new refusal under observe or guarded (#530): the lint is a plan line;
  approve refuses less.
- [x] CHK010 Every next action is a command `next` returns (#551): `--repo` start command,
  the park command, the existing goals row; no `then` text changes.
- [x] CHK011 Strict is not weakened: `memory/goals.md` stays written only by `goals edit`.
- [x] CHK012 New rules have invariant rows planned (I26, I27) in design 9.2 and
  `tests/test_invariants.py`.

## Testability and scope

- [x] CHK013 Each FR has a test task ordered before its implementation task (tasks.md).
- [x] CHK014 One-repository behaviour is pinned unchanged (FR-002, SC-003).
- [x] CHK015 Out of scope items from #603 are not touched (#600 fast checks and card
  values, deploy.deny patterns, GitHub tracker auth); `plan add --repo` is Deferred.
