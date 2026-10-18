Verdict: PASS
Gate: arch
Item: verdict-symlink
PR: taoq-ai/wuwei#1137
Head: e2211fd00d0ae82f35da9e80fcb1e86c04260943
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/ws.py:44 blocks: no. Closed: the previous blocking finding (CWE-59, a link at atomic_write's temp-file name was followed and overwrote a ledger file). atomic_write now unlinks the temp name, then creates it with O_CREAT|O_EXCL. I re-ran my earlier probe (an 11-pid spray of temp-name links into the ledger) at this head, and nothing was written through a link: ws.verify gives [] after, the ledger file still starts with its own first row, the copy is a regular file, and the attest is recorded.
- [low] cli/wuwei/hook.py:152 blocks: no. Closed: the refusal-text note. The refusal now names the first linked component (`.wuwei` or `.wuwei/verdicts` in my probes) and tells the seat to leave it and report it under Blocked:. That fits a sentinel's Boundaries 1.
- [medium] cli/wuwei/ws.py:42 blocks: no. Unchanged from the last round: a parent link planted inside the check-to-write window is still followed. The builder records it as residual risk (analysis A4).
- [low] cli/wuwei/hook.py:161 blocks: no. Unchanged existing gap: a verdict written directly under a symlinked `.wuwei/` raises ValueError outside the try, and the hook fails open with a hook.error row.
- [low] cli/wuwei/hook.py:151 blocks: no. This is an untested gap: with two links on the path, no test fixes which component the refusal names. Mutant D6 (the last link instead of the first) survived twice, in fresh copies. Either answer names a real link and the write is refused either way, so nothing gets through. The missing piece is a two-link test.
- [low] cli/wuwei/ws.py:45 blocks: no. O_NOFOLLOW adds no protection beside O_CREAT|O_EXCL. I ran a generated differential over 9 pre-planted states of the temp name (none, file, a link to a file, a dangling link, a link to a directory, a directory, a hard link, a fifo, a link loop): 0 differences in outcome, and the outside file was never touched. It is harmless defence in depth on the same line, so keeping it is fine.
- [low] blocks: no. The ws.atomic_write change now carries the exclusive create for every caller, including sync.py:82, setup, plan and cache. The behaviour is the same apart from the new refusal of a pre-existing temp name, which OSError surfaces. The file mode is still 0o666 under umask, as with write_text before. The change stays within the Assumption recorded at spec.md (a change to ws.atomic_write is inside the promise's temporary-file write). It is two-way.

## Probes
- Delta read with `git diff 200f361 e2211fd -- cli tests`: hook.py changes 2 lines (the refusal), ws.py changes 3 lines (unlink, then an exclusive os.open), and test_hook.py adds 4 tests (6 cases).
- Suite at e2211fd (git archive copy): `/root/.local/bin/pytest -q` gave 1695 passed, 2 skipped. The timing test that flaked last round passed.
- Runtime budget: `wc -l cli/wuwei/*.py` gives 2979 (main 2976, +3, budget 3, cap 3000). The vendored copy matches: `diff -r -x __pycache__ cli/wuwei .claude/wuwei/cli/wuwei` is clean.
- Route differential: routes.json sha256 12725ace6adab6f965422e9a2a010d13b93e0897f177fd00bda53b080bfe1cb1. All 251 routes went through guards.bash and hook.handle PreToolUse at efcd9e7 and at e2211fd, and 0 moved.
- Symlink probe at e2211fd. Plain copy-in: attested. Nested path: attested. Symlinked `.wuwei/` outside the root: refused, naming `.wuwei`. `verdicts` linked to a folder inside the root: refused, naming `.wuwei/verdicts`. Direct verdict under a symlinked `.wuwei/`: hook.error, an existing gap. Temp-name link into the ledger: no write through the link, and verify stays clean.
- Delta mutants, each in a fresh copy, running tests/test_hook.py. D1 no unlink: 4 failed. D2 O_TRUNC instead of O_EXCL: 1 failed (the hardlink case). D4 neither O_EXCL nor O_NOFOLLOW: 2 failed. D5 names the copy instead of the link: 2 failed. D3 no O_NOFOLLOW survived, and the differential shows it equivalent (0 differences over 9 states). D6 last link instead of first survived, and I re-ran it in a fresh copy (untested, see finding).
- Confidence is high: the one blocking finding is closed, as the re-run probe shows, and the route corpus, suite, budget and mutants all hold at this head.

## Residual risk
A parent link planted inside the microsecond check-to-write window is still followed, as recorded. A symlinked `.wuwei/` with a verdict written directly in the workspace still fails open, which is an existing gap outside this promise.
