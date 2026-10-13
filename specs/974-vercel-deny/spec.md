# Feature Specification: Narrow Vercel host permissions

**Feature Branch**: `974-vercel-deny`
**Created**: 2026-10-13
**Status**: Ready
**Input**: GitHub issue #974 and the owner's 2026-10-13 decision.

## User Scenarios & Testing

### User Story 1 - Initialize a workspace (Priority: P1)

A new workspace blocks Vercel deployment and environment writes at the host while allowing reads to reach WUWEI's guard.

**Independent Test**: Initialize a project and inspect its local `permissions.deny`.

**Acceptance Scenarios**:

1. Given a new project, when `wuwei init` runs, then both `vercel` and `vc` have bare, deploy, `--prod`, promote, rollback, redeploy, alias, domains add, env add, env rm, and env pull deny entries.
2. Given that project, then neither broad legacy pattern exists; reads such as env ls, ls, inspect, logs and whoami are absent from host denials.
3. Given pre-existing project settings with either legacy broad pattern, new workspace initialization removes those patterns.

### User Story 2 - Upgrade an existing workspace (Priority: P1)

An existing workspace replaces its old broad Vercel entries without losing unrelated Claude settings.

**Independent Test**: Seed a settings file containing both legacy patterns and custom keys, run `init --upgrade`, and compare the result.

**Acceptance Scenarios**:

1. Given both legacy patterns, upgrade removes them and inserts the narrow entries once, preserving all other settings and deny entries.
2. Given a dry run, upgrade reports the pending settings change and leaves the file unchanged.
3. Given a second upgrade, no duplicate entries appear.

### Edge Cases

- A workspace with only one legacy pattern still gets the complete narrow set.
- Settings without legacy Vercel patterns remain untouched by this migration.
- Symlinked or malformed settings must not be overwritten.
- The existing #947 guard still classifies reads and writes and requires owner approval for writes.

## Requirements

### Functional Requirements

- **FR-001**: Replace broad Vercel host denials with the exact narrow command patterns for both binary names.
- **FR-002**: Migrate old host denials during `init --upgrade`, changing no unrelated settings values or entries.
- **FR-003**: Preserve dry-run and idempotent upgrade behavior.
- **FR-004**: Preserve #947 guard outcomes and owner-only publish flow.

## Success Criteria

- **SC-001**: New and upgraded settings contain the required narrow patterns and no legacy broad patterns.
- **SC-002**: Unrelated settings values remain equal before and after upgrade.
- **SC-003**: Focused permission, upgrade, and #947 guard tests pass without network access.

## Assumptions

- The owner's 2026-10-13 decision supersedes #947's assumption that broad host denials remain. Proposed owner-only design wording: host permissions block the enumerated Vercel deployment and environment write forms, while reads reach the guard.
- `Bash(vercel)` and `Bash(vc)` denote bare invocations. Space-prefixed patterns cover the named subcommands and flags.
- Upgrade migrates settings only when at least one legacy broad pattern exists. It adds the complete narrow set and removes both legacy forms if present.
- The issue's explicit test-file instruction overrides the constitution's full-suite instruction. No real network or GitHub calls are made.

## Clarifications

No questions asked as instructed. The above assumptions resolve the pattern, migration and dry-run details.
