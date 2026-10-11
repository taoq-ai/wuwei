# Specification Analysis Report: 833-notes-voice-out

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.1.0);
- the #789 pass plan (owner constraints, "Process control kept", outward duties, #831 handoff);
- the code and tests at 9639dd8, with part 12's plan applied.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| K1 | Owner keep | CRITICAL | FR-002 | The owner keeps the retro to charter loop. Trimming `promotion._apply` could break charter `add`, `patch` or the drop. | Resolved. Only note and voice branches go; the kept tests (charter add, patch, drop, ledger, changelog, configured changelog, dirty changelog) stay, and SC-003 adds an end-to-end landing (T003, T004). |
| K2 | Owner keep | CRITICAL | FR-003 | Deleting `goals edit` without a replacement would leave the gate's goals unrecorded, and `memory/goals.md` is kept. | Resolved. `plan approve` writes them through `save_goals` before its state write (T001, T002). |
| K3 | Owner keep | HIGH | design 5.6 | The baseline the outcome metrics read is a note at `memory/notes/baseline.md`. Deleting notes could delete or unprotect it. | Resolved. The path, the template file and the protect rule stay; promote refuses it as a target (Assumption 3). |
| P1 | Process control | HIGH | `note --fix` | `wuwei note --fix` is the seat finding intake `next` reads (#646). Deleting the `note` command would break the item loop. | Resolved. Only `note add` goes (Assumption 1). |
| C1 | Owner constraint | HIGH | LEFT rows | `next` `THEN['goals']`, `memory forget` help and the consolidation prompt name a host terminal. | Resolved. All three units go with this part; T009 deletes the rows and adds none. |
| D1 | Data | MEDIUM | RETIRED_FILES | Deleting owner-written `voice.md`, notes or digests on upgrade would lose owner content. | Resolved. Only the CLI-written `memory/forget.json` is retired (Assumption 4). |
| G1 | Graph | MEDIUM | `graph.py` | The register reads `voice.sources`; removing `[voice]` without the view breaks `graph.sync`. | Resolved in plan: the view goes with the table; `tests/test_graph.py` runs (T007). |
| A1 | Growth | LOW | archive | Days no longer archive. | Accepted (Assumption 5, Risks). |
| D2 | Constitution | LOW | design spec edits | The design spec is amended only by its owner. | Resolved: part of the owner-approved #789 pass. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 modules, commands, skill, template deleted | yes | T002, T006, T007, T008, T010 |
| FR-002 promotion keeps the charter loop | yes | T003, T004 |
| FR-003 approve records the goals | yes | T001, T002 |
| FR-004 memory.py trimmed | yes | T005, T006 |
| FR-005 memory, note, goals commands | yes | T002, T006 |
| FR-006 outward without voice | yes | T007 |
| FR-007 close, doctor, RETIRED | yes | T006, T008 |
| FR-008 texts, LEFT rows, docs, agents | yes | T009 to T011 |

**Constitution Alignment**: I, II, III and V hold. IV holds (red tests T001, T003, T005, T008).
VII holds: the records protection stays; no publishing edge changes.

**Unmapped Tasks**: none.

**Metrics**: 8 requirements, 12 tasks, coverage 100%. 2 critical and 3 high findings, all
resolved.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to implement.
