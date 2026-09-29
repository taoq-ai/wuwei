# Feature Specification: Outcome metrics

**Feature Branch**: `080-outcome-metrics`  
**Created**: 2026-09-29  
**Status**: Ready  
**Input**: GitHub issue 80

## User Scenarios & Testing

### User Story 1 - Read outcome against baseline (Priority: P1)

The owner runs `wuwei metrics` or builds a report and sees each outcome metric beside a value from the workspace baseline. Missing evidence reads `unmeasured`.

**Acceptance Scenarios**:

1. Given a baseline with named values, when metrics run, then those values appear beside measured outcomes.
2. Given no baseline or no tracker adapter, when metrics run, then the missing comparison or lead time reads `unmeasured`.

### User Story 2 - Measure owner attendance safely (Priority: P1)

The owner sees weekday attended minutes with a 10 minute cut and 5 and 15 minute sensitivity figures. Transcripts are local to the configured projects directory and workspace repositories.

**Acceptance Scenarios**:

1. Given fixture transcripts with overlapping sessions, when metrics run, then attended stretches are counted once.
2. Given fixture transcript messages containing a sentinel, when metrics run, then the sentinel appears in no stdout, stderr, event or state output.

### User Story 3 - Measure delivery outcomes (Priority: P2)

The owner sees escaped defects, review rework and lead time from existing code host and tracker ports.

**Acceptance Scenarios**:

1. Given merged PRs with full 14 day observation windows, then escaped defect rate and raw follow-up count are shown.
2. Given human review threads followed by commits, then mean, median, p90 and nonzero share are shown.
3. Given tracker In Progress history and merged PR timestamps, then lead time and secondary durations are shown.

## Requirements

- **FR-001**: Extend the existing metrics command and report, with no second command.
- **FR-002**: A metric without enough evidence must read `unmeasured`, never zero.
- **FR-003**: Escaped defects use only complete 14 day windows and include raw revert and follow-up fix counts.
- **FR-004**: Review rework counts human review threads followed by a new commit.
- **FR-005**: Owner attendance reads transcript timestamps, record type, sidechain and meta flags, cwd, content block types and a short system-prefix check only. It never emits message text.
- **FR-006**: Consecutive human turns less than the idle cut apart form a stretch, plus half a cut of lead-in. Overlap across sessions is merged. Only complete weekdays contribute to distribution statistics.
- **FR-007**: Lead time runs from tracker In Progress to first merged PR. No tracker yields `unmeasured`.
- **FR-008**: Baseline lives only in workspace `memory/notes/baseline.md`; repository template contains blank fields.
- **FR-009**: External reads go through existing code host and tracker ports; core invokes no subprocess.

## Success Criteria

- **SC-001**: All acceptance scenarios pass with local fixtures and no network.
- **SC-002**: A fixture sentinel message appears in no metric output, stderr, event or state.
- **SC-003**: The full test suite passes.

## Assumptions

- The existing merge journal provides observed defect outcomes for WUWEI managed merges. Other merged PRs require code host evidence and report `unmeasured` until available.
- A human review thread followed by a later commit before merge is the available evidence that the thread forced a change; the code host does not expose a direct causal link.
- PRs and tracker items come from the workspace's recorded day state. The metric cannot discover unrecorded external work.
- A complete weekday is any weekday ending before the metric run time; an empty complete day between first and last observed turn counts zero minutes.
- Baseline fields are values entered by the owner from the hand-run period, using the same transcript estimator for attendance.
- The optional input-idle sampler is deferred because it is not required to compute transcript estimates.

## Deferred

- Optional input-idle sampler.
