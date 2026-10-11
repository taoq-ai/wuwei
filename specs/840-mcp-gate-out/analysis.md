# Specification Analysis Report: 840-mcp-gate-out

Artifacts read: spec.md, plan.md, tasks.md; `.specify/memory/constitution.md` (2.2.0); the #789
pass plan (owner constraints, "Process control kept", lead calls); the part 14, 16 and 17 plans;
the code and tests at d60253b8 and part 16's working tree.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| O1 | Order | CRITICAL | FR-005 to FR-007 | At d60253b8, `drafts.py` and `commands/outbound.py` still call `_host_confirm`, `owner_confirm`, `gate_topics` and the D-n library; deleting them before part 16 breaks those modules. | Resolved: plan.md marks each such edit [after 16]; tasks.md starts Phase 3 with a grep that must show only `mcp.py` and `decision.py` callers. |
| K1 | Owner constraint | CRITICAL | FR-004, US3 | The owner kept the ZIRAN findings the security gate reads. `adapters/scanner/ziran.py` holds both the kept `audit`, `gate`, `traces` and the deleted `mcp`. | Resolved: only `mcp`, `_rollback` and `_mcp_report` go; T001 records the kept tests green before any edit and T009 reruns them. |
| C1 | Hidden reader | HIGH | FR-008 | `scanner.mcp.plugins_file` is read by `integrity.registered`, `specmode.present` and doctor, not only by the gate. Retiring the whole table would break plugin discovery. | Resolved: the key stays (Assumption 2); four siblings retire. |
| T1 | Test kept | HIGH | `tests/test_next.py` | The once-row rule test used the `mcp` row; deleting it with the row would lose the rule. | Resolved: the test moves to `pr-flow` (T002). |
| P1 | Records | MEDIUM | `guards/protect_state.py` | Dropping the `('ziran',)` tail would let a seat overwrite old registry files. | Resolved: the tail stays; only the hint text (a LEFT row) goes. |
| T2 | Telemetry | MEDIUM | `telemetry.AREAS`, `OWNER_KINDS` | Telemetry is kept by the owner and validates stored weeks. | Resolved: unchanged (Assumption 3). |
| D1 | Docs | LOW | `docs/site/security.md:66-68` | The lead noted a duplicated paragraph; part 17 also edits it. | Plan says leave one copy without `mcp check`. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 deletions | yes | T003 |
| FR-002 launch paths | yes | T003 |
| FR-003 readers | yes | T002, T003 |
| FR-004 scanner kept | yes | T001, T009 |
| FR-005 no host confirm | yes | T004, T005 |
| FR-006 decision.py slice | yes | T005 |
| FR-007 record_gate, sessions, doctor | yes | T004, T005 |
| FR-008 retired keys | yes | T006, T007 |
| FR-009 docs and governance | yes | T008, T009 |
| FR-010 LEFT rows | yes | T004, T005 |

**Constitution Alignment**: I, II, III, V hold. IV holds (red tests T002, T004, T006). VII
holds: the security sentinel keeps S4; no publishing edge changes.

**Unmapped Tasks**: none. **Metrics**: 10 requirements, 9 tasks, coverage 100%; 2 critical and
2 high findings, all resolved.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to implement after parts 16 and
17 are on the branch.
