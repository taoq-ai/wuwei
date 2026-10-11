# Specification Analysis Report: 831-owner-answers-in-session

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.0.0);
- the #789 pass plan, its owner constraints and its "Process control kept" table;
- the plans of parts 9, 10 and 11 in this batch;
- the code and tests in the worktree, with part 9 in progress.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| X1 | Cross-part | CRITICAL | part 11 plan (deploy guard, `next` merge row, charters, constitution VII amendment) | Part 11 is built after this part and its plan writes "the owner runs it in a host terminal" in several places. The new terminal-text test refuses them, and the owner rule forbids them. | Resolved in plan.md, Handoff: part 11 routes the owner merge and owner-only publishing through `needs_owner` and words its amendment as "on the owner's recorded Owner step answer". Risks asks the lead to brief part 11's builder. |
| S1 | Security | HIGH | FR-002, US2 | Any session can run `bin/wuwei hook PostToolUse` with a forged payload and record an answer the owner never gave. Card answers (#529, #800) already had this hole; with the terminal gone it is the only path. | Resolved: FR-005 refuses a Bash `wuwei hook` call in the state guard (records area, every posture); T004 and T005. The opaque-interpreter route stays outside the boundary, as design 9.1 already states (Assumption 4). |
| S2 | Security | HIGH | FR-001 | Reading answers from `state.json` session rows fails while state is unreadable, so `state recover` could never be answered. | Resolved: the helper reads today's `events.jsonl` (reserved `gate.asked`, protected file), and `record_gate` records Owner step answers before any state read (T002 `test_owner_answer_records_without_reading_state`). |
| S3 | Security | MEDIUM | Assumption 1 | Owner step answers count from any main session, not only the planner's. | Accepted: a main session's AskUserQuestion is answered by the owner; seats (`agent_id`) never count (T002). Gate and decision topics keep their planner-only rule. |
| P1 | Process control | HIGH | FR-003 | Each `_host_confirm` call stops a real process error (an unconfirmed owner step). Deleting the prompt without a replacement would open it. | Resolved: every call site in code that stays moves to `needs_owner` (plan.md table), refusing without the answer; one red-then-green test per site (T006, T007). |
| C1 | Constitution | MEDIUM | VII | VII: "Under strict, refusals stay" and "an owner-only action runs only on the owner's recorded answer". The Owner step card counts under strict. | Consistent: under strict the step still refuses without the answer; the recorded answer is what VII names. No amendment needed. |
| T1 | Test | MEDIUM | T006 | Two card tests pin the terminal prompt (`..._prompts_as_today`, `..._ignores_the_card_and_prompts`). | Resolved: deleted together with the terminal path they cover; new cases pin the card under every posture, so no behaviour loses its test (SC-004). |
| T2 | Test | MEDIUM | FR-007 | A LEFT list could hide new terminal texts. | Mitigated: rows are (file, substring, part), each must still match (stale rows fail), and the deleting part removes its row. |
| L1 | Test | LOW | `tests/test_reasons.py` lints | Rewritten texts must still name a next step, keep pronouns out of seat-facing text and "the owner" out of person-facing text. | Plan.md states the rule; T009 runs `tests/test_reasons.py`. |
| D1 | Docs | LOW | design 9.1, 4.6 lines | The strict and merge lines that mention a host terminal sit in text part 11 rewrites. | Left to part 11 (Handoff); 9.1 gains the Owner answers paragraph here. |
| A1 | Scope | LOW | `doctor --fix --widget` | With the Owner step card, the doctor widget path asks two cards for one fix batch. | Accepted; the command count is cut in part 24, which can drop `--widget`. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 helper | yes | T002, T003 |
| FR-002 hook records, citation skip | yes | T002, T003 |
| FR-003 call sites | yes | T006, T007 |
| FR-004 config set branches | yes | T006, T007 |
| FR-005 Bash `wuwei hook` refused | yes | T004, T005 |
| FR-006 texts | yes | T008, T009 |
| FR-007 terminal-text test | yes | T008 |
| FR-008 charter, design, agents | yes | T010, T011 |

**Metrics**: 8 functional requirements, 12 tasks, 0 unresolved CRITICAL or HIGH findings.
