Verdict: PASS
Gate: quality
Item: 1161
PR: taoq-ai/wuwei#1167
Head: cc6d07fed440f8ac2afdda66818c5f26675f69b4
Confidence: high
Breaking: no
Supersedes: .wuwei/verdicts/1161/quality-bb26ee7.md

## Findings
- [low] blocks: no. The PR body says the mutants were applied "to both cli/wuwei and .claude/wuwei/cli/wuwei" and killed by the named behavioural tests. The tests import cli/wuwei, so a mutant in the vendored copy survives every behavioural test; it is killed only by tests/test_setup.py::test_the_vendored_plugin_matches_the_tree_it_was_copied_from (byte equality). The result is the same (the mutant cannot land), but the "Killed by" column is true for cli/wuwei only. Wording note.
- [low] blocks: no. Carried note, unchanged: `pr-acme__app-*` also matches `acme/app-extra` entries, which are removed only after a day, so no live entry is lost.
- [low] blocks: no. Carried note, unchanged: a cached compare answer keeps only `status` and `files`; an uncached call also returns `commits`. No caller reads `commits` today.

## Probes
- Head confirmed: gh api repos/taoq-ai/wuwei/pulls/1167 head.sha is cc6d07fe. I reviewed `git diff bb26ee7 cc6d07f` (4 files, 58 insertions, 4 deletions) from a `git archive cc6d07f` copy in my scratch folder.
- Full suite at head, `/root/.local/bin/pytest -q` in the archive copy: 2151 passed, 2 skipped (the two ssh-keygen skips from before). Matches the PR body and is four more than bb26ee7 (2147), as the four new tests account for.
- Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` shows no difference. Runtime lines: `cat cli/wuwei/*.py | wc -l` is 3208 of 3400, matching the builder and the PR body.
- Mutants re-run one at a time in fresh copies of the head, tests/test_status_perf.py + tests/test_evidence.py, cold-board wall-clock test and tests/test_setup.py excluded (behavioural kills only). The vendored-copy rows show no behavioural kill, for the reason in the first finding.
  - spec_cache_missing (`if True:`), cli/wuwei: killed by test_a_spec_read_through_a_host_error_is_read_again (1 failed). Vendored copy: 265 passed (behaviourally invisible).
  - spec_key_no_head (`{name}-x-{listing}`), cli/wuwei: killed by test_a_push_reads_the_spec_at_the_new_head. Vendored copy: 265 passed.
  - spec_key_no_listing (`{name}-{head}`), cli/wuwei: killed by test_a_retarget_at_the_same_head_reads_the_spec_of_the_new_file_list. Vendored copy: 265 passed.
  - cmp_branch_cached (`if False:`), cli/wuwei: killed by test_a_compare_naming_a_branch_is_never_kept. Vendored copy: 265 passed.
  - prune_wildcard (`'*', '*'` in board.py), full tests/test_status_perf.py: killed by test_reading_the_open_list_prunes_pr_entries_older_than_a_day. The kept-entry assertion is now real.
  - A vendored-copy mutant (spec_cache_missing in .claude/wuwei) is caught by test_the_vendored_plugin_matches_the_tree_it_was_copied_from (1 failed, 39 passed).
- New tests assert exact outcomes: the host-error test compares the full gap list to `['specs/001-x/plan.md missing: run the spec engine step that writes it']` and then to `[]`; the push test compares to `[]` and then to `['specs/001-x/tasks.md has 1 unchecked item']`; the retarget test checks the merge door is None, then names `specs/8-stacked/tasks.md has 1 unchecked item`; the branch test counts exactly two compare calls and no `cmp-*` file; the prune test asserts both removals and three kept entries (budget-other__repo, a fresh pr- entry, a fresh cmp- entry), none of which the board rewrites. None depends on the wall clock beyond utime backdating, a network or a shared file.
- Previous findings: both medium findings (spec_cache_missing, spec_key_no_head) are closed at cc6d07f; the cmp_branch_cached and prune_wildcard lows are closed at cc6d07f. closed: spec cache keeps a missing result at cc6d07f. closed: spec key lacks the head at cc6d07f. closed: compare guard untested at cc6d07f. closed: prune kept-entry assertion vacuous at cc6d07f.
- Delta code: the key now adds the first 16 hex of sha256 of the sorted PR paths (`hashlib` is already imported in evidence.py). It is the same in both trees. One pure expression, no new branch, no new guard other than the key part that spec_key_no_listing reverses.
- PR body Fix round 1 figures: 2151 passed, 2 skipped; four new tests (retarget, host error, push, branch compare: four); 3,208 lines; no change to guards.py or hook.py (the diff touches evidence.py and tests only, so the route corpus is unaffected and no differential was run). All re-derive at the head. The table's "1 failed, 1568 passed" counts come from a larger test selection (adds tests/test_guards.py) than mine and I did not re-measure that total; each row's single failing test matches what I saw.
- Not run: the wall-clock cold-board test, and the specs/verdict-at-head probe and calls.py (the delta does not touch the compare or ancestor path they cover; the previous round's counts stand).
- Simplicity: none to delete in the delta. The listing digest is the one extra key part the retarget case needs and is not a trust-boundary or fail-closed safeguard. The earlier note stands: ws.cache_prune is called as `cache_prune(...) or gh.open_prs(repo)`, which relies on a None return.

## Residual risk
Low. All four surviving mutants from bb26ee7 are killed by behavioural tests at the head, the suite is green, and the vendored copy matches. The cache key does not cover file contents at a head, which is right since a head's contents never change; a retarget is covered by the file list.
