# Tasks: Deployment ban

## Setup

- [X] T001 Read design, constitution, hooks contracts and existing implementation; write specs/076-deploy-ban/spec.md and plan.md.

## US1: Refuse deployments in every profile

Independent test: in-process tables assert codes and named reasons across profiles.

- [X] T002 [US1] Add failing config and deployment table tests in tests/test_deploy.py, covering tools, wrappers, git refs, workflows, APIs, custom patterns, merges and unreadable evidence.
- [X] T003 [US1] Add validated deployment fields in cli/wuwei/workspace.py and document them in templates/workspace/config.toml.
- [X] T004 [US1] Extend protected command handling in cli/wuwei/shell.py and implement cli/wuwei/guards/deploy.py using registry ports.
- [X] T005 [US1] Update tests/test_hooks.py and tests/test_workspace.py for installed guard/defaults; verify hook translation in tests/test_deploy.py.

## US2: Install workspace deny rules

Independent test: initialize temporary workspaces with absent, existing, and invalid settings.

- [X] T006 [US2] Add failing permission installation, preservation and failure tests in tests/test_deploy.py.
- [X] T007 [US2] Merge local permissions atomically in cli/wuwei/commands/init.py using guard rules.

## Verification

- [X] T008 Run full suite, review bypass resistance, and inspect changed files for hygiene; record results in specs/076-deploy-ban/tasks.md.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008.
US2 depends on US1's static rule definitions. No parallel implementation is needed.
Deliver the complete issue; US1 is the minimum independently testable increment.

## Verification results

- Initial guard/config red run: 194 failures for missing guard/config support.
- Init red run: 10 failures for missing permissions and validation.
- Adversarial review regressions were reproduced before fixes; delta regressions
  cover wrapper-name custom rules and option values mistaken for repository flags.
- Initial implementation full suite: 1188 passed in 14.16s.
- git diff --check passed. All 12 changed/added files passed the em-dash, emoji,
  and machine-path scan. All work remains in the working tree.

## Review fixes

- [X] T009 Reproduce F1-F5 and feature-branch push failures with regression tables.
- [X] T010 Return clean outside workspaces; skip irrelevant commands before parsing;
  restrict mention/opaque checks to git/gh and merge the duplicated parser block (F1-F3, F7).
- [X] T011 Restrict init permissions to the reviewed unambiguous deploy list (F4).
- [X] T012 Add missing deploy verbs, aliases and container build publication checks;
  allow explicit unqualified feature branch pushes (F5, usability).
- [X] T013 Document owner/repo naming for merge_deploys and align spec/plan (F6).
- [X] T014 Run the full suite with the requested interpreter and inspect the final diff.

Review regression red run: 81 failed, 479 passed. Focused green run: 560 passed.
Final full suite with the requested interpreter: 1266 passed in 13.88s.
Final git diff --check passed. No commits or pushes; changes remain in the worktree.
