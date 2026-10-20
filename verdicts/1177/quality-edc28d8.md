Verdict: PASS
Gate: quality
Item: 1177
PR: taoq-ai/wuwei#1185
Head: edc28d8a9283c216227330af6403d96309764922
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/report.py:176 blocks: no. The median of restore times is still untested: replacing `statistics.median` with `max` survives all 360 tests in test_report, test_evidence, test_status_perf and test_replay (one restored run in the tests). With restore hours 1, 4 and 10 the head gives 4.0 and the mutant 10.0. Missing test only, carried from my first verdict.
- [low] cli/wuwei/evidence.py:232 blocks: no. Two production deploys of one environment with the same `created_at` (GitHub stamps seconds) sort stably, so the list order (newest first) puts the newer one first. A failure then a green rerun in the same second would read as success-then-failure and leave the run open. Not probed with a run; rare and bounded to one extra failure.
- [low] blocks: no. Cost and ordering notes from my first verdict stand: one status call per production deploy, now bounded at the newest 100 by `[-100:]` and tested; deployments and statuses are assumed newest first (the PR records it), and `failures()` re-sorts deployments by created_at, so only the paging stop and the status state rely on it.

## Probes
- closed: inactive skip untested at 8e626d2, killed at edc28d8 by test_a_green_deploy_a_later_one_superseded_still_ends_the_failed_run (mutant `if s['state'] != 'inactive'` to `if True`).
- closed: any-state restore at 8e626d2, killed by test_a_rerun_not_yet_finished_restores_nothing[in_progress] (mutant `state == 'success'` to `state`).
- closed: environment check on restore at 8e626d2, killed by test_a_success_in_another_production_environment_leaves_the_run_open (mutant `d['environment'] in failing` to `failing`).
- closed: deployments read outside the try at 8e626d2, killed by test_a_refused_deploy_read_still_counts_the_reverts_and_raises_the_tier[deployments]; the reverts-fallback line dropped is killed by the same test.
- closed: production_environment flag at 8e626d2, killed by test_github_s_production_flag_marks_production_whatever_the_name.
- closed: `revert\b` boundary at 8e626d2, killed by test_a_title_that_only_starts_with_the_letters_of_revert_is_no_revert[revertible: x] (and reverting x, fix: revert x).
- Mutants: 36 run, each in a fresh copy of `git archive edc28d8`, applied to both cli/wuwei and .claude/wuwei/cli/wuwei (assert count==1 in each tree), one at a time against test_report, test_evidence, test_status_perf, test_replay (360 tests pass unmutated). 35 killed by a behavioural test, 1 survived (median to max, above). The 15 mutants the PR lists plus my seven (six closed above, median open) were included. Then 15 of the new-test mutants re-run against only the named new test: all killed by that test (inactive, any-state, env check, outside-try, reverts fallback, flag, `\b`, status bound, board warm-up, both rate caps, pre prefix, non prefix, word start, word end). Also killed: board limit, pages stop, deploy window and stop, release stop, PR stop, merged window, rerun restarts, open and restored uncounted, error and failure state each dropped, no sort, production filter, both re.I, budget and dora without deploy failures, time_to_restore forced unmeasured, restore pair swapped, releases fallback, rate None when unmerged.
- Tests drive behaviour: the new tests call evidence.failures, evidence.budget, report.dora and board.compute against FakeGh with real paging; no sleeps, no network, no shared files; assertions are on counts, rates, state tuples and the host call log, not prose. The `runs` helper builds deploys by hour offsets from a fixed date.
- Full suite on the git archive copy of the head (uvx --python 3.13 --from pytest pytest -q, offline gh stub first on PATH, CLAUDE_CODE_SESSION_ID unset): 2776 passed, 1 skipped, 4 failed. The 4 are the bash 3.2 cases (test_the_hook_commands_run_under_either_harness_shell and 3 test_bash_runs_the_push_in_each_refused_shape). The PR body says 2777 passed; I read one test fewer in the archive copy and did not trace which (unmeasured, no failing test).
- Runtime lines: cat cli/wuwei/*.py | wc -l gives 3334 at the head and 3322 on origin/main, as the PR says; under the 3,400 cap.
- CI at the head (gh pr view 1185 --json statusCheckRollup): all 8 checks SUCCESS (test 3.11, 3.12, 3.13, ziran-audit, ZIRAN, CodeQL, Analyze python and actions). wuwei evidence lists only the gates, the announcement URL and owner review on cli/wuwei/evidence.py as open, no quality or CI gap.
- Guard and route probes: the diff touches no guards.py or hook.py (the hook.py change in the 8e626d2..edc28d8 range is main merged in); the route differential and parser probes are the security seat's and the PR's reported run (0 moved); not re-run by me.
- Simplicity: none to delete. The first `failures(repo, merged, [])` call in budget is the reverts-only fallback that a test needs; the `or ''` guards and GhError handling are fail-closed and not deletable.

## Residual risk
The failure-run logic now has a named test for each branch I reversed. What stays open is the median test and the same-second tie, both small. The newest-first order of deployments and statuses is an undocumented GitHub assumption the tests share with the code.
