# Feature Specification: Checkout install integrity

**Feature Branch**: `165-install-integrity`
**Created**: 2026-09-29
**Status**: Ready for implementation
**Input**: Issue #165, plugin installs from the marketplace or a source checkout do not lock the workspace.

## User Scenarios & Testing

### User Story 1 - Confirm a development checkout once (Priority: P1)

A developer confirms a clean checkout on the host and uses the workspace until the
checkout changes, without repeating confirmation for each tool call.

**Independent Test**: Confirm a clean checkout, exercise repeated tool calls, then
move HEAD or edit a shipped file and verify refusal.

**Acceptance Scenarios**:

1. Given a clean plugin checkout, when the owner reconfirms once, then PreToolUse
   passes repeatedly while its commit and clean tree remain unchanged.
2. Given a confirmed checkout, when a pull moves HEAD, then PreToolUse denies until
   the owner reconfirms the new clean commit, even if file contents are unchanged.
3. Given a confirmed checkout, when a shipped file has an uncommitted edit, then
   PreToolUse denies and reconfirmation cannot bless the dirty checkout.
4. Given missing or malformed checkout evidence, when integrity is checked, then
   it fails closed with a reason.
5. Given an unrelated project, when a tool is called, then checkout integrity does
   not block it, including commands beyond the shell parser's supported syntax.

### User Story 2 - Install the signed release (Priority: P1)

An operator follows the documented signed release path without reconfirmation.

**Independent Test**: Measure a signed release and read the two installation guides.

**Acceptance Scenarios**:

1. Given an authentic signed release asset, when installed, then integrity passes
   without reconfirmation, with the existing verification preserved.
2. Given README or the documentation landing page, when following installation,
   then the operator downloads and extracts the release asset before running init.
3. Given the marketplace listing, then its local source is identified as development;
   both guides describe checkout confirmation and the shipped planning skill accurately.

### Edge Cases

- Dirty, missing, unreadable or malformed VCS evidence cannot be confirmed.
- HEAD or content changing during host confirmation requires a retry.
- Git worktrees use a `.git` file and must be supported alongside ordinary clones.
- A partially present release manifest/signature cannot become a checkout fallback.
- Legacy confirmations without checkout evidence require a new confirmation.

## Requirements

### Functional Requirements

- **FR-001**: Record the confirmed content fingerprint, commit and clean state.
- **FR-002**: Check current checkout commit and cleanliness before allowing cached
  confirmation at PreToolUse; changed or unavailable evidence refuses.
- **FR-003**: Preserve signed release verification and its existing cached behavior.
- **FR-004**: Keep host confirmation local evidence, protected by existing producer
  restrictions, never proof against a process running as the owner.
- **FR-005**: Both entry guides use the signed release path and remove stale statements;
  the marketplace identifies its local source as development.

### Key Entities

- Checkout confirmation: content fingerprint, HEAD commit and clean state.
- Cached verdict: measured result and checkout evidence when applicable.

## Success Criteria

- **SC-001**: One confirmation permits repeated calls at the same clean commit.
- **SC-002**: Every tested changed HEAD, dirty tree and unavailable evidence case denies.
- **SC-003**: Signed releases require zero confirmations.
- **SC-004**: Both entry guides document download, extraction and initialization.

## Assumptions

- A development checkout has its own `.git` directory or worktree file and neither
  release manifest nor signature. Partial release artifacts remain on the signed path.
- Clean means no changes reported by the existing VCS status operation, including
  untracked files. Ignored development artifacts are not Git dirtiness.
- Existing owner confirmation remains local tamper evidence under spec 9.1.
- Depends on the integrity implementation from #104; no new configuration is needed.

## Deferred

None. No new guard, port or authentication boundary is needed.
