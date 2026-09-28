# Feature Specification: Outbound approval tiers

**Feature Branch**: `095-outbound-tiers`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #95, M1 Guards. Design sections 4.3, 4.9, 9.1 and 15.10.

## User Scenarios & Testing

### User Story 1 - Safe work replies (Priority: P1)

The owner permits routine work replies while retaining control over personal,
external, sensitive and consequential messages.

**Independent Test**: Classify replies using configured work destinations and audiences.

**Acceptance Scenarios**:

1. Given a configured work channel and a resolvable commit, when the reply is
   "fixed in abc1234", then auto-send.
2. Given the same channel and a thread reply whose participants cannot be verified,
   then draft, including when an external person participates.
3. Given "happy to give feedback on your performance review" in a work channel,
   then draft because the topic is sensitive.
4. Given "I'll add that in a follow-up" in any channel, then draft as a commitment.
5. Given a work channel, acknowledgements and bounded status replies may auto-send.
6. Given a verified team PR and a technical reply about its discussion subject,
   then auto-send. Unknown authors, participants or scope require a draft.
7. Every DM, shared, connected or client channel requires a draft, even when
   otherwise configured as a work channel. External evidence always wins.

### User Story 2 - Consistent enforcement (Priority: P1)

The owner gets the same tier from the CLI, chat/tracker hooks and adapter writes.

**Independent Test**: Run in-process CLI and hook tables, including malformed inputs.

**Acceptance Scenarios**:

1. A refused send gives a draft-for-owner hint; it never sends or creates a draft.
2. Tier classification precedes outward lint. Eligible sends still undergo lint.
3. Malformed policy, payload or unavailable evidence fails closed with exit 2.
4. Unrelated projects and native tools pass without parsing unrelated commands.
5. Unknown destinations, mixed text fields and local approval claims cannot bypass policy.

### Edge Cases

Missing audience, conflicting channel aliases, unknown mentions, external email
suffix lookalikes, Unicode obfuscation, external PR participants, missing PR evidence,
invalid patterns and malformed metadata all fail closed. Standard profile may warn
for lint but cannot relax approval tiers.

## Requirements

- **FR-001**: One classifier decides send or draft from text and destination context.
- **FR-002**: Only configured work channels or verified team PR discussions qualify.
- **FR-003**: DMs, external parties, sensitive topics, disagreements and scope/time
  commitments always require drafts. Unknown classifications require drafts.
- **FR-004**: Sensitivity and commitment rules have small configurable keyword and
  pattern lists with conservative defaults.
- **FR-005**: Exits are 0 send, 1 draft, 2 unable to classify; errors never send.
- **FR-006**: Existing outward lint remains enforced after tier selection.
- **FR-007**: Scope includes the workspace, configured repositories and associated
  worktrees; unrelated projects pass. No approval file authorizes sending.

### Key Entities

- Destination: configured work channel or verified team PR, plus explicit audience.
- Audience: company email domains and code-host organizations, known identity mappings.
- Tier: send or draft; inability to evaluate is distinct from a policy refusal.

## Success Criteria

- All four issue acceptance examples produce their specified decisions.
- Every tested DM, external, sensitive or consequential message remains a draft.
- CLI, hooks and ports agree on the same inputs; unrelated projects stay usable.
- No outward message bodies are included in refusal diagnostics.

## Assumptions

- A configured work channel is an internal broadcast destination unless explicit
  audience or external-channel evidence contradicts it. Missing destinations draft.
  Chat threads draft because the current chat port cannot verify participants.
  Tracker writes always draft, even if a payload claims a work channel.
- Known people use slack:<id>, github:<login>, and email:<address> keys;
  unknown addressed people draft. Exact domain/org matches only. GitHub authors
  and participants require the PR's organization, never email-only evidence.
- The owner edits .wuwei/config.toml outside agent tools; protect-state refuses
  file edits and normalized shell writes to this policy file.
- Team PRs belong to a configured repository in an allowed organization, with a
  known internal author and known internal discussion participants.
- Technical auto-send is limited to explicit mechanical sentence forms whose subject
  occurs in the PR discussion. Other technical prose remains a draft.
- Section 4.9 wins over 15.10's acknowledgement exception: time commitments draft.
- #85 is absent from this checkout. Preserve the shared lint seam for its voice checks.
- No shell-send support or drafting adapters are added. Existing MCP/port scope applies.

## Deferred

Voice profile enforcement and learning remain #85. Draft creation remains adapter work.
A semantic classifier and broader technical language coverage are later work.
