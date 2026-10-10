# Feature Specification: a wake fires only for a change that needs an action

**Feature Branch**: `674-wake-only-actions`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #674 (owner, 2026-10-10, item 42): "Wakes repeat known events and fire
on trivial changes. This one reported '#17 merged' again and '#19 updated (updated_at)'. The
planner gets woken for a timestamp change and for something it already acted on. A wake
should only fire for a state change that needs an action." Deliver: `updated_at` leaves the
snapshot fingerprint (kept as evidence time only); a wake carries only the parts the diff
names and fires when at least one part maps to a planner action (`watch.ACTIONS`); a part
already delivered (recorded in `watch.delivered` with the PR and the fingerprint of that
part) is not delivered again until it changes; `wuwei watch why <pr>` shows what fired and
what was suppressed.

## Root cause

Reproduced in-process on `main` with the `tests/test_watch.py` fixtures (fake code host,
PR `example/project#7`, planner session `planner`):

| Step | Today |
|---|---|
| Baseline poll, then only the PR's `updated_at` moves | `watch.poll` returns 1 and prints `planner wake: PR example/project#7: updated (updated_at)` |
| The PR merges; poll; SessionStart shows `PR example/project#7: merged`; then only `updated_at` moves; poll; the planner's next Stop | Stop blocks with `PR example/project#7: merged` and `PR example/project#7: updated (updated_at)`: the merge the planner already saw comes back with a timestamp wake |

In the code:

- `cli/wuwei/watch.py:368-369`: `snapshot` puts `updated_at` in the fingerprinted fields, so
  the diff in `poll` (`watch.py:480-482`) names `updated_at` whenever the host touches the
  PR (a label, a bot comment edit, a branch delete after merge).
- `cli/wuwei/watch.py:431`: `summary` falls back to `updated (<fields>)` when no rule names
  a change, and `poll` (`watch.py:484-493`) wakes for every diff, whatever it says. Nothing
  asks whether the change needs a planner action; `new` and `gone` (`watch.py:397-398`) wake
  too.
- `cli/wuwei/guards/lifecycle.py:100`: SessionStart shows the pending wake with
  `watch.wake(root)` and never marks it seen, so the marker stays unseen after the planner
  read it. `watch.mark_wake` (`watch.py:511-514`) then prepends every unseen summary to the
  next wake, and the planner's next Stop (`lifecycle.py:151`) delivers it again.
- Nothing records which part of a change was delivered, so nothing can suppress a part that
  comes back unchanged, and nothing tells the owner why a wake fired or did not.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is a part? A: One thing the facts diff names: a state change (merged, closed), new
  commits, conflicts (or conflicts resolved), a group of new comments, a new review, a check
  that failed (or passed), reviewers newly requested; `new` and `gone` for a PR that starts
  or stops being owned; and, when the diff names fields but no part, one `updated (<fields>)`
  part. Each part has a kind, a key that is stable for its subject on that PR (`state`,
  `head`, `mergeable`, `check:<name>`, `review:<id>`, the comment group, `requested`,
  `watched`, `fields`), the evidence it was derived from, and its text.
- Q: Which kinds need a planner action? A: `watch.ACTIONS`, kind to action text: `merged`,
  `closed`, `commits`, `conflicts`, `comments`, `approved`, `changes_requested`, `review`,
  `check_failed`. The rest (`resolved`, `check_passed`, `requested`, `new`, `gone`,
  `updated`) never wake on their own.
- Q: When is a part already delivered? A: `watch.delivered[<pr>][<key>]` holds the
  fingerprint (`watch.fingerprint`) of the part's evidence the last time the diff named that
  key. A part whose fingerprint equals the recorded one is suppressed as already delivered.
  Every named part records its fingerprint, fired or not, so a conflict that was resolved and
  comes back, or a check that passed and fails again, fires again.
- Q: Does a suppressed change still write `pr.changed`? A: No. `pr.changed` is the record of
  a fired wake, and the listener DMs the owner each one; a suppressed change writes no event.
  What fired and what was suppressed for a PR is kept in `watch.why[<pr>]`.
- Q: Does showing a wake at SessionStart deliver it? A: Yes, when the starting session is the
  registered planner (`planner_session_id`): SessionStart then consumes the marker as Stop
  does. Any other session still sees the notice read-only, so a seat never consumes the
  planner's wake.
- Q: What does `wuwei watch why <pr>` print? A: The last recorded poll for that PR that had a
  diff: its time, each fired part with its action, and each suppressed part with its reason
  (`already delivered`, `no action`). Exit 0 with a record, 1 with none, 2 when the state
  cannot be read, the reference is invalid or there is no workspace.

## User Scenarios and Testing

### User Story 1 - A timestamp alone never wakes (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a baseline poll of an owned PR, **When** only `updated_at` changes, **Then**
   `watch.poll` returns 0, writes no `pr.changed` and leaves no wake marker.
2. **Given** a baseline saved by the previous version (its snapshot holds an `updated_at`
   fingerprint), **When** the next poll reads the same PR, **Then** it reports no change.

### User Story 2 - A delivered part is not delivered again (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a merge delivered once (the wake fired and the planner's Stop consumed it),
   **When** the next poll runs, **Then** it delivers nothing for the merge.
2. **Given** that state, **When** a new check fails, **Then** one wake fires whose summary is
   `PR <ref>: check <name> failed` only.
3. **Given** a wake shown at SessionStart to the registered planner session, **When** the
   next actionable part fires and the planner stops, **Then** the Stop message carries only
   the new part.
4. **Given** a wake shown at SessionStart to a session that is not the registered planner,
   **Then** the marker stays unseen and the planner's Stop still delivers it.
5. **Given** a part whose key and evidence fingerprint are already in `watch.delivered` for
   that PR, **When** the diff names it again (a baseline reset), **Then** it is suppressed as
   already delivered.

### User Story 3 - Only parts that need an action wake (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a diff whose only parts are `check <name> passed`, `conflicts resolved` or
   `review requested from <login>`, **Then** no wake fires.
2. **Given** a PR that starts or stops being owned (`new`, `gone`), **Then** no wake fires.
3. **Given** a diff with a failed check and a passed check, **Then** the wake summary names
   only the failed check, and `watch why` lists the passed check as suppressed with
   `no action`.
4. **Given** a diff that names fields but no part (an edited comment body, a `merge_state`
   change), **Then** no wake fires and `watch why` lists `updated (<fields>)` as suppressed
   with `no action`.

### User Story 4 - The parts list is the single source (Priority: P1)

**Acceptance Scenarios**:

1. **Given** any diff, **Then** the wake summary is `PR <ref>: ` followed by the texts of the
   fired parts joined with `; `, and whether it fires is decided only by the parts' kinds in
   `watch.ACTIONS` and their fingerprints in `watch.delivered`.
2. **Given** `watch.ACTIONS`, **Then** every key is a kind that `watch.parts` produces.

### User Story 5 - The owner can see why (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a poll that fired `check ci failed` and suppressed `merged` (already delivered),
   **When** the owner runs `bin/wuwei watch why <ref>`, **Then** it prints the poll time,
   `fired: check ci failed (start a fix round)` and `suppressed: merged (already
   delivered)`, and exits 0.
2. **Given** a PR with no recorded diff, **Then** `watch why` prints that there is no record
   and exits 1.
3. **Given** an invalid PR reference or no workspace, **Then** it exits 2 with the reason.

### Edge Cases

- A failed read of one PR keeps its old snapshot, facts and delivered record, as today.
- A check that fails on a new head after it failed on the old head fires again: the check's
  evidence holds the head.
- A merged PR whose head, checks or reviews do not change produces no diff after the merge;
  only the delivered record stops a reset baseline from re-delivering it.
- `delivered` and `why` carry over midnight from the previous day like `prs` and `facts`,
  and keep only PRs still owned.
- The listener shares `watch.poll` through `poll_prs`, so its wakes and owner DMs follow the
  same rule.

## Requirements

- **FR-001**: `watch.snapshot` no longer fingerprints `updated_at`; `watch.evidence` still
  validates it as a time.
- **FR-002**: `watch.poll` counts a PR as changed only when a field of the current snapshot
  differs from the baseline, so an old baseline's extra `updated_at` key is no change.
- **FR-003**: `watch.parts(before, after, fields)` returns the parts of a diff as
  `(kind, key, evidence, text)` rows, replacing `watch.summary`; it keeps today's texts.
- **FR-004**: `watch.ACTIONS` maps each action kind to its planner action text.
- **FR-005**: `watch.poll` fires a part when its kind is in `watch.ACTIONS` and its
  fingerprint differs from `watch.delivered[<pr>][<key>]`; it records every named part's
  fingerprint in `watch.delivered`, records fired and suppressed parts in `watch.why[<pr>]`,
  writes `pr.changed` and the wake marker only for PRs with a fired part, and returns 1 only
  when a part fired.
- **FR-006**: SessionStart consumes the pending wake when the session is the registered
  planner.
- **FR-007**: `bin/wuwei watch why <pr>` prints the PR's last `watch.why` record with the
  action of each fired part, and exits 0, 1 or 2 as in User Story 5.
- **FR-008**: Docs say the rule: design spec 4.2.1 "Wake outside the model" (a wake fires
  once for a change that needs a planner action), `docs/site/daily.md` (the PR changes
  paragraph) and `docs/site/reference.md` (`watch why`).

## Success Criteria

- **SC-001**: No wake fires for a timestamp-only change or for `new`, `gone`, passed checks,
  resolved conflicts or reviewer requests.
- **SC-002**: The planner never receives the same part of the same PR twice unless its
  evidence changed.
- **SC-003**: The owner can see, per PR, what fired, what was suppressed and why.

## Assumptions

- The orchestrator notes file named in the task (`notes/674-full.md`) does not exist; this
  spec is built from the issue and the reproduction above.
- `new commits` wakes the planner: the issue lists it as a part, and a push the planner did
  not order (a reviewer's suggestion commit) invalidates the gate verdicts. A seat's own push
  still wakes, as today.
- `check passed`, `conflicts resolved` and `review requested` need no planner action: the
  shepherd's PR action states (`pr_actions.ACTIONS`) already act on approval, and the merge
  path re-reads checks itself.
- `new` and `gone` need no action: the planner raised or claimed the PR itself, and `gone`
  at midnight is the day rolling over.
- A suppressed change writes no event. `watch why` keeps only the last diff per PR; the day's
  `pr.changed` events hold the fired history. A per-poll suppressed history is the upgrade if
  the owner needs it.
- A fresh planner session that has not yet run `wuwei plan session` is not the registered
  planner at SessionStart, so its first Stop still repeats the wake once.
- This changes when the planner is notified, not who decides or what a guard refuses, so it
  adds no row to the design 9.2 invariants table.
