# Feature Specification: Report and steward retro

**Feature Branch**: `025-report-retro`  
**Created**: 2026-09-29  
**Status**: Draft

## User Scenarios & Testing

### User Story 1 - Close with landed learning (Priority: P1)

The steward reviews each role's captured evidence, records the day's cycle and proposes checklist learnings. The planner promotes supported charter proposals. Hard-rule changes remain decision proposals.

**Acceptance Scenarios**:

1. Given an applied learning, when the planner closes the day, then a charter commit with a promotion trailer and a dated changelog line exist and the Stop guard passes.
2. Given an unpromoted proposal or missing committed changelog, when the planner closes the day, then the Stop guard refuses.
3. Given a hard-rule learning, when the retro is written, then it appears as a decision proposal and no guard rule changes.

### User Story 2 - Read the daily report (Priority: P2)

The owner reads one local report covering outcome against baseline, open and parked work, answered decisions and carry.

**Acceptance Scenarios**:

1. Given recorded day evidence, when the owner runs report, then it shows outcome metrics beside baseline, open at close, parked items with decision records, answered decisions and carry.
2. Given absent measurements, when the owner runs report, then the affected metric says unmeasured.

### Edge Cases

- Missing or malformed evidence fails with a reason; no result is called clean when unmeasured.
- Outside a WUWEI workspace, commands have no blocking effect.
- An empty set of lessons is represented explicitly as none.

## Requirements

### Functional Requirements

- **FR-001**: Retro MUST include a per-role review based on captured notes, verdicts, events and metrics, plus a cycle table.
- **FR-002**: Retro MUST create charter checklist proposals with evidence; promotion MUST land applied proposals and record a dated changelog line in committed workspace history.
- **FR-003**: Hard-rule changes MUST be proposed only.
- **FR-004**: Stop MUST verify applied charter changes and the dated changelog in the promotion repository.
- **FR-005**: Report MUST show outcome and baseline, open at close, parked with decision records, answered decisions and carry.
- **FR-006**: Report MUST be local owner text; outward posting uses existing outbound tiers.

### Key Entities

- **Retro**: Dated review, per-role findings, cycle table, applied and proposed changes.
- **Proposal**: Charter text, reason and evidence to be landed by promotion.
- **Report**: Dated owner summary from day evidence.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every applied charter learning has one committed charter change and one committed dated changelog line.
- **SC-002**: A complete retro with a landed learning passes the existing Stop guard.
- **SC-003**: Report covers all five requested sections and labels missing measures unmeasured.

## Assumptions

- The local `.wuwei` repository is the authoritative history for charter changes.
- Existing seat retro captures are the per-role source; the steward compiles them at close.
- Outcome measures not implemented by existing producers remain unmeasured and are deferred.
