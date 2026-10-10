# Specification Analysis Report: 599-decide-card

Artifacts: spec.md, plan.md, tasks.md, against `.specify/memory/constitution.md`, the item's
Deliver and Acceptance sections and the orchestrator notes.

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Coverage | HIGH | spec FR-003, FR-004, FR-005, Assumptions | The item asks for `--card <hash>` in the widget's record command. The widget is printed before the owner answers, so the hash cannot be an answer hash. | Resolved: the widget carries `card_hash(Question, Options)` of the record as it stands; a hash from an edited record never records (I30); an id-only command without `--card` (every widget printed before this change) still passes through the state fallback. |
| A2 | Coverage | HIGH | spec Assumptions, Deferred | The item lists `consolidate` answers among the paths that use `owner_confirm`. They do not: `memory forget` is owner-only in `protect_state` and `consolidation.forget` always asks y/N. A card path needs a hook change, which the notes rule out ("nothing new on a hook path"). | Resolved: recorded under Assumptions and Deferred as its own follow-up issue; the shared fix covers every path that does read a card (`decide`, `mcp decide`, `decision undo`, `config set --from-card`, `calibrate --answer`); `drafts approve` already reads the planner from state. |
| A3 | Inconsistency | MEDIUM | plan "Test updates", tasks T005 | pytest's captured stdin is not a terminal, so existing tests that meant "no variable is a host terminal" while a topic was asked now resolve the planner. | Resolved: T005 names the one known test and the rule for others (give a terminal stdin where a host terminal is meant; never change the rule). |
| A4 | Security | MEDIUM | spec FR-001, US2.3 | The state fallback treats any caller without a terminal as the planner for asked topics. | Accepted: the hook refuses record commands from seats and non-planner sessions before the CLI runs (I8), pinned again by T010; the environment variable it replaces was already settable by any same-uid process (spec 9.1 ceiling). Strict yields no topics. |
| A5 | Coverage | MEDIUM | plan item 5, guide sentence | `wuwei mcp decide` gets no `--card`. | Accepted: `wuwei decide` routes the pending MCP decision to `mcp.decide` with the card hash, and the rerun rule names `wuwei decide D-n "<label>" --card <hash>`; the state fallback fixes `mcp decide` without the flag. |
| A6 | Constitution | LOW | plan item 9 | The design spec is amended only by its owner. | Accepted: the constitution Workflow (#530) requires the 9.2 row for a changed decision rule; only the row is added. |
| A7 | Ambiguity | LOW | spec Assumptions | `config set` without `--from-card` keeps `current()`; in a session without the variable it reaches the host prompt instead of the card hint. | Accepted: the hook refuses it for the planner in every posture without a card; out of this item's path. |
| A8 | Coordination | LOW | plan, design row id | Parallel items may also add an invariant row. | Accepted: the builder takes the next free id at merge time (spec Assumptions). |

## Coverage

| Requirement or scenario | Tasks |
| --- | --- |
| FR-001 | T003, T005 |
| FR-002 | T001, T004, T005 |
| FR-003 | T001, T002, T006, T007 |
| FR-004 | T006, T007 |
| FR-005 | T008, T009 |
| FR-006 | T011, T012 |
| FR-007 | T013, T014 |
| FR-008 | T015, T016 |
| FR-009 | T017, T018 |
| Issue acceptance 1 (no variable, no TTY, records) | T001 |
| Issue acceptance 2 (TTY, not asked, prompt) | T002 |
| Issue acceptance 3 (strict) | T006 (c), I8 unchanged, T017 |
| Issue acceptance 4 (seat refused by the hook) | T010 |
| Issue acceptance 5 (doctor row) | T013, T014 |

Every behaviour has a test task before its implementation task (T001 to T004 before T005,
T006 before T007, T008 before T009, T011 before T012, T013 before T014, T015 before T016,
T017 before T018). T010 pins an existing rule and has no implementation task. No refusal is
added below strict (#530): `--card` without a confirmation is the existing decline exit, and
the doctor row is a warn. The planner's next step after a failed confirmation is one command
(#551). The hook path gains one bool on an event it already writes.

CRITICAL: 0. HIGH: 2, both resolved in the artifacts. MEDIUM: 3. LOW: 3.
