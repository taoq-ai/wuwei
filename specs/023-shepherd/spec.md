# Feature Specification: Shepherd PR flow

**Feature Branch**: `023-shepherd`
**Created**: 2026-09-29
**Status**: Ready

## User Scenarios and Testing

### User Story 1 - Raise with relevant reviewers (P1)

Given a PR touching files last edited by two people, when the shepherd raises it, both people are requested and named in the review channel post. Reviewers come from recent authorship of changed source files, excluding the PR author and bots, with configured recent-history windows followed by all history. A configured lead joins every eligible reviewer set and supplies the floor when history is sparse.

### User Story 2 - Ping only when ready (P1)

Given red, pending, missing or unreadable CI, no review ping is sent. Dirty and behind PRs are held. Required checks come from branch protection, with a configured fallback for unprotected bases. A configured review bot must have a clean score at the current head and no open findings. Reply obligations must be clear before a repeat ping.

### User Story 3 - Own replies and merge (P2)

Given a fresh unanswered thread, the shepherd reads the API again and replies only if the target is still its last word. Replies pass outbound tiers and voice lint; an approve tier remains a draft for the owner. The PR ownership action is dispatched from `wuwei pr state`. An approved PR is merged through the existing merge command after its policy clears; otherwise an owner decision remains due.

## Requirements

- FR-001: PR creation checks the existing pre-PR gates and uses the code_host port.
- FR-002: Reviewer selection uses changed source paths and the sparse-history ladder, with configured identity mapping and no fixed roster.
- FR-003: Requested reviewers and channel mentions contain the same set; the post is recorded only after the chat adapter confirms sending.
- FR-004: The ping gate follows the production refusal order and returns 0 clean, 1 findings, 2 unmeasured with a reason.
- FR-005: Thread replies re-read the target and last word immediately before posting and verify the posted answer before acknowledging.
- FR-006: PR actions reuse the existing ownership loop, obligations, outbound policy, and merge policy.
- FR-007: Trusted shepherd state and events are dedicated-producer only.

## Success Criteria

- SC-001: A two-author fixture produces two requested reviewers and two matching channel mentions.
- SC-002: Red CI yields no chat post.
- SC-003: Every refusal inherited from the production gate has a test.

## Assumptions

- The owner config supplies author email to code-host login and chat mention mappings; unmapped authors cannot be requested safely.
- A configured review channel is an internal work channel. The lead is optional and used only to reach the reviewer floor.
- An unprotected base uses configured default-branch protection. A repository can configure required checks when protection offers none; otherwise ping is refused.
- PR creation accepts a prepared title and body. The existing planner and builder supply the content and pushed head.

## Deferred

- Automated fix rounds, conflict resolution and scope adjudication require builder and owner decisions; this command reports the ownership action for those states.
