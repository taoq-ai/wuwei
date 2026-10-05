# Specification Analysis Report: 520-checks-venv

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against
`.specify/memory/constitution.md` and the code they name (`cli/wuwei/fast_checks.py`,
`adapters/checks/local.py`, `cli/wuwei/commands/build.py`, `cli/wuwei/commands/worktree.py`,
`cli/wuwei/commands/doctor.py`, `cli/wuwei/brief.py`, `cli/wuwei/workspace.py`).

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | Correctness risk | HIGH | spec Assumptions; plan Design 3 | Running the main worktree's interpreter in an item worktree can import the main worktree's code when the package is installed editable there (src layout), so a check could pass for code the item did not change. | Keep the issue's resolution order, record the interpreter on every relative-interpreter check so a gate can see it, and document in `configuration.md` (plan Design 7) and in the `worktree add` warning that `[checks] bootstrap` is the remedy. Fixing import paths is out of scope. | Resolved (documented) |
| I1 | Inconsistency | HIGH | first draft of spec root cause | The draft claimed the missing interpreter parks the item as an environment failure. `/bin/sh` prints `.venv/bin/python: No such file or directory` and the `[\w.-]+` pattern in `_environment` excludes `/`, so it is an ordinary failure fed back to the builder, which is why the builder improvises. | Root cause and US1 scenario 3 corrected; no change to `_environment` (the fallback removes the failure in the issue's case). | Resolved |
| A1 | Ambiguity | MEDIUM | issue Scope bullet 1 | "`[checks] python` overrides both" does not say which commands it applies to. | Applies to a relative interpreter whose file name starts with `python`; `node_modules/.bin` tools and bare `python3` are untouched (spec Assumptions, T003). | Resolved (assumption) |
| A2 | Ambiguity | MEDIUM | issue Scope bullet 1 | "repository-relative" for `[checks] python`. | Relative to the `[[repos]] path` (the main worktree), per repository (plan Design 2, T003). | Resolved (assumption) |
| A3 | Ambiguity | MEDIUM | issue Scope bullet 2 | Exit and posture of a failed bootstrap. | One warning line, exit 0, under every posture (#530: no new refusal); the next check measures (spec US3 scenario 2, T010). | Resolved (assumption) |
| C1 | Constitution | LOW | plan Design 4 | Core must not import `subprocess`; bootstrap runs a shell command. | Bootstrap goes through the existing checks port (`run(path, command)`), no new port method. | Resolved |
| S1 | Security | LOW | plan Design 4 | Bootstrap executes config text. | Same trust as `repos.fast_checks`, which the same port already executes; `.wuwei/config.toml` is owner-edited. The warning prints exit and reason only, not command output. | Accepted |
| T1 | Test fallout | LOW | plan What must not change | An unconditional `interpreter` key, doctor row or brief line would change exact-equality assertions (`tests/test_fast_checks.py:52`, `tests/test_doctor.py:295`). | All three stay conditional on a relative interpreter; T007 and T012 assert the unchanged cases. | Resolved |
| P1 | Performance | LOW | tasks T005, T006, T009 | Three tests spawn a real shell or a real repository. | Acceptable: one real smoke per boundary (checks port, worktree add); the helper table (T003) and T007 stay in-process. | Accepted |
| M1 | Merge | LOW | plan Design 1 | `CONFIG_CACHE_VERSION` is bumped by parallel items. | Take main's value plus one at merge. | Accepted |

## Coverage Summary

| Requirement | Has task? | Task IDs | Notes |
| --- | --- | --- | --- |
| FR-001 `[checks]` config | yes | T001, T002 | |
| FR-002 shared helper | yes | T003, T004 | |
| FR-003 run and record | yes | T005, T006, T007, T008 | issue acceptance 1 and 2 |
| FR-004 worktree add bootstrap or warn | yes | T009, T010, T011 | issue acceptance 3 |
| FR-005 doctor row | yes | T012, T013 | |
| FR-006 builder brief line | yes | T014, T015 | |
| FR-007 docs and template | yes | T002, T016, T017 | |
| SC-001 acceptance as tests | yes | T005, T006, T009 | |
| SC-002 no changed expectations | yes | T007, T012, T014, T018 | |
| SC-003 no new refusal | yes | T010, T018 | |

## Constitution Alignment

- I stdlib: `shlex`, `pathlib` only. Pass.
- II exits: port results unchanged; a bootstrap failure is a warning, never reported as a
  pass. Pass.
- III one function: resolution only in `fast_checks.interpreter`. Pass.
- IV test first: every implementation task follows its test task. Pass.
- V ponytail: one helper, conditional fields, no new module, adapter or state key. Pass.
- VII security and #530: no new refusal under any posture. Pass.

## Unmapped Tasks

None. T018 is the suite run.

## Metrics

- Requirements: 7 functional, 3 success criteria.
- Tasks: 18 (8 test, 7 implementation, 1 docs check, 1 docs, 1 verify).
- CRITICAL: 0. HIGH: 2, both resolved in the artifacts.

## Next Actions

Proceed to `speckit-implement`.
