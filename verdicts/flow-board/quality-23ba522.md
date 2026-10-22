Verdict: PASS
Gate: quality
Item: flow-board
PR: taoq-ai/wuwei#1252
Head: 23ba522d1e991f335bf0bd88c94b8d8aaac24110
Confidence: medium
Breaking: no
Supersedes: flow-board/quality-a38050d.md

## Findings
none

## Probes
- closed: unanchored limit match (prose "WIP limit: 0" set the limit to 0) at 23ba522; the regex now needs line start, optional list marker and ISO date, and 1 to 4 digits; the test covers a mid-line mention and "WIP limit: 99999" (both ignored, the earlier dated line 6 holds).
- closed: unreadable or non-UTF-8 standards.md broke the board at 23ba522; limit() reads with errors='replace' and keeps the defaults on OSError. Re-probe in a git archive copy: a b'\xff\xfe WIP limit: 3' file no longer raises; the test covers a cp1252 file (limit 5, ceiling default 8) and a directory in place of the file (defaults, board.compute works).
- closed: surviving mutants M6 (role filter) and M14 (no note on a Codex-style launch) at 23ba522; each is now killed by test_a_builder_seat_counts_only_while_live_and_under_four_hours (shepherd seat naming X does not count) and the seat-ceiling hook test (codex:codex-rescue launch gets the note).
- Mutants re-run one at a time on both trees against test_watch.py, the two hook tests and test_status_perf.py: 11 run, 11 killed by a behavioural test: first-line wins, line anchor removed, digit bound removed, errors='strict', OSError narrowed to FileNotFoundError, date prefix removed, order ascending, Codex clause removed, note turned into a deny, role filter removed, Codex-launch note dropped.
- Route corpus: tests/fixtures/routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 unchanged by the delta; 288 routes through guards.bash and hook.handle(PreToolUse) at 0 and 9 seats are byte-identical to main (1b8ef2b8): 0 moves. The delta touches neither guards.py nor hook.py.
- Vendored board.py and hook.py identical to cli/wuwei at the head. The delta is board.py (+10/-6), two tests; the full suite was not re-run by me (builder: 3752 passed).
- Open notes from the first round stay notes: the team row's seat count is the largest per-session count; queue() counts builders of every session; the runtime line count exceeds the 3600 cap on main already.
Simplicity: none to delete; limit() is one read and one regex.

## Residual risk
A line such as "WIP limit: 3 per person" at line start still sets the limit to 3; that is the owner's own line form. Medium confidence because the full suite was not re-run here.
