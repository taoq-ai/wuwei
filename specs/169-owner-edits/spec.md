# Feature Specification: Owner memory edits

**Feature Branch**: `169-owner-edits`
**Created**: 2026-09-29
**Status**: Ready
**Input**: GitHub issue #169

## User Scenarios & Testing

### User Story 1 - Edit goals without an integrity nudge (Priority: P1)

The owner edits goals through WUWEI. The resulting history identifies the owner action and workspace integrity stays clean.

**Acceptance Scenarios**:

1. Given a WUWEI workspace, when the owner runs `wuwei goals edit` with valid changed goals, then SessionStart reports no goals integrity nudge and workspace history contains `Promoted-by: wuwei` and `Edited-by: owner`.
2. Given invalid goals or an unavailable editor, when the owner attempts an edit, then no change is committed and the command explains the failure.

### User Story 2 - Keep goals owner only (Priority: P1)

Seats cannot edit goals directly or use the owner edit action.

**Acceptance Scenarios**:

1. Given a seat writing goals.md, when the write guard runs, then it refuses the write.
2. Given any agent session in the workspace, when it invokes the owner edit action, then the action is refused.

### User Story 3 - Edit voice through the same owner flow (Priority: P2)

The owner can edit voice.md with the same recorded provenance and without an integrity page.

**Acceptance Scenarios**:

1. Given a WUWEI workspace, when the owner edits a valid voice profile, then SessionStart reports no voice integrity page and history contains both provenance lines.

## Edge Cases

- Reject invalid goal blocks and invalid voice rules before changing workspace memory.
- Refuse symbolic links for owner memory targets.
- Report missing workspace or unavailable VCS as an unmeasured failure.

## Requirements

### Functional Requirements

- **FR-001**: Provide owner edit actions for goals and voice using an editor or input file.
- **FR-002**: Validate the resulting content before replacing owner memory.
- **FR-003**: Commit an accepted change through the workspace promotion producer with both provenance lines.
- **FR-004**: Refuse owner edit actions from agent tools in the workspace and preserve direct write protection.
- **FR-005**: Preserve the refusal of goals through seat proposal promotion.

## Success Criteria

- **SC-001**: Every successful owner edit produces a clean integrity result for its target.
- **SC-002**: Every successful owner edit records both provenance lines in workspace history.
- **SC-003**: Every tested seat write and seat owner edit is refused.

## Assumptions

- An unchanged edit creates no new commit when the target has no uncommitted workspace change.
- `--file` names a source file whose contents are copied into the owner memory target.
- The hook uses workspace scope to refuse owner edit actions from agent tools.

## Deferred

- No new configuration keys or proposal approval flow are needed.
