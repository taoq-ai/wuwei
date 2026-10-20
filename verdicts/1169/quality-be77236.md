Verdict: PASS
Gate: quality
Item: 1169
PR: taoq-ai/wuwei#1183
Head: be77236eec1be9a855af0ddfd3761bf7c9b62176
Confidence: medium
Breaking: no
Supersedes: 1169/quality-1a397d0-2.md

## Findings
- [low] blocks: no. `board.replies` writes (plan file plus an `item.done` ledger row) on a read path, and two simultaneous reads can write two `item.done` rows. The PR body names this; it is a limit, not a regression.
- [low] blocks: no. Each open PR-keyed owe re-reads the whole ledger via `ws.rows` on every board read; fine at current ledger sizes, unmeasured.

## Probes
- Read: `git diff 1a397d0 be77236` is 7 added lines in tests/test_watch.py only (runtime unchanged); `git diff main...be77236 --stat` is cli/wuwei/board.py and .claude/wuwei/cli/wuwei/board.py (4 lines each) plus tests/test_watch.py. The two board.py copies are identical (`cmp`).
- `git archive be77236` copy: `uvx --python 3.13 --from pytest pytest -q tests/test_watch.py` gave 16 passed.
- Mutants, each in a fresh `git archive` copy, applied to both runtime trees, tests/test_watch.py run one suite at a time:
  - PR match replaced by `True` (board.py:33): killed by test_an_owe_keyed_to_a_pr_stays_open_on_a_later_send_naming_another_pr (1 failed, 15 passed).
  - `&` to `|`: killed by the same test (1 failed, 15 passed).
  - `>= opened` to `> opened`: killed by the Slack-send and the other-session/`wuwei sent` close tests.
  - `>= opened` to `<= opened`: killed by the earlier-send/other-PR test.
  - drop the `ts` condition: killed by the earlier-send/other-PR test.
  - `continue` to `pass`: killed by the Slack-send and the other-session/`wuwei sent` close tests.
- The new test opens the owe five minutes before now and records a send for acme/app#8 at the current clock, so the send is after the owe and only the PR match can keep it open; no future-dated owe, no sleeps. It asserts the owe is listed and `plan.find(...)['status'] == 'open'`. closed: acceptance 4 untested (PR match and `&` mutants surviving) at be77236.
- Acceptance 1 to 3 and 5 are unchanged from my earlier read at 1a397d0: the thread-link rule in hook._replied is untouched.
- Simplicity: none to delete; the four runtime lines reuse evidence.refs, ws.rows and plan.mark. The leading `prs and` is redundant for correctness but spares a ledger read per thread-keyed owe, so keep it.
- Not run: the full suite (the 4 macOS bash 3.2 failures the brief names are environmental and not in this diff).

## Residual risk
The PR match is by text, so a send that merely mentions the PR closes the owe; that follows from the item's design. The write on a read path is a known limit.
