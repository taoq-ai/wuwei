Verdict: PASS
Gate: quality
Item: vendored-drift
PR: taoq-ai/wuwei
Head: 8b188da0299289caf82c973235508077c7cdeeb0
Confidence: medium

## Findings
- [low] tests/test_setup.py:127 blocks: no. The `p.suffix != '.pyc'` clause is redundant with the `__pycache__` check for vendored output (vendor() ignores both); harmless, and it also covers a stray .pyc outside __pycache__.
- [low] tests/test_setup.py:134 blocks: no. `import tempfile` is inline in the helper; the module-level import convention is a style nit only.
- [low] tests/test_setup.py:156 blocks: no. The release-please test checks the config entry and version equality, not an actual simulated bump; a wrong jsonpath would pass. Acceptance 3 is covered only by configuration shape.

## Probes
- Full suite on a git-archive copy at the head: 292 passed. cli/wuwei is 3000 lines, within the limit, and the diff changes no runtime file.
- Re-vendor check: setup.vendor() into a fresh dir, then diff -r against .claude/wuwei, .claude/agents and the three skills (wuwei, wuwei-close, wuwei-plan, wuwei-watch): identical. The copied plugin.json says 1.2.1, same as the root (acceptance 4).
- Mutant: drop the `extra` set. test_the_drift_check_names_a_changed_vendored_file fails.
- Mutant: owned-path filter disabled. The same test fails.
- Mutant: compare only presence, not bytes. The same test fails.
- Mutant: __pycache__ and .pyc not ignored. The same test fails.
- Mutant: remove the .claude/wuwei plugin.json extra-files entry. test_release_please_bumps_the_vendored_plugin_version_with_the_root fails.
- Mutant: append a line to the vendored gh.py. test_the_vendored_plugin_matches_the_tree_it_was_copied_from fails, naming the file in its message (acceptance 1). A fresh vendor passes (acceptance 2).
- The tests do not mutate the real tree. The helper test builds its own tmp copy and covers changed, removed-upstream, missing, project-owned agent and skill, and pycache cases.
- ADR docs/adr/0001-cut-1.2.1-before-1068.md has context, decision, consequences and rollback, and agrees with the item. I did not check the PR #1072 and 2a306da references against the code host.
- Simplicity: none. The helper is small, reuses setup.vendor() and the stdlib, and adds no abstraction. `_files` and `vendored_drift` are each used by more than one test.

## Residual risk
Contributors must re-vendor on every change to cli/, charters/, agents/ or skills/. This is intended, and the failure message gives the fix command. Project-owned agents and skills outside the owned prefixes are intentionally ignored.
