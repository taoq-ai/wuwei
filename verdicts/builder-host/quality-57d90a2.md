Verdict: FIX
Gate: quality
Item: builder-host
PR: taoq-ai/wuwei#1251
Head: 57d90a2fac28bbb537ffa68490d49cdfd9d741fb
Confidence: medium

## Findings
- [medium] cli/wuwei/board.py:164 blocks: yes. Failure: no test covers a host-session item with no recorded session that has sat idle STALE_HOURS (a queued item whose builder is not started yet); reversing the new `and item.get('session')` clause survives all four suites and the board then raises KeyError 'session' at the `item["session"]` in the stale message, so `board.compute` crashes for every reader (requirement: a session item with no record is no seat and must not break the board; untested guard on the new stale line)
- [low] cli/wuwei/__main__.py:37 blocks: no. `wuwei plan session <unknown id>` with no session id (or no args) now ends in a raw TypeError ("can only concatenate str (not NoneType)") from `"builder session " + args.title` instead of a refusal; at 90191150 it was a ValueError refusal. Nothing is recorded and the exit is non-zero, so fail-closed, but the caller cannot act on it. Check `args.title` before the item lookup or build the reason after the guard.
- [low] cli/wuwei/board.py:164 blocks: no. A host-session item with a PR never goes stale (the live set from running(hosted=True) holds it), so a dead session builder after the draft PR opens shows only through `get_session`; charter and spec say the planner reads progress from the branch and PR, so this is a known limit.

## Probes
- Fetched and read the delta 90191150..57d90a2f; ran `git archive 57d90a2f` into my scratch folder. test_plan, test_watch, test_flow, test_charters: 334 passed. `bin/wuwei agents check`: agents match the charters. agents/builder.md 1986 words (ceiling 2250, 100 words of room kept); runtime 3710 lines.
- Mutants one at a time on both trees (`cli/wuwei` and `.claude/wuwei/cli/wuwei`), 14 run, 13 killed by a behavioural test: no session check (now killed by tests/test_watch.py); hook uses hosted at hook.py:61 and at the Stop read (both killed); status check dropped so a closed item reopens (killed, test_plan covers done, parked, dropped); host check dropped; missing id allowed; unknown-item path (killed by the exact stderr assertion); stale line: host clause dropped, age check dropped, live-seat clause dropped, message changed, stale flag off (all killed in test_flow). Survived: dropping `item.get('session')` from the stale condition (the finding).
- Probe (scratch copy): host-session item, no session, added 5h ago: at the head the row reads `no pull request yet`; with the clause removed `board.compute` raises KeyError: 'session'. A session item with a recorded session and no PR after 5h reads `stale: no event since ..., no PR from builder session s-old`; an agent item with a session stays `no pull request yet`.
- closed: no test for host-session item with no recorded session (the board.py:72 guard) at 57d90a2 (tests/test_watch.py builds the board with such an item and the reversed guard is killed).
- closed: `plan session` reopens a done, parked or dropped item at 57d90a2 (refused, tested for all three).
- closed: hook not counting session builders untested at 57d90a2 (gate launch not refused, Stop not quieted, both hook mutants killed).
- closed: re-add host reset untested at 57d90a2 (test_plan asserts it); test_flow blank-line style fixed.
- Simplicity: none to delete; the sentinel is gone and the refusals are trust-boundary validation. The charter's planner paragraph now names session tools (get_session, send_message, archive_session) pinned by test_charters.

## Residual risk
The stale condition for session items rests on the recorded id and the item's last event; a dead session with a PR is not surfaced by the board. One missing test (idle session item with no record) separates the head from PASS.
