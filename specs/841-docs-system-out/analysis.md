# Specification Analysis Report: 841-docs-system-out

Artifacts read: spec.md, plan.md, tasks.md; the constitution (2.2.0); the #789 pass plan; the
part 16 plan and working tree; the code and tests at d60253b8.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| H1 | Hidden reader | CRITICAL | `specmode.governed` | It imports `docs._sections`; deleting `docs.py` first breaks `wuwei spec analysis` and the brief spec block. | Resolved: T001 moves the helper before any deletion. |
| S1 | Scope | HIGH | MCP `docs` channel | The word "docs" also names the MCP Notion and Confluence channel of the outward lint and the owner's own pages (#838). Deleting it would change outward sends. | Resolved: Assumption 2 keeps it; SC-001's grep names only docs-system symbols. |
| S2 | Security | HIGH | `env.py` | Removing the Notion and Confluence credential names would stop scrubbing them from seats. | Resolved: Assumption 3 keeps them. |
| C1 | Config | MEDIUM | `workspace.py` | The `adapters.docs` mirror and the cache version. | Plan names both; RETIRED gets both keys. |
| T1 | Test | MEDIUM | `tests/test_brief.py` | Two live-read tests use the docs brief helper. | Ported to a plain helper, not deleted. |

**Coverage**: FR-001 T001, T004; FR-002 T002, T003; FR-003 T003, T004; FR-004 T005; FR-005 T006;
FR-006 T006, T007. 6 requirements, 7 tasks, 100%.

**Constitution Alignment**: I to VII hold; IV via T002 and T005.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to implement.
