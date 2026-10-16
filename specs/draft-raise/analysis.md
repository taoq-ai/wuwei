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
| C1 | Coverage | LOW | `_draft` | Short clusters (`-fd`) were drafts to gh but held by the reader | Resolved in the fix round: one pflag reader unpacks clusters; 96 argument lists agree with pflag |
| C2 | Coverage | LOW | `_api` | A malformed `--input` body that starts with `{` raises | Recorded: the hook fails closed on that call; GitHub refuses such a body anyway; a list, text or stdin body is tested to pass a route with no door |
| I1 | Inconsistency | MEDIUM | plan, budget | The estimate was +25; the change is +37 | Within the cap (2,999 of 3,000); recorded in plan.md |
| I2 | Inconsistency | MEDIUM | charters/planner.md, charters/_gate.md, skills, evidence.md | Lines outside the promise's list still said the PR opens after the gates | Resolved: updated to the draft order, so no doc contradicts the doors |
| B1 | Inconsistency | HIGH | spec, Breaking | Routes that passed on main (`gh pr ready`, reviewer requests on drafts, two mutations) now meet a door | Resolved: declared breaking with migration notes, as doors-by-rest was |

| S1 | Inconsistency | HIGH | `_repo_number` | The PR door read the first bare number and missed `--repo=` and `-R<value>`, so `gh pr edit -t 5 7 --add-reviewer bob` checked PR 5 (security gate, real gh) | Resolved: the PR is the first positional and the repository the last `-R` as pflag reads them; the merge door shares it |
| S2 | Inconsistency | HIGH | `_api`, `--input` | A draft was read from the hook's copy of the `--input` file, which `cd` or `cp` before gh can change | Resolved: an `--input` draft counts only when gh is the command's only segment |
| S3 | Inconsistency | HIGH | `_api`, endpoint | `//` and percent-escapes missed the ready and merge routes | Resolved: escapes decoded and slashes collapsed before matching |
| Q1 | Coverage | MEDIUM | `_draft` | No test held a cluster that names a reviewer (`-dr=bob`, `-drbob`) or an unknown flag in a cluster (`-dx`) | Resolved: in NOT_DRAFTS; an `--input` draft of `"false"` or `1` pinned |

| S4 | Inconsistency | HIGH | `_api`, endpoint | `.` segments still missed the ready and merge routes (arch and security at 76a738a) | Resolved: empty and `.` segments drop after decoding; a write through `..` is refused |
| S5 | Inconsistency | HIGH | `--input` draft | A wrapper (`env -C`, `sudo -D`) or a shell expansion (`~`, `$`, globs) hands gh another file than the hook reads | Resolved: an `--input` draft needs gh as the first word of a one-segment command with no such character |
| Q2 | Coverage | MEDIUM | `_repo_number` | The URL's repository and the last `-R` were untested | Resolved: unit tests and corpus routes for ready and merge |

No open finding above LOW: A1, A2, I1, I2, B1, S1 to S5, Q1 and Q2 are resolved.

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
