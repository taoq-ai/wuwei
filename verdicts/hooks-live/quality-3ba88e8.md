Verdict: PASS
Gate: quality
Item: hooks-live
PR: taoq-ai/wuwei
Head: 3ba88e83212a44669a7563caa556b5237554ba4d
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:60 blocks: no. The stamp is the first line of pre_tool, so if the cache write raises (unwritable .wuwei/cache), handle() fails open for non-door calls and skips the later pre_tool checks (for example the sentinel handback check). Doors still deny. An unwritable state dir breaks WUWEI anyway, so a note only; a try around the stamp, or stamping last, would isolate it.
- [low] blocks: no. The hook-seen age shown comes from the stored value while the 120 s window uses the file mtime; they agree in practice, so no harm.

## Probes
- Ran the suite on a git archive of the head: 471 passed, 2 skipped. Runtime is 2,938 lines (cap 3,000, enforced by tests/test_setup.py:53).
- Mutant, stamp removed in pre_tool: fails the test in tests/test_hook.py and tests/test_setup.py (1 failed with -x on each run).
- Mutant, window 120 widened to 100000: fails, caught by the +121 s warn assertion.
- Mutant, window 120 narrowed to 3: fails, caught by the "fired 5s ago" assertion.
- Mutant, isinstance(seen, ...) forced to True: fails, caught by the no-stamp warn assertion.
- Mutant, role prefix cut dropped (role is "wuwei:sentinel-quality"): fails test_post_tool_trace_carries_the_seats_role.
- git grep HOOK_ROWS: no readers left. The executable file is still written by hook.py:306 and read by sync.LOCAL and test_hook.py:242; only the doctor shortcut is gone, so no other reader breaks.
- Vendored copy: diff -r cli/wuwei .claude/wuwei/cli/wuwei shows identical files (only __pycache__ differs).
- Acceptance coverage: the ok with age (5 s), the warn with earlier ledger rows and no stamp, the role, and the line cap are each tested. The pre_tool stamp test uses a 5 s tolerance and not a mocked clock, which is fine.
- Cost: one small atomic_write (temp file plus rename) per PreToolUse. It is about the same cost as existing cache writes and negligible next to the hook process start.
- Simplicity: none. HOOK_ROWS and the ledger scan are already deleted, and cache_get/cache_put are reused. The replaced tests covered removed code.

## Residual risk
The doctor shows a fresh hook only if the doctor's Bash call fires PreToolUse. Outside a session it will always warn, as the spec intends. Confidence is medium because the PR and CI were not inspected.
