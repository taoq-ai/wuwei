# Feature Specification: Adopt Existing Starts

**Issue**: #950  
**Created**: 2026-10-13  
**Status**: Ready

## User Scenarios & Testing

### Avoid a duplicate builder (Priority: P1)

An approved plan item may already have an open PR, an ad-hoc seat, or a named worktree with a commit. The planner shows that evidence before offering another builder.

**Acceptance scenarios**:

1. Given an open PR on the item's branch, `wuwei next` reports review with the PR reference and offers no start.
2. Given a recorded builder or spec ad-hoc seat that names the item, `wuwei next` offers one Owner step park card, including after the seat stops. A reviewer or casual prompt mention does not hold it.
3. Given a registered worktree named for the item with a HEAD beyond its own creation commit, `wuwei next` reports blocked and offers a reconciliation card. A builder brief or build record suppresses this check.
4. Given none of these signals, a planned item still receives its ordinary start.
5. Given a failed PR listing for the item's repository, the planner still offers the start and says the PR check is unmeasured.
6. Given `origin/main` ahead of the main checkout and a fresh worktree at `origin/main`, the planned item still starts.
7. Given an item held for an open PR or committed worktree, one Owner step card names the evidence and exact reconcile command, with both `--worktree` and `--pr` when both are found. Yes runs that command. No rejects that evidence for the item and uses the ordinary start path.
8. Given an old cached open PR that is absent from a fresh read, `next` and `dispatch next --all` refresh at the start boundary and offer the ordinary start.
9. Given a committed worktree and an ad-hoc seat for one item, the worktree reconcile card comes first. A No on that card exposes the seat park card. A No on one seat's park card does not reject a later seat.

## Requirements

- **FR-001**: Check existing work evidence before offering any new builder for a planned item.
- **FR-002**: Recognize an open PR whose head branch's last segment matches the item's branch last segment, case-insensitively and as a whole name.
- **FR-003**: Recognize a recorded builder or spec ad-hoc seat that names the item, including a stopped seat. Match item IDs case-sensitively. Accept an explicit `Item X.` line for an uppercase ID; a casual prompt mention does not link it.
- **FR-004**: Discover linked worktrees through the repository Git worktree registry and compare HEAD with the item's recorded creation start. Without that event, use the first reflog entry for that worktree, then the remote default branch ref when readable. Skip commit detection after a builder brief or build record. Expand `~` in repository paths.
- **FR-005**: Report matching evidence as one Owner step card with the exact reconcile or park command. Order combined PR and worktree evidence before worktree evidence, then seat evidence. Yes runs the command. No rejects that evidence and exposes the next evidence, or uses the normal path when none remains. A failed PR listing skips only that check and adds an unmeasured note to any offered start.
- **FR-006**: Keep the ordinary start route for an item with no matching evidence.
- **FR-007**: Refresh the PR listing in the shared launch set when a planned start is about to be offered, and only for its repository when its cached listing is due. Keep existing polling for recorded PRs.
- **FR-008**: Read the event log once per derived offer set and tolerate a damaged proposal lookup without hiding other evidence.

## Success Criteria

- **SC-001**: The six reported items avoid a duplicate builder when a safe, explicit link to the item is present. A differently named infra PR needs an explicit seat or park record.
- **SC-002**: A planned item with no existing work still starts on the same planner turn.
- **SC-003**: Every evidence-held item names its exact reconciliation or park command in a planner row; one owner decision is offered per turn.

## Assumptions

- The item's branch is its recorded `branch` when present, otherwise the item ID. Only its final slash-separated segment is used for PR matching.
- PR discovery trusts a cached listing only while fresh. An old cached open PR cannot hold an item before a due read at the imminent-start boundary. A failed read cannot prove either presence or absence of a PR, so the start reason says unmeasured.
- A named worktree is the item's recorded worktree or a Git-registered worktree whose path or branch ends in the whole item name, case-insensitively. The baseline is its `worktree.created` start, then its own first `logs/HEAD` creation commit, then the configured remote default branch ref. An unreadable baseline yields no commit inference.
- An ad-hoc hold needs a builder or spec role and an explicit item link in the seat ledger or a matching `Item:` or `Item X.` prompt line. A general prompt mention is not evidence. The unbriefed-seat refusal may name an item from prompt prose to preserve its existing repair command.
- A No answer to an evidence card is the owner's rejection of that evidence for the item. It does not park the item or claim a PR. New commits in a rejected worktree are not asked again the same day. Each ad-hoc seat has its own park card command, so a No for one seat does not cover a later seat.
- A worktree checked out on an existing branch with commits may read as no work when its first reflog entry is already the branch tip. An open PR on that branch is still detected.
- Existing PR review and build reconciliation remain explicit workflows. This issue prevents duplicate starts and reports evidence; it does not automatically claim a PR or infer a completed build.
- The design spec says `next` refreshes the PR listing when older than `pr.poll_seconds` and describes the day's derived inputs, but does not specify the new start adoption rule. Proposed owner wording: The shared launch set refreshes a due PR listing immediately before offering a planned start, then checks builder and spec ad-hoc seats and Git-registered worktrees against their creation commit. It offers one Owner step reconciliation or park card for linked work. Yes runs its exact command; No rejects that evidence and resumes the normal path. A failed PR read is unmeasured and leaves the start available. Existing PR supervision continues at its normal poll boundary.

## Clarifications

No open questions. The recommended choices are recorded under Assumptions.
