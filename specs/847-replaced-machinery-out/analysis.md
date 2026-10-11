# Specification Analysis Report: 847-replaced-machinery-out

Artifacts read: spec.md, plan.md, tasks.md; `.specify/memory/constitution.md` (2.3.0); the #789
pass plan (owner constraints, "Process control kept", outward duties, lead calls); the #844
plan ("Modules this part replaces, and what part 23 then deletes"); the batch 8 review findings
(F1 to F9, G1 to G9); the code and tests at 71d3f06b.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| C1 | Hidden job | CRITICAL | `merge.poll` | Its only caller is the watch. It trips auto-merge and reverts on a red base and records the 14-day outcome the 5.6 escaped-defect metric reads. Deleting the watch would silently stop both. | Resolved: FR-009, Assumption 6; it runs from `next.run` with the listing refresh and from `report` (T004, T005). |
| C2 | Test harness | CRITICAL | `tests/conftest.py:22-29` | An autouse fixture imports `wuwei.heartbeat`; deleting the module fails every test. | Resolved: T001 deletes the fixture first. |
| H1 | Hidden job | HIGH | `commands/git_hook.install` | It also writes the worktree anchor `<git dir>/wuwei-workspace` that `workspace.worktree_workspace` and the records guard use to find the workspace from a worktree. | Resolved: `_anchor` writes it without hooks; `init --upgrade` rewrites it (FR-011, T010). |
| H2 | Hidden job | HIGH | `telemetry.step` | Only the watch sweep records telemetry weeks; the owner kept telemetry. | Resolved: `report` runs it (FR-010, Assumption 8). |
| H3 | Hidden job | HIGH | `scanner.trace_sweep` | Only the watch sweep runs it; the lead kept S2. | Resolved: `dispatch receive` and `close` run it (FR-010, Assumption 7). |
| H4 | Hidden reader | HIGH | `doctor.diagnose` | Doctor's day and guards rows are built on `heartbeat.measure`, and the heartbeat probes a write to `state.json`. | Resolved: FR-012; doctor runs two probes and the state probe targets `events.jsonl` (T006). |
| H5 | Hidden reader | HIGH | `sessions.export` | `current()` reads `WUWEI_SESSION_ID`, which only `export` puts into later Bash calls; the #844 list named `export` for deletion. | Resolved: `export` and `current` stay (FR-004). |
| H6 | (b) check | HIGH | `obligations` helpers | `merge.py` reads `_ledger`, `_replies`, `_visibility`, `_owner_login`: a merge with an unanswered review thread is refused. | Resolved: only `evaluate` and `sweep` go (FR-005, Assumption 3). |
| H7 | Hidden reader | HIGH | `commands/watch._remove` | `init --upgrade` uses it to remove the retired `listen` unit. | Resolved: the remover moves into `init.py` and also removes the watch and shepherd units (FR-011). |
| H8 | Owner constraint | HIGH | records floor | Deleting the whole "records guard" would let a seat write day records; a hand-written `state.json` would be read as a legacy day. | Resolved: only the snapshot name and the hint go; `days/*/state.json` stays protected (Assumption 11). |
| M1 | Latency | MEDIUM | `state._fold` | Without the cache every read folds the day log, also on the hook path. | Resolved by lead call B9(a): the cache stays, so a hook folds only the tail past its size; the hook latency tests hold. |
| M2 | Parallel work | MEDIUM | `state.py`, `tests/test_loop.py` | The batch 8 fix round edits the same functions (F4, F6 to F8). | Resolved: F4 to F8 stay with the cache (lead call B9(a)); rebased onto the fix round. |
| M3 | Metrics | MEDIUM | `telemetry.hook_latency_ms`, `metrics.session_age`, `planner_turns` | Their sources (heartbeat clock, `session.seen`, Stop rows) go. | Resolved: telemetry reads stored weeks and reports new ones unmeasured; the session figures go (Assumption 9); none is a 5.6 outcome. |
| M4 | Lost check | MEDIUM | pre-commit identity, pre-push fast checks | `git-hook` refused a commit with the wrong identity and a push without fast-check evidence. | Resolved: Assumption 15; `build next` holds the handoff on fast checks at HEAD and `pr raise` checks pushed identities. |
| L1 | Docs | LOW | `docs/site/*`, README, hero | Prose still names the deleted units. | Deferred to part 24's rewrite; this part edits only what a docs test forces. |
| L2 | Records | LOW | `guard.would_refuse` | Loses its `item` field with the claims. | Accepted: telemetry counts refusals by guard, not item. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 deletions | yes | T003, T007, T009, T011 |
| FR-002 watch helpers | yes | T007 |
| FR-003 headless shepherd | yes | T007 |
| FR-004 sessions | yes | T007 |
| FR-005 obligations | yes | T005 |
| FR-006 state | yes | T002, T003 |
| FR-007 texts | yes | T003, T007, T013 |
| FR-008 hooks | yes | T008, T009 |
| FR-009 merge poll | yes | T004, T005 |
| FR-010 trace sweep, telemetry | yes | T004, T005 |
| FR-011 anchor, upgrade | yes | T010, T011 |
| FR-012 doctor | yes | T006, T007 |
| FR-013 config | yes | T010, T011 |
| FR-014 docs, charter, spec | yes | T012 |

**Constitution alignment**: II (DAMAGED is exit 2), III (one writer, one reader of records),
IV (red tasks before each behaviour change), V (deletion), VII (records floor and edges kept).
The constitution's Constraints line on the watch is amended in T012.

**Metrics**: 14 functional requirements, 13 tasks, 100 percent covered. CRITICAL 0 open,
HIGH 0 open.
