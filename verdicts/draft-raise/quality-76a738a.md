Verdict: FIX
Gate: quality
Item: draft-raise
PR: taoq-ai/wuwei
Head: 76a738ad735a284b76c5246cd77f834826d887fb
Confidence: medium

## Findings
- [medium] cli/wuwei/guards.py:165 blocks: yes. Failure: the URL branch of _repo_number (`url[1] if url else ...`) is untested; dropping it leaves all 620 tests in tests/test_guards.py and tests/test_hook.py green, because the fixtures' URL repository is the same o/r as the checkout origin. With the guard gone, `gh pr ready https://github.com/other/x/pull/7` run from an o/r checkout checks o/r#7 instead of other/x#7, so a draft in other/x flips to ready (or gets reviewers, or merges) without its gates. Add a route whose URL names a repository other than the origin (for ready and merge).
- [low] cli/wuwei/guards.py:158 blocks: no. Removing `r`, or the `remove-*` names, from PR_VALUED survives, but it fails closed (a value read as the PR number gives no number, so the door denies); a test pinning `gh pr edit --add-reviewer a --remove-reviewer b 7` would document it.
- [low] cli/wuwei/guards.py:151 blocks: no. Two survivors are equivalent: dropping `or word == '-'` (a lone dash adds nothing) and the `n in ('d','draft') and v not in (...)` clause (an invalid value already reads as not draft through `v in (None, *TRUE)`); the second clause can be deleted.
- [low] cli/wuwei/guards.py:171 blocks: no. `.strip('/')` after the segment collapse is redundant with the leading and trailing slash removal in the inner re.sub; removing it fails nothing.

## Probes
- Finding closed: `-dr=bob` is now in tests/test_guards.py (one occurrence) and the suite is green.
- Suite at 76a738a in a clean worktree: 853 passed, 2 skipped (pytest -q -p no:cacheprovider).
- Size: wc -l cli/wuwei/*.py = 2999, within the 3000 cap that tests/test_setup.py:53 asserts.
- Vendored .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py (cmp); charters and agents drift tests pass in the suite.
- Mutants caught: `--` handling in _flags (1 failed); short-cluster stop at `=` or a valued flag (3 failed); `n in VALUED and v is None` in _draft (1 failed); draft default `[False]` flipped (19 failed); merge exclusion of -m/-r (2 failed); `alone` flag on --input draft (3 failed) and the one-segment check (3 failed); unquote (3 failed); slash collapse (8 failed); both normalisation steps removed (11 failed); -R/--repo read (3 failed).
- Mutants surviving: URL repository branch (blocking, above); PR_VALUED r and remove-* (fail closed); the equivalent ones listed above.
- Simplicity: delete the redundant `n in ('d','draft') and v not in (None, *TRUE, *FALSE)` clause in _draft and the trailing `.strip('/')` in _api; the shared _flags reader replacing the two earlier parsers and API_FLAG is a net reduction. _flags and _draft are dense one-liners but readable with their comments.

## Residual risk
_flags mimics pflag for short clusters; a shape it misreads would fail toward a missing number or not-a-draft, which deny, so the risk is friction rather than a gap.
