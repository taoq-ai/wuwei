# Feature Specification: Guards control on evidence, not actions

**Feature Branch**: `997-guards-nudge`
**Created**: 2026-10-14
**Status**: Implemented; offline validation complete, real-day observation pending
**Input**: Issue #997, superseding #919. Owner boundary dated 2026-10-14.

## User Scenarios & Testing

### US1 - Visible guidance with protected evidence (P1)
The owner delegates ordinary work once. Every permitted PreToolUse refusal appears as a nudge in additionalContext, while its recorded event stays unchanged.
Acceptance: an unlisted send, unowned PR merge, approval or process refusal runs with a visible nudge by default. Raw merges of raised or claimed PRs must use bin/wuwei merge. Explicit guards.enforce=true still enforces ordinary refusals. Config, admin, infrastructure, canaries, unrun send checks, state, verdict and answer protections still block. Outside a workspace guards return clean.

### US2 - App delivery without repeated cards (P1)
With gates and required checks green, merge and app deployment proceed without a card. Infrastructure remains owner-only.
Acceptance: merge.auto, risk, size and cycle eligibility do not demand a card; owner_paths and never_auto_paths retain head-bound Owner step cards, including rename sources. Failed or unreadable gates/checks still prevent merging. App deploy command variations pass. Terraform/Pulumi changes, cloud resources, DNS, hosting settings and admin bypasses remain protected. New and upgraded host settings do not deny app deploys or PR approvals; secret pulls remain denied.

### US3 - Stable connector permission (P2)
An outward.allow entry for a UUID connector survives an account switch.
Acceptance: the same exact tool name with another UUID server matches; named servers and different tool names do not. Canary and honeytoken checks run on allowed and unlisted sends.

### US4 - Evidence-only fix handoff (P1)
A builder may rebut all blocking findings without a throwaway commit.
Acceptance: a clean unchanged fix head with a reason for every blocking finding advances to delta at that head. The delta reviewer receives the handback and decides the findings. Initial builds, missing/partial/empty reasons, dirty worktrees and failed checks retain their refusal and repeat/park limits.

## Functional Requirements

- FR-001: Show every let-through PreToolUse refusal as redacted additionalContext with actionable nudge wording describing the call and destination; preserve guard.would_refuse payloads. Never instruct that the owner adds a permission in a nudge.
- FR-002: Default guards.enforce to false in schema and templates; upgrades fill missing defaults and retain explicit true. Ordinary send/deploy/merge/approval findings nudge. Unrun send checks and raw merges of WUWEI-owned PRs stay on the floor. Scan raw MCP input for canaries before validating its shape. Retain the records floor and Stop behavior unchanged.
- FR-003: Merge with fresh gates, CI and branch protection without an ordinary eligibility card. Keep owner_paths and never_auto_paths cards. Preserve explicit owner_merge holds, pacing and breaker protection. Admin bypasses, repository settings and protection writes remain owner-only, including collaborators, hooks, keys, Actions settings, transfers, branch renames, environments, secrets and variables.
- FR-004: Limit deploy refusals and generated host denies to infrastructure. App deploys, releases and image publication pass; configured deploy.deny entries explicitly designate infrastructure. Migrate only known shipped host rules; preserve custom settings.
- FR-005: Canonicalize only a UUID connector server for outward.allow comparisons; exact case-sensitive tool names and named servers remain distinct.
- FR-006: Accept unchanged fix heads only with a complete reasoned handback answering each initial blocking finding, with checks clean. Route to delta and expose that evidence in resumed, fresh and second-opinion review prompts. Do not count the answer as a passing verdict.

## Assumptions

- Clarify completed non-interactively: the supplied boundary is the approved design. Extension hooks are skipped as requested.
- Existing explicit guards.enforce=true is owner intent, including existing files written by old templates; there is no reliable provenance to silently overwrite it.
- App publishing includes release/tag/image publication and application workflows. Kubernetes/Helm resource mutations, IaC, DNS and hosting project mutations are infrastructure. deploy.deny is the owner's explicit additional infrastructure list.
- Explicit owner_merge vetoes, circuit breakers and pacing are existing holds; ordinary eligibility does not require another owner card.
- Fix-round clarification: owner_paths and never_auto_paths express protected changes. Raw merges of raised or claimed PRs must preserve the merge journal, daily cap, breaker and gate checks. Approval stays a nudge. Cloud operation matching excludes option values; access, identity and secret deploy flags are infrastructure. deploy.workflows has no reader and is retired on upgrade.
- Handback format: `No change: <gate> <blocking finding number>: <reason>`, using one-based order within each gate's parsed blocking findings. The fix brief supplies the keys. Duplicate, missing or empty answers do not qualify.
- A real owner day cannot be simulated as completed by unit tests. No external sends, deploys, merges or network tests are authorized by this implementation task.

## Success Criteria

- SC-001: All six behaviors have offline regression tests and the explicit-file full suite passes.
- SC-002: Existing security and record refusal tests remain covered.
- SC-003: A later real day asks only for the morning plan and config, admin or infrastructure changes; this operational observation is not claimed by the test suite.

## Deferred

- Stop hook #989 and Codex runtime #976 are unchanged.
- Real-day validation and issue closure are external follow-up; no gh, commit or push commands are run.
