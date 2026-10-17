Verdict: PASS
Gate: security
Item: free-lines-5
PR: taoq-ai/wuwei#1123
Head: a287d4458e68ee0cafb94c0e70246718a8892ed0
Confidence: high

## Findings
- [low] blocks: no. Existing gap, same on both trees: hook.handle on PreToolUse with a payload that is not a dict (None, list, str, int, float, bool) raises AttributeError out of handle, because the except branch calls door(payload), which calls payload.get. The hook.error row is written first. The harness always sends a dict, so this is a note for a later item, not caused by this diff.
- [low] blocks: no. Existing gap, same on both trees: evidence.verdicts raises TypeError on an attest row whose path is None or an int, and report.learning raises KeyError on an approved exception ruling with no pr. Only WUWEI writes those ledger rows, so a seat cannot plant one.

## Probes
- Trees: git archive of a287d44 (head) and d1c3d79 (base) into scratch. The vendored .claude/wuwei/cli/wuwei matches cli/wuwei byte for byte at head (diff -r). Runtime lines: 2996 at base, 2975 at head (wc -l cli/wuwei/*.py).
- Read through the diff: every walrus rewrite (hook.handle, subagent_stop, _verdict_problem, verdict.parse x2, plan.mark, __main__ x2, setup.doctor) binds the same expression, tests the same thing and sits in the same place. In hook.handle the HANDLERS.get is still outside the try, as before. board.rows now calls evidence._cached(root, 'board', compute, TTL), which is cache_get then cache_put, the same as the old two lines: same cache name, same TTL (60), same file. upgrade.items counts len(known) - before, which matches moved because every add is guarded by "not in known".
- Differential probe (pytest file run in both copies, outputs dumped to JSON, tree path normalised): the outputs are IDENTICAL (cmp). It covered 237 route-corpus commands and 5315 generated commands through guards.bash (door words x 16 operators plus punctuation runs of ;&| up to length 4 x 4 positions). Outcomes were 177 deny / 59 pass / 1 note for the routes and 3283 deny / 2032 pass for the generated set. Decisions and reasons matched.
- hook.handle: 282 calls (5 events plus an unknown event and None, x 40 odd payloads: None, wrong types, missing keys, non-string messages, missing or odd verdict paths, stop_hook_active), plus unhashable events. Return values, exceptions and ledger rows were identical on both trees.
- verdict.parse: 425 texts (25 handwritten plus 400 generated line mutations), strict and non-strict. Error lists were identical (185 valid, 240 invalid on both trees).
- Attestation: SubagentStop on 1275 verdict-file and role pairs, plus a worktree copy, a conflicting worktree copy, a symlink out of .wuwei/verdicts, and another agent replacing an attested file. Identical on both trees: 186 attest rows, the symlink refused, the replacement refused.
- evidence.verdicts: attested rows, a lookup by PR ref, injected rows (a ../ path, an absolute path, a missing sha, imported PASS or FIX with a changed sha, path None or int) and edited files. Counts and errors were identical, and the edited files dropped out on both trees.
- board.rows cache: miss, hit, a planted board.json, a stale mtime, invalid JSON, null, and an entry 1 s inside the TTL. Results, compute call count (4) and cache file names were identical. The guard's CACHE protection covers the same .wuwei/cache/board.json name.
- Full suite: 1500 passed, 2 skipped on both trees.
- Timing at 125 KB and 500 KB, best of 3 (head vs base, seconds). parse-500 0.0275 vs 0.0268; parse with no Findings section 0.0052 vs 0.0052; _verdict_problem-500 0.0044 vs 0.0044; _verdict_problem no-match-500 0.0027 vs 0.0025; evidence.verdicts with 2000 rows 0.087 vs 0.079 (+10%); report.learning-500 0.031 vs 0.030; board.compute with 1000 items 0.021 vs 0.036; upgrade.items (100 items, single run) 0.149 vs 0.136 (+9%). No shape was more than 20 percent slower.
- Confidence high: the diff is mechanical and has no new branch, the probe outputs are byte-identical, and guards.py is untouched.

## Residual risk
The generated commands cover the guard paths only through evidence and cache calls, because guards.py did not change. The timings are wall-clock on a shared host, and the two closest shapes are within 10 percent.
