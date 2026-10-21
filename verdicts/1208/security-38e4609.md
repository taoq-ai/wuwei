Verdict: PASS
Gate: security
Item: 1208
PR: taoq-ai/wuwei#1217
Head: 38e4609c0d0eefd1f9b503c3a01271391b0ca0e5
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:181 blocks: no. A planted entry named for the seat can still drop or slow its kept report in three narrower ways. (a) A regular file the seat cannot read (mode 000, seat not root): is_file() holds and read_bytes() raises PermissionError, so the stop records hook.error and keeps nothing. Checked with setpriv as uid 65534: is_file True, then PermissionError. Main keeps the report. (b) A large regular file is read whole: a sparse 300 MB entry took 1.87 s and about 299 MB RSS, while main reads nothing. (c) An entry swapped from a file to a FIFO between is_file() and read_bytes() still blocks (a race). Each needs write access to .wuwei/reports, which on main already lets a session forge a pending report, so this is the same existing exposure, now narrower (CWE-400, CWE-367). Possible hardening: compare st_size with the encoded length first, and skip entries that fail to open or read.
- [low] tests/test_hook.py:1199 blocks: no. The fifo case has no timeout of its own. When the is_file() guard regresses, the suite hangs instead of failing: mutants N1, N3 and N5 ran past 60 s and were killed, while the head finished in 5.8 s. CI still catches this only through its job timeout.

## Probes
Scope: this delta (git diff 23a26e5 38e4609) changes one expression in subagent_stop, hook.py:181 and its vendored copy, which are byte-identical (cmp), plus 24 lines of tests. guards.py and the guard parsing are unchanged, so this is not a parser rewrite or a normalisation round, and the probes that do not rely on door words and the path-class probes do not apply.
Route corpus: tests/fixtures/routes.json has sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at main c2fafc7 and at the head. Main-versus-head differential through hook.handle PreToolUse, in git archive copies: 288 routes x 8 permission_mode values x 3 callers = 6912 Bash rows, 0 moved. Of 48 SubagentHandback rows, 30 moved, all in the 5 non-auto modes, and none says "hand back again". After path normalisation, 0 of 6960 rows differ from the previous head's dump.
Suite: pytest -q at the head copy gave 3196 passed, 2 skipped.
Planted entries at the head (main in brackets). Each line gives whether the stop blocked for more than 4 s and how many reports were kept. Symlink to a FIFO: no, 1 [no, 1]. Symlink to a folder: no, 1. Symlink to /dev/zero: no, 1. Symlink loop: no, 1. Dangling symlink: no, 1. Unix socket: no, 1. A FIFO under pending/: the stop does not block and keeps 2. FIFO plus a regular file with the same text: no, 0 (dedupe still works) [1]. Unreadable file with the same text, run as root: 0 [1]. A CRLF file against an LF report: 1. Re-run of the earlier probes: P3 folder, 1 kept, no error (was 0 with hook.error). P4 non-UTF-8, 1 kept (was 0). P5 FIFO, not blocked (was blocked). P1, a symlink to the same text outside .wuwei, still suppresses (equality only, no content leaves). P2 1, P6 1, P7 0, P8 2, all unchanged.
Encoding: CRLF, CRLF, LF keeps 2 (main 3). A lone surrogate in the report raises UnicodeEncodeError, records hook.error and keeps nothing. Main fails the same way in atomic_write, so this is not a new regression.
Mutants: each applied to cli/wuwei/hook.py and .claude/wuwei/cli/wuwei/hook.py in a fresh git archive copy, then tests/test_hook.py was run one mutant at a time. In the runs with -k 'not fifo': N1 (is_file dropped) and N3 (is_file changed to exists) were each killed by [folder]. N2 (back to read_text on str) was killed by [binary] and the CRLF test. N4 (no dedupe) was killed by the repeat test and the CRLF test. M6 (glob widened to the whole session) was killed by test_another_seats_identical_report_never_suppresses_this_one. N5 (is_file changed to not is_dir) survived that run. In separate runs of the fifo case under a 60 s KILL timeout, N1, N3 and N5 each hang (rc 137), and the head passes in 5.8 s. So N5 is killed by the fifo hang only (see note 2).
closed: [low] the dedupe raised on a folder or non-UTF-8 entry and hung on a FIFO, at 38e4609 (P3, P4, P5 now keep the report; the remaining parts are in note 1)
closed: [low] the seat glob had no test, at 38e4609 (M6 is now killed)
closed: [low] a CRLF report was kept again on every repeat, at 38e4609
Scanner: the repository's scanner, ziran in tests.yml, is not installed here, so it is unmeasured. This delta does not touch agents/, dependencies, lockfiles or workflows.
Confidence high: the delta only narrows which entries are read. The differential and the earlier probes are unchanged, and every new guard has a test that kills its mutant. A harness that runs seats as a non-root user beside root-owned report files would make note 1(a) reachable without any planting.

## Residual risk
A session with write access to .wuwei/reports can still drop one seat's kept report (an unreadable or swapped entry) or make the stop read a large file. On main, that same access already forges reports.
