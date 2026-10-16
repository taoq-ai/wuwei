Verdict: PASS
Gate: quality
Item: draft-raise
PR: taoq-ai/wuwei
Head: f1ca82b2a9570af2f02f8f4a2a38d6f161a3a73d
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:178 blocks: no. The endpoint split expression and the `alone` condition in gh_command are single long lines (152 and about 140 characters); they are correct and mutation-tested, but a named helper would read better if the runtime cap ever allows it (the runtime is exactly 3000 of 3000, so any further change must delete first).
- [low] cli/wuwei/guards.py:158 blocks: no. Removing `r` or the `remove-*` names from PR_VALUED survived at the previous head and fails closed (the door denies); unchanged, not re-raised.

## Probes
- Suite at f1ca82b in a clean worktree (merge of origin/main 7f31a51 included): 901 passed, 2 skipped (pytest -q -p no:cacheprovider).
- Size: wc -l cli/wuwei/*.py = 3000, which tests/test_setup.py asserts as at most 3000.
- Vendored .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py (cmp); drift tests pass in the suite.
- Previous finding closed: the cross-repo URL branch of _repo_number reversed now fails 4 tests (the new `-R a/b -R o/r 7` and URL plus -R routes for ready and merge).
- Mutants, each run in a copy and each caught: the `..` dots door removed (4 failed); the endpoint split without the `.` filter (21 failed) and without the empty filter (9 failed); unquote removed (5 failed); query and fragment strip removed (2 failed); the plain-command check for `alone` removed (3 failed) and its gh-first check forced true (18 failed); `alone` itself removed (10 failed); MCP `'copilot' in tool` removed (1 failed); _draft bad-value clause set false (1 failed, pinned by `--draft=yes -d`); `n in VALUED and v is None` removed (1 failed); merge -m/-r exclusion removed (2 failed).
- No em dashes, en dashes or emoji in the added lines (scan of non-ASCII above U+2000 over the diff from main: none).
- Spec artifacts under specs/draft-raise were updated across the rounds and remain the full-tier set (spec, plan, tasks, analysis, checklists/requirements).
- Simplicity: none to delete; the `.strip('/')` is already replaced by the split, and the _draft clause I flagged as deletable is now pinned and stays.

## Residual risk
The runtime sits at the 3000-line cap, so the next change to guards must delete before it adds; _flags and the endpoint split mimic gh and GitHub parsing, and unknown shapes fail closed.
