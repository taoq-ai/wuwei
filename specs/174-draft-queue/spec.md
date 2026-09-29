# Feature Specification: Owner draft queue

**Feature Branch**: `174-draft-queue`
**Created**: 2026-09-29
**Status**: Ready
**Input**: Issue #174, owner draft queue for outward replies.

## User Scenarios & Testing

### User Story 1 - Keep replies awaiting approval (Priority: P1)

A seat's approve-tier reply stays available for owner review without being sent.

**Independent Test**: Call a text-bearing adapter with approve-tier prose and inspect the queue and fake transport.

**Acceptance Scenarios**:
1. Given a seat reply classified approve, when the adapter is called, then a draft exists and nothing was sent.
2. Given invalid policy or security evidence, when the adapter is called, then it fails closed with a reason.
3. Given a pending draft, when the owner lists drafts, then its ID, destination, text and reason are visible.

### User Story 2 - Owner approves, edits or drops (Priority: P1)

The owner decides what leaves the workspace from the host CLI.

**Independent Test**: Approve through a fake adapter, repeat approval, and exercise the seat hook.

**Acceptance Scenarios**:
1. Given a pending draft, when the owner runs `wuwei drafts approve <id>`, then the adapter sends exactly that text once and the draft closes.
2. Given a seat calling `drafts approve`, then it is refused as owner-only.
3. Given `--edit`, when the owner saves final text, then final outward and voice lint run before sending and both versions and edit size are recorded.
4. Given `drafts drop <id>`, then the decision is recorded and nothing is sent.
5. Given repeated or concurrent approval, an adapter failure or an interrupted send, then the command cannot blindly resend the draft.

### User Story 3 - Read-only visibility and voice measurement (Priority: P2)

The cockpit shows pending drafts and a host CLI approval command. Voice metrics use successful sends, grouped by audience.

**Independent Test**: Inspect cockpit JSON, escaped HTML, and metrics for edited, unedited, dropped and unsent drafts.

**Acceptance Scenarios**:
1. Given pending drafts, the cockpit displays them without a POST action.
2. Given successful approvals, the share sent unedited and edit sizes are measurable per audience; absent successful sends remain unmeasured.

### Edge Cases

Malformed queue records, unreadable state, editor errors and adapter errors fail closed. Unknown IDs and closed drafts are findings. Lint failures leave the draft pending. Events contain metadata only, never reply bodies. Generic state and event commands cannot forge draft evidence.

## Requirements

- FR-001: Persist approve-tier adapter calls with ID, channel, destination, original text, item when available, creation time, tier reason and original operation inputs.
- FR-002: Only owner host actions may approve or drop. No persisted approval flag may authorize an ordinary seat send.
- FR-003: Approval validates final text with security, outward and voice rules and executes the original adapter operation at most once.
- FR-004: Record successful sends, drops, original and final text, and character edit size; exclude unsuccessful sends from voice metrics.
- FR-005: Keep cockpit read-only and preserve existing scope and shell relevance behavior.

### Key Entities

Draft: original destination and operation, text, audience, lifecycle and owner decision. Voice measurement: successful send count, unedited fraction and character edit sizes per audience.

## Success Criteria

- Every accepted approve-tier adapter reply creates a reviewable draft and zero transport calls.
- A successful approval makes one transport call; repeated approvals make zero additional calls.
- All seat approval and drop attempts through guarded tools are refused.
- Cockpit output and metrics agree with stored decisions.

## Assumptions

- Queue scope is today's day, matching the existing cockpit. IDs are unique within and across days.
- Existing hooks enforce host-only actions under spec 9.1. Same-UID arbitrary Python or disabled hooks are outside that threat model; a seat-writable approval flag is never trusted.
- Existing text-bearing adapter operations are queued. Arbitrary MCP tools remain refused because their inputs do not identify a replayable installed adapter operation.
- `--edit` uses the existing editor adapter and EDITOR, defaulting to vi. Single-field replies edit plain text; multi-field drafts edit a JSON object of text fields.
- A send with an uncertain outcome is terminal for automatic retry. Transport-level reconciliation is deferred.
- The issue's read-only cockpit requirement takes precedence over the broader future cockpit approval surface in spec 5.9.

## Deferred

Cross-day queue browsing, arbitrary MCP replay, transport reconciliation and automatic voice proposals from repeated edits are follow-up work.
