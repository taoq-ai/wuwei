# Specification Analysis Report: #845 window budget

Artifacts read: `spec.md`, `plan.md`, `tasks.md`, `research.md`, the constitution (2.4.0).
Run on 2026-10-12, after `tasks.md` was written; findings marked resolved were fixed in the
artifacts before this report was saved.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|---|---|---|---|---|---|
| H1 | Constitution (hook latency #346, Simplicity) | HIGH | plan.md Design, CAP per runtime | `dispatch.host` runs inside the PreToolUse Agent guard (`guards/agent_launch.py`). Computing windows there would scan up to eight day logs on every Agent launch. | Resolved: `host(..., runtimes=False)`; only `launch_set` asks for runtimes. Dropping the `tokens_per_day` block also removes today's past-day scan from the guard. FR-005 and T018 updated. |
| H2 | Coverage (FR-009) | HIGH | plan.md Routing | A builder routed to Codex had no launch path: before this feature a Codex builder reached the planner as an Agent launch the guard refuses, so routing would have stalled. | Resolved in the plan: `resolve_offer` turns a non-Claude builder launch into a background `wuwei build <item> <brief> <worktree>` run; `run_loop` and the guard read the build record's runtime (T024 to T029). |
| M1 | Inconsistency | MEDIUM | spec FR-004 vs plan Room | The spec said `until` is the reset "of the window that gives 0"; the plan took the latest of several spent windows. | Resolved: FR-004 says the latest reset among windows at 0. |
| M2 | Coverage | MEDIUM | tasks T028 | Unbriefed planned items (`start` entries) were not tested against the routed runtime's room. | Resolved: T028 adds the case. |
| M3 | Underspecification | MEDIUM | spec Assumptions | Claude gate sentinels and Codex seats record no tokens, so the estimate undercounts their use. | Accepted and recorded: readings correct for it where exposed; Codex tokens from the rollout are Deferred. A `ponytail:` comment in `windows` names the ceiling. |
| M4 | Ambiguity | MEDIUM | spec FR-003 | A reading with no budget bounds nothing below 100 percent, so the fit guarantee needs a budget. | Accepted: clarified in the spec (Clarifications) and to be said in `docs/site/configuration.md` (T032). Capacity inference from a reading is Deferred: early in a window it would hold all work on little evidence. |
| L1 | Terminology | LOW | all | "room", "reading", "until" used consistently; "window budget" and "per-window token budget" both appear. | No change: same meaning. |
| L2 | Ambiguity | LOW | spec FR-007 | "a command that exits shortly after" the reset. | The plan fixes it: `sleep max(60, seconds to reset + 60)`. |
| L3 | Risk | LOW | plan Risks | The Codex rollout format is undocumented. | Reader returns no reading on any parse failure (T012). |

No CRITICAL finding. Both HIGH findings are resolved in the artifacts.

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 config keys | T001, T003 |
| FR-002 seat.usage runtime | T004, T005, T006, T007 |
| FR-003 room per runtime | T016, T017 |
| FR-004 runtime room and until | T016, T017 |
| FR-005 CAP per runtime | T018, T019 |
| FR-006 held launches | T028, T029 |
| FR-007 timed wait | T030, T031 |
| FR-008 alternate routing | T020 to T025, T028, T029 |
| FR-009 non-Claude builder launch | T024 to T029 |
| FR-010 status line readings | T008 to T011 |
| FR-011 Codex readings | T012 to T015 |
| FR-012 upgrade | T002, T003 |
| FR-013 running seats untouched | T028 |

Every functional requirement has at least one test task before its implementation task.
Every task maps to a requirement or to docs and verification (T032 to T035).

## Constitution alignment

- I stdlib only: met.
- II three-state exits: no new exit; damaged inputs degrade to "unmeasured" in the capacity
  text, never to clean, and never block a launch, as the day budget did.
- III one behaviour, one function: `windows`, `route`, `save_windows`, each with one test.
- IV test first: tasks order every test before its code.
- V simplicity: no new module, event kind or command; one cache file like `prs.json`.
- VII security: the Codex thread id is validated before it names a file; no guard loosens.
- Constraints: the timed wait runs in the background, so the owner's session is never
  blocked; no charter or skill tells the planner to wait.

## Metrics

- Functional requirements: 13; tasks: 35; requirements with tests: 13 of 13.
- Ambiguities open: 0; duplications: 0; CRITICAL: 0; HIGH open: 0.
