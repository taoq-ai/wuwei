# Specification Analysis Report: 867-github-fanout

Artifacts read: spec.md, plan.md, tasks.md; the constitution (II fail closed, III one
behaviour one function, IV test first, V simplicity, VII security); `adapters/_http.py`,
`adapters/code_host/github.py`, `adapters/tracker/github.py`, `cli/wuwei/commands/doctor.py`,
`cli/wuwei/commands/config.py`, `cli/wuwei/commands/why.py`, `cli/wuwei/plan.py`,
`cli/wuwei/discovery.py`, `cli/wuwei/derive.py`, `cli/wuwei/merge.py`, every caller of
`open_prs` (only `plan._owner_prs`).

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Root cause | HIGH | spec Root causes 1 | Printing another bucket's counter is the field defect; changing only the wording would keep it. | Resolved: `gh_limit` reads the failed call's own resource (FR-001); T001 covers REST and GraphQL. |
| A2 | Scope | HIGH | spec Assumptions, issue comment 3 | The owner lists PRs requesting the owner's review as needed; the spec does not fetch them. | Resolved as an assumption: nothing reads review requests today; fetching them would add a candidate source the issue does not ask for. The owner's own PRs (the only rows read) move server-side (FR-006). |
| A3 | Correctness | HIGH | FR-005 | A cached protection verdict could hide the owner's fix or a config change. | Resolved: only clean reads are kept; findings and errors are read again; rows are recomputed from the cached data against the current config, so a changed `review_required_checks` still shows. |
| A4 | Security | MEDIUM | FR-005 | A cached file could claim protection. | Accepted: the day directory is the CLI's (seats' writes are refused by the records guard); the merge policy and the shepherd read protection live; the cache feeds a diagnostic only. |
| A5 | Correctness | MEDIUM | FR-006 | GitHub's search index lags a few seconds to minutes behind a new PR. | Accepted: plan propose runs at the morning gate; a PR opened in the last minutes is adopted at the next propose or claimed by hand. |
| A6 | Coupling | MEDIUM | FR-003 | An environment variable as the doctor-to-adapter channel. | Accepted: the adapters already read their wait outside the CLI's call arguments (workspace config); one variable checked in `cap` is the shortest path, and doctor restores it. |
| A7 | Coverage | LOW | SC-001 | `why` needs no change; T006 is green on arrival. | Accepted: it pins the measured fact so a later network read fails a test. |
| A9 | Correctness | HIGH | FR-006, review F1 | Owner handles hold chat IDs; GitHub search answers 422 for them and the sweep went unmeasured. | Resolved: only login-shaped handles and `outbound.owner.code_host` are searched (T013). |
| A10 | Root cause | HIGH | FR-008, review residual | `rate_limit` can disagree with the failed response (field case). | Resolved: the failed read's own headers via `--include`; `rate_limit` only when none come back; the calls that cannot expose headers are listed in Assumptions (T014). |
| A8 | Scope | LOW | spec Deferred | `merge.poll` per-round core cost is not addressed. | Deferred to a follow-up issue, named in the spec. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 resource named | yes | T001, T007 |
| FR-002 secondary wording | yes | T001, T007 |
| FR-003 doctor never waits | yes | T002, T003, T008 |
| FR-004 config check waiting | yes | T003, T008 |
| FR-005 protection once a day | yes | T004, T009 |
| FR-006 open_prs search | yes | T005, T010 |
| FR-007 why local | yes | T006 |
| FR-008 headers of the failed response | yes | T014 |

**Constitution alignment**: II (incomplete search and rate limits fail closed), III (one
function per behaviour), IV (T001 to T005 red first), V (no cache module, one plain file),
VII (exact allowlist pattern for the search endpoint, login shape checked).

**Metrics**: 8 functional requirements, 16 tasks, 100 percent covered. CRITICAL 0 open, HIGH 0
open.
