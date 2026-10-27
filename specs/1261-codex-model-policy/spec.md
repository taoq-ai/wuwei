# Codex role model policy

Promise: generate Codex-native role defaults from the existing table and owner models rows. Keep requested settings distinct from measured turn settings and provider-resolved child settings. Missing measurements stay unmeasured. The owner session model stays unchanged.

Acceptance: regeneration honors role-and-tier overrides before role overrides; native dispatch preserves requests even when inheritance prevents enforcement; reports name requests and supplied metadata separately; absent resolved metadata is explicit.

## Clarifications

### Session 2026-10-27

- The approved item 1261 and authorization.md answer scope and the 3,800-line cap. No further owner question is needed.
- Role files have no item context. Their default tier is standard; the planner selects item-tier settings per call when the surface supports overrides.
- Full forks inherit settings. An omitted fork field is not evidence of inheritance. A launch-turn model is not a resolved child model.

## User Scenarios & Testing

### US1: role defaults (P1)

You regenerate Codex roles and receive native model and effort settings. A role-and-standard row wins over a role row, which wins over the mapped standard table setting. An explicit tier passed to generation selects that tier. Independent test: parse generated TOML, regenerate after config changes, and read doctor output.

### US2: dispatch visibility (P1)

You read a report and see requested model and effort beside provider-resolved child model. Launch-turn metadata has its own label. Explicit full-fork inheritance policy is named; missing metadata stays unmeasured. Independent test: submit recorded native spawn payloads and inspect ledger rows and report output.

## Requirements

- FR-001: Map Opus to gpt-6.1-sol, Sonnet and Haiku to gpt-6-luna, and Fable to gpt-6-astra. Keep table effort names.
- FR-002: Select owner role-and-tier, then owner role, then table tier/default. Preserve native owner IDs as requests, without claiming availability.
- FR-003: Init and doctor use the same configured standard-tier renderer. Claude role generation and the owner session remain unchanged.
- FR-004: Preserve requested model/effort, separately supplied launch-turn model/effort, resolved child model, and explicitly requested fork policy. Never infer resolved child settings from parent settings or the table.
- FR-005: Existing report grouping exposes those meanings and absent resolution as unmeasured. Dispatch telemetry never implies attestation.
- FR-006: Reuse models config and seat.started records; no new config key or telemetry store. Runtime delta is at most 21 physical lines and total at most 3,800.

## Edge cases

Unknown owner model IDs remain requests; malformed models rows follow existing config filtering. Explicit full forks may request an override which the surface cannot apply. Surfaces without override fields use the brief to communicate requests; absent values remain unrecorded or unmeasured. Responses without resolution metadata never inherit the launching turn's model.

## Success criteria

SC-001: Focused tests cover generated defaults, owner/tier precedence, doctor drift, inherited/unavailable override visibility and report consumers.
SC-002: Main/head route corpus has every moved decision or reason listed; parser probing is N.A. because command parsing is unchanged.
SC-003: Required checks pass within the runtime budget, and full-tier spec artifacts have no open critical or high findings.

## Assumptions

The deterministic Sonnet mapping uses gpt-6-luna to preserve a second model for review seats. The current local model catalog and active tool schema list those IDs and effort levels. Measured delivery outcomes or removed model support would overturn this choice. Owner-supplied native IDs are passed through because provider availability belongs to Codex; resolved metadata can overturn the requested choice.

## How this fails:

1. A provider substitutes an unavailable model and the report incorrectly claims the request ran.
2. Doctor compares unconfigured output and falsely reports fresh owner overrides as stale.
3. A full fork receives requested overrides but inherits the parent's settings and the report hides that limitation.

Rollback: revert this change and regenerate Codex roles with wuwei init --codex.
