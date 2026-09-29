# Feature 077: Merge policy and circuit breaker

## User Scenarios & Testing

### US1: Decide whether a PR may merge (P1)

The owner enables automatic merging per repository. A single policy clears only small,
low-risk changes whose current head has passed every gate and repository requirement.

Acceptance scenarios:
1. A skipped required check returns 1 and names the check.
2. Missing explicit `merge_deploys = false` returns 1.
3. Any unreadable precondition, including an API error body, returns 2 and routes to owner.
4. Risk flags, protected paths, excessive change size or cycles, stale gates, pending or
   missing checks, outstanding reviews or obligations, stale bot review, an outdated
   branch, soak, quiet hours, daily cap or a tripped breaker prevent merging.
5. Classic branch protection and repository rulesets both contribute requirements.

### US2: Merge the measured head (P1)

A cleared PR merges with a head pin and without an override. A push between check and
merge causes failure and nothing merges. Every accepted merge has evidence and an undo
entry. Direct merge tools cannot bypass the policy's writer and monitoring.

### US3: Stop after an escaped defect (P1)

The watch follows the actual merge commit on the base branch across restarts and days.
A red check opens a revert PR, pages the owner, and disables auto-merge for that repository.
Reverts also trip the breaker. The mature rolling 14-day auto-merge defect rate is compared
with the owner's baseline; missing measurements are unmeasured, never zero.

## Functional Requirements

- FR-01: Per-repository opt-in; explicit non-deployment declaration; configurable size,
  never-auto paths, daily cap and soak; one fix round plus one delta review.
- FR-02: Fresh head-bound checks, gate files, approvals, threads and bot evidence. Reject
  skipped/neutral required checks, author/bot approvals and outstanding changes requested.
- FR-03: Read both protection sources; either failure returns 2. Never override host rules.
- FR-04: Reuse obligations, scope, relevance, shell normalization, ports and state writers.
- FR-05: Serialize merge decisions and mutations; persist intent before the host mutation,
  reconcile uncertain outcomes through the watch, and retain evidence plus undo information.
- FR-06: Reserve trusted state and event namespaces for dedicated producers. Local records
  are coordination evidence, never proof of an owner approval or host protection override.
- FR-07: Watch base checks, revert and page on red, retain breaker until owner reset, and
  compare fully observed outcomes with the baseline.
- FR-08: All commands and reads follow 0 clean, 1 findings, 2 could not run, with reasons.

## Key Entities

- Merge decision: PR, item, head, gates, checks, approvals, protection and observation time.
- Merge journal: intent, accepted/merged state, actual merge commit, evidence and undo PR.
- Breaker: repository, reason, trip timestamp; persists beyond the day it tripped.
- Outcome: merged timestamp, complete observation window, reverts and same-line fixes.

## Assumptions

- PRs use canonical `owner/repo#number` or GitHub URL; a numeric PR is resolved only when
  a configured repository is unambiguous from cwd. Items link through their `pr` field.
- Item flags and cycle history use the existing day state and producer events; gate files
  are linted afresh for the linked item and full head. They are not owner authorization.
- Configured review bots must provide full-score and current-head evidence; an explicitly
  unconfigured bot is not treated as an installed bot that has not reviewed yet.
- All required checks, including human review gates, must pass for merging. The source
  ping gate excluded human-driven checks only to request review; that exclusion is unsafe
  for merging. No engagement-specific fallback check names are retained.
- `updated_at` is a conservative soak timestamp: unrelated PR activity may extend soak.
- Breaker reset is an owner config generation increment, not a CLI approval switch.
  The baseline note is owner-maintained and excluded from generic note writers.
- The mature cohort contains PRs merged 14 to 28 days ago; each outcome observes the first
  14 days after merge. Baseline is read from the owner's baseline note.
- Save each completed outcome once. Other polls read commit messages for reverts without
  fetching patches; monitoring ends at age 28 days, clearing expired observation errors.

## Success Criteria

Every acceptance case has an offline test, no refused/unknown decision calls merge,
post-merge failure remains disabled across day rollover, and the full suite passes.

## Deferred

General reporting and baseline collection belong to the outcome-metrics feature. Remote
owner veto delivery belongs to the control-plane feature; disabling config is available now.
