# Feature Specification: one re-entry command for work done outside the record; no builder without a build record

**Feature Branch**: `901-reconcile` (stacked on `904-recovery`)

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #901 (independent review, item 1, with the owner's decision): "Give every
item one idempotent re-entry command. The launch guard refuses a builder seat launched with no
build record and points the planner to `build next` (or `reconcile` for work already done
outside)."

## What happened

On the owner's 2026-10-12 day several items were built outside the record during workarounds:
TIN-790 with 15 pushed commits, TIN-916, REVIEW-3140 and TIN-929 ran unregistered, and teammate
PR takeovers were done by hand. Nothing let that work back in. `worktree adopt` records a clean
checkout but no build; `dispatch next` refuses the gates until a builder seat has stopped; `pr
claim` only moves a `planned` item. The Agent guard let a builder launch with no build record,
which is how those seats left the record.

## Claims checked against the base branch

| Claim | Holds | Where | Failing test |
|---|---|---|---|
| Adoption records a checkout, never a build | yes | `workspace.adopt_worktree` (`workspace.py:768`), `state.record_worktree` | `test_reconcile_brings_outside_work_back_in_three_repositories` |
| Adoption refuses dirty work outright | yes | `workspace.py:791-795` | same test (repository `api`) |
| The gates need a stopped builder seat | yes | `dispatch.next_step`, `dispatch.py:679-682` | same test: `dispatch next` on a reconciled item |
| A builder launch with no build record registers | yes | `agent_launch._check` `reserve`, `build.started` returns on no record | `test_a_builder_launch_with_no_build_record_is_refused_and_build_next_launches_it` |
| `pr claim` moves only a `planned` item, to `raised`, skipping the gates | yes | `state.record_pr`, `state.py:412` | `test_reconcile_with_a_pr_goes_through_checks_and_gates` |

## User Scenarios & Testing

### User Story 1 - finished work outside the record comes back in (Priority: P1)

**Independent Test**: three repositories, one item each: committed work on a branch worktree
(`app`, item planned), the same with the item already in `implement` and no build record
(`web`), committed plus uncommitted work (`api`). `build reconcile` each, twice. One item each,
the work untouched, and a next action that runs.

**Acceptance Scenarios**:

1. **Given** a planned item and a linked worktree with commits over the default branch, **When**
   `wuwei build reconcile <item> --worktree <path>` runs, **Then** the worktree is the item's, a
   builder brief records what exists, a build record starts at the fast checks (no builder seat
   is invented), the checks run, and on a pass the item reaches `gate`; `dispatch next` then
   returns the gate launches.
2. **Given** an item in `implement` with no build record, **When** reconcile runs, **Then** the
   same.
3. **Given** uncommitted files, **When** reconcile runs, **Then** the work is registered as it is,
   the build is not done (the existing uncommitted-changes rule), the next action is a builder
   `continue` naming the files, and its launch registers; gates and publication stay blocked
   until the tree is clean.
4. **Given** any of these, **When** reconcile runs again with nothing changed, **Then** nothing is
   written again: one item, one brief, one build record, no second check run.
5. **Given** an item whose build record holds an unlaunched `launch` (or a `continue`) and work
   done outside it, **When** reconcile runs, **Then** the record keeps its start head and fix
   rounds and goes to the fast checks on a brief at the current HEAD.
6. **Given** a reconcile interrupted after its record was written, **When** it runs again,
   **Then** it finishes the checks; nothing is duplicated.

### User Story 2 - a builder launch needs a build record (Priority: P1)

**Independent Test**: launch a builder from its brief with no build record; the guard refuses,
naming `bin/wuwei build next <item>` and `bin/wuwei build reconcile`; `build next` returns a
launch of that brief and the guard accepts it.

**Acceptance Scenarios**:

1. **Given** `guards.enforce` on and no build record, **When** a builder seat launches, **Then**
   it is refused and nothing is registered.
2. **Given** that refusal, **When** the planner runs `build next <item>` and launches its prompt,
   **Then** the launch registers (no loop).
3. **Given** `guards.enforce` off, **When** the same launch runs, **Then** the hook records
   `guard.would_refuse`, and the seat is registered as before so `build next` continues it
   (#892).
4. Sentinel, shepherd, lead and steward launches are unchanged.

### User Story 3 - a PR, a branch, a different repository (Priority: P2)

1. **Given** `--pr <owner/repo#n>`, **When** reconcile runs, **Then** the PR is claimed for the
   item once (the existing `pr claim`), and a planned item still goes through checks and gates:
   the claim moves it to `implement` in its own write instead of jumping it to `raised`.
2. **Given** `--repo <name> --branch <b>` and no worktree, **When** reconcile runs, **Then** the
   repository's worktree on that branch is adopted, else `worktrees/<item>` is checked out on it
   (the path `pr claim` already takes).
3. **Given** a worktree of another repository than `--repo` or the item's planned repository, or
   an item that records another worktree, **When** reconcile runs, **Then** it refuses (exit 1)
   and changes nothing: those need an explicit resolution.

### Edge Cases

- A running builder seat on the build: refused, wait for its stop hook.
- A parked or escalated item: refused, `plan resume` first. A merged item: nothing to do.
- An item past its build (`gate`, `delta`, `raised`): the worktree and PR steps run, the build
  is left as it is.
- No fast checks configured: the record says so and the gates and CI are the evidence.
- No merge base with the remote default branch: `seat brief`'s own refusal (fetch first).

## Requirements

- **FR-001**: `wuwei build reconcile <item> [--worktree PATH] [--pr REF] [--repo NAME --branch B]`
  composes `workspace.adopt_worktree`, `shepherd.claim_pr`, `brief.write`, `build.check` and
  `complete_checks` (its spec step check). It prints what exists (worktree, HEAD, start,
  changed files, uncommitted files, PR), what was verified (the fast checks at HEAD) and what
  stays unmeasured (gates, owner approval, anything the outside work ran). Exit 0 recorded, 1
  refused, 2 could not run.
- **FR-002**: a reconciled build is an ordinary build record in status `check` with its own
  logged builder brief; `start` is the brief's merge base, or the existing record's start.
- **FR-003**: idempotent: each step reads what is recorded first; the record keeps the HEAD and
  uncommitted files it reconciled, and a rerun with both unchanged writes nothing.
- **FR-004**: `workspace.adopt_worktree` takes `dirty=True` for reconcile; `worktree adopt` stays
  clean-only and its refusal names reconcile.
- **FR-005**: `dispatch.next_step` accepts a `done` build record in place of a stopped builder
  seat before the gates.
- **FR-006**: the launch guard refuses a builder launch with no build record for its item, naming
  `bin/wuwei build next <item>` and `bin/wuwei build reconcile <item> --worktree <path>`. With
  `guards.enforce` off it registers the seat as before and the hook logs `guard.would_refuse`.
- **FR-007**: one checkout path for an existing branch (adopt its worktree, else `worktree add
  --branch`) serves `pr claim` and reconcile; `pr act`'s missing-worktree step names reconcile.
- **FR-008**: the planner charter says a builder launches only from `build next`, and work done
  outside comes back with `build reconcile`; reference and daily docs describe it.
- **FR-009**: `build next` for a new build of a planned item past the day's derived CAP raises
  the CAP wait, as `wuwei next` counts it; `build check` with no record names reconcile.

## Review round (FIX)

- **FR-010** (F1): reconcile refuses while any builder seat of the item runs, recorded on the
  build or only in the seat ledger.
- **FR-011** (F2): an item's recorded repository is never overridden by `--repo` or by the
  repository of `--pr`; reconcile refuses and names the explicit way.
- **FR-012** (residual): `complete_checks` records `checked`, the HEAD the passing checks ran on.
  `brief.gate_ready` refuses a gate brief or launch at another head; `dispatch next` sends a done
  build whose worktree moved past it back to `build check` (`build.rechecked`), and refuses the
  gates while a build that has a checked head is not done. This holds for every build.
- **FR-013** (F3): a reconcile at a new HEAD keeps the record's iteration, repeats and signature,
  so an unchanged failing outside loop parks at `build.stuck_after`.
- **FR-014** (F4, F6): one helper, `_base_start`, reads the brief's merge base and keeps it only
  when it is an ancestor of HEAD, for `build next` and reconcile.
- **FR-015** (F5): stdout is one JSON document (the claim prints to stderr); `verified` lists
  passing checks, `failed` the others.
- **FR-016** (F7): `--track FULL` records the item's track through the brief, and the protected
  path refusal names it.

- **FR-017** (delta D1): every check completion runs `_unbuilt` (uncommitted changes, private
  files in the commits since start, no change), a recheck at a gate included; only the spec step
  stays with `implement` and `fix`.
- **FR-018** (delta D2): `checked` is the one HEAD every fast check measured (a mismatch or a
  missing row is incomplete: rerun), and HEAD only when no fast check is configured.

## Success Criteria

- **SC-001**: the failing tests above pass; every test file importing a changed module passes
  under 3.12 and 3.11.

## Assumptions

- `reconcile` is `build reconcile`, a subcommand: `tests/test_cli.py` pins the twenty listed
  commands (#848), and reconcile produces a build record that starts at the build's own checks.
- The item must already be in the approved plan (`plan add` on the owner's word). Reconcile never
  admits an item: "never finish an owner's item outside the plan" stays the planner's rule.
- A reconciled build gets its own builder brief named `<item>-reconcile-<head12>`. It is the
  brief a fix round or a failed check continues, so every later builder launch passes the guard
  (logged brief at an unchanged HEAD). A new HEAD gets a new brief.
- Dirty work is verified like any build: the existing `_unbuilt` rule makes uncommitted changes a
  builder iteration, so no new blocking state is added; the gate launch already refuses a dirty
  tree.
- The idempotency key is (HEAD, uncommitted paths): unchanged means nothing new to verify.
- `--pr` on a planned item: `pr claim`'s state write takes it to `implement`, not `raised`
  (`record_pr(built=True)`), so a refused claim moves nothing. Tracker claim is the existing
  idempotent duty.
- `build next` for a new build past the day's derived CAP waits instead of recording it: the
  guard sends a builder with no record there, and the CAP refusal at launch only logs (#837 B5),
  so the wait has to come before the record. Reconcile does not check CAP: the work is done and
  it launches no seat.
- `worktree adopt` stays: it is the plain clean-checkout primitive the docs and owner use;
  reconcile is the one re-entry command the planner is told about.

## Deferred

- Binding a stopped seat that ran outside the record to the reconciled build (#892 already
  continues it through `build next`).
- Scope changes between the outside work and the item's plan: the gates judge them.
