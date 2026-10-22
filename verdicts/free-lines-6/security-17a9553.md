Verdict: PASS
Gate: security
Item: free-lines-6
PR: taoq-ai/wuwei#1229
Head: 17a95531fcc27580a78a1487f7fe553f018e4f69
Confidence: high

## Findings
- [low] cli/wuwei/ws.py:28 blocks: no. Untested guard, pre-existing (the base has the same gap): reversing is_dir to exists, or the None default to the start path, leaves 2972 tests passing in two fresh copies. Both are killed by the builder's probe and by the attack probe below. A test that pins find to skip a .wuwei file or link-to-file and return None with no workspace would close it.
- [low] cli/wuwei/ws.py:218 blocks: no. Untested guard, pre-existing: suppress(OSError) without ValueError survives the suite in two fresh copies. The attack probe kills it (bad UTF-8, BOM and non-JSON entries raise). A test that reads a planted non-JSON cache entry as None would close it.
- [low] cli/wuwei/ws.py:233 blocks: no. Untested guard, pre-existing: cache_prune without suppress survives the suite in two fresh copies. The attack probe kills it (dangling and looping links raise). A test that prunes past a dangling link would close it.
- [low] blocks: no. Pre-existing, identical on both trees, not in this diff: cache_get follows a symlinked entry outside .wuwei/cache, joins a name holding ../ unchecked (hook.py builds stop-<session_id> and guards.py builds notes-<session> from the payload), and when .wuwei/cache is itself a link, cache_prune deletes files in the link's target directory.

## Probes
- Diff read at 17a9553 against bcdfc1b with git diff: 6 runtime files (cli and the vendored .claude copy, byte-identical, checked with cmp), tests/test_plan.py and specs/. No change to guards.py, hook.py, board.py, evidence.py, workflows, pyproject or any dependency. Supply chain: nothing added.
- Exit codes: every cmd_* returns an int or None, and hook.main returns only 0 (hook.py:554-569). So `or 0` only maps None to 0, and SystemExit(None) already exited 0. Exceptions skip the `or`, so the bin/wuwei wrapper's exit 2 on a failed PreToolUse is untouched.
- Real-binary differential (probe/hookexit.py, gh stub on PATH logging calls) on base and head, 28 records, identical apart from one wall-clock due time in `owe`. PreToolUse with cwd=5 gives exit 2 (TypeError). cwd holding NUL gives exit 2 (ValueError). Payload [1] gives exit 2. A merge Bash command in the workspace, from a child whose .wuwei is a link to a file, and with session_id ../../../x is denied in all three cases. With a dangling .wuwei and no parent workspace the hook exits 0 with no output, the same on both trees.
- find, cache_get and cache_prune attack differential (probe/attack.py, 185 records) on base and head: identical, sha256 cd37792d...4df4d2. The classes:
  - find: .wuwei as a link to a directory, to a file, dangling, or looping; .wuwei as a plain file; a start through a link in either direction; a looping start; mode 000; a missing start; // /./ /../ %2e; NUL; and non-string starts ('' 0 [] {} 5 5.5 True ~ bytes).
  - cache_get: an entry linked outside the cache, a link to a directory, dangling, looping, bad UTF-8, BOM, NaN, a 5000-digit int, 200k-deep JSON (RecursionError on both), sub/x, ../ names, an empty name, NUL, an absolute name, a linked cache directory, and ages nan and inf.
  - cache_prune: patterns ln-*, sub/*, ../../outside/*, **/*, and *, ages nan and 0, a linked cache directory, a directory entry, and no root.
- The builder's probe (test_zz_probe.py, sha256 76d98e68...) re-run in my archives of both trees: 184 records (72 cache_get, 4 cache_prune, 33 find, 73 CLI), identical, sha256 694cf854...4a66.
- Route corpus (tests/fixtures/routes.json, sha256 de377966...ed71c1, 288 routes): pytest tests/test_guards.py -k route gives 388 passed on both base and head, so 0 routes move.
- Full suite at head in a git archive copy: 3210 passed, 2 skipped.
- Mutants, one at a time, applied to cli/ and .claude/ copies, focused suite of 13 test files:
  - killed: cache_get suppress(ValueError) only (1067 failures, for example test_plan.py::test_an_operations_item_shows_its_run_evidence_not_a_missing_pr);
  - killed: main without `or 0` (36 failures, including test_restore_reopens_a_parked_or_dropped_item);
  - killed: restore reason blank (test_restore_reopens_a_parked_or_dropped_item);
  - the 4 survivors under Findings were re-run in fresh copies and survived again; the attack probe kills each one.
- Scanner: the repository's CI scanner is ziran audit over agents/, which this diff does not touch. It is not installed locally, so it is unmeasured here.
- Confidence high: the three rewrites are semantically identical (the same exception sets, next() over the same generator, and None to 0 only where SystemExit already exits 0). Three differentials over 397 records show 0 differences.

## Residual risk
contextlib.suppress also swallows an ExceptionGroup made only of matching errors (Python 3.12+). No code path in these bodies raises one. The pre-existing cache path-containment gaps above are outside this item.
