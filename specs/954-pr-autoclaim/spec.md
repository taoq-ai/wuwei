# Feature Specification: PR Auto Claim

**Issue**: #954  
**Created**: 2026-10-13  
**Status**: Ready

## User Scenarios & Testing

### Discover a PR created outside the item workflow (Priority: P1)

The planner creates a PR with `gh pr create` from a branch outside a recorded item worktree. WUWEI records its URL and offers a verified claim action, so the PR does not disappear from the day.

**Acceptance scenarios**:

1. Given a successful creation with one GitHub PR URL in a configured repository, when no approved item matches, the next action offers `pr claim` with the URL.
2. Given several goals and no matched item goal, the offer names the goal choice for the owner.
3. Given a closed or merged PR, the next command refreshes its repository listing and does not offer a claim.
4. Given a stuck seat and an unclaimed PR, the seat recovery is offered first.
5. Given a refused claim command, running it once dismisses its repeated offer for the day.
6. Given a cached PR listing newer than the unclaimed event, `next` reuses it until `pr.poll_seconds` elapses. A claimed, dismissed, done or closed row causes no extra refresh.

### Preserve the guarded item workflow (Priority: P1)

An item worktree or branch that does not link a PR still uses `wuwei pr raise` and its pre-PR gates. A hook result never promotes a planned item past checks or gates.

**Acceptance scenarios**:

1. Given a bare `gh pr create` in a recorded item worktree or head branch, the existing pretool guard refuses it when enforcement is on and names `wuwei pr raise`.
2. Given a successful creation that bypassed the guard and maps to an item without passed gates, WUWEI records it as unclaimed and leaves the item phase unchanged.
3. Given a gate-verified item and an unambiguous successful creation, WUWEI links the PR through the shared writer and records its local head branch.
4. Given an existing PR matched to an item whose gates have not passed, `next` tells the planner to run that item's gates first and offers `pr claim <url> --item <item>` with its goal. It does not suggest creating the PR again.

### Reject ambiguous evidence (Priority: P2)

The hook links no PR when the command or output cannot identify exactly one created PR.

**Acceptance scenarios**:

1. Failed commands and `--dry-run` or `--web` commands record no PR.
2. Multiple creates, multiple PR URL lines, or another output-producing command never auto link an item. Valid URLs are recorded as unclaimed for verification.
3. A claim refusal records the URL and refusal reason as unclaimed. A timeout follows the existing trace slow path. Hook errors never refuse the tool result.

## Requirements

- **FR-001**: Keep the existing pretool PR creation refusal for recorded items.
- **FR-002**: Accept only successful `gh pr create` output with one valid URL for automatic linking.
- **FR-003**: Match only configured repositories, ignoring repository letter case, and prefer approved items for branch matches.
- **FR-004**: Link a matched item only after its pre-PR gates pass at the local head; leave unsafe matches unclaimed.
- **FR-005**: Record a matched item's head branch with the PR; make no GitHub call from the hook.
- **FR-006**: Offer unclaimed open PRs after stuck-seat recovery, with a goal choice where needed, and permit dismissal after the offered claim command runs.
- **FR-007**: Record claim errors and refusal reasons without refusing PostToolUse.
- **FR-008**: Preserve a matched item in the offered manual claim command, and tell the planner to run its gates before claiming the existing PR.
- **FR-009**: Refresh an unclaimed PR's repository when the cache predates its event, then honor `pr.poll_seconds`; stop extra refreshes after ownership, dismissal, completion or day close.

## Success Criteria

- **SC-001**: The real planner-created field case is recorded and offered after one hook call.
- **SC-002**: A PR from a recorded item without passed gates is never auto linked.
- **SC-003**: Offline tests cover success, ambiguity, failure, refusal, closed PRs, and timeout.

## Assumptions

- Claude Code Bash responses carry command output in `stdout` and an `exitCode` or `exit_code` when present. Codex builder commands outside Claude Code do not emit this PostToolUse hook; that scope gap remains.
- The hook trusts only the URL, configured repository, local branch and gate evidence. `next` checks listing freshness before offering an unclaimed PR. The manual `pr claim` command verifies live host details.
- `next` refreshes a pending unclaimed PR once when its repository cache predates the event, then follows `pr.poll_seconds`. A local gate check cannot confirm the remote PR head without a host call; merge still gates the PR head before merging.
- With several goals and no matched item goal, the owner chooses one in the offered command. A refused claim command dismisses that day's offer; the owner can run `pr claim` directly later.
- Automatic linking does not perform the tracker `in_review` move. A later manual `pr claim` or shepherd tick handles that duty.
- Proposed owner design wording: Keep the existing PreToolUse refusal for a recorded item. PostToolUse records successful `gh pr create` calls that passed the guard, linking only gate-verified items and offering other configured PRs for manual claim. The owner-only design document is unchanged.

## Clarifications

No open questions. Recommended choices are recorded under Assumptions.
