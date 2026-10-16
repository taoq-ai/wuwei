Verdict: PASS
Gate: security
Item: free-lines-2
PR: taoq-ai/wuwei
Head: 3317b703b82cd2c9fbc737397631e19cdfa4d55e
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:108 blocks: no. The cache key 'default-' + repo.replace('/', '__') is unchanged from main and no other cache name starts with 'default-' (grep of cache_get, cache_put and _cached across cli/wuwei), so no other key can poison the default-branch answer; the existing owner/repo flattening could only collide for an owner holding '__', which GitHub logins cannot contain.
- [low] blocks: no. The 21 crashes the comparison harness records for gh pr create with no origin come from the test FakeGh having no answer for an empty repository; they are identical on main and head and not a change of this item.

## Probes
git archive of origin/main 8ea4192 and of head 3317b70 into separate scratch trees; vendored copy at head equals cli/wuwei (diff -r).
Main-versus-head comparison (scripts/compare.py): 489 commands (every command literal in tests/test_guards.py plus push, merge and create extras) times 8 default-branch states (fresh lookup, cached trunk, stale cached trunk, GhError, non-github origin, cached null, corrupt cache file, gh answering trunk) times 3 current branches = 3,912 rows; decision, reason, gh calls and default-* cache files after each call: 0 differences.
GhError: push to main and master denied, no default-* cache file written, on both trees. Cached trunk: push to trunk denied with no gh call, main allowed. Stale cache refetches once. Non-github origin answers main/master with no gh call.
Mutants in copies of head, tests/test_guards.py: removing the except GhError, answering an empty set on error, renaming the key prefix, inverting the no-repo test and a zero cache age each fail one of the two new tests (test_a_push_to_main_is_refused_when_the_default_branch_lookup_fails_and_nothing_is_cached, test_a_cached_default_branch_refuses_its_push_with_no_gh_call).
Full suite: head 693 passed 2 skipped; main 689 passed 2 skipped (pytest -q).
board._list to evidence._cached keeps the same name and TTL; items_named inlined with the same regex; replay() leaving the runtime removes a monkeypatching helper from the shipped code. No auth, secret, external call or dependency change.
Confidence high: the push door's inputs and outputs were compared exhaustively over the corpus and every mutant of the changed guard is killed.

## Residual risk
The comparison runs on the test FakeGh; a real gh failure mode other than GhError (for example a timeout raising another type) behaves the same on both trees but was not exercised.
