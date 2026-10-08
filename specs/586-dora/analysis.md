# Specification Analysis Report: 586-dora

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 5.6, 5.13 and 6.6, issue #586 (read from the public issue page; no issue
file or orchestrator notes were in the pipeline directory) and the code on `main` at 7370a2f.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Performance / contract | HIGH | plan Telemetry, design 5.13 budget | The first draft read deployments for every computed week on every daily run (current week plus up to four unfinalised weeks, per repository), which can pass the 10 second budget; a run over budget records `telemetry.skipped` and repeats the same work the next day, so telemetry could stall for good. | Resolved: `dora(..., host=False)` for any non-final week; the code host is read only when a week is finalised, once per week. The current week's deploy keys stay `unmeasured`. Spec FR-008 and US4, plan Telemetry and T004/T010 updated. |
| A2 | Test isolation | HIGH | plan "Tests never reach gh" | About forty test files build a report, retro, digest or close with the default `code_host = "github"` and repositories configured; each would spawn `gh` for deployments, against the constitution's "tests never need network or the real tool". | Resolved: one autouse fixture `unread_deploys` in `tests/conftest.py`, shaped like `rehearsed_undo`, replaces `metrics._deploys` and returns the real helper; `tests/test_dora.py` and the deploy cases of `tests/test_telemetry.py` restore it (T005, T010). |
| A3 | Inconsistency | HIGH | `README.md:42`, `tests/test_docs.py` `test_readme_landing_marks_follow_main` | README marks #586 as landing; once `specs/586-dora/` exists the #561 test fails, and removing the only landing sentence trips its `assert sentences`. | Resolved: README swaps the landing line for a DORA feature bullet; the test's `assert sentences` applies only when a landing sentence exists, every other check kept (plan Docs, T012/T013). |
| A4 | Design contract | MEDIUM | design 5.13 "reads the day directories" | The deploy keys are the one telemetry metric read from the code host, not from day records. | Accepted: the issue puts the four keys in the weekly signal set; the read runs in the watch sweep (never a hook), once per final week, and a failure is `unmeasured`. The 5.13 rows say so (T013). |
| A5 | Versioning | MEDIUM | telemetry `SCHEMA` | 5.13 says changing a key or definition raises `schema`. Five keys are added; none changes. | Accepted: `SCHEMA` stays 1 (Assumptions). A collector still on the old module rejects the new keys as unknown and the week retries until it is redeployed with the bundled `telemetry.py`; bumping the schema instead would reject every older plugin's weeks. |
| A6 | Definition | MEDIUM | spec FR-002 | DORA's lead time runs from commit to production; WUWEI's runs from the item's plan approval (`cycle_minutes`). | Accepted: the issue names `cycle_minutes` as the source; the table's source column says so. |
| A7 | Measurement | MEDIUM | plan code host port | Deployments count in every environment at creation, without statuses, so preview deployments can inflate frequency. | Accepted with a `ponytail:` comment naming the upgrade (filter `production_environment` or read statuses). |
| A8 | Performance | MEDIUM | adapter `deployments` | The read paginates the repository's whole deployment history. | Accepted: bounded by the adapter's 30 second `gh` timeout; a timeout is a failed row with the reason, never a crash, and telemetry reads it once per final week. |
| A9 | Exit semantics | LOW | spec FR-006 vs US3 | `wuwei dora` exits 2 when the code host failed, while the report and retro show the same failed row and still succeed. | Accepted: the command is the check (fail closed, never clean when unmeasured by error); the report and retro are readings that already name the reason. |
| A10 | Coverage | LOW | spec FR-010 | "No new config key or event kind" has no dedicated test. | Accepted: T003 asserts no `adapter: none` event; the plan adds no key; the review checks the diff. |
| A11 | Scope | LOW | issue Pace and Tier | Per-pace and per-tier lead time and failure rate could be read as a new split. | Accepted (Assumptions): `by_pace` and `cycle_by_tier` already carry them; the issue asks for the table beside them. |
| A12 | Input | LOW | pipeline | No issue file and no `586-full.md` notes existed. | Recorded under Assumptions; the issue text came from the public issue page. |
| A13 | Invariants | LOW | constitution, design 9.2 | `tests/test_invariants.py` exists on the base. | No guard or decision rule is added or changed, so no 9.2 row; no refusal is added under any posture (#530). |

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001, FR-002, FR-005 | T003, T005 |
| FR-003 | T001, T002 |
| FR-004 | T004, T005 |
| FR-006, FR-007 | T006, T007 |
| US3 (report, retro, digest) | T008, T009 |
| FR-008 | T010, T011 |
| FR-009 | T012, T013 |
| FR-010 | T003 (no event), review |
| Issue acceptance 1 | T003, T006 |
| Issue acceptance 2 | T001, T004 |
| Issue acceptance 3 | T008 |

Every behaviour has a test task ordered before its implementation task.

## Constitution alignment

- I: stdlib only; `gh` only through the code host adapter, inside the existing allowlist.
- II: three-state exits for `wuwei dora`; unmeasured never zero; adapter fails closed.
- III: one computing function (`metrics.dora`), one renderer (`report.dora_lines`).
- IV: test-first task order throughout.
- V: reuses `cycles`, `_escaped`, `_pages`, `record_none`, the fake and the replay helper.
- VII and #530: no new refusal, no allowlist change.
- #551: `wuwei dora` is a read-only report; no planner action changes.

## Metrics

- Requirements: 10 functional, 4 user stories; tasks: 14.
- CRITICAL: 0. HIGH: 3, all resolved in the artifacts. MEDIUM: 5 accepted. LOW: 5.
