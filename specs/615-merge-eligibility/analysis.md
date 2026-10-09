# Specification Analysis Report: 615-merge-eligibility

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 4.6, 4.7 and 9.2, docs/site/configuration.md, issue #615 (the owner's report of
2026-10-09) and the code on `main` at 082e1c6.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Design contract | HIGH | design 4.6, eligibility | `size_exclude` changes what "the diff" means for `max_changed_lines`. | Resolved by scope: the default is `[]` (no change unless the owner sets it in `config.toml`, a record only the owner writes), never-auto paths and the completeness checks still read every file. The conflict is raised with proposed 4.6 text and a 9.2 row, not edited here, since the design spec is amended only by its owner. |
| A2 | Security | HIGH | plan add replan | Backfilling evidence from day state could launder a cleared risk flag into evidence. | Resolved: item flags are producer-owned (`state set` refuses `items.<id>.flags`; only `plan approve` and `plan add` write them), the backfill runs only when no day holds evidence for the item, and `item_evidence` still requires every recorded flag set and the state flags to be all False. A True flag in state is recorded True and still blocks. |
| A3 | Security | MEDIUM | interview `deploys` | Recommending `Merges do not deploy` could lead the owner to clear a deploying repository. | Resolved: recommended only when calibration measured no deploy workflow, deny command or never-auto path; unmeasured or missing facts recommend `Merges deploy` (constitution II). A repository answer writes nothing on its card: it lands only through the setup digest or `config promote` in a host terminal. |
| A4 | Owner control | MEDIUM | `repos.merge.size_exclude` | A seat widening the exclusion would lift the size rule. | Resolved by existing rules: `config.toml` is a record (records floor); `config set` from a session needs the owner's card answer. No new guard. |
| A5 | Invariants | MEDIUM | design 9.2, `tests/test_invariants.py` | The constitution asks for a 9.2 row for a changed eligibility rule; `test_table_matches_the_checks` pins the test table to the design table, which only the owner edits. | Raised in the spec with the proposed I25 row; the regression tests in `tests/test_merge.py` (excluded never-auto file refused, completeness on unfiltered sums, rename counted) carry the check until the owner adds the row. |
| A6 | Ordering | LOW | `merge.check` | The size rule moves after the path loop, so a never-auto refusal now shows before a size refusal. | Accepted: both are refusals with the same owner route; path validation must run before `matched` reads the paths. |
| A7 | False negative | LOW | interview recommendation | A deploy file calibration flags (instruction-like or unsafe) contributes no fact, so its repository may get `Merges do not deploy` first. | Accepted: the same rule governs calibration's `merge_deploys` proposal, the digest names the flagged file, and the owner answers. |
| A8 | Readers | LOW | `why`, metrics, telemetry | A replan `plan.added` row is one more row for the item. | Accepted: metrics and telemetry keep the first start (`setdefault`, oldest first); `why` shows one more `queued` line. |
| A9 | Tests | LOW | tests pinning the table | The id list, the terminal reply sequence, the answer count and setup's `first` change. | Updated deliberately in T005; doctor, upgrade and next tests derive their counts from `QUESTIONS`. |
| A10 | Tracker hygiene | LOW | constitution Workflow | Three bugs in one feature. | The issue asks for one feature; each bug has its own phase and tests. |

No CRITICAL finding. HIGH findings A1 and A2 are resolved above.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T001, T003 |
| FR-002 | T002, T003 |
| FR-003 | T001, T002, T003 |
| FR-004 | T002, T003 |
| FR-005 | T004, T005 |
| FR-006 | T004, T005 |
| FR-007 | T006, T007 |
| FR-008 | T008 |
