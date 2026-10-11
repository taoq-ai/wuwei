# Specification Analysis Report: 844-derived-next

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.1.0);
- the #789 pass plan (owner constraints, "Process control kept", "Batch 8 care", "Outward
  duties", the lead calls);
- `tests/test_loop.py` at b34f15a3, run: 22 passed, 9 xfailed;
- the code at 703b40de; the batch 5 and 6 specs; the batch 7 issues.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Coverage | CRITICAL | test_loop.py | Every xfail must pass and every passing test keep passing. Two passing tests encode today's shape: `test_614` reads a fix round opened as a side effect of `next`, and `test_729_an_owner_merge_row` expects a `pr` row before the owner decision. | Resolved. `test_614` resolves the pure offer (same assertion on the prompt); `test_729` expects the decision at once, which the oracle's `test_nothing_ready` requires anyway (spec Assumption 5). Both are stricter, not looser (T018). |
| A2 | Inconsistency | CRITICAL | FR-002, FR-004 | Overlaid facts read by a writer would be written back into the log (a derived park or `stale_verdicts` becoming a record). | Resolved. Writers fold without overlays (`_fold`); only readers get the overlaid view (plan.md, `state.py`; T002). |
| A3 | Scope | HIGH | issue inputs | The issue lists five inputs; approvals, owner answers, fix rounds and duty records exist only in the event log. | Resolved. The log is named the sixth input (spec Assumption 1); it is append-only and kept by the owner. |
| A4 | Risk | HIGH | Assumption 2 | Recomputing every phase from the world would rewrite the build loop and hundreds of fixtures. | Resolved by design: the loop's phase record is kept and the world overrides it on every recorded drift case; reviewer 2 is briefed to find a drift the overlays miss. |
| A5 | Ambiguity | HIGH | "pass at head" | A gate that passed before a fix round counts today at its old head. | Resolved literally (Assumption 3): passing gates re-read at the new head; the raise check tightens (FR-014). Cost named. |
| A6 | Dead end | HIGH | red checks at the cap | `open_fix` raises a ValueError at the cap, so `pr act` had no owner path. | Resolved. `pr act` parks with the cap reason and prints `plan resume`'s card; `next` offers it as the decision (T016). |
| A7 | Purity | HIGH | `next.step` | The loop test refuses subprocesses; `git worktree list` and the PR listing are calls. | Resolved. HEAD from files (Assumption 6); the listing is a cache refreshed only by `next.run` and WUWEI's own PR commands. |
| A8 | Dependency | HIGH | parts 16 to 21 | The part edits files batches 5 to 7 change. | Resolved. Every dependency is marked (spec Assumption 9, plan.md Batch 7 dependencies and Handoff); T000 checks the base. |
| A9 | Duplication | MEDIUM | part 20 | Part 20 may land a duty record and command. | Mitigated: reuse it; FR-010 shrinks (T000, T020). |
| A10 | Performance | MEDIUM | hook path | The fold parses the day log on a cache miss. | Mitigated: cache keyed by log size; SessionStart latency case in T022. |
| A11 | Two tables | MEDIUM | `derive.offers`, `dispatch.next_step` | Precedence could drift between them. | Mitigated: one test per verdict row runs both; `resolve` names a disagreement instead of looping. |
| A12 | Redaction | LOW | `_append_jsonl` | A recorded value holding a known secret would fold back redacted. | Mitigated: a fold test proves no state key holds one (T002). |
| A13 | Wording | LOW | spec, plan | No emojis, em-dashes, absolute local paths, client, repository or people's names. | Checked. |

No CRITICAL or HIGH finding is open.

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 patch on write | yes | T002, T003 |
| FR-002 fold and cache | yes | T002, T003, T006 |
| FR-003 lifecycle checks out | yes | T003 |
| FR-004 derive readers and overlays | yes | T007, T008, T011 |
| FR-005 next set | yes | T014, T015, T018 |
| FR-006 stale receipts, re-check all | yes | T009 |
| FR-007 cards | yes | T012, T016 |
| FR-008 launch_set | yes | T017 |
| FR-009 duties config | yes | T019, T020 |
| FR-010 duty records | yes | T019, T020 |
| FR-011 close waits | yes | T019, T020 |
| FR-012 depends_on | yes | T012, T013, T018 |
| FR-013 pulls port | yes | T008 |
| FR-014 raise at head | yes | T010 |
| FR-015 texts | yes | T023, T025 |

**Constitution alignment**: I, II, III, IV, V, VII hold (plan.md, Constitution Check). No
violation.

**Unmapped tasks**: T000, T001, T026 to T028 (base check, baseline, verification).
