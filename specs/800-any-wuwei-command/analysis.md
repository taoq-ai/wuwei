# Specification Analysis Report: 800-any-wuwei-command

Artifacts read: spec.md, plan.md, tasks.md, the constitution (1.5.0), AGENTS.md, the #789 pass
plan and the code at main (bfbf6a3). Every file and line in plan.md was checked against the code.

## Findings

| ID | Category | Severity | Location(s) | Summary | Resolution |
|---|---|---|---|---|---|
| C1 | Constitution | CRITICAL | constitution Workflow (invariant row per guard change); plan.md Constitution Check | This change edits a guard. Until #798 lands, the constitution asks for a 9.2 row and a `tests/test_invariants.py` case per guard change, and rows I8, I16, I36 test the deleted rule. | Resolved: T000 makes #798 a precondition (it deletes the bullet and the walk); spec Assumptions and plan.md say what to do if it has not merged. |
| C2 | Constitution | HIGH | constitution VII; spec FR-009 | The moved `plan set` checks refuse in a session in every posture, naming a host-terminal form. VII says below strict a guard is a warning or a card. | Resolved: these are owner records (5.10 spec skip, #678 owner merge hold), the records floor VII names; behaviour changes: the guard's text refusal goes, and the command asks the host y/N in every case (the environment is not trusted). These checks, and config set, integrity reconfirm and decide, now rest on the /dev/tty prompt, which a pty wrapper defeats; per design 9.1 it is a friction boundary, and the edges stay guarded by the code host, credentials and the merge policy. No pty guard (lead decision); see spec Assumptions. Recorded in spec Assumptions. |
| C3 | Constitution | HIGH | constitution preamble (design spec wins, conflicts are raised); design 9.2 I8, I16, I36 | The design spec rows describe guard behaviour this change deletes; only the owner amends it. | Resolved: #798 replaces the 9.2 table first (T000); otherwise the builder leaves the design spec and the PR body raises it (plan.md Constitution Check). |
| A1 | Coverage | HIGH | spec US3; plan unit table | The pass plan's PR 3 detail deletes the table with no move. Three rows were the only check on a real process error: `drafts approve` (outward send without the owner; `drafts.approve` skips the prompt below strict because the guard stood in front), `plan set spec=skipped` (spec before gates) and `plan set owner_merge=false` (merge outside policy; `test_plan_set_owner_merge` shows the command records a planner's release). | Resolved: FR-008 and FR-009, tasks T006 to T010 move each check into its command with a failing test first. |
| A2 | Inconsistency | HIGH | pass plan PR 3 detail ("delete ... _wuwei_action") vs plan.md | `_wuwei_action` is also used by `_write_targets` to exempt the CLI from the state-file write check. Deleting it would refuse CLI calls whose arguments name state files. | Resolved: plan.md keeps `_wuwei_action`, `_READERS`, `_INTERPRETER`; T002 pins the CLI-exempt and state-write cases. |
| A3 | Inconsistency | MEDIUM | pass plan PR 3 detail (RECORDS_FLOOR drops the owner-marker string) | The owner disposition marker refusal lives in `security.gh_outbound` and `guards/outward.py`, not in the owner table; removing the string from `RECORDS_FLOOR` would level a live refusal. | Resolved: not touched; spec Assumptions defer it to the edges part. |
| A4 | Coverage | MEDIUM | spec FR-006; plan init items | Older workspaces hold the guide block in `CLAUDE.md`, which every session reads. Deleting the writer alone leaves a stale reference to a deleted command and the owner-only list. | Resolved: `init --upgrade` removes the block (T013, T015); `doctor` reports it as a pending template change. |
| A5 | Underspecification | MEDIUM | plan Risks; `shell.reads` | Without the command sets, a CLI loop that fails to parse is no longer read-only in `shell.classify`, which the decision, verdict and commit guards consult. | Resolved: T005b names the guard test files to run; a failure not about a deleted unit is a code regression to fix, not a test to change. |
| A6 | Ambiguity | MEDIUM | tests/test_invariants.py corpus | Moving `_text`, `_cwd`, `_cd_target` to `shell.py` takes their reasons out of the wall lint corpus (it reads `guards/` plus `CALLED`). | Resolved: plan adds a `CALLED` row for `shell.py`; the floor `len(rows) > 200` stays (estimate about 230 after the deletion, 315 today). |
| A7 | Ambiguity | LOW | spec FR-008 | The draft card's Always answer records a `:text:` topic, so `drafts approve <id> --always` from a session was refused by the guard. | Kept as is: the command check mirrors the guard (`:send`, or `:edit` with `--edit`/`--file`). Not widened here. |
| A8 | Duplication | LOW | tests/test_docs.py guide assertions | Seven docs tests pin guide prose; #798 may delete some first. | Resolved: plan says skip a test #798 already removed. |
| A9 | Terminology | LOW | spec acceptance vs FR-009 | The issue acceptance says no subcommand is refused because of who runs it; FR-009 refuses two assignments in a session. | Resolved in spec Assumptions: the acceptance targets the verb table; FR-009 is an owner-answer requirement on two policy-relaxing values. |

## Coverage

| Requirement | Tasks |
|---|---|
| FR-001 | T001, T004b, T004c |
| FR-002 | T002, T004b |
| FR-003 | T005a, T005b |
| FR-004 | T011, T012 |
| FR-005 | T014, T016 |
| FR-006 | T013, T015 |
| FR-007 | T003, T004a |
| FR-008 | T006, T007 |
| FR-009 | T008, T009, T010 |
| FR-010 | T004c, T005b, T012, T016 |
| SC-001 | T017 |
| SC-002 | T019 |
| SC-003 | T018 |

Every task maps to a requirement; every requirement has a task.

## Metrics

- Requirements: 10 functional, 3 success criteria; coverage 100 percent.
- Findings: 1 CRITICAL, 4 HIGH, 3 MEDIUM, 3 LOW; every CRITICAL and HIGH is resolved in the
  artifacts.

## Next

Ready for `speckit-implement` once T000 holds.
