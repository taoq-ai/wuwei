# Specification Analysis Report: 839-edges-exact-argv

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.2.0) and design spec 4.1, 4.5, 4.6, 4.7, 9.1, 9.2;
- the #789 pass plan (owner constraints, "Process control kept", the #831 handoff, the B5 lead
  call, the lead's note on the duplicated docs paragraph);
- part 16's spec and plan (`specs/838-outward-allowlist/`, batch 5 branch);
- the code and tests at d60253b8.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| P1 | Process control | CRITICAL | US1.1, Assumption 3 | Refusing every `gh pr merge` without running `merge.check` must not block the one legitimate merge path. | Resolved. `bin/wuwei merge` runs `gh` as a CLI subprocess through the code-host port, never through the Bash tool, so no hook sees it. The refusal names it. |
| P2 | Floor | CRITICAL | FR-007, US1.9 | Folding three modules into one must keep merge, approve, admin, branch protection, deploy and outward send on the floor and keep force push and PR raise off it. | Resolved. `MERGE` reason prefixes floor the first four from `check_bash`; `FLOOR` holds `edges.check_deploy` and `edges.check_send`; T003 and T008 assert both settings per edge. |
| A1 | Acceptance | HIGH | issue "logged with enforce off", constitution VII | Read literally, every edge would log with enforce off, which would lower the floor. | Resolved (Assumption 1): the floor wins; floor edges assert the block, force push and PR raise assert the log. |
| A2 | Scope | HIGH | issue deploy list, design 4.7 | The issue names `deploy.deny` and workflow argv; 4.7 names more. | Resolved (Assumption 2): 4.7's list stays, by exact argv; only the parse machinery and the code-host PR lookup go. |
| R1 | Records floor | HIGH | US2.3, Assumption 6 | The state-file guard stops refusing an unparsed call that names a state file. | Accepted and documented: the issue rules out parse refusals; parsed writes stay refused; state files are 0444 with the CLI as their only writer; part 23 replaces the records guards. |
| R2 | Process control | HIGH | plan unit table | Push to the default branch loses its Claude hook refusal. | Resolved for this part: the native pre-push hook (`commit_push.push_check`) and the protected base branch still refuse it. Handoff to part 23, which deletes `wuwei git-hook`. |
| R3 | Records floor | HIGH | Assumption 5 | Deleting `guards/pr.py` would drop the `gh` body canary and marker scan. | Resolved: `edges.check_bash` calls `security.gh_outbound` for each `gh` text write; the canary rows move to `tests/test_edges.py` (T003). |
| D1 | Dependency | HIGH | Assumption 11, T005 | Part 16 is not built yet; the final name and shape of `check_send` are unknown here. | Resolved: the move follows part 16's code as merged, keeps its tests, and the floor key follows the new home. |
| H1 | Heartbeat | HIGH | Edge Cases | The watch heartbeat's `git push --force origin main` probe must still be refused. | Resolved: force push is an edge; heartbeat refusals are always enforced; T003 adds the row. |
| C1 | Constitution | MEDIUM | II | "Exit 2 blocks exactly like exit 1" conflicts with a logged unreadable call (already true for `UNPARSED` since part 15). | Resolved by T019: II names the one exception. |
| T1 | Tests | MEDIUM | `tests/test_invariants.py` | The reason corpus asserts more than 200 reasons; this part deletes many. | Resolved (T016): the count follows the code; the wall check is unchanged, so no test is loosened. |
| T2 | Tests | MEDIUM | `tests/test_hooks.py` import map | `edges` loads on every PreToolUse for `check_send`, so the Write row of the import-map test has no Bash-only module left. | Resolved: the row goes with the modules it covered; the Bash path imports lazily (plan.md, Imports). |
| L1 | Latency | MEDIUM | design 10.6 | A Bash call now loads one module instead of three and never runs the lenient walk; a Write loads `edges` too. | Accepted: fewer modules and less parsing on Bash; the latency benchmark stays the gate. |
| B1 | Body files | MEDIUM | `security.gh_outbound` | An unreadable `--body-file` still exits 2 (blocks with enforce on). It is a records read, not a parse. | Accepted; the canary scan is unchanged. |
| M1 | Telemetry | MEDIUM | `telemetry.GUARDS` | The pin follows `MODULES`; stored weeks name `commit_push`, `deploy`, `pr`. | Resolved: `RETIRED_GUARDS` in `INNER` (plan.md). |
| S1 | Ceiling | LOW | Edge Cases | Quoted `$( )`, backticks, scripts, aliases and built names reach an edge unrefused. | Accepted (Assumption 8, design 9.1); `ponytail:` comment in `segments`. |
| D2 | Docs | LOW | docs/site | Stale guard text in `reference.md` and `daily.md`. | Deferred to part 24; the triplicated `security.md` paragraph is fixed here (lead's note). |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 edges module | yes | T003, T004, T005 |
| FR-002 exact argv, relevance, scope | yes | T003, T004 |
| FR-003 unreadable logged | yes | T003, T009, T010 |
| FR-004 modules leave guards | yes | T001, T002, T004, T007 |
| FR-005 shell deletions | yes | T010, T015 |
| FR-006 hook | yes | T009, T010 |
| FR-007 floor | yes | T003, T008 |
| FR-008 integrity | yes | T012, T013 |
| FR-009 other shell callers | yes | T009, T010 |
| FR-010 governance and docs | yes | T017, T018, T019 |
| US5 launch contract | yes | T014 |

**Constitution Alignment Issues**: II, resolved by T019. VII unchanged (the floor keeps its
members).

**Unmapped tasks**: none (T006, T011, T015 and T020 serve FR-004, FR-005 and the sweep).

**Metrics**: 10 functional requirements, 5 user stories, 20 tasks, no open CRITICAL or HIGH.
