# Feature Specification: Prompt canary and honeytoken

**Feature Branch**: `105-canary`
**Created**: 2026-09-28
**Status**: Ready for implementation
**Input**: Issue #105, design sections 7.1 and 9.1.

## User Scenarios & Testing

### User Story 1 - Workspace instruction markers (Priority: P1)

The owner initializes a workspace whose seat instructions carry a unique private marker.

**Independent Test**: Initialize two temporary workspaces and build their instructions.

**Acceptance Scenarios**:
1. Given a new workspace, when init runs, then independent random canary and decoy values are created and protected like configuration.
2. Given workspace generation, when agents build runs, then every generated agent, charter and available skill contains the canary instruction and the shipped sources remain unchanged.

### User Story 2 - Refuse leaked instructions (Priority: P1)

The owner is paged when private instruction markers appear in outbound messages.

**Independent Test**: Submit text containing a generated marker through outward lint and the existing outbound guard.

**Acceptance Scenarios**:
1. Given outbound text containing the canary, when lint checks it, then it refuses with exit 1 and records a page event.
2. Given outbound text containing the decoy value, when lint checks it, then it refuses with exit 1 and records a page and scanner finding.
3. Given either profile, when approval policy would draft a message, then security detection still runs first.

### User Story 3 - Detect suspicious reads without leaking values (Priority: P1)

The owner receives evidence of decoy reads and fetched canaries without recording secrets.

**Independent Test**: Replay completed Read, WebFetch and other tool payloads.

**Acceptance Scenarios**:
1. Given a Read of the honeytoken path, when traced, then a page and scanner finding are recorded.
2. Given fetched Read or WebFetch content containing the canary, when traced, then a security.canary page is recorded.
3. Given tokens anywhere in trace metadata, keys or arguments, when recorded, then neither token appears in traces or events.
4. Given an unrelated call outside a workspace, then security checks return clean.

### Edge Cases

- Missing or malformed security material in an initialized workspace fails closed with a reason.
- Repeated builds preserve token values; invalid or escaping decoy paths are rejected.
- Symlink and hardlink aliases to the decoy are recognized.
- Irrelevant shell syntax is not parsed or blocked.
- Public event/state writers cannot impersonate the security producer.

## Requirements

### Functional Requirements

- **FR-001**: Init creates random per-workspace markers and a configurable decoy credentials path.
- **FR-002**: Workspace instruction generation embeds the canary without changing shipped instruction sources.
- **FR-003**: Outward detection always refuses matching text and records redacted page evidence.
- **FR-004**: Completed tool reads detect the decoy path and fetched canary content.
- **FR-005**: Trace serialization removes both marker values recursively before writing.
- **FR-006**: Security event kinds and state namespaces are reserved for dedicated producers.
- **FR-007**: Checks reuse workspace scope, locked event append, atomic writes and the current outbound integrations.

### Key Entities

- Workspace security material: canary, independent honeytoken value and relative decoy path.
- Security evidence: reserved event kind, page classification and source, never raw content.
- Generated instructions: workspace copies of agents, charters and available skills.

## Success Criteria

- All specified outbound leaks are refused and recorded as pages in both profiles.
- All tested decoy reads generate page evidence and scanner findings.
- No generated token appears in shipped source files, traces, events or diagnostics.
- Existing tests and new acceptance tests pass without network or external scanners.

## Assumptions

- The configurable honeytoken path is relative to `.wuwei`, selected at init; moving or rotating it later is outside scope.
- Existing workspaces without security configuration keep their prior behavior until upgraded. New workspaces require their generated security material.
- Generated instruction copies live under `.wuwei/generated`; briefs and runtime dispatch reference these copies. Shipped skills are copied when present; this branch has no shipped runtime skills.
- Detection is exact token matching, not a general encoded-data exfiltration detector.
- A Read response that exactly matches an on-disk generated instruction file is an expected instruction load. That exact content is exempt from fetched-canary alerts; altered content, other response fields and WebFetch remain checked.
- Completed tool traces provide read evidence through path fields, literal shell operands or exact honeytoken values in any tool response. Reads without that evidence require scanner analysis.
- The existing trace recorder's observational error reporting remains in place; security failures return exit 2.

## Deferred

- ZIRAN execution and general tool-chain analysis: no scanner implementation exists on this branch. Emit reserved scanner findings and trace attributes for consumption by that integration.
- Tamper-proofing against an owner-level process remains outside the section 9.1 threat model.
