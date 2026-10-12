# Specification Analysis Report: 887-pr-wait

Artifacts: spec.md, plan.md, tasks.md, constitution 2.4.0.

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| B1 | Constitution | HIGH | Constraints: "The plugin runs no long-running process" | A blocking command could read as a retired watch. | It is a bounded command (`--timeout`, default 3600) the planner starts in the background when `next` says so; no service, no unit, nothing survives the session. Constraint "the owner's session is never blocked" is met by `background`. Resolved. |
| B2 | Coverage | HIGH | spec FR-003 | A change landing between `next` and the first tick would enter the baseline and never wake anyone. | Baseline read from the current listing before the first refresh. Resolved (plan 2). |
| B3 | Ambiguity | MEDIUM | spec US2.1 | "One GraphQL request per tick" with several repositories. | One listing request per repository holding an owned PR; recorded under Assumptions with the upgrade path. Accepted. |
| B4 | Underspecification | MEDIUM | spec US2.3 | The refusal text is the only carrier of the reset time. | Parse `rate limit until HH:MM:SS UTC` (the #899 wording, `adapters/_http.py`); a reset more than 12 h behind means the next day. Resolved. |
| B5 | Consistency | MEDIUM | 906 A5 | The wake test must not re-fire on a launch that stays offered. | Keys are compared with the previous tick, so a standing step is not new; a step that leaves and comes back is. Resolved. |
| B6 | Tests | LOW | test_charters BLOCKING | New planner text must not read as blocking. | `then` says "in the background". Resolved. |

No CRITICAL finding. HIGH findings resolved.

Coverage: FR-001 T001/T007, FR-002 T001/T002, FR-003 T001, FR-004 T001/T003, FR-005 T005/T009.
