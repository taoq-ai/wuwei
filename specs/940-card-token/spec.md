# Feature Specification: Owner step card token binding

**Issue**: #940
**Branch**: 940-card-token
**Created**: 2026-10-13
**Status**: Implemented and verified

## User Scenarios & Testing

### US1: Answer a card with context (P1)

The planner appends context to `Owner step: bin/wuwei build next TIN-790-MERGE-MAIN (15924e1a464b)` and the owner answers Yes. The same command recognizes that answer. Acceptance: context on the same line or a later line binds; a seat's identical answer does not; a consumed Yes cannot authorize another application.

### US2: Explain a mismatched answer (P1)

The owner answers a card whose token is missing or whose command differs. The command refuses and identifies the matching command or token, explains the differing part, and supplies the expected card. Acceptance: ordinary refusals, build next's Blocked card, and dispatch cards share this diagnostic. No recorded answer produces no mismatch hint.

## Requirements

- FR-001: An answer binds when its question starts with the exact Owner step command and parenthesized card token, allowing trailing context.
- FR-002: A missing or different token or different command must never authorize the expected action. A related answered card must produce a diagnostic identifying the shared command or token and the missing or differing component.
- FR-003: Build next and dispatch card paths must use the same identity and diagnostic rules as ordinary Owner step refusals.
- FR-004: Only answers recorded from a main session count. Latest answers win; Yes is spent once under existing consumption rules; terminal input never grants permission.
- FR-005: Continue recording hashed topics only, without question or answer bodies. Preserve exact-card historical topics and tokenless exact-card behavior.

## Key Entities

Owner step card: exact command plus optional token, with Yes and No choices.
Recorded answer: gate.asked topic hashes. Consumption: existing owner.approved or workflow transition.

## Edge Cases

Changed command with the same token, missing token, wrong token, unrelated answer, prefixed context, No or free text after Yes, context containing another parenthesized token, and a seat answer all retain their documented identity and refusal behavior.

## Success Criteria

- SC-001: The reported extended-question Yes progresses without a second ask.
- SC-002: Missing-token and changed-command answers refuse with a specific mismatch on both ordinary and build card paths.
- SC-003: Offline tests for affected importers pass with no runtime dependency added.

## Assumptions

- Scope is #940 only; #937, #938 and #941 are context.
- Generated tokens are 12 lowercase hexadecimal characters. Other existing token forms retain exact-question matching.
- Extra context is permitted after the leading command and token, not before or within that identity. Tokenless cards retain exact matching.
- Hashed events cannot reveal an unknown differing command or token. Diagnostics identify the shared component and the expected identity, without storing question bodies.
- Historical extended-question hashes cannot be reversed or migrated; a new answer is needed. Historical exact-card hashes stay valid.
- Proposed design clarification for owner review: the exact leading command and token bind the reply; following context does not. The owner-only design document remains unchanged.
- No questions are asked. The supplied scope resolves behavior choices; implementation and review proceed in this worktree without commits or publishing.

## Clarifications

All material ambiguities resolved by the assumptions above. Functional scope, identity, failure handling, trust boundary and acceptance are clear. No external integration is required.

## Deferred

F2 same-line context without a token remains undiagnosable from the recorded hashes; the owner requested only the small first-line hint improvement.

## Owner-requested review follow-up

The owner explicitly authorizes this follow-up after the initial fix and review round.

- F1: If one recorded call contains both Yes and No for the same canonical card, treat it as no answer, superseding an earlier Yes. A later unambiguous reply can answer it again.
- F3: Mismatch diagnostics consider related answers after the most recent owner.approved for the requested command. An approval for another command does not erase them.
- F2: Also record a diagnostic-only command topic from the first line. A tokenless question with context on subsequent lines can then identify a mismatch, without authorizing the card. Same-line context without a token remains outside this small change because the command boundary is unavailable.
