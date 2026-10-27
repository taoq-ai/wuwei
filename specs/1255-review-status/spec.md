# Review status ready and auto-merge evidence

Promise: Review-driven statuses use one positive classification across ready and merge evidence. A draft with passed gates and green non-review checks can become ready. Auto-merge can wait for pending review and permitted CI, while direct merge still waits.

Acceptance scenarios:
1. A pending positively identified review status adds no CI-running refusal to a draft with passed gates and green builds.
2. Pending review alone, or with running CI, permits arming auto-merge. Direct merge remains held.
3. Failed review, missing gates, owner review and unreadable classification keep both merge routes held.
4. Main and head route results name every changed verdict or reason, with the tested PR's gates satisfied.

## User Scenarios & Testing

### US1: Request review after green builds
A builder can turn a draft ready when its review status waits for a reviewer. Classification must use the status's workflow evidence, never its context name.

### US2: Arm auto-merge while review waits
A shepherd can arm auto-merge when only pending review and permitted CI remain. GitHub applies its merge protections before completing the merge.

### US3: Keep safety failures held
Failed review, missing gates, owner review, unanswered threads and unreadable evidence prevent auto-merge and direct merge.

## Requirements

- FR-001: Reuse positive workflow classification for pending review evidence on every door.
- FR-002: Permit auto-merge for pending review with no other safety gaps beyond permitted CI waits.
- FR-003: Preserve direct merge and safety refusals, including unreadable classification.
- FR-004: Record every main-versus-head route movement with the corpus hash and satisfied gate evidence.

## Success Criteria

- SC-001: All accepted ready and merge scenarios pass their regression tests.
- SC-002: Every corpus route runs against main and head under identical fake-host evidence.

## Clarifications

The approved item supplies all required decisions. No new classification shape is authorized without an actual failure sample.

## Assumptions:

- The existing 1067-probe fixture remains the supported review-status shape. Its source documents ai-stacks' observed Actions URL and workflow. A new sanitized sample would overturn this assumption.
- An unreadable review classifier must remain a safety gap even for auto-merge. The approved acceptance explicitly requires this. A changed owner-approved promise would overturn it.

## How this fails:

1. A failed review is accidentally waived by an overly broad pending-review match.
2. A context name is mistaken for positive workflow evidence and skips CI.
3. A host error becomes ordinary running CI, allowing auto-merge without readable classification.

Rollback: Revert the change.
