# Specification Analysis Report: 602-tracker-gh-auth

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 5.11 and 9.1, docs/site/security.md, issue #602 (the owner's request of 2026-10-09) and
the code on `main` at 6627e24 (v0.23.0).

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Design contract | HIGH | design 5.11 adapter table | The table names `GITHUB_TRACKER_TOKEN, a fine-grained token for issues and projects only` as the github credential; a gh login path departs from it. | Resolved by scope: the token stays the default and wins when set; the gh path is an owner opt-in. The conflict is raised (spec, Design spec conflict) with proposed row text for the owner, not edited here, since the design spec is amended only by its owner. |
| A2 | Security | HIGH | spec Clarifications, seats | The first reading left open whether seats inherit the broad gh login. | Resolved: seats reach tracker operations only through the CLI and the outward policy, as with the token; nothing is added to `.wuwei/env` or a seat environment; gh's store is already reachable by any process running as the owner (9.1), so an owner-side-only gate would be a refusal without a guarantee. The trade-off (least privilege lost on the tracker path) is documented in adapters.md (T010). |
| A3 | Security | MEDIUM | plan `_gh` | gh's stderr can carry private text. | Resolved: only the exit code, an `(HTTP nnn)` status and a fixed hint are reported (FR-003, T005). |
| A4 | Owner control | MEDIUM | `tracker.auth` | A seat switching the key on would widen the credential. | Resolved by existing rules: `config set` from a session needs the owner's card answer and `config.toml` is a record (records floor). No new guard. |
| A5 | Performance | LOW | plan `_query` | The gh path loads `config.toml` on each GraphQL call (two or three per operation). | Accepted: milliseconds against a network call; the token path does not load it unless the token is unset. |
| A6 | False positives | LOW | `env.malformed` | A legitimate token could contain a flagged character. | Accepted: only whitespace, a path-like start and shell characters are flagged; GitHub, Linear, Slack, Notion and Atlassian tokens use none of them. URL, email, site and channel credentials are not checked. |
| A7 | Posture | LOW | security.md, strict | Strict describes workspaces with shared credentials, where the broad login is least welcome. | Accepted: documented as "keep the token"; no new finding or refusal (#530 keeps new walls out of observe and guarded, and a strict-only finding would be a new rule the request did not ask for). |
| A8 | Tracker hygiene | LOW | constitution Workflow | The issue was filed late: creation was refused to this session at first (403). | Filed as #602; the feature directory carries that number. |
| A9 | Invariants | LOW | design 9.2 | No guard or decision rule changes. | No 9.2 row. |

No CRITICAL finding. HIGH findings A1 and A2 are resolved above.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T005, T006 |
| FR-002 | T005, T006 |
| FR-003 | T005, T006 |
| FR-004 | T001, T002 |
| FR-005 | T003, T004 |
| FR-006 | T007 to T010 |
