# Feature Specification: Outward-text guard

**Feature Branch**: `011-outward-lint`
**Created**: 2026-09-28
**Status**: Implemented
**Input**: Issue #11, outward-text lint and owner-sent drafts for chat and tracker calls.

## User Scenarios & Testing

### User Story 1 - Protect the owner's outward voice (Priority: P1)

As the owner, I want outgoing text checked before it reaches chat or a tracker.
This prevents third-person attribution and disclosure of routine internals.

**Independent Test**: Table-test clean text, findings and unreadable rules.

**Acceptance Scenarios**:

1. Given the configured owner, sending "per <owner>, the fix is in" is refused.
2. Sending "drafts are with the owner" is refused as internal state.
3. Configured pronouns, internal-state patterns, banned characters and channel length
   limits are enforced, including case, Unicode width and invisible-format variants.
4. In standard profile, lint findings warn; invalid inputs and rules still block.

### User Story 2 - Deliver substantive messages as drafts (Priority: P1)

As the owner, I want control over technical claims, disagreement and scope statements.

**Independent Test**: Verify mechanical sends and refusal despite forged local approval records.

**Acceptance Scenarios**:

1. "fixed in abc1234" is allowed without a draft only when the VCS port resolves the commit in a configured repository.
2. Technical claims, disagreement and scope statements return 1 with the hint
   "deliver as a draft for the owner to send".
3. No local file or hook payload can authorize sending a non-mechanical message.
4. The reusable classifier returns send or draft; adapters own draft delivery.

### User Story 3 - Enforce the rule at tool use (Priority: P1)

As the owner, I want configured chat and tracker calls checked by PreToolUse.

**Independent Test**: Replay in-process hook payloads for adapter and MCP tool names.

**Acceptance Scenarios**:

1. Configured full-match tool patterns select the lint channel.
2. Alternate text fields and tracker draft objects cannot bypass checking.
3. Unknown structured content, invalid payloads and ambiguous matches fail closed.
4. The hook returns 0 outside a workspace only when WUWEI_WORKSPACE is unset.
   Invalid explicit overrides return 2; irrelevant native tools skip policy parsing.
5. Unmatched MCP tools pass only when the first underscore-separated word in their last
   segment is get, list, search, read, find, fetch, query, describe, view or lookup,
   or the first word appears in the MCP server segment and the second is a read verb
   (case-insensitive). All others return 2 with a configure hint.
6. chat.post, chat.dm, tracker.create and code_host.comment enforce policy at the port.
   A missing workspace at a port is an error (2).

### Edge Cases

Empty text; missing owner; invalid regex; exact length boundary; multiple text fields;
rich blocks; zero-width characters; forged draft flags and local approval records;
configured tool names unrelated to vendor names; unavailable workspace.

## Requirements

- FR-001: Rules come from workspace configuration with safe internal-state and banned
  character defaults. Channel limits count original Unicode code points.
- FR-002: Lint has one reusable entry point for future voice and outbound-tier policies.
- FR-003: Only a narrowly recognized mechanical message sends. Unknown prose returns
  draft rather than relying on semantic keyword classification.
- FR-004: The approve tier never sends. A process with the owner's uid can forge any
  local file or hook payload, so local approvals cannot authorize a send.
- FR-005: Guards return 0 clean, 1 findings, 2 unable to check. Both nonzero results block.
- FR-006: Diagnostics contain rule names, never message bodies, owner names or draft text.
- FR-007: Test every behavior before implementing it, including bypass and error tables.

### Key Entities

- Outward rules: owner identity, internal patterns, banned characters, length limits,
  tool-name patterns and their policy channels.
- Send classification: send for a resolved mechanical commit message; draft otherwise.
  Draft delivery belongs to chat and code_host adapters (Slack draft, GitHub pending
  review comment) and is outside this feature.

## Success Criteria

- SC-001: All three issue acceptance examples produce their stated decisions.
- SC-002: All tested malformed evidence and bypass attempts block.
- SC-003: The complete existing suite and new in-process guard tables pass.

## Assumptions

- Owner names and configured pronoun tokens are conservatively forbidden anywhere in
  outward text. This may reject references to other people with the same pronouns.
- Mechanical means the complete message matches "fixed in <7-40 hex digits>", with
  optional final period and surrounding whitespace, and the commit resolves in a configured
  repository. Unknown commits return 1; unavailable lookups return 2. Everything else is a draft for the owner to send.
- The standard profile downgrades only lint findings, never draft requirements or errors.
- Configuration owns MCP tool matching. Defaults cover Slack, Linear and GitHub write
  names. Unmatched MCP writes fail closed; adapter ports enforce policy independently.
- Unsupported payload shapes block. Plain text aliases and a tracker draft object are
  supported; arbitrary rich content and batch calls await adapter-specific normalization.
- The state writer retains its generic reserved-namespace mechanism with an empty
  reservation set. Features reserve only keys they own; #8 will add fast_checks.
- State and event writes require an existing .wuwei directory; they may create days/
  and the day directory beneath it. Missing workspaces return 2 without creating files.
- Bash-level sends (`gh pr comment`, curl to Slack) are covered by the Bash guards and
  the code_host port allowlist, not by this tool-name guard.
- owner.handles optionally lists bare chat IDs and code-host handles. NFKD normalization
  removes Mn, Me and Cf before casefold; cross-script confusables remain distinct.

## Deferred

Per-channel outbound tiers (#95), audience voice rules (#85), and adapter draft delivery.
No local approval creation, shell guard or vendor network integration here.
