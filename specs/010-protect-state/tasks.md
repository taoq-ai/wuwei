# Tasks: Protect state files and the workspace root

## Setup

- [X] T001 Read hook contracts and shell implementation; write spec.md and plan.md in specs/010-protect-state/.

## User Story 1: Preserve CLI ownership of state

Independent test: direct and shell state writes block, ordinary writes and reads pass.

- [X] T002 [US1] Add failing normalization tables for output targets and dynamic writer bypasses in tests/test_shell.py.
- [X] T003 [US1] Preserve output targets and reject opaque writer forms in cli/wuwei/shell.py.
- [X] T004 [US1] Add failing Write/Edit and Bash writer tables for exits 0/1/2 in tests/test_protect_state.py.
- [X] T005 [US1] Implement protected path and writer checks in cli/wuwei/guards/protect_state.py.

## User Story 2: Keep the persistent shell in the workspace

Independent test: external top-level cd blocks; subshell and internal cd pass.

- [X] T006 [US2] Add failing directory, environment, symlink and missing-workspace tables in tests/test_protect_state.py.
- [X] T007 [US2] Implement workspace containment checks in cli/wuwei/guards/protect_state.py.

## Integration and validation

- [X] T008 Add and run discovered-guard hook replay tests in tests/test_protect_state.py.
- [X] T009 Run full tests, inspect diff and hygiene, record results in specs/010-protect-state/tasks.md.

## Dependencies and strategy

Execute sequentially: T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009.
US1 is the first independently useful increment. Both stories share the guard file;
no parallel implementation is planned. Extension hooks are skipped as instructed.

## Validation record

- Shell metadata/bypass tests: 26 expected failures before changes; 267 shell tests passed afterward.
- File and writer guards: 95 expected missing-module failures; 362 focused tests passed after implementation.
- Directory containment and integration: 19 expected failures, plus 3 isolated alias failures; 403 focused tests passed after implementation.
- Adversarial cases: 6 environment/xargs/interpreter bypass failures and 2 program expansion failures reproduced before fixes.
- Initial full suite: 1106 passed, one obsolete empty-registry assertion failed. Isolated that assertion with the existing plugin fixture.
- Final full suite: `1119 passed in 17.07s`.
- Hygiene: all 10 authored files passed checks for machine paths, emojis and em-dashes; `git diff --check` passed.
- Hook benchmark reported p95 CPU 49.54 ms and wall 67.41 ms. The existing CPU-based assertion passed; wall time exceeds the design target on this run.

## Adversarial review fixes

- [X] T010 [F1] Scope both guards to a workspace and restrict resolved protected paths to day state/events and archive contents.
- [X] T011 [F2] Compare path names with casefold and check existing hard-link aliases with samefile.
- [X] T012 [F3] Preserve zsh >! and >>! redirect targets in shell normalization.
- [X] T013 [F4] Default to refusing protected operands, except known readers and source-only copies; register MultiEdit and NotebookEdit.
- [X] T014 [F5, F7] Remove shared interpreter rejection and the guard's generic is_opaque call; only relevant parse failures block.
- [X] T015 [F6] Contain pushd, refuse unknown persistent popd destinations, and treat the final pipeline stage as persistent.
- [X] T016 Run the full regression suite and hook CPU latency budget after review fixes.

Review validation so far: new review regression tables produced 57 failures before fixes.
The destination-directory move regression separately failed before its fix. Existing
expectations for reserved basenames, irrelevant parse failures, and absent workspaces
were updated to the reviewed policy.

Final review validation:

- Six additional reader-option, equals-path, and directory-stack regressions failed
  before their fixes, alongside the separately reproduced destination-directory move.
- A full run exceeded the hook CPU budget at 50.78 ms. Defer workspace configuration
  and shell imports until the guard is in scope; the final benchmark passed at p95
  CPU 33.89 ms and wall 43.14 ms over 60 runs.
- Supplied-interpreter full suite: `1201 passed in 14.69s`.
- `git diff --check` and authored-file hygiene checks passed. No commit was made.

## Second adversarial review fixes

- [X] T017 [F8] Add outside-workspace target tables; check resolved file/Bash targets independently of cwd and override, retain known-root hard-link scanning, and gate only directory containment.
- [X] T018 [F9] Add dynamic writer and glob tables; preserve typed nonliteral path errors, recognize dynamic write parse failures, and expand parsed writer glob operands relative to cwd.
- [X] T019 [F10] Add container-removal and git apply tables; refuse rm/mv of day containers and git apply within .wuwei; document the outside-cwd patch residual.
- [X] T020 [Second anchor] Test non-root overwrite denial and permissions across repeated/failing writes; use atomic state mode 0444 and restore event mode 0444 under the existing append lock.
- [X] T021 Update spec.md, plan.md and contracts/guards.md to match the reviewed scope and independent file-mode anchor.
- [X] T022 Run the supplied-interpreter full suite, review the delta, and check diff hygiene.

Second review red/green evidence:

- F8: 43 expected failures before fixes; 273 guard tests passed afterward.
- F9: 81 expected failures before fixes; 628 guard/parser tests passed afterward.
- F10: 8 expected failures before fixes; 363 guard tests passed afterward.
- Second anchor: plain non-root overwrites failed to raise before the fix; separate
  pre-rename mode assertion also failed before the state change. All 68 writer tests
  passed afterward, including unchanged lock, append and sync contracts.
- Delta review caught git/gh variable names masking nonliteral redirection errors.
  Six new regressions failed before prioritizing the typed error; all 644 parser/guard
  tests passed afterward. Reviewer confirmed no remaining blocking delta findings.
- Final supplied-interpreter full suite: `1353 passed in 13.42s`.
- Hook p95: CPU 43.82 ms, wall 64.19 ms over 60 runs. The existing CPU assertion passed;
  measured wall time exceeded the design target on this run.
- `git diff --check` and authored-file hygiene passed for all 12 changed/untracked files.
  No commit was made.

## Final adversarial review fixes

- [X] T023 [F11] Preserve glob-only writer arguments, expand protected matches in the guard, and scope opaque writes according to the ordinary-command examples. Record the workspace-relevance assumption in spec.md.
- [X] T024 [F12] Refuse removal/move of .wuwei, workspace roots and ancestors; keep ordinary directory operations and move destinations allowed.
- [X] T025 [F13] Refuse git apply at or inside a workspace including git -C, and check chmod/chown containers in directories mode.
- [X] T026 Run the supplied-interpreter full suite and check diff hygiene.

Final review red/green evidence:

- F11: 42 new failures before changes; 686 parser/guard tests passed afterward.
  Hook subprocess cases cover /tmp, this worktree and a workspace root.
  Earlier F9 expectations outside workspaces now follow the reviewed relevance policy;
  protected glob matches return refusal rather than a parser error.
- F12: 14 expected failures before changes; 705 parser/guard tests passed afterward.
- F13: 11 expected failures before changes, then two Git reader/empty -C regressions
  caught and fixed with failing tests; 725 parser/guard tests passed afterward.
- Supplied-interpreter full suite: `1434 passed in 14.29s`.
- Hook p95 over 60 runs: CPU 30.44 ms, wall 37.04 ms.
- `git diff --check` and hygiene checks passed for all 12 changed/untracked files.
  No commit was made.
