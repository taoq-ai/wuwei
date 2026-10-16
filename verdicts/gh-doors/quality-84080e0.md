Verdict: PASS
Gate: quality
Item: gh-doors
PR: taoq-ai/wuwei#1108
Head: 84080e0a7435293c7c02b090c48db56cfb248bcc
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:183 blocks: no. The `unread` and `fields |=` lines stay dense; a small helper would read better (carried from the previous round, not blocking).

## Probes
- Suite at head in a git archive copy: 1035 passed, 2 skipped, including test_the_runtime_reads_numbers_in_ascii_digits_only (the merged digit scan) and test_the_vendored_plugin_matches.
- The `path != '-' and ` mutant, re-run in a fresh copy of head: killed by test_a_file_named_dash_is_never_read_for_the_stdin_gh_reads (both `--input -` and `-F query=@-`); 2 failed, 658 passed in tests/test_guards.py.
- The mixed-case `GraphQL --input -` shape has a test case at tests/test_guards.py:1015 and a routes.json row (line 136).
- Runtime lines: summed over git ls-tree of cli/wuwei/*.py at 84080e0 gives 2996, within the 3000 budget.
- Vendored copy: diff -rq of cli/wuwei and .claude/wuwei/cli/wuwei shows only __pycache__ differences.
- Delta since fd32bc2 is test, spec, doc and the merged ascii-digits change; guards.py logic for the gh-doors clauses is unchanged, so my earlier mutant results (all other mutants killed) stand.
Simplicity: none to delete; the guards are trust-boundary validation.

## Residual risk
The earlier mutants were not re-run on the merged tree beyond the dash one; the full suite passes and the guards.py clauses are unchanged. Emoji grep on spec files remains partly unmeasured.
