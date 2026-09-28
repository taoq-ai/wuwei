# Tasks: Commit and push guard

## Setup

- [X] T001 Read source harness, existing ports and hook contracts; write spec.md and plan.md in specs/008-commit-push-guard/.

## US1: Identity

- [X] T002 [US1] Add source-harness identity/order tables in tests/test_commit_push.py and observe failure.
- [X] T003 [US1] Implement shared identity policy in cli/wuwei/guards/commit_push.py and repository identity config in cli/wuwei/workspace.py.

## US2: Checked feature pushes

- [X] T004 [US2] Add normalized command, push and evidence tables in tests/test_commit_push.py and VCS replay tests in tests/test_vcs_guard.py; observe failures.
- [X] T005 [US2] Implement Bash guard, VCS context operations, registry and fake contracts in cli/wuwei/guards/commit_push.py, adapters/vcs/git.py, cli/wuwei/registry.py and tests/fakes/vcs.py.

## US3: Git hooks

- [X] T006 [US3] Add Git-hook policy, executable integration and installation tests in tests/test_git_hook.py; observe failures.
- [X] T007 [US3] Implement cli/wuwei/commands/git_hook.py and connect workspace.create_worktree to hook installation after the pure VCS worktree call.

## Verification

- [X] T008 Update templates/workspace/config.toml and specs/008-commit-push-guard/contracts/guard.md with configuration, evidence and port contracts.
- [X] T009 Run the full test suite, review the diff and check changed files for prohibited characters and local paths.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009.
All three stories are required for this issue. Tests precede each implementation.
Independent table rows can execute in parallel; source edits are sequential.

## Adversarial fix round

- [X] T010 Add failing regressions for F1/F2; restore shared shell code/tests and scope guard parsing to relevant commands inside workspaces.
- [X] T011 Add failing regressions for F3; cover all commit-creating verbs and read every pushed commit through the VCS allowlist at both anchors.
- [X] T012 Add failing regressions for F4/F7 and runtime lookup; move installation to the core caller, mark created worktrees and set only worktree-local hooksPath. Verify owner/sibling isolation in a local clone.
- [X] T013 Add failing regressions for F6/F8/F9 and ordinary command forms; protect hooksPath, require explicit pushes and default branches, and use native Git ref/boolean validation.
- [X] T014 Record F5 as a known dependency on #11 and runtime-pointer upgrades as #40 work; align spec, plan and port contracts.
- [X] T015 Run the complete required pytest command and inspect the final diff.

## Second adversarial fix round

- [X] T016 Add failing F10 obfuscation regressions, then introduce shared shell.mentions for relevance without changing normalization behavior.
- [X] T017 Add failing F11 compound-command regressions, then refuse push after commit creation while retaining add/commit support.
- [X] T018 Add failing F12 regressions, then protect worktreeConfig, core/extensions section mutations and hook-pointer removal.
- [X] T019 Add failing F14 native-hook and HEAD-port regressions, then read HEAD and its identities directly through vcs.head.
- [X] T020 Record F13 as deferred: narrowing relevance to command position needs coordinated parser changes beyond a small fix.
- [X] T021 Run the complete required pytest command and inspect the final diff.

## Post-rebase fix round

- [X] T022 Resolve Git, shell and hook-test conflict markers while retaining main's typed parser errors, glob/redirect behavior, outward/verdict lint and SHA resolution, plus the branch's shared relevance and pushed-range reads.
- [X] T023 Add failing unrelated-substitution regressions, narrow shared relevance, and update outward test configuration for the required default branch.
- [X] T024 Add failing F5 CLI-forgery and both-anchor push regressions; reserve fast_checks and add a dedicated recorder with checks port adapters, derived SHA/exit evidence and failed-rerun invalidation tests.
- [X] T025 Update spec, plan, contracts and template; retain F13 as an accepted false positive under Assumptions.
- [X] T026 Run the complete required pytest command and inspect the final diff without changing git state.

## Validation history

- Each correctness fix followed failing regression tests before implementation.
- Shared normalization behavior and existing test_shell.py are unchanged; shell.py now also exposes mentions.
- No commit, push or gh command was run.
- Previous fix round, required interpreter: 1153 passed in 13.89s.
- Second round, required interpreter, full suite: 1226 passed in 14.00s.
- Post-rebase round, required interpreter, full suite: 2254 passed in 19.02s.
- Final git diff --check and changed-file whitespace/character checks passed.
