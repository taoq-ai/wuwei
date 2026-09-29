# Feature Specification: Documented schemas and actionable errors

## User Scenarios and Testing

### User Story 1: Start from valid templates (P1)
An operator prints plan, rank, or decision templates and can use them without repairing their shape.

**Acceptance**: In an initialized workspace, `wuwei plan template | wuwei plan propose -` exits 0. Rank template has framework components and a lead candidate. Decision template passes decision lint.

### User Story 2: Find the data contract (P1)
An operator can use one reference page to construct lead JSON, scores, flags, decisions and retro notes, configure retro and merge behavior, and call the Codex companion.

**Acceptance**: The site links a reference page covering each named format and command.

### User Story 3: Recover from refusals (P1)
An operator gets a named setting, file or next command for every dry run error and a reason when a tool read times out.

**Acceptance**: A table test checks the listed messages; tool timeouts fail closed with a reason.

## Requirements

- FR-001: Each template prints a skeleton valid under its own validator.
- FR-002: The site documents lead JSON, WSJF, RICE, tracks, flags, envelope, decisions, retro notes, `[retro]`, `merge.auto`, and Codex task/status/result/cancel with JSON fields.
- FR-003: Each listed refusal identifies a relevant key, file, path or next command.
- FR-004: Blocking tool reads have finite timeouts and print the reason when unmeasured.

## Edge Cases

- Rank uses the configured framework. Plan goals cite an identifier present in goals.md.
- A template printed outside a workspace must fail with an explicit reason when workspace data is required.
- An adapter timeout is an exit 2, not a clean or policy finding.

## Success Criteria

- The plan template pipeline exits 0 in a configured workspace.
- The decision skeleton lints and rank skeleton ranks.
- Every dry run message table entry contains a recovery cue.
- The full pytest suite passes.

## Assumptions

- A plan template uses the first goal in memory/goals.md and configured framework.
- `-` means standard input for JSON consumers.
- Templates may include sample evidence that operators replace before approving real work.
