Verdict: PASS
Gate: security
Item: ci-not-started
PR: taoq-ai/wuwei#1106
Head: 97553d7efc3cd9bbe070667ff90e3a71f8af6392
Confidence: high

## Findings
- [medium] cli/wuwei/evidence.py:399 blocks: no. The answer is cached in .wuwei/cache/ci-<owner>__<repo>.json, which only the ledger guard leaves unprotected (guards.py LEDGER covers .wuwei/ledger only). A seat that writes a falsy JSON value ([], {}, false, 0, "") there, and touches it to keep it fresh, removes the new gap, and a head with no checks merges again. That is main's behaviour, not a regression, and the other cache keys (default-, review-, budget-, login) already share the same exposure. Follow-up: guard writes to .wuwei/cache, or hash cache entries like the verdicts.
- [low] cli/wuwei/evidence.py:399 blocks: no. A real {"workflow_runs": []} reply is cached as "no pull_request CI" for a day. If a repository adds pull_request CI within that day, its no-check heads still pass the door until the entry expires. Failed and odd reads are never cached (probed). No test pins the one-day expiry: a mutant setting max_age to forever would survive.
- [low] blocks: no. The probe only counts event=pull_request. A repository whose CI runs only on push or only on pull_request_target gets no gap on a head with no checks, which is the same as main. This is a limit of the spec, not a bypass of it.
- [low] blocks: no. This is liveness, not security. A repository that once ran pull_request CI reports "CI not started" forever on a head that no workflow will ever check (for example a docs-only PR skipped by a paths: filter). It holds fail-closed but needs an owner exception. Worth a note for the goal gate.

## Probes
- Suite at head: 945 passed, 2 skipped; at main 247d72e: 937 passed, 2 skipped (pytest -q in git-archive copies).
- Main vs head, stubbed host, PR with checks=None in a repo with a pull_request run: main gaps [] and the merge door returns None for both plain and --auto. Head denies both with "CI not started at aaaaaaa".
- Push-only repo (run event=push): no gap, the door passes on head as on main. This is by design.
- Odd Actions reads at head: {}, {"workflow_runs":[{}]} and {"message":..} give "evidence unreadable: 'path'" (KeyError caught by the outer gaps() handler), and the door denies. [], '' and 'null' give "CI not started". A GhError (HTTP 500/403) gives "CI not started" and nothing is cached. Only a real {"workflow_runs": []} is cached, as [].
- Cache tamper: falsy JSON in ci-o__r.json ({} false 0 "" []) makes the door pass. null, garbage or a truthy dict makes it deny (cache_get treats null or garbage as a miss). An entry backdated 86401s is re-read and denies.
- Cache key: 'ci-' + repo.replace('/', '__'). It is keyed per base repository (fork PR runs list under the base). It cannot contain '/', so there is no path escape. Case variants (O/R) get a separate entry and re-read, which fails closed.
- --auto exemption: the text is still exactly g['text'] == 'CI running'. A FAILURE rollup, [] and None all deny with --auto. Mutant startswith('CI ') is killed by test_auto_merge_is_refused_while_ci_has_not_started.
- Mutants: ci=True to False on the error path is killed by 3 test_an_unreadable_actions_host_counts_as_having_ci cases. not rollup to bool(rollup) is killed by 8 or more tests. event=pull_request to push is killed by 4 tests.
- Real read-only call: gh api repos/taoq-ai/wuwei/actions/runs?event=pull_request&per_page=1 returns total_count 992, path .github/workflows/tests.yml. Head gh.workflow_paths parses it as ['.github/workflows/tests.yml'] (truthy). Head 97553d7 has 8 check-runs, so the gap would not fire there.
- No secret or token reaches a log: the new code adds only an api path on the code host, and its error text is caught, never echoed outward.
- Confidence high: every changed guard has a killing test, all error paths probed fail closed, and the only bypass found needs a seat writing workspace cache, which predates this PR.

## Residual risk
The cache under .wuwei/cache is unguarded and unhashed, so a seat that misbehaves can flip this answer, like the other cached answers. A same-day "no CI" cache can hide CI that was just added.
