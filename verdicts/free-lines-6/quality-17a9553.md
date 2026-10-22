Verdict: PASS
Gate: quality
Item: free-lines-6
PR: taoq-ai/wuwei#1229
Head: 17a95531fcc27580a78a1487f7fe553f018e4f69
Confidence: high

## Findings
- [low] cli/wuwei/ws.py:218 blocks: no. Four rewritten guards are not pinned by any suite test: cache_get without ValueError in its suppress (m4), cache_prune without its suppress (m6), find walking outermost first (m9), find matching .wuwei with exists() instead of is_dir() (m10) each pass the full suite (3210 passed, twice, in fresh copies). The differential probe kills all four. The gap already exists on main, where the only test change is the restore test. Missing tests: a non-JSON cache entry reads as None, a cache directory named x.json survives a prune, nested workspaces resolve to the innermost one, and a .wuwei file is not a workspace.
- [low] cli/wuwei/__main__.py:251 blocks: no. `or 0` maps a falsy non-int return ('', [], {}, 0.0) to 0. Before, SystemExit printed that value and exited 1. Direct main() callers also get 0 instead of None. No command can reach this today: every cmd_* returns an int or None, and hook.main returns 0 on all three paths. A future command that returns an empty string as an error would now exit 0.
- [low] blocks: no. PR body: "7 of 7 mutants killed" counts probe kills. AGENTS.md counts a kill only when a behavioural test fails, and in the suite the cache_get OSError-only and cache_prune no-suppress mutants survive. The wording should say the probe killed them.

## Probes
- Diff read with `git diff bcdfc1b 17a95531` (cli/wuwei, .claude/wuwei/cli/wuwei, tests). The vendored hunks match cli/wuwei line for line. guards.py, hook.py, board.py and evidence.py are untouched. Runtime lines (git archive | wc -l): main 3396, head 3373, so 23 lines freed. plan.restore has no other caller (git grep at head, specs excluded).
- Full suite, one tree at a time, in git archive copies (/root/.local/bin/pytest -q -p no:cacheprovider): main bcdfc1b 3210 passed, 2 skipped (ssh-keygen absent, test_release.py:36,57); head 3210 passed, 2 skipped.
- Builder probe (test_zz_probe.py, sha256 76d98e68...) re-run on my own archives of both trees: out-base.json and out-head.json are both 694cf8543c41b50d9b20bc4ec8e539f1af0016b47aac38297c6d332396ae4a66, the same as the builder's. Case counts read from the JSON: 73 CLI calls (61 int returns, 12 raised), 72 cache_get, 33 find, 4 cache_prune. This matches the PR body.
- Extra probe (test_zz_extra.py, 174 records) covering the input classes the builder probe missed. After normalising the tree path, the only differences are the 6 func_returns cases listed below; everything else is identical.
- func_returns class (cmd_status monkeypatched to return 13 values): None, False, '', [], {} and 0.0 become int 0. 0, 1, 2, True, 'text', [1] and 3.5 pass through unchanged. No real command returns any of the changed values (all cmd_* return paths read at head).
- hook class: 7 events x 6 stdin shapes, plus VENDORED=True. All 43 calls return int 0 on both trees, with identical stdout.
- Subprocess exit codes (python -m wuwei): 9 argv cases, identical rc and stderr on both trees.
- cache_get with other exceptions: 12 names x 4 ages. TypeError from a None or 'x' age propagates on both trees (14 cases). Symlink loops, a mutual link pair, a 5000-digit int (ValueError), NUL in the name, a 300-char name, utf-16 data, a BOM and a lone surrogate all match.
- cache_prune: 7 rounds plus a file where the cache folder should be. TypeError and a NUL-pattern ValueError propagate on both trees, and the remaining files match.
- find on symlink loops: self loop, mutual loop, a .wuwei that loops to itself, a parent cycle, a .wuwei linked to a real folder, a file start and a NUL start (ValueError on both). Plus nested workspaces: 8 starts x 3 cwds. All identical.
- Mutants, each applied to both cli/wuwei and .claude/wuwei/cli/wuwei in a fresh archive, run one at a time. m1 drop `or 0`: killed (36 tests asserting main()==0, e.g. test_plan.py::test_a_goal_the_owner_rewrites_in_place_is_a_new_goal). m2 restore reason '': killed by test_restore_reopens_a_parked_or_dropped_item. m3 restore status parked: killed by the same test. m5 cache_get suppress ValueError only: killed (1165 failures). m7 find default '': killed by 3 tests in test_sync.py. m8 find skips the start: killed (38 failures). m4, m6, m9 and m10 survived the full suite twice and are each killed by the differential probe (probe_mutants.py).
- Complexity: find keeps a lazy generator that stops at the first match, the same as the loop. Each suppress wraps the same statements with the same exception tuple.
- Readability: the next() line in find (103 chars) follows the existing `next((... ), None)` pattern in plan.mark. contextlib.suppress was already used twice in ws.py. Deleting plan.restore removes a one-caller wrapper. The `or 0` carries a comment and replaces 11 identical lines. The two early `return 0` lines left in cmd_plan are needed control flow. I see no line golf and no denser line.
- Simplicity: none further. Each change already deletes a wrapper or repeated boilerplate, and the remaining candidates (the two early `return 0` in cmd_plan) free no lines.
- Confidence high: identical suite counts, a byte-identical builder probe hash, an extra probe that differs only in an input class no command can produce, and every suite-surviving mutant killed by the probe.

## Residual risk
The suite still does not pin the cache tolerance or find ordering, so a later edit to those lines relies on review rather than tests. `or 0` would hide a future command that signals failure with a falsy non-int.
