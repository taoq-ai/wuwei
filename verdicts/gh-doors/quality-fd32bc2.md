Verdict: FIX
Gate: quality
Item: gh-doors
PR: taoq-ai/wuwei#1108
Head: fd32bc2b11a23d71f5007e14e67b707f17bd5eaa
Confidence: medium
Breaking: no

## Findings
- [medium] cli/wuwei/guards.py:172 blocks: yes. Failure: the `_read` blank for `-` has no test. With `path != '-' and ` removed (fresh copy, whole tests/test_guards.py passes, 652 passed), a file named `-` in cwd holding a benign query makes `gh api graphql --input -` read that file, so `unread` is false and the call passes, while gh sends stdin, which can carry markPullRequestReadyForReview. A test with a file `-` in tmp_path and `gh api graphql --input -` (also `-F query=@-`) must expect a refusal.
- [low] cli/wuwei/guards.py:183 blocks: no. The `unread` line packs a walrus, a nested conditional and a continuation indent into one expression; a named helper (for example `_query_file(f, v)` returning the path or None) would read better. Same for the `fields |= {...} if alone and data else {}` line at 182.
- [low] cli/wuwei/guards.py:172 blocks: no. The trailing comment `# gh reads - as stdin` is the only statement of the rule; the line is over 120 columns.

## Probes
- Suite at head (pytest -q in a git archive copy): 1009 passed, 2 skipped.
- Red on main: head's tests/test_guards.py and routes.json on the main tree gave 37 failed, 972 passed, so the new tests and rows fail without the implementation.
- Runtime lines: summed `git show fd32bc2:<f>` over cli/wuwei/*.py gives 3000, exactly the budget; test_setup asserts <= 3000 and passes.
- Vendored copy: diff -r of cli/wuwei and .claude/wuwei/cli/wuwei differs only in __pycache__; test_the_vendored_plugin_matches passes.
- No em dash or emoji found by grep in specs/gh-doors, cli/wuwei/guards.py, tests/test_guards.py, docs/design.md (the grep for the emoji range errored on the code point class, the em dash grep ran clean; emoji check partly unmeasured).
- Spec artifacts present: spec.md, plan.md, tasks.md, analysis.md, checklists/requirements.md; routes.json rows each name their source.
- Mutants, each in a fresh copy of head with the vendored copy untouched, run with pytest -x:
  - merge `on('admin')` reverted to raw argv: killed by test_every_route_reads_as_recorded[--admin=true].
  - merge `on('auto')` reverted to raw argv: killed by test_merge_reads_auto_the_way_pflag_does[-st x --auto=T].
  - last-wins changed to first-wins: killed by test_merge_reads_auto_the_way_pflag_does[--auto=false --auto].
  - TRUE reduced to 'true': killed by routes row `--admin=1`.
  - graphql `unread` rule off: killed by routes row `gh api graphql --input q.json`.
  - `unread` ignoring `alone` (plain-call rule for --input): killed by test_a_graphql_query_wuwei_cannot_read_is_refused[--input q.json | cat].
  - `unread` dropping the `-F query=@` branch: killed by routes row `-F query=@-`.
  - `unread` dropping the --input branch: killed by routes row `--input q.json`.
  - `\u` decode removed: killed by test_a_graphql_input_file_has_its_query_read_for_door_mutations[mark].
  - whole-data query append removed: killed by the same test (plain and array forms).
  - `_read` blank for `-` removed: SURVIVED (re-run in a fresh copy: tests/test_guards.py 652 passed; a probe test with a file named `-` fails on the mutant and passes on head). See the blocking finding.
  - `repositories/` write rule off: killed by routes row `-X POST repositories/123/...requested_reviewers`.
  - `repositories/` rule case-sensitive: killed by test ... [-X DELETE /Repositories/123].
  - plain-words `alone` condition inverted: killed by test_a_draft_opens_before_its_gates_with_the_pr_standard_once.
  - removed segments clause: not a mutant to reverse; its cases (`| cat`, `cd sub &&`) are covered by test_a_graphql_query_wuwei_cannot_read_is_refused and pass.
Simplicity: none to delete. The `alone` check now rests on the plain-words regex alone (the segments clause is gone, as the promise asked); trust-boundary refusals stay.

## Residual risk
The `-` stdin blank is untested, so a later edit could reopen the stdin bypass when a file named `-` exists. Emoji check on the spec files is only partly measured.
