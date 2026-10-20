Verdict: FIX
Gate: quality
Item: 1200
PR: taoq-ai/wuwei#1203
Head: e3cdef2d393e2caac923291d206f297274648f33
Confidence: medium
Breaking: no

## Findings
- [medium] cli/wuwei/board.py:96 blocks: yes. Failure: the note is written only when `not item.get('reason')`, but the only way to make an item kind run is `wuwei plan run <id> --reason`, which refuses an empty reason (__main__.py:46), so a real run item always has a reason and the note is never written. Run `plan run R --reason "run: head none on production"`, then merge a PR naming R: the item stays open (the core fix holds) but the board row reads `run: run: head none on production`, with no `code merged ... run owed`; acceptance 1 and the promise ("a merged PR records run evidence `code merged as <ref>, run owed`") fail on the reachable path, and the row shows the stale pre-merge evidence the issue calls misleading. The test passes only because `_item('R', kind='run')` seeds a run item with no reason, a state the CLI cannot produce. Fix: record the merge alongside the existing reason (for example append `; code merged as <ref>, run owed` once, guarded by `'run owed' not in reason`), and make the test reach the item through `cli.main(['plan','run',...])`.
- [low] cli/wuwei/board.py:96 blocks: no. A mutant dropping `not linked` from the note line survives (the new test never has a merged run PR plus an open linked PR for the same item); the missing test is a run item with one merged and one open PR. With it the note would be written while the item still shows its open PR rows.
- [low] cli/wuwei/board.py:96 blocks: no. With the first-writer-wins guard, a second merged PR never updates the note, and an item restored (reason `restored`, plan.py:89) shows `run: restored` instead of the owed-run line; the append fix above covers both.

## Probes
- Ran at e3cdef2 from `git archive`, offline gh on PATH, CLAUDE_CODE_SESSION_ID unset: tests/test_watch.py 24 passed; full `pytest -q` 2999 passed, 1 skipped, 4 failed; the 4 failures (test_codex hook-commands-under-either-shell; test_guards push shapes `{fd}>x`, `{a_b}<x`, `|& sh -s`) are the bash 3.2 failures named in the brief, unrelated to board.py.
- Mutants applied to both cli/wuwei/board.py and .claude/wuwei/cli/wuwei/board.py, tests/test_watch.py run one mutant at a time with the vendored-copy test deselected: dropping `kind != 'run'` KILLED (test_a_run_item_stays_open_with_run_owed...); `== 'run'` KILLED (3 tests); dropping `not item.get('reason')` KILLED (second compute writes a second item.open row); inverting it KILLED; status 'open'->'done' KILLED; dropping `item['reason'] =` KILLED; note text change KILLED; dropping `and done` KILLED (several tests); dropping `not linked` from the note line SURVIVED (untested, see the low finding). Only the one new test kills the new-behaviour mutants; each kill is a behavioural assertion.
- Acceptance coverage: scenario 1 (run item, merged PR, stays open, shows run owed) is driven against the real board.compute but only with a reasonless run item, so it does not cover the reachable `plan run` state (finding 1); scenario 2 (build item B in the same merged PR is done) is driven; scenario 3 runs `cli.main(['plan','done','R','--reason',...])` and checks done. A real-flow probe (plan run, then merge) returned `run: run: head none on production`, status open.
- CI at the head, read once with `gh pr checks 1203`: test 3.11/3.12/3.13, Analyze (actions), Analyze (python), CodeQL, ZIRAN, ziran-audit all pass.
- Vendored copy byte-identical to cli/wuwei/board.py in the diff (same hunks, same blob index 2eeae4c3).
- Simplicity: none to delete; the two runtime lines are the minimum, the test could drop the `capture`-free `import os` inside the function only cosmetically.

## Residual risk
The core guard (a run item is not closed on merge) is correct and tested, so the original harm (later items looking unblocked) is fixed; what is wrong is the shown evidence line on the normal `plan run` path.
