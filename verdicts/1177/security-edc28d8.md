Verdict: PASS
Gate: security
Item: 1177
PR: taoq-ai/wuwei#1185
Head: edc28d8a9283c216227330af6403d96309764922
Confidence: high

## Findings
- [low] cli/wuwei/evidence.py:244 blocks: no. This is the existing CWE-636 limit, carried over from the last round. When any merged page from 2 to 30 errors, merged stays [] and the rate is None, and _cached keeps that for a day. Main read only one page, so it never had a page 2 to fail. The failure is transient (a token that can read page 1 can read page 2), and main behaves the same when page 1 fails.
- [low] cli/wuwei/evidence.py:231 blocks: no. Accuracy limit: the cap reads only the newest 100 production deploys. Someone allowed to create deployments can push an older failed run out of that window with 100 green deploys. The count never drops below the revert count main uses (failed = reverts + runs), so the tier never falls below main. 'pre.prod' and 'prod1' still count as production, which only ever raises a tier.
- [low] cli/wuwei/evidence.py:235 blocks: no. The word rule follows the promise. Titles that main's prefix rule counted ('Reverts #1', 'Reverted ...', 'Reverting ...') no longer count, so a repository that titles its reverts that way gets a lower rate than on main.

## Probes
- closed: [medium] CWE-636, a refused deployments or status read dropped the rate and the tier was not raised, at edc28d8. In budget(), lines 245 and 246 set failed to the revert count before the deploy read, and the except keeps that count.
- closed: [low] CWE-770, status reads with no limit, at edc28d8. Probe with 3,100 production deploys and 2 reverts in 10 merges: 100 status reads and 131 gh calls in total (30 list pages, 100 statuses, 1 merged page). The previous head made 3,031. The rate stays at 0.2 and raised stays true.
- closed: [low] the 'prod' substring counted preprod, nonprod and product-docs, at edc28d8. Probe: preprod, pre-prod, PRE_PROD, nonprod, non-prod, product-docs, products, reprod, staging and '' each cost 0 status reads and add 0 to the rate. Production, PROD-eu, eu-prod, prod1 and pre.prod count.
- closed: [low] the inactive-skip and \b mutants survived, at edc28d8. Both are now killed (test_a_green_deploy_a_later_one_superseded_still_ends_the_failed_run, and test_a_title_that_only_starts_with_the_letters_of_revert_is_no_revert[revertible: x, reverting x]).
- CI at edc28d8, read once with gh pr view --json statusCheckRollup: 8 of 8 checks SUCCESS (test 3.11, 3.12 and 3.13, ziran-audit, CodeQL Analyze python and actions, CodeQL, ZIRAN). The repository's own scanners (CodeQL, ZIRAN) are green at the head.
- Suite at the head, in a git archive copy, with the offline gh stub on PATH and CLAUDE_CODE_SESSION_ID unset (uvx --python 3.13 --from pytest pytest -q): 2776 passed, 1 skipped, 4 failed. The 4 failures are the known bash 3.2 cases (test_the_hook_commands_run_under_either_harness_shell and 3 test_bash_runs_the_push_in_each_refused_shape).
- Route differential, main 17ff289 against head edc28d8: the corpus sha256 is 4f6e25d0...4be4d49 on both sides. All 263 routes went through guards.bash in 8 variants:
  - 0 routes moved in plain; reverts (10 merged, 2 reverts); reverts with the deployments list refused (403); reverts with a single status read refused (404, 2 host reads); reverts with 150 deploys where status read 70 of 100 returns 404 (72 reads, then the fallback); reverts with 150 green deploys (102 reads); and 150 deploys with failures only among the oldest 50 (0 raised on both sides). Every variant with reverts raises the same 57 routes on both sides.
  - deploy_failures (0 reverts; fail, green, fail): 57 routes moved, every one deny to deny, from requiring quality to requiring arch, quality, security and goal. The new input only tightens the gates.
- Budget probe, main against head: refused deployments read, deployments page 2 returning 502, a single status 404, and a status 404 after failed runs give the same result on both sides (0.2 raised, or 0.1 with 1 revert). gates_for with the deployments read refused (403) and with the single status read refused (404) gives full and 4 gates on both sides.
- Cold board with the deployments read refused (403), 18 linked PRs: the head makes 1 deployments read and 2 merged reads (the board's one page plus the budget's). Main made 9 merged reads (one per pool thread). The cached budget at the head keeps cfr 0.2.
- Mutants, one at a time in fresh git archive copies, applied to both trees, running test_report, test_evidence, test_status_perf and test_replay. Every one is killed:
  - dropping the revert-only prefill: test_a_refused_deploy_read_still_counts_the_reverts_and_raises_the_tier[deployments, a status]
  - except returning None: the same 2 tests
  - no 100 cap: test_only_the_newest_hundred_production_deploys_cost_a_status_read and test_a_cold_board_reads_the_error_budget_once_and_at_most_a_hundred_deploy_statuses
  - the oldest 100 instead of the newest: test_only_the_newest_hundred_production_deploys_cost_a_status_read
  - no board pre-read: test_a_cold_board_reads_the_error_budget_once_and_at_most_a_hundred_deploy_statuses
  - no pre lookbehind: 3 env tests
  - no min(…,1): test_the_rate_is_at_most_one_when_failed_runs_outnumber_merges
  - board read with limit 30: test_a_board_reads_one_page_of_merged_prs_however_many_merged
- Supply chain: no new dependency, lockfile, workflow or install script. The only new tests/conftest.py import is the stdlib urllib.parse.
- Injection and host: pages() builds its own page query on the same repos/{repo} path and follows no Link header. Status reads go to repos/{repo}/deployments/<host id>/statuses on the same gh host. No token goes to a new host.
- Confidence is high. The original failure no longer reproduces at the budget, gates_for and route levels, with refusals at each read. The fallback and the cap are each pinned by a test that kills its mutant.

## Residual risk
A cold budget read inside a door now costs at most 100 status reads plus up to 30 deployments pages and 30 merged pages. I did not measure whether Claude Code 2.1.284 lets a command PreToolUse hook that runs past its timeout through. The SDK callback timeout path in the binary stops the call. Any failed merged read still turns off the tier raise for a day, as it does on main.
