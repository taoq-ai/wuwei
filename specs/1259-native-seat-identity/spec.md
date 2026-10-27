# Native seat identity

Promise: Keep successful native task paths and legacy agent ids, explicit known roles and requested settings. Diagnose unsupported dispatch shapes without inventing a running seat or attesting work.

Acceptance scenarios:
1. A sanitized native launch through spawn_agent or the observed collaborationspawn_agent retains its task path, explicit role, message, requested model and reasoning effort; resolved model stays unmeasured.
2. A legacy agent_id launch retains its identity and role.
3. A task path without a validated role retains its identity in an unconfirmed diagnostic, regardless of role words in its message.
4. Missing or malformed identity records a diagnostic and creates no running seat or attestation.

## User Scenarios & Testing

### US1: Track successful dispatches (P1)
A planner sees the actual dispatched identity, known role and requested settings. Scenarios 1 and 2 are independently replayable.

### US2: Diagnose unsupported dispatches (P1)
A planner sees why a successful identity lacks role support, or why an unreadable response cannot establish identity. Scenarios 3 and 4 are independently replayable.

## Requirements

- FR-001: Preserve agent_id and task_name identities from supported object or JSON object results.
- FR-002: Preserve requested message, model and reasoning effort without claiming resolved execution settings.
- FR-003: Accept a role only from the explicit agent_type field, matching a known WUWEI role, including its existing wuwei namespace.
- FR-004: Retain identities with missing or unknown roles as unconfirmed diagnostics, never running seats.
- FR-005: Diagnose missing, blank, non-string, malformed and nested-only identity responses without creating seats or attestations.
- FR-006: Dispatch guidance must inspect active schema support before supplying role fields.
- FR-007: Newly recorded seat metadata must redact recognized credentials and the workspace canary before any clipping, while normalization retains the requested message.
- FR-008: A stopped or unconfirmed identity closes only its session. Sessionless historical stops retain compatibility for non-path legacy ids; native task paths require session matching.

## Edge cases

Empty objects, nulls, lists, numbers, whitespace-only ids, malformed JSON and nested error strings cannot establish identity. Prompt prose cannot establish role. Legacy agent_id takes precedence when both identity fields exist. Pre-tool calls have no response yet and create no seat.

## Success Criteria

All four acceptance scenarios pass. Invalid responses and missing roles create zero running seats and zero attestations. Existing command-route verdicts remain unchanged.

## Clarifications

Approved plan and native probe settle scope. No owner question remains. This item does not enable native transcript attestation.

## Assumptions:

Only agent_type is currently validated as a role field. A captured supported alternative mapping would overturn this choice. The observed task_name is an opaque identity, not a role.

The captured 2026-10-27 PostToolUse schema names collaborationspawn_agent, with task_name, agent_type and message input fields and a JSON string result. Support is limited to that spelling and the existing spawn_agent name. A captured additional spelling would require its own regression.

## How this fails:

1. A regex matches an id buried in an error and invents a running seat.
2. Prompt text supplies a role that the harness never accepted.
3. Requested model settings are mistaken for provider-resolved settings.

Review clarification: board.py is an authorized native-identity consumer in this fix round. The planner reallocated one runtime line for redaction before clipping, raising the item allowance from +9 to +10 while keeping the overall 3,800 cap.

Rollback: revert this change.
