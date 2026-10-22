Verdict: PASS
Gate: quality
Item: cross-platform
PR: taoq-ai/wuwei#1248
Head: e3a79723c9075b38496933f4ea63d6af6b306910
Confidence: medium
Breaking: no
Supersedes: cross-platform/quality-429525d.md

## Findings
none

## Probes
- closed: the untested door-word re.I in guards.bash at e3a7972. Four rows now cover it (`GIT push -f origin main # it's`, `Git.EXE push --force origin main # it's`, a newline-then-comment form, `echo $'a'; GIT.exe push origin main`). With re.I reversed, 2 tests fail (test_windows_and_macos_spellings_judge_as_on_linux[GIT push -f origin main # it's-deny] and the Git.EXE row).
- closed: test_offline.py keeps the strict `offline` match off Windows (`'offline|could not run' if os.name == 'nt' else 'offline'`); the 3 tests in test_dump plus test_offline pass at the head.
- Mutants on the delta, one at a time, applied to cli/ and .claude/wuwei/cli/ in a git archive copy, tests/test_guards.py and tests/test_hook.py selected by -k. KILLED: union reduced to the raw reading (19 failed, e.g. the rm -rf '.wuwei\ledger' row); union reduced to the Windows reading (7 failed, test_a_name_holding_backslash_dots_inside_the_ledger_is_refused_where_backslash_is_a_name_character); windows() without the :stream strip (3 failed), without trailing dot and space strip (4), without the drive strip (2), without the backslash read (11); named() without the 8.3 rule (killed, WUWEI~1 rows), without lower() (killed, .WUWEI rows); the '~' gate removed (killed, 8.3 rows); harness() reading backslashes on every OS (2 failed: test_a_memory_path_with_backslash_dots_that_lands_on_a_transcript_is_refused and test_a_windows_memory_path_with_backslashes_stays_writable). Each of these mutants ran in a fresh copy.
- SURVIVED: harness() drive-letter pattern accepted on every OS (`if True`). Not a block: it needs a Linux literal path `C:/...` that realpath resolves under the projects folder from the hook's working directory, and it reaches the memory exemption only; noted below.
- Route corpus differential at the new head: sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1; 288 routes read at main (8c38073) and at e3a7972 with a PR 5 safety gap and with an attested PASS: 0 and 0 moved.
- New POSIX-only marks (2), each reason true and hiding no defect: test_a_name_holding_backslash_dots_inside_the_ledger_is_refused_where_backslash_is_a_name_character (on Windows the backslash is a separator, so `x\..\..\evil` leaves .wuwei and the write is not a ledger write; the Windows reading is covered by the spelling tests that run everywhere) and test_a_memory_path_with_backslash_dots_that_lands_on_a_transcript_is_refused (on Windows the same string names the memory file; test_a_windows_memory_path_with_backslashes_stays_writable covers that reading with WINDOWS patched on Linux, and runs on every OS).
- The delta adds 22 new cases (16 Windows spellings, 3 backslash names, 4 glob and cd rows, 2 memory tests); the union rule is the one test target for all, and the mutants above show they fail when it is changed.
- Vendored copy identical (diff -r clean); bin/wuwei agents check passes; runtime 3687 lines against the 3800 budget.
- Simplicity: none deletable. records() now carries two readings by design (the union is the trust-boundary fix); windows() and named() are each used once but hold the Windows name rules and cannot be inlined shorter.
- Confidence medium: the new Windows-name rules (8.3 short names, :stream, trailing dots) are checked on Linux through string readings only; Windows CI (green per the coordinator) is the check for the real file system.

## Residual risk
8.3 short-name matching is a prefix test (first six characters), so it can refuse a harmless name such as WUWEI~9 in a plain folder; that fails closed. [low] note: the harness() drive-letter pattern on POSIX is untested (mutant survives), guards.py:101.
