Verdict: FIX
Gate: quality
Item: session-context-cap
PR: taoq-ai/wuwei#1149
Head: d9d48c13eceea548ec816aa341a4ecce53aa2fdb
Confidence: high

## Findings
- [medium] tests/test_charters.py:332 blocks: yes. Failure: whether the tests catch a change to the 9,900 board room (cli/wuwei/hook.py:303) depends on how long the checkout path and the pytest tmp path are. Both paths appear in the context: the plugin path 3 times, the root once. Mutant X2 (`> 9900` to `> 9990`) is killed here only by the newline test. On that test's 40-item board at this scratch path, X2 returns exactly 10,000 characters and cuts the left-out line, which breaks FR-003 and acceptance 2. At the paths the CI runner uses, X2 passes all three tests and would merge green. I inferred those paths: /home/runner/work/wuwei/wuwei, and /tmp/pytest-of-runner/pytest-0/<30-character test name>N. I ran a replica of session_start that matches the real function byte for byte here, with the CI paths: plain 40 passes, newline 40 passes, singular passes. Swept over 200 root path lengths, X2 passes all three tests at 51 lengths and X1 (`> 10000`) at 21. The head passes at all 200. This is a test-quality defect: the assertion's power depends on the environment, and the pytest-N counter alone moves it. Fix: run the 40-item check (whole last line, `< SESSION_CAP`) over a range of title lengths that covers one item line, for example padding the title by 0 to 190 characters in steps of 10. Some board then lands in the cut window at any path length, which kills X1 and X2 everywhere.
- [low] cli/wuwei/hook.py:303 blocks: no. Untested: P2 (`cut > 1` to `cut > 2`) survives. Only a cut of exactly 2 would read "2 more item left out". The harm is wording only.
- [low] cli/wuwei/hook.py:303 blocks: no. Limit (I read the code; no probe run): the trim now keeps going while any line anywhere starts with '- '. Take a multi-line andon reason with a line that starts with '- ': once every real item is gone, the trim drops the board header and the andon lines below that fragment, and it counts the fragment as an item. The cap holds. The count can be off by the number of such fragments.
- [low] cli/wuwei/hook.py:303 blocks: no. Carried from 3fab3cb, still untested: X4a and X4b (`'- '` to `'-'` in the guard and in the count) survive, because no board line starts with '-' without a space. N3 (`any` over `lines[1:]`) survives, because the header always comes before the first item. No equivalence claim and no differential run.
- [low] cli/wuwei/hook.py:298 blocks: no. Carried, still untested: X5 (drop the `\Z` arm) and X10 (drop the `is_file()` fallback) survive. Both are fail-safe handling for a reordered or missing charter. Keep them.
- [low] blocks: no. Limit, carried and recorded in the spec (A3): the trim drops lines in board order, not by lowest score.

## Probes
- closed: X1 kills at this head's paths (the 40-item test asserts `<` and the whole left-out line) at d9d48c1. The path dependence that is left is the open medium finding above.
- I ran each mutant once in its own fresh `git archive` copy (bin/mut.py), applied to both hook.py copies, with tests/test_charters.py, test_hook.py, test_codex.py and test_setup.py (296 tests). Killed: X1, X2, N1 (old last-line guard), N2 (count every dropped line), P1 (always plural) and P3 (never plural). X1, X2, N1 and N2 are killed only by the newline test. Survived: X4a, X4b, X5, X10, N3 and P2. I re-ran each survivor in a fresh copy: all 6 survived again.
- X1 measured at this scratch path: on the plain 40-item board my probe got 10,000 characters ending "11 more i", but the 40-item test passed. Its tmp path has a different length. That is how I found the path dependence.
- Sweep (tests/test_sweep_x.py in copies): 200 root lengths, each checked against the three conditions the tests assert. All three pass at 200 of 200 lengths at the head, so the head does not flake. They pass under X1 at 21 lengths and under X2 at 51.
- Replica with the CI paths (tests/test_replica_x.py): the replica equals hook.handle's output at this path. With the CI paths, X1 is killed by newline 40, and X2 survives all three.
- The new tests reach session_start through the real entry point: session_context calls hook.handle(root, 'SessionStart', ...). With 3fab3cb's hook.py in a copy of the head tests, the singular test and the newline test both fail (2 failed, 3 passed). The title's newline reaches the board lines, because N1 is killed by the newline test.
- Merge dc39cae: `git diff 1acde97 d9d48c1` for cli/wuwei/hook.py touches only _verdict_problem (the next free file name). board.py and ws.py are unchanged. _way.md, _common.md and planner.md are unchanged; only _gate.md moved. tests/test_charters.py only gained a gate-charter test at the end. session_start depends on nothing the merge changed.
- Suite at the head in a fresh copy: `pytest -q -rs` gave 1882 passed, 2 skipped (test_release.py, ssh-keygen is absent). This matches the builder.
- CI at the head, read once with `gh api repos/taoq-ai/wuwei/commits/<head>/check-runs`: CodeQL, ZIRAN, test 3.11/3.12/3.13, ziran-audit and Analyze (actions, python) all succeeded.
- Confidence is high. The code holds the cap and keeps the left-out line whole at all 200 path lengths. The blocking finding is reproduced by a sweep and by a replica checked against the real function. The CI paths are inferred from runner defaults, not observed.
- Simplicity: none. The `any` guard and the boolean count are what make the newline case work (N1 and N2 are killed). The plural switch is one expression. The `\Z` arm and the `is_file` fallback are fail-safe handling.

## Residual risk
Until the tests sweep title lengths, a change to the board room can pass CI and cut the left-out count in users' sessions, whose path lengths vary. On multi-repository boards the trim still drops the highest-scored items when they sit in the last repository.
