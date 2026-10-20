Verdict: FIX
Gate: quality
Item: 1169
PR: taoq-ai/wuwei#1183
Head: 1a397d018106d12bc696ba1f21615de4dbf73880
Confidence: medium
Breaking: no

## Findings
- [medium] tests/test_watch.py:160 blocks: yes. Failure: acceptance 4 ("a sent row naming acme/app#8 after T keeps the owe open") is not tested. In test_an_owe_keyed_to_a_pr_stays_open_on_an_earlier_send_or_another_pr the owe is opened one minute in the future, so the #8 row is excluded by the `ts >= opened` guard, never by the PR match. Reversing the match in cli/wuwei/board.py:33 (`prs & set(r['data'].get('refs', ()))` replaced by `True`, or `&` by `|`) leaves all 15 tests in tests/test_watch.py green. With that reversal, any recorded send after the owe (a Slack ping about acme/app#8) would close the owe on acme/app#7, and the owed reply would silently disappear from the board, `wuwei watch` and the Stop reminder. Fix: record the #8 send after an owe opened now (no future `opened`) and assert R-1 stays open. In copies, such a test passes at the head and fails against both mutants.
- [low] blocks: no. `board.replies` now writes (plan file plus an `item.done` ledger row) on a read path, and two simultaneous reads can write two `item.done` rows. The PR body names this; it is a limit, not a regression.
- [low] blocks: no. Each open PR-keyed owe re-reads the whole ledger via `ws.rows` on every board read; fine at current ledger sizes, unmeasured.

## Probes
- Read: `wuwei plan show 1169`, `gh pr view 1183`, `git diff main...1a397d0 -- cli tests`; `wuwei evidence` shows only the quality gate missing at the head.
- `git archive 1a397d0` copy: `uvx pytest -q tests/test_watch.py` gave 15 passed. `cli/wuwei/board.py` and `.claude/wuwei/cli/wuwei/board.py` are identical. `uvx pytest -q tests -k "owe or reply or replied or watch or sent"` gave 122 passed (the thread-link rule in hook._replied is untouched and still green).
- Mutants, applied to both trees, one suite at a time on tests/test_watch.py:
  - `>= opened` to `> opened`: killed by test_an_owe_keyed_to_a_pr_closes_on_a_slack_send_that_names_the_pr (weak kill, relies on the send landing in the same clock second as the owe).
  - `>= opened` to `<= opened`: killed by the stays_open test.
  - drop the `ts` condition: killed by the stays_open test (earlier send).
  - `opened` fallback only to `added`: killed by the stays_open test.
  - `continue` to `pass` (owe still listed after close): killed by the Slack test.
  - PR match replaced by `True`: SURVIVED (the finding above), re-run in a fresh copy.
  - `&` to `|`: SURVIVED (the finding above), re-run in a fresh copy.
  - drop the leading `prs and`: survives, equivalent (an empty set `&` anything is empty, so falsy); not a defect.
- Consumers reached: the tests call `hook.handle` PostToolUse, `cli.main(['sent', ...])`, `board.compute`, `board.replies`, `plan.find`. Both producers clear the board cache (hook.py:256, __main__.py:121), so a cached board does not hide the close.
- Timestamps: ledger rows, `opened` and `now()` are all UTC isoformat to the second, so the string comparison is consistent. The `added` fallback compares a date to a timestamp, as the PR body states.
- Simplicity: none to delete; the four lines are minimal and reuse evidence.refs, ws.rows and plan.mark. The leading `prs and` is redundant for correctness but spares a ledger read per thread-keyed owe, so keep it.
- Not run: the full suite (the 4 failures the brief names are environmental).

## Residual risk
Once the other-PR test lands, the change is small and behaves as the promise states. The PR match is by text, so a send that merely mentions the PR closes the owe; that follows from the item's design.
