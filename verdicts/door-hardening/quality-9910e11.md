Verdict: PASS
Gate: quality
Item: door-hardening
PR: taoq-ai/wuwei
Head: 9910e11ee8edc50b36fa017538cc1c8fe3993498
Confidence: medium

## Findings
- [low] blocks: no. hook.door() matches guards.NETWORK whole (gh, curl, wget, nc, ssh, scp, http, https) while the promise and SECURITY.md name only curl, wget, ssh, scp, nc; a bare gh, http or https word in a command also fails closed when the guard raises. Wider than documented but still fail closed; align the SECURITY.md sentence or note it.
- [low] blocks: no. tests/test_hook.py: no test passes NotebookEdit or MultiEdit through door() or the ledger check; dropping NotebookEdit from DOORS['edit'] is caught only by the vendored-copy drift test, not by a behavior test. Pre-existing gap, now one table.

## Probes
- Baseline at the head (git archive copy): pytest 484 passed, 2 skipped. Runtime lines in cli/wuwei/*.py: 2941 (cap 3,000).
- Vendored copy: cli/wuwei and .claude/wuwei/cli identical (diff -r, ignoring pycache); test_the_vendored_plugin_matches_the_tree_it_was_copied_from passes and failed when I mutated only cli.
- Mutant, drop NotebookEdit from DOORS['edit']: only the vendored drift test fails (see low note).
- Mutant, drop enable_pr_auto_merge from DOORS['merge']: test_an_mcp_merge_goes_through_the_evidence_door fails.
- Mutant, empty DOORS['create']: test_the_mcp_create_route_meets_the_same_door fails.
- Mutant, _unwrap back to '=' not in a: test_irreversible_edges_are_denied[env /opt/a=b/git push origin main] fails.
- Mutant, remove quote and backslash stripping in door(): the g''it push case of the new fail-closed test fails.
- Mutant, remove the network match: test_an_error_inside_a_door_refuses_the_call[curl] fails. Mutant, drop the "/" from the program-word prefix: the /usr/bin/ssh case fails.
- Mutant, codex() moved back outside handle's try: test_an_apply_patch_that_writes_the_ledger_is_refused fails (the new malformed-patch test is also in the file). Mutant, drop apply_patch from door(): the malformed-patch test fails.
- Mutant, drop the mcp__ door rule: the mcp__github__merge_pull_request case fails.
- Shared table: grep of cli/wuwei shows the MCP suffixes and the edit tool names only in guards.DOORS; the new test reads hook.py source for any DOORS suffix and swaps the edit tuple with monkeypatch to prove door() reads the table.
- Acceptance: scenarios 1 to 5 each have a test that fails when reversed; scenario 6 holds (suite passes, 2941 lines). Fail-open cases (Read, Glob, git clone https) are tested.
Simplicity: none to delete; the table replaced the copied literals and the net is small. The network regex is rebuilt on each call, which is cheap and not worth a constant.

## Residual risk
Refusing every mcp__ call while the hook is broken is the recorded assumption. The wider NETWORK match is the only behavior beyond the promise.
