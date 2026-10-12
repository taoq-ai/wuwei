# Feature Specification: `wuwei pr wait` wakes the planner when a raised or claimed PR needs a step

**Feature Branch**: `906-shepherd-launch` (one batch with #906)

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #887: the shepherd loop is modelled as duties and launches, but nothing
triggers it between owner messages. The planner bridged it with its own 5-minute GraphQL poller.
The owner: "I don't want to need to ask you for this loop on open PRs."

## User Scenarios & Testing

### User Story 1 - a PR change wakes the planner (P1)

1. **Given** two claimed PRs and `wuwei next` waiting on people, **When** a new review thread lands
   on one, **Then** `wuwei pr wait` exits 1 within one poll and prints one line naming that item,
   `shepherd` and the PR.
2. **Given** checks turn red, a conflict, a moved head, a merge or a close, **Then** the line names
   the step `next` offers for it (`fix`, `pr`, `merge`, `owner`, a duty).
3. **Given** nothing changes before `--timeout`, **Then** it exits 0 and prints nothing.

### User Story 2 - a tick is cheap (P1)

1. A tick refreshes the PR listing only for repositories that hold a raised or claimed PR and only
   once their listing is `pr.poll_seconds` old; one GraphQL listing request per such repository,
   whatever the number of PRs.
2. A listing `next` read inside the interval is reused: no request.
3. A rate-limit refusal (#899) holds the next read until its reset; a tick never spins.

### User Story 3 - next says when to run it (P1)

1. **Given** only PRs waiting on people remain, **Then** `wuwei next` returns the row `wait` with
   command `wuwei pr wait` and action `background`, and its `then` tells the planner to run it in
   the background and run `wuwei next` when it exits.

## Requirements

- **FR-001**: `wuwei pr wait [--timeout SECONDS]` (default 3600) under the existing `pr` command.
- **FR-002**: the change test is `next.step`: the launches, duties and decision it returns for
  items with a PR, keyed by item, kind and why; a key absent at start is an event.
- **FR-003**: the baseline is read from the listing before the first refresh, so a change that
  lands between `next` and `pr wait` is reported.
- **FR-004**: output: one line per event, `<item> <kind> <pr>: <why>`; exit 1 with events, 0 on
  timeout or nothing to wait on, 2 when it cannot run.
- **FR-005**: the planner charter, the plan skill and the daily guide name it.

## Success Criteria

- **SC-001**: the acceptance test: two claimed PRs, a new review thread on one, exit within one
  poll with that item and `shepherd`.
- **SC-002**: a fake code host counts one listing call per tick for one repository with two PRs,
  and zero for a tick inside `pr.poll_seconds`.

## Assumptions

- The tick reuses the existing per-repository listing query (`_PULLS`). A live probe on a real PR
  (2026-10-12, run by the coordinator) showed `latestReviews` returns each reviewer's newest review
  of any state; a thread reply shows as that reviewer's latest COMMENTED review at the reply time,
  so `activity_at` moves on thread replies. The query only gains a top-level `viewer{login}` (no
  cost) to leave WUWEI's own replies out. Review threads are not added: they would multiply the
  GraphQL point cost for every PR in the repository.
- A merge or a close of a PR item is a step of its own (review F5), so the wait exits on it even
  when no tracker duty follows; repositories whose PRs are all merged or closed are not read.
- One request per repository, not one for all repositories: the listing is per repository, and a
  day usually has one or two. ponytail: an aliased multi-repository query is the upgrade when a day
  carries many repositories.
- `pr wait` is a bounded command the planner starts in the background, not a service; the plugin
  still runs no long-running process of its own (constitution, Constraints).
- Exit 1 for events follows the three-state convention: something needs `next`.
