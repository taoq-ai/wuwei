# Specification analysis: draft-raise

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | promise, create door | A draft create that also names reviewers is a draft and a review request | Resolved in Clarifications: it meets the create door as a non-draft does (gh `-r`, MCP `reviewers`) |
| A2 | Ambiguity | MEDIUM | promise, ready door | Is the flip held on a PR that is not a draft? | Resolved: no; the promise holds the flip and reviewer requests on a draft, and reviewer requests on a ready PR are outside |
| A3 | Ambiguity | LOW | promise, REST draft | Which draft spellings count | Resolved: a JSON true only, from `-F draft=true` or the top level of the `--input` object; checked against gh 2.89.0 |
| U1 | Underspecification | LOW | item assumption, MCP | A separate reviewer tool would join the check | Resolved: `request_copilot_review` exists in MCP v1.14.0 and joins the ready door |
| U2 | Underspecification | LOW | GraphQL | `requestReviews` would request reviewers on a draft around the door | Resolved: refused beside `markPullRequestReadyForReview`, recorded under Assumptions and Breaking |
| C1 | Coverage | LOW | `_draft` | Short clusters (`-fd`) are drafts to gh but held by the reader | Recorded in Clarifications: held, never passed; the refusal names `--draft` |
| C2 | Coverage | LOW | `_api` | A malformed `--input` body that starts with `{` raises | Recorded: the hook fails closed on that call; GitHub refuses such a body anyway; a list, text or stdin body is tested to pass a route with no door |
| I1 | Inconsistency | MEDIUM | plan, budget | The estimate was +25; the change is +37 | Within the cap (2,999 of 3,000); recorded in plan.md |
| I2 | Inconsistency | MEDIUM | charters/planner.md, charters/_gate.md, skills, evidence.md | Lines outside the promise's list still said the PR opens after the gates | Resolved: updated to the draft order, so no doc contradicts the doors |
| B1 | Inconsistency | HIGH | spec, Breaking | Routes that passed on main (`gh pr ready`, reviewer requests on drafts, two mutations) now meet a door | Resolved: declared breaking with migration notes, as doors-by-rest was |

No open finding above LOW: A1, A2, I1, I2 and B1 are resolved.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 draft create passes | yes | T002, T003, T006, T008, T016 | |
| FR-002 non-draft refused naming --draft | yes | T007, T008, T016 | |
| FR-003 flip to ready held on a draft | yes | T009, T010, T011, T017 | |
| FR-004 reviewer requests held on a draft | yes | T009, T012, T017 | |
| FR-005 GraphQL mutations refused | yes | T013, T017 | |
| FR-006 DOORS | yes | T012, T014, T017 | |
| FR-007 charters, docs, budget | yes | T018 to T023 | |

## Constitution alignment

Stdlib only, test first, no config key, no new evidence rule (the ready door reuses create_door),
runtime under 3,000 lines. No violation.

## Metrics

- Requirements: 7; tasks: 23; coverage 100 percent
- Critical issues: 0; high: 0 open
