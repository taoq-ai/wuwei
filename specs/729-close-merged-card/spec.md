# Feature Specification: a merge decision card closes when its PR merges, so next and the status line stop pointing at a dead card

**Feature Branch**: `729-close-merged-card`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #729 (owner, 2026-10-10, item 55): a decision card still asked whether
to merge a PR the owner had merged hours before, and `next` and the status line kept pointing
at it. Deliver: a decision whose subject is a PR (`merge` topic, `pr:` target) is closed with
outcome `merged by the owner` when the watch or `pr state` sees the PR merged; `next`, the
status line and the board drop it; the same for a `deploy`/`release` card whose target
workflow ran. The close is recorded as an event with the evidence (merge sha, who).

## Root cause (read on main at f2567cb, reproduced read-only)

Reproduction: a scratch test outside the repository, built on the `case` fixture of
`tests/test_stop.py` and `linked` of `tests/test_pr_actions.py` (nothing in the worktree
written). Item `A` is raised with PR `acme/widget#7`. Two merge cards are written through
`grants.ask`, the two shapes main produces:

- a planned card (`plan.propose` from a lead's `owner_actions`, `grants.plan`): grant row
  `{'action': 'merge', 'target': 'pr:acme/widget#7', 'rule': 'planned', ...}`;
- a runtime card (`wuwei merge` with no grant, `merge.by_grant` then `grants.gate`): grant row
  `{'action': 'merge', 'target': 'repo:acme/widget', 'rule': 'merge: acme/widget#7 at <head>', ...}`.

The fake host then reports the PR `state = closed, merged = true` and `wuwei pr state` runs.
Result: item `A` moves to `merged`, and both cards stay open: `decision_routes` has `D-1` and
`D-2`, `decision.answered(data, D-n)` is `None` for both, and both grant rows keep
`answered: None`.

Why:

1. `pr_actions.observe` (`cli/wuwei/pr_actions.py:151`) is the one place both the watch
   (`watch.poll`, `cli/wuwei/watch.py:482`) and `wuwei pr state` (`pr_actions.evaluate`,
   `cli/wuwei/pr_actions.py:254`) turn a fresh PR read into state. On a merged PR it only moves
   the linked items to `merged` (`cli/wuwei/pr_actions.py:226`); nothing looks at the day's
   decision cards.
2. Every surface that lists an open card uses one predicate, `decision.answered(data, D-n)`
   (`cli/wuwei/decision.py:497`) being `None`: `next` (`cli/wuwei/commands/next.py:228`, whose
   list the close hold at `:315` reuses), the status line and `status --json`
   (`cli/wuwei/commands/status.py:216` and `:314`), the board
   (`cli/wuwei/control_plane.py:40`, `cli/wuwei/commands/dashboard.py:40`), day close
   (`cli/wuwei/closing.py:190`) and session rotation (`cli/wuwei/sessions.py:125`). `answered`
   reads only `decision_outcomes[D-n]`, which only an owner answer, a seat or the mandate
   writes.
3. The grant row of the card keeps `answered: None`, so `grants.gate`
   (`cli/wuwei/grants.py:192`) names the dead card again for the next merge on the same
   repository target, and `grants.gate_widgets` (`cli/wuwei/grants.py:312`) would ask a
   planned one at the gate.

The fix belongs at the shared spot of fact 1: one call from `observe` when it classifies the
PR `merged`, writing the owner outcome row that fact 2's predicate already reads and marking
the grant row of fact 3. No reader changes.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which cards are "a decision whose subject is a PR"? A: An open grant card with action
  `merge` whose target is `pr:<ref>` (planned) or whose rule starts `merge: <ref> at `
  (runtime, written by `wuwei merge`), where `<ref>` is the merged PR exactly as the watch
  reads it. A merge card on `repo:` with a planned rule (a per-repository planned card) is not
  about one PR and stays open. Other decision records (scope cards from `pr act`, config
  cards) are not grant cards and are untouched.
- Q: What is "open"? A: The grant row's `answered` is `None` and the decision has no owner
  outcome (`decision.answered` is `None`). An answered card is never rewritten.
- Q: How is the card closed? A: Under the shared writer, one write per card: the grant row's
  `answered` becomes `merged`, and `decision_outcomes[D-n]` becomes
  `{'option': 'merged', 'outcome': 'merged by the owner', 'decided_by': 'owner', 'pr': <ref>,
  'sha': <merge commit>, 'by': <login or null>, 'at': <now>}`. `decided_by: owner` is what
  every reader's `answered` predicate needs; the option `merged` is not an option of the
  card, so agreement, calibration and unnecessary-ask counts (which compare the option with
  the recommendation) never count it as the owner agreeing. The row carries no
  `reversibility`, `class` or `cisr`, so the report's one-way list and class counts read the
  route as before.
- Q: The event? A: One `decision.closed` event per card, written by that same write, with
  payload `{'id', 'pr', 'outcome', 'sha', 'by'}`. `sha` is the adapter's `merge_commit`;
  `by` is who merged it on the code host (`merged_by` login), `null` when the host does not
  say. The kind is silent in `signal.classify` (a record, nothing to act on) and is named in
  the event producer table, so `wuwei event decision.closed` is refused like every other
  non-free kind.
- Q: Where does "who" come from? A: The GitHub adapter's `pr` read gains `merged_by`
  (`_login(value.get('merged_by'))`, a login or `None`). The REST pulls endpoint the adapter
  already calls returns it; no new call.
- Q: Does a close create or lift a grant? A: No. `grants.active` matches only `today` and
  unspent `once`; `merged` is neither, and is not `keep`, so a later merge on the same
  repository target asks a fresh card instead of naming the dead one. Invariant I5 (no seat,
  default or hook creates a grant) holds.
- Q: Is the merge fact trusted from a seat-writable record? A: No. It is the code host read
  through the adapter in the same `observe` call that already moves items to `merged`, and a
  close grants nothing.
- Q: The decision record file `D-n.md`? A: Left as written. Every reader of an outcome reads
  state (`report.py` overrides the file's Outcome line with the state row), and the board
  skips a card with a state answer.
- Q: What if the close write fails? A: It raises like any `observe` failure: the watch marks
  the PR unreadable for that poll (exit 2, `watch: read-failed`) and `pr state` reports exit 2
  for it. The PR stays owned and `observe` runs on every poll, so the next poll closes the
  card. A card answered between the read and the write is a race (`RACE`), never overwritten.
- Q: The `deploy`/`release` half ("a card whose target workflow ran")? A: Deferred. Main has
  no port that reads workflow runs; the watch reads only owned PRs. See Deferred.

## User Scenarios and Testing

### User Story 1 - A merged PR closes its merge card (Priority: P1)

**Acceptance Scenarios** (from the issue's Acceptance section):

1. **Given** an open merge card for a PR (planned `pr:` target, and separately a runtime card
   whose rule names the PR) and the PR merged, **When** the next poll runs (`watch.poll`, and
   separately `wuwei pr state`), **Then** the card is closed with the evidence: its
   `decision_outcomes` row reads option `merged`, outcome `merged by the owner`, decided by
   `owner`, the merge sha and the merger's login; its grant row reads `answered: merged`; one
   `decision.closed` event carries `id`, `pr`, `outcome`, `sha` and `by`.
2. **Given** that close, **Then** `next` no longer returns the `decision` row for it, the
   status snapshot's `decisions` list omits it, and the board (`control_plane.pending`)
   omits it.
3. **Given** a second poll of the same merged PR, **Then** no second `decision.closed` event
   and no state change for the card.

### User Story 2 - Only cards about that PR close (Priority: P1)

**Acceptance Scenarios**:

1. **Given** open cards for other subjects (a runtime merge card whose rule names
   `acme/widget#70`, a planned merge card on `pr:acme/widget#8`, a planned merge card on
   `repo:acme/widget`, a deploy card on `repo:acme/widget`) and PR `acme/widget#7` merged,
   **Then** none of them changes.
2. **Given** a merge card for the PR the owner already answered (`keep`), **Then** its outcome
   and grant row are unchanged and no `decision.closed` event is written for it.
3. **Given** the PR closed without merging, **Then** no card closes.

### User Story 3 - A closed card grants nothing and is not reused (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a closed runtime merge card on `repo:<org>/<name>`, **Then** `grants.active` for
   `merge` on that target is `None`, and the next refused merge on that repository writes a
   new card and names it, not the closed one.

### Edge Cases

- A PR the day neither raised nor claimed is never read by the watch, so its card stays open
  (see Assumptions).
- `merged_by` absent from the host read (a fake, an older recording): `by` is `null`; the
  close still happens.
- Two open cards about the same PR (a planned one and a runtime one): both close, one event
  each.

## Requirements

- **FR-001**: `adapters/code_host/github.py` `pr` returns `merged_by` (the merger's login or
  `None`).
- **FR-002**: `grants.close_merged(root, ref, pr)` closes every open merge card about `ref`
  with the outcome row, the grant mark and one `decision.closed` event each, and returns the
  closed ids.
- **FR-003**: A card is about `ref` when its grant row's action is `merge` and its target is
  `pr:<ref>` or its rule starts with `merge: <ref> at `.
- **FR-004**: `pr_actions.observe` calls `grants.close_merged` after its own write when it
  classifies the PR `merged`; the watch and `pr state` reach it through `observe` only.
- **FR-005**: `decision.closed` is silent in `signal.SILENT` and named in
  `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`; `state.STATE_PRODUCERS` names the watch and
  `pr state` among the producers of `decision_outcomes` and `grants`.
- **FR-006**: `docs/site/concepts.md` (the merge paragraph under Grants) says a card about a
  PR that merges closes with outcome `merged by the owner` and a `decision.closed` event.

## Success Criteria

- **SC-001**: The issue's acceptance holds through both producers (`watch.poll` and
  `wuwei pr state`).
- **SC-002**: No reader of open cards changes; all of them stop listing the card because the
  shared predicate `decision.answered` now sees an owner outcome.
- **SC-003**: The full suite passes.

## Assumptions

- No `_pipeline/notes/729-full.md` exists and no dry-run workspace is named; the issue, the
  code on main and the read-only scratch reproduction above are the inputs.
- "`merge` topic, `pr:` target" is read as the grant card's action and target. The runtime
  card `wuwei merge` writes has a `repo:` target, but its rule names the PR and it is the card
  a planner meets for an approved PR, so it counts as a card whose subject is that PR.
- The outcome text stays `merged by the owner` whoever merged it on the host; the evidence
  `by` records the actual login.
- Only PRs the day owns (raised or claimed) are read by the watch and `pr state`; a card about
  a PR the day does not own stays open until answered.
- The change is a state producer, not a guard or a decision routing rule, and it creates no
  grant, so no 9.2 invariant row is owed; the US3 test re-checks I5 for the closed row.
- The design spec is the owner's to amend; this feature does not edit it.

## Deferred

- The `deploy`/`release` half of the issue: closing a deploy or release card whose target
  workflow ran needs a code host operation that reads workflow runs (a new adapter call, its
  allowlist entry and recordings) and a rule for which run answers which card. To be filed as
  its own issue linked to #729.
