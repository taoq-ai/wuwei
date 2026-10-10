# Feature Specification: an item-level owner_merge flag that wuwei merge and the auto-merge daemon both respect

**Feature Branch**: `678-owner-merge-flag`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #678 (owner, 2026-10-10): the auto-merge daemon has no concept of
owner-only. Nothing tells WUWEI that a PR may only be merged by the owner; the only protection
is keeping the PR in draft. An item-level `owner_merge = true` that `wuwei merge` and the
daemon both respect replaces that workaround.

## Root cause (read on main at 66b3720)

Every merge path already routes through one function, `merge.check` (`cli/wuwei/merge.py:208`):

- `wuwei merge check <pr>` (`cli/wuwei/commands/merge.py:19`) calls it directly;
- `wuwei merge <pr>` (`cli/wuwei/commands/merge.py:23`) calls `merge.execute`
  (`merge.py:386`), which calls `check` and, on a refusal, `by_grant` (`merge.py:359`), which
  calls `check(granted=True)`;
- `wuwei pr act <pr>` on an approved PR calls `merge.execute` (`cli/wuwei/pr_actions.py:526`);
- the session `gh pr merge` guard calls `merge.check` (`cli/wuwei/guards/pr.py:30`);
- the daemon, the scheduled overnight shepherd, calls `merge.check` for each approved PR
  (`cli/wuwei/shepherd.py:587`) and logs `result.reason` in its `shepherd.overnight` event.

`check` reads no owner-only signal from the item. The only owner hold it honours is
`require(not pr['draft'], 'PR is a draft')` (`merge.py:237`). The item schema
(`state.ITEM_DEFAULTS`, `cli/wuwei/state.py:43`) has no such field, and `plan set`
(`cli/wuwei/commands/plan.py:83-97`) knows only `spec=`, `docs=`, `ticket=` and `pace=`. So a
green, approved, non-draft PR the owner wants to merge personally is merged by `wuwei merge`
and cleared by the daemon. No orchestrator notes or dry-run workspace exist for this issue;
the root cause is read from the code above (`owner_merge` appears nowhere on main).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where does the rule live? A: One function in `merge.py`, `owner_hold(item)`, which
  returns `(who, date)` for a set flag and `None` otherwise, read once at the top of
  `merge.check` for the item linked to the PR, before every other rule. Every path above
  reads it through `check`, granted or not, so no path needs its own copy; `pr raise` reads
  the same function for its body line. The issue's `merge.policy(item, pr)` is this function.
  It is not named `policy` because `check` already binds a local `policy` (the repository's
  merge settings), and it takes no PR because only the item record decides: a PR label is
  writable by anyone with repository access, so it is never read as the flag.
- Q: What does the refusal say? A: `owner merges: owner_merge set by <who> on <date>; clear it
  with bin/wuwei plan set <item> owner_merge=false`. `check` wraps it as it wraps every
  refusal: `merge policy: <line>; the owner merges; ask the owner` (exit 1), and on the granted
  path `merge: <line>; no grant lifts this; ...` (exit 1). No grant, posture or cruise level
  lifts it.
- Q: What is recorded on the item? A: `items.<id>.owner_merge = {"value": bool, "by": str,
  "at": iso8601}`, written only by `wuwei plan set <item> owner_merge=true|false`, with a
  `plan.set` event (`{"item", "owner_merge", "by"}`; the `plan.set` kind is already reserved to
  `wuwei plan set`). A clear keeps the record with `value: false`, so it shows who cleared it
  and when.
- Q: Who is `<who>`? A: The caller: `owner` from a host terminal (no `WUWEI_SESSION_ID`, no
  `WUWEI_SEAT_ROLE`), the seat role from a seat, else `planner`. It is informational: only
  `value` is read by the policy, and only in the direction that refuses.
- Q: Who may set and clear it? A: Setting it only narrows what WUWEI may do, so the literal
  `bin/wuwei plan set <item> owner_merge=true` passes `protect_state` from any agent tool
  session, as `docs=` does; this is how the planner records the owner's answer from the gate
  card or the chat. Clearing (`owner_merge=false`) lowers a hold, so it stays an owner action
  like every other `plan set` (the existing `('plan', 'set')` row of `_OWNER_ACTIONS`). The
  card path for a clear arrives with #661, which lets card-answered record commands pass from
  the planner.
- Q: How is the flag recorded on the PR? A: The label `owner-merge`, and a body line at raise.
  `plan set` adds the label when it sets the flag on an item that links a PR and removes it
  when it clears the flag; `pr raise` of a flagged item adds the body line
  `Owner merges: owner_merge set by <who> on <date>` and the label. The label is a new
  code_host operation, `label(ref, name, present)`, with a closed allowlist (POST
  `repos/<r>/issues/<n>/labels`, DELETE `repos/<r>/issues/<n>/labels/owner-merge`). The state
  is written before the label, so a label failure never loses the hold: `plan set` exits 2
  naming the rerun.
- Q: How does the owner see which way it ended? A: The item record. Cleared: `owner_merge.value`
  is false with who and when. Merged by hand: the value is still true, and `pr_actions`
  already moves the item to `merged` when it reads the merged PR (`pr_actions.py:223`).
  Nothing new is written.
- Q: What does "the next daemon pass merges under the normal policy" mean today? A: The daemon
  checks and queues; the morning merges (the existing `ponytail:` note at `shepherd.py:585`).
  After a clear, the next overnight pass gets `merge.check` exit 0 and logs
  `merge cleared by policy`, the same outcome as an unflagged PR. Making the daemon merge is
  not this issue.
- Q: The gate card's option? A: The morning gate card already has four options, the most
  `decision.widget` allows (three pace rows and `Change something`). `Change something` gains
  one sentence: name any item you merge yourself and the planner records it with
  `wuwei plan set <item> owner_merge=true`. No fifth option.

## User Scenarios and Testing

### User Story 1 - A flagged item is never merged by WUWEI (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `owner_merge = true` on an item with a green, approved PR, **When** `wuwei merge`
   runs, **Then** it exits 1 with the owner line, the code host `merge` operation is never
   called, and a `merge.policy_blocked` event carries the reason.
2. **Given** the same, **When** the overnight shepherd sweeps, **Then** its `shepherd.overnight`
   event for the PR has outcome `queued` and a reason containing
   `owner merges: owner_merge set by`.
3. **Given** the same, **When** `wuwei merge check <pr>` runs, **Then** it exits 1 and prints
   `owner merges: owner_merge set by <who> on <date>`.
4. **Given** the same, **When** `wuwei pr act <pr>` runs, **Then** it exits 1 with the owner
   line and nothing merges; **When** a session runs `gh pr merge <pr>`, **Then** the PR guard
   refuses with the owner line.
5. **Given** a merge grant for the repository (`once`, `today` or standing), **Then** every
   scenario above still refuses.

### User Story 2 - The owner clears the flag and the normal policy applies (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a flagged item, **When** the owner runs `wuwei plan set <item> owner_merge=false`,
   **Then** the item records `value: false` with who and when; the next overnight pass logs
   `merge cleared by policy` for the clean PR, `merge check` exits 0 and `wuwei merge` merges.
2. **Given** a flagged item merged by hand, **When** `pr act` or the watch reads the merged PR,
   **Then** the item moves to `merged` with `owner_merge.value` still true.

### User Story 3 - Setting and guarding the flag (Priority: P1)

**Acceptance Scenarios**:

1. **Given** today's item, **When** `plan set <item> owner_merge=true` runs, **Then**
   `items.<item>.owner_merge` is `{value: true, by, at}` and a `plan.set` event records it.
2. **Given** an unknown item (exit 1) or a value other than `true` or `false` (exit 2),
   **Then** `plan set` prints the usage and writes nothing.
3. **Given** a seat or the planner, **When** it runs `bin/wuwei plan set X owner_merge=true`,
   **Then** `protect_state` passes it; **When** it runs `owner_merge=false`, or a smuggled form
   (`owner_merge=true spec=skipped`, `$A`, `xargs`), **Then** it is refused.
4. **Given** `state set items.<item>.owner_merge`, **Then** it is refused as reserved, written by
   `wuwei plan set`.

### User Story 4 - The PR shows the flag (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an item linking a PR, **When** `plan set <item> owner_merge=true` runs, **Then** the
   code host `label` operation adds `owner-merge`; clearing removes it.
2. **Given** a flagged item, **When** `pr raise` runs, **Then** the body carries
   `Owner merges: owner_merge set by <who> on <date>` and the PR gets the label.
3. **Given** the label call fails, **Then** the state already holds the flag and `plan set` exits
   2 naming the rerun.

### Edge Cases

- A malformed `owner_merge` record (not an object, or `value` not a bool) is exit 2 (damaged),
  never read as cleared.
- An item without the key, or a PR with no linked item, is unaffected by this rule (`check`'s
  existing `PR needs one linked item` still applies later).
- Removing a label the PR does not carry is not an error.

## Requirements

- **FR-001**: `merge.owner_hold(item)` returns `(by, date)` when the item's `owner_merge.value`
  is true, `None` when it is false or absent, and raises `ValueError` (damaged) on a malformed
  record.
- **FR-002**: `merge.check` refuses (exit 1) with the owner line, built from `owner_hold` of the
  item linked to the PR, before any other rule, granted or not, so `wuwei merge`,
  `merge check`, `pr act`, the PR guard and the overnight shepherd all refuse and log it.
- **FR-003**: `wuwei plan set <item> owner_merge=true|false` writes `items.<item>.owner_merge`
  and a `plan.set` event; `items.<id>.owner_merge` is reserved to `wuwei plan set`.
- **FR-004**: `protect_state` passes the literal `plan set <item> owner_merge=true` from any agent
  tool session; `owner_merge=false` stays owner-only.
- **FR-005**: code_host gains `label(ref, name, present)` (github and none adapters, the port
  contract and the fake); `plan set` and `pr raise` use it; `pr raise` adds the body line.
- **FR-006**: The gate card's `Change something` option names the owner_merge route.
- **FR-007**: Design 9.2 gains row I37 and `tests/test_invariants.py` its check, with one table
  over the command paths and the daemon path, flag set and cleared.
- **FR-008**: `docs/site/daily.md` documents the flag, who sets and clears it, and the refusal.

## Success Criteria

- **SC-001**: With the flag set, no path in the invariant table calls the code host `merge`
  operation, and each names the flag.
- **SC-002**: With the flag cleared, each path gives the same result as an unflagged item.
- **SC-003**: The full suite passes.

## Assumptions

- No `_pipeline/notes/678-full.md` exists; the issue and the code on main are the inputs.
- #661 (card answers recorded by the planner) and #675 (`merge.owner_paths`) are not on main.
  The rule match from `merge.owner_paths` and the card-answered clear are deferred to them;
  #675 can write the same record with `by = "rule merge.owner_paths: <path>"`.
- "The daemon" is the scheduled overnight shepherd (`shepherd.overnight`, installed by
  `wuwei shepherd schedule`), the only unattended merge path; cruise mode never decides a merge
  (`cruise.py:75`).
- `by` is informational and a seat setting `true` could write any label there; nothing trusts it.
- The record lives on the item in the day state, like `spec`; an item carried to a later day
  keeps it only if carry copies item fields, which this issue does not change.

## Deferred

- The rule source `merge.owner_paths` (#675) and clearing from a card answer (#661).
- Editing the body of an already raised PR; after raise, the label is the PR record.
