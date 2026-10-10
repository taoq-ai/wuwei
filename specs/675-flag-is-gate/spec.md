# Feature Specification: a trust_surface flag asks for the security gate, not the owner

**Feature Branch**: `675-flag-is-gate`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #675 (owner, 2026-10-10, item 43): "Every risk-flagged PR needs you,
however small the risk. The trust_surface flag sends any such PR to you even after the
security gate passed a delta round. A flagged item whose security gate passes should be able
to merge under the normal policy, or the flag should name which change needs the owner's
eyes." Deliver: the merge policy treats `trust_surface` as "security gate required", not
"owner merges". Once the security verdict is PASS for the current head (delta included), the
PR follows `merge.default_tier` and the repository rules like any other. While the gate is
open or FIX, the PR waits on it, not on the owner. An owner-only route remains for the
explicit list `merge.owner_paths`, and the reason names the path that matched. `merge check`
prints which rule applies.

## Root cause

Reproduced in process on `main` (the `case` fixture of `tests/test_merge.py`: one configured
repository with `merge.auto = true`, `merge_deploys = false`, all three gate verdicts PASS at
the head, green checks, an approval at the head), with `flags.trust_surface` set on the item
and in its `plan.approved` event:

| `merge.default_tier` | `wuwei merge check` | `wuwei merge` |
| --- | --- | --- |
| `today` | exit 1, `merge policy: item carries a risk flag; the owner merges; ask the owner` | merges (through the `today` default grant) |
| `ask` | exit 1, same reason | exit 1, card D-1 written for the owner |
| unset (guarded) | exit 1, same reason | exit 1, card D-1 written for the owner |

The same PR without the flag clears `merge check` (exit 0) and merges with no card under every
tier. So the flag alone sends the PR to the owner, and `merge check` tells the planner "the
owner merges" even where `wuwei merge` would merge.

In the code:

- `cli/wuwei/merge.py:165-168` (`item_evidence`): every risk flag, `trust_surface` included,
  is `Refused('item carries a risk flag')`, read from the item and from every recorded
  `plan.approved` / `plan.added` event. The verdict of the security gate is never consulted
  for this rule, so a PASS at head changes nothing.
- `cli/wuwei/merge.py:323-326`: any refusal in the auto policy is printed as
  `merge policy: <reason>; the owner merges; ask the owner`. A pre-PR gate that is still open
  or FIX at the head (`merge.py:276-277`, `gate_check` in `cli/wuwei/guards/pr.py:142`) gets the
  same owner wording, although no owner answer can clear it: the gate has to pass.
- `cli/wuwei/merge.py:359-385` (`by_grant`): a refused auto policy falls back to the owner's
  grant or `merge.default_tier`. That is why `today` merges the flagged PR while `merge check`
  says the owner merges, and why `ask` writes a card for a PR whose gates all passed.
- There is no owner-only path list: `repos.merge.never_auto_paths` only keeps a path out of
  the auto policy, and the `today` default or any grant lifts it (`merge.py:268`,
  `require(granted or ...)`).

The gate machinery this feature relies on already exists: `dispatch.gate_set` (dispatch.py:25)
gives a flagged item all three gates (a lead flag raises the tier to standard, dispatch.py:73-75,
and standard records `arch`, `quality`, `security`), and `gate_check` passes only when every
gate in that set is PASS at the head, reading the delta record when round one was FIX
(guards/pr.py:85-139).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which flags change? A: `trust_surface` only, as the issue title scopes it.
  `boundary_relevant` and `agent_surface` keep making an item ineligible for the auto policy,
  unchanged (design 4.6).
- Q: What does "security gate required" check? A: The item's recorded gate set
  (`dispatch.gate_set`) holds `security`, and the existing pre-PR gate check passes at the
  head, which already reads the security delta after a FIX. No second reading of the
  security verdict is added. A `trust_surface` item whose gate set has no `security` stays
  ineligible for the auto policy (today's behaviour, fail closed).
- Q: What does "waits on the gate" say? A: A pre-PR gate not passed at the head, for any item,
  is reported as `merge: waits on the gate: <the gate check reason>; no grant lifts this; run
  bin/wuwei pr act <pr> once it holds`, from `merge check` and from `wuwei merge` alike. It never
  says "the owner merges" and never writes a card.
- Q: Where does `merge.owner_paths` live and what is its default? A: In the workspace `[merge]`
  table beside `default_tier`, as the issue names it: a list of globs matched like
  `never_auto_paths` (any path suffix, old and new path of a rename). Default empty, so
  nothing changes until the owner lists paths.
- Q: What does "the owner merges" mean for an owner path? A: The existing owner-only route:
  the reason names the path and the matching glob and prints the exact
  `gh pr merge <url> --squash --match-head-commit <head>` for a host terminal, the command the
  `owner_only` tier already prints. No grant, standing line or `merge.default_tier` lifts it.
  It is reported only once every other precondition holds, so the owner is asked only for a
  PR that is otherwise ready.
- Q: What does "merge check prints which rule applies" mean? A: Each outcome names its rule:
  exit 0 prints the evidence (the normal policy cleared it), a gate not passed prints the wait
  reason above, an owner path prints the path and glob, and any other refusal keeps naming its
  rule as today (`merge.auto is off`, `never-auto path: ...`, and so on). No new output field.

## User Scenarios and Testing

### User Story 1 - A trust_surface PR with a passed security gate merges under the normal policy (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `trust_surface: true` on the item and its plan record, all gates (security
   included) PASS on the head, and `merge.default_tier = "today"`, **When** `wuwei merge check`
   runs, **Then** it exits 0 with the head-bound evidence, and **When** `wuwei merge` runs,
   **Then** it merges at the head.
2. **Given** the same with `merge.default_tier = "ask"`, **When** `wuwei merge` runs, **Then**
   it merges with no card, like the same PR without the flag.
3. **Given** the security gate was FIX at round one and its delta is PASS at the head,
   **Then** the result is the same as scenario 1.

### User Story 2 - While the security gate is open or FIX the PR waits on the gate (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the same PR with the security verdict still FIX (a blocking finding) on the head,
   **When** `wuwei merge check` runs, **Then** it exits 1 with a reason starting
   `merge: waits on the gate:` that names `security`, and the reason does not contain
   `the owner merges` or `ask the owner`.
2. **Given** that PR, **When** `wuwei merge` runs under `merge.default_tier` `ask` or `today`,
   **Then** it exits 1 with the same wait reason, nothing merges, no card is written and no
   `grant.used` is recorded.
3. **Given** no security verdict yet for the head, **Then** the same wait reason.

### User Story 3 - An owner path goes to the owner and the reason names it (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `[merge] owner_paths = ["guards/*"]` and a PR whose diff touches
   `cli/wuwei/guards/example.py`, otherwise ready, **When** `wuwei merge check` runs, **Then**
   it exits 1 with a reason naming `cli/wuwei/guards/example.py`, `merge.owner_paths guards/*`
   and the exact `gh pr merge https://github.com/<org>/<name>/pull/<n> --squash
   --match-head-commit <head>` for a host terminal.
2. **Given** that PR with `merge.default_tier = "today"`, or a standing merge grant, or an
   Allow today answer, **When** `wuwei merge` runs, **Then** nothing merges, no card is written,
   no `grant.used` is recorded, and the reason is the one of scenario 1.
3. **Given** a renamed file whose old path matches an owner path, **Then** the same refusal
   naming that path.
4. **Given** an owner path in the diff and a gate not passed at the head, **Then** the reason
   is the gate wait (the owner is asked only for a PR that is otherwise ready).

### Edge Cases

- A `trust_surface` flag recorded only in a `plan.approved` event (the item row says false)
  still counts: the item needs the security gate as if the row said true.
- A `trust_surface` item whose recorded gate set has no `security` (a set recorded before the
  flag) is refused by the auto policy with a reason naming the missing security gate; the
  owner's grant path behaves as today.
- `boundary_relevant` or `agent_surface` true: `item carries a risk flag`, as today.
- A second opinion gate (`security@codex`) is part of the gate set and must pass too, as today.
- An empty `merge.owner_paths` (the default) changes nothing for any PR.

## Requirements

- **FR-001**: In `merge.item_evidence`, `trust_surface` no longer refuses. `boundary_relevant`
  and `agent_surface` still refuse with `item carries a risk flag`. When `trust_surface` is
  true on the item or in any recorded plan event, the item's gate set must hold `security`,
  else the auto policy refuses naming the missing security gate.
- **FR-002**: A pre-PR gate check that fails at the head is reported, with or without a grant,
  as `merge: waits on the gate: <reason>; no grant lifts this; run bin/wuwei pr act <pr> once it
  holds`. No card, no `grant.used`, no merge.
- **FR-003**: `[merge] owner_paths` (list of strings, default empty) in the workspace schema.
  A changed path (new or old name) matching one, by `merge.matched`, makes `merge.check`
  return exit 1 with `merge: <pr> is ready at <head>; <path> matches merge.owner_paths <glob>:
  the owner merges: ask the owner to run <command> in a host terminal`, after every other
  precondition passed, whether or not the check runs under a grant.
- **FR-004**: The owner command string is built by one helper shared with the `owner_only`
  tier message in `merge.by_grant`; that message is unchanged.
- **FR-005**: Design 4.6 is amended (owner, 2026-10-10, #675) and the 9.2 I3 row names the new
  routes, with their check in `tests/test_invariants.py`.
- **FR-006**: `docs/site/configuration.md` documents `merge.owner_paths`, and
  `docs/site/concepts.md` says a `trust_surface` PR waits on its security gate and an owner
  path is always the owner's.

## Success Criteria

- **SC-001**: A `trust_surface` PR whose gates passed at the head is never routed to the owner
  by the flag alone.
- **SC-002**: No `merge check` or `wuwei merge` reason for a gate not passed at the head says the
  owner merges.
- **SC-003**: Every owner route for a path names the path and the glob that matched.

## Assumptions

- No orchestrator notes or dry-run workspace exist for #675 (the pipeline notes file for it is
  absent), so the failure was reproduced in process with the `tests/test_merge.py` fixtures;
  the table above is that run.
- The acceptance scenarios use a repository with `merge.auto = true` (the test fixture). With
  `merge.auto = false`, `merge check` reports `merge.auto is off` for every PR, flagged or not,
  while `wuwei merge` may still merge under `merge.default_tier = "today"`. That mismatch is
  not specific to the flag and is left as is (Deferred).
- `boundary_relevant` and `agent_surface` keep today's rule; the issue scopes `trust_surface`.
  Extending the same treatment to them is a separate decision for the owner.
- The owner route for an owner path is the host-terminal command, as the `owner_only` tier
  does, not a card: the issue asks for an owner-only route, and a card answered Allow today
  would let later PRs touching the same path through.
- `merge.owner_paths` is workspace-wide, as named in the issue, and matches repository-relative
  paths in every configured repository.
- Shipped default empty: listing guard files, workflows or the signing key path is the owner's
  choice per workspace (`bin/wuwei config set merge.owner_paths ...`).
- The invariant is added to the existing I3 row (merge only at the gated head) rather than a
  new row, so the 9.2 walk and its one-second budget are untouched; the check is a standalone
  parametrized test beside `test_merge_only_at_the_gated_green_head`.

## Deferred

- `merge check` with `merge.auto = false` does not report what `merge.default_tier` would do;
  a read-only preview of `by_grant` is its own item.
- The PR guard's suffix for a session `gh pr merge` (guards/pr.py:31-32) still adds
  "run bin/wuwei merge" after an owner-path reason; harmless (that command prints the same
  reason) and left as is.
- A profile (`profiles.DENIED`) that removes `merge.owner_paths` entries is not refused, as for
  `merge.default_tier`; add a row if profiles start carrying merge settings.
