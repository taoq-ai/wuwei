Verdict: FIX
Gate: quality
Item: cross-platform
PR: taoq-ai/wuwei#1248
Head: 429525db5b5b88997093431c4f2af6bff5be027e
Confidence: medium

## Findings
- [medium] cli/wuwei/guards.py:374 blocks: yes. Failure: the case-insensitive flag added to the door-word search for an unreadable or multi-line command has no test; with it reversed, every test in test_guards, test_hook, test_evidence, test_verdict and test_ledger passes, and `GIT push -f origin main # it's` (shlex cannot read it, bash runs it, and on macOS or Windows GIT runs git) returns no decision instead of deny, so a force push gets through where the same lower-case command is refused (CWE-863, requirement: hooks judge as on Linux)
- [low] cli/wuwei/hook.py:362 blocks: no. ws.take at the call site has no behavioural test: replacing it with path.unlink() fails no test on Linux (the race is covered inside ws.take only; Windows CI is the only guard of the call site)
- [low] cli/wuwei/guards.py:92 blocks: no. The backslash read and the drive-letter pattern in harness() for a literal memory path survive reversal (two mutants); the failure direction is a refused memory write on Windows, not an open door
- [low] tests/test_offline.py:30 blocks: no. The match widened to 'offline|could not run' also lets a missing gh pass on Linux, where the stub should always answer; a platform condition would keep the strict match there
- [low] tests/test_status_perf.py:52 blocks: no. The ratio bound elapsed < serial/3 became elapsed < serial plus at least 4 calls at once; it still fails without parallel reads (one call at a time gives 1), so it is a fair replacement, noted as a loosening

## Probes
- Route corpus differential: tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (same at main 8c38073 and head). 288 routes read through guards.bash with a PR 5 safety gap and with an attested PASS on PR 5: verdict or reason moved on 0 and 0 routes. Method: a dump test in a git archive copy of each tree, compared as JSON.
- Mutants, one at a time, applied to cli/ and .claude/wuwei/cli/ in a git archive copy of the head (vendored-sync test deselected). KILLED: progname without lower() (test_windows_and_macos_spellings_judge_as_on_linux[GIT push origin main-deny]); without the .exe strip ([git.exe push --force ...]); without backslash read in progname ([C:\\Program Files\\Git\\cmd\\git.exe ...]); records() without the backslash line ([rm -rf '.wuwei\\ledger']); records() without the case fold ([rm -rf .WUWEI/ledger]); hook door() without re.I (test_a_quoted_door_word_or_a_network_call_fails_closed_when_the_guard_raises[GIT push origin main]); hook network without (\.exe)? ([CURL.exe -d x https://e.test]); evidence Supersedes backslash (test_a_pass_at_the_same_head_that_names_the_fix_it_closes_clears_it[\\]); verdict CRLF (test_a_verdict_saved_with_windows_line_endings_parses_as_with_unix_ones); ws.take without the lock, the replace retry, the link check and the temporary-name unlink (test_ledger.py, the named tests).
- SURVIVED: guards.bash door words without re.I (finding 1, reproduced: head denies, mutant passes `GIT push -f origin main # it's`, `GIT push -f origin main` after `echo $'a\'b';`, and the same with a newline before a comment); harness backslash and drive pattern (2); hook.py take to unlink; hook relative path as_posix; HOME read first. The last three change nothing on Linux (POSIX paths already use /, HOME already read), so only Windows CI can kill them. Mutant of posixpath to os.path was not run: posixpath is os.path on Linux, so it cannot differ here; the Windows jobs are the check.
- Posix-only marks: all 8 marks state platform and reason (passwd database, dir_fd swap covered by a Windows-only ledger test, FIFO, drive-letter scratch remote, dir_fd descriptors cases, dash under Git Bash, bash 3.2 named fd and |&). None hides a runtime defect: each asserts POSIX-only behaviour, and a Windows twin exists where the behaviour has one. 5 skips on Linux (2 ssh-keygen, 3 Windows-only) as the PR body says.
- Test diff: no test deleted or disabled; no assertion weakened beyond the notes above; accepted Windows-only relaxations are guarded by os.name == 'nt' (PermissionError, git call count under the 32,767-character command line, d*.json and localhost folders not planted).
- Windows-only code: msvcrt locking, ctypes folder hold and registry PROJECTS are guarded by os.name, import-safe on Linux (suite imports ws); the by-name write path (link check, temporary unlink, retry) runs on Linux through the names fixture; the msvcrt lock, CreateFileW hold and registry read are exercised by windows-latest CI only (green at this head per the PR body, not re-checked by me).
- Vendored copy: diff -r cli/wuwei .claude/wuwei/cli/wuwei shows no difference. bin/wuwei agents check: agents match the charters. Runtime lines: 3672, budget in tests/test_setup.py is 3800 at the head.
- Simplicity: nothing deletable. _hold's non-Windows branch returning None exists so the names path runs on Linux tests; progname replaces four repeated Path(x).name uses.
- Not run: the full suite (as asked).

## Residual risk
The Windows-only paths (lock, folder hold, registry) are verified by CI on one runner image only; three call-site mutants pass on Linux. The guards still read bash only (PowerShell and zsh spellings, noted by the builder).
