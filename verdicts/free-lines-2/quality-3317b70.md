Verdict: PASS
Gate: quality
Item: free-lines-2
PR: taoq-ai/wuwei
Head: 3317b703b82cd2c9fbc737397631e19cdfa4d55e
Confidence: medium

## Findings
- [low] cli/wuwei/guards.py:107 blocks: no. Mutant: _default returning set() when repo is empty survives the whole suite; no test pins the {'main', 'master'} answer with no repository. The behaviour is unchanged from main, so this is an existing gap, not a regression; a test calling guards._default(root, '') would close it.
- [low] cli/wuwei/guards.py:107 blocks: no. Mutant: the 86400 s cache age changed to 1 survives (a fresh cache entry reads the same either way); an existing gap, equivalent under test timing.
- [low] cli/wuwei/board.py:64 blocks: no. Mutant: the board TTL of 60 changed to 86400 survives; an existing gap, the argument is passed through unchanged.
- [low] tests/test_replay.py:27 blocks: no. Mutant: dropping the monkeypatch of ws.now in replay_case survives; the helper moved verbatim and the recorded case does not depend on the clock.

## Probes
- git archive of the head, pytest in the copy: 693 passed, 2 skipped (both ssh-keygen absent, unrelated); cat cli/wuwei/*.py | wc -l gives 2962.
- diff -r cli/wuwei .claude/wuwei/cli/wuwei is empty, and setup.vendor() into a temp dir gives an identical .claude/wuwei/cli (diff exit 0).
- tests/fixtures/routes.json and the tests/replay case are not in the diff, so the route corpus and the recorded case read as recorded.
- Equivalence read against origin/main: _default keeps the cache name default- plus repo with / as __, the 86400 age (the _cached default), {'main','master'} with no repo and on GhError, and caches nothing on error (cache_put runs only after read() returns). board._list became evidence._cached with TTL and the same name. items_named inlined with the same body or '' guard. replay moved verbatim, with its imports added to the test module.
- Mutants (both copies patched): _default GhError fallback to set() fails test_a_push_to_main_is_refused_when_the_default_branch_lookup_fails_and_nothing_is_cached; cache name changed fails test_a_cached_default_branch_refuses_its_push_with_no_gh_call; board cache name changed and findall limited to the first item both fail test_a_pr_naming_two_items_links_both_and_closes_both_once_merged; replay error branch off and workspace copy removed both fail test_a_recorded_case_gives_the_same_gaps. Survivors are the four notes above.
- Confidence is medium: survivors are untested but unchanged in meaning; the no-helper-defined test and the --record test were not mutated.
- Simplicity: none to delete; the diff already removes the helpers it replaces, and the structural test pin costs test lines only.

## Residual risk
The no-repository answer, the cache age and the board TTL have no test; a later edit to them would pass the suite.
