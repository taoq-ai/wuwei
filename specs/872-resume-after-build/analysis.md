# Specification Analysis Report: 872-resume-after-build

Artifacts read: spec.md, plan.md, tasks.md; the constitution (III one behaviour one function,
IV test first, V simplicity); design spec section 9.2 (the `plan resume` card: Yes resumes the
item); `cli/wuwei/plan.py` `resume`, `cli/wuwei/commands/build.py` `complete_checks` and
`next_action`, `cli/wuwei/derive.py` `offers`, `cli/wuwei/dispatch.py` `resolve_offer`,
`cli/wuwei/state.py` `_validate`.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Root cause | HIGH | spec Root cause | A fix in `next` or `build next` alone would hide the dropped move and leave `plan resume` restoring a phase the build already left. | Resolved: the resume applies the move the build loop dropped, through the same function (FR-001, FR-003). |
| A2 | Coverage | HIGH | FR-002 | The issue asks that park then resume work in every phase, not only this one. | Resolved: T001 is a table over planned, implement (ready, check, done), gate, fix (check, done). |
| A3 | Concurrency | MEDIUM | plan.md `resume` | The checks can finish between the resume's read and its write. | Resolved: the build status is read inside the state write; if the checks finish after the resume, `complete_checks` sees `implement` or `fix` and moves the item itself. The end head is read from the worktree, which the checks do not change. |
| A4 | Recovery | MEDIUM | spec Assumptions | Items already stuck on 0.28.0 are not healed by the code. | Accepted: park and resume them again; no migration (Principle V). |
| A5 | Owner decision | LOW | design 9.2 | Moving to `gate` on resume could skip an owner card. | Resolved: `plan resume` already takes the owner's Yes; the gate round after it is the one the resume grants (`dispatch._resumed`), as for an item resumed at the gate today. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 advance a done build on resume | yes | T001, T002, T004 |
| FR-002 every other phase unchanged | yes | T001 |
| FR-003 one move function | yes | T003 |

**Constitution alignment**: III (one move function for the build loop and the resume), IV
(tests red first), V (two runtime files, no new state).

**Metrics**: 3 functional requirements, 5 tasks, 100 percent covered. CRITICAL 0 open, HIGH 0
open.
