Verdict: PASS
Gate: quality
Item: multi-session
PR: taoq-ai/wuwei#1238
Head: b19c6b928b0ee15c22cffa8e9b99fbe0e30e80a6
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/plan.py:149 blocks: no. followup() and owe() pick the next free X-n / R-n id from the local plan only, so two clones that each create X-1 (or R-1) with different content collide on one id and the merge by item keeps the newer one, dropping the other (not run: read from the code). Still better than the old whole-file last writer; a note for the PR review notes.
- [low] cli/wuwei/plan.py:39 blocks: no. save() stamps `changed` from each clone's wall clock, so a clone whose clock runs ahead wins every tie it should lose; and two sessions in one workspace still read-modify-write plan.json without a lock (existing gap, outside the sync promise).
- [low] cli/wuwei/board.py:66 blocks: no. A session that crashed holds its item for up to 6 hours with no way to release it (the launch is denied, "launch after its seat stops"); a bounded, documented limit.
- [low] cli/wuwei/sync.py:79 blocks: no. Mutant: dropping `local is not None` from the pull guard survives, because merge() raises OSError on the missing local file and is suppressed, falling through to the old write path. Equivalent in effect; untested rather than deletable.
- [low] cli/wuwei/hook.py:61 blocks: no. Mutant: `held or guards.pre_tool(...)` survives. guards.pre_tool returns None for Agent and Task launches, so the order is unobservable today; a guard that later answers an Agent launch would hide the held-item denial.

## Probes
- Tests at the head, in a `git archive` copy, one file at a time: test_sync 18 passed, test_watch 73 passed, test_codex 13 passed, test_hook all passed including the vendored-plugin drift test. 626 passed across the four files in the unmutated run of the mutant harness. Runtime is 3402 lines, under the 3,600 limit.
- Mutants, each applied to both cli/wuwei and .claude/wuwei/cli/wuwei, run one suite at a time. 18 killed, 2 survived (listed above).
  - Killed by test_watch: no stop check (test_a_dead_stopped_or_unconfirmed_seat_never_counts_as_running), no live bound and a 600 hour bound (same test), an empty session counting (test_a_seat_recorded_without_a_session_holds_nothing), the own session blocked too, an item compared case-sensitively and the held denial removed (test_a_launch_for_an_item_another_live_session_holds_is_sent_back_naming_it), the old asked regex (the quoted-line parametrised cases), the holder gap on any item, the shepherd test ignored and unconfirmed rows ignored (the team-row and dead-seat tests).
  - Killed by test_sync: no stamping, restamp on merge, theirs winning a tie, oldest winning, no merge in pull and no merge in push.
  - Killed by test_hook: Stop silenced by another session's seat (test_a_seat_another_session_left_running_never_silences_the_stop).
- Merge by item, lost updates: two clones each adding an item keep both; the newest change to a shared item wins whichever clone syncs last, in both directions; a tie keeps this clone's item; a non-plan, a non-string stamp, an item without an id and an items object are never merged (file bytes unchanged). The push re-merges on its retry, so a racing push does not drop the other clone's item. A stale view cannot overwrite a newer item because the stamp decides, not the arrival order.
- Live-session test: live means a seat.started row within 6 hours, with a non-empty string session and string agent, and no seat.stopped or seat.unconfirmed row for that agent. A seat at 6h01 is dead, one at 5h59 is live (test_a_seat_past_the_live_bound_no_longer_counts_in_any_session); a row with no or empty session holds nothing; the holder's own session is never blocked; a stopped seat frees the item. ts compares as ISO strings in one timezone and format, so the order is sound.
- Route differential (hook.pre_tool and guards.bash over tests/fixtures/routes.json, 288 routes, main 1bcefca versus head b19c6b9, run in two `git archive` copies): 0 routes move, in decision or in door. Corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (same at both refs; guards.py is untouched). The hook change applies only to Agent and Task launches, never to Bash. A generated combinatorial parser probe is not required: the diff changes no guard parsing (the one regex change reads a brief's Item: line in asked(), not a command).
- Item regex: lazy and anchored with \A, so linear on a prompt without Item:. The 20 parametrised briefs (prefix ids, quotes, list and bold lines) are all killed by the old-regex mutant, and asked() feeds both the hold and the seat.started row, so the two agree.
- Docs (hooks.md, cloud.md) match the behaviour: 6 hour bound, first Item: line, plan merged by item with the newest stamp.
- Confidence is medium: the mutant and differential runs are real, but the clock-skew and id-collision notes are from reading the code, not run.
- Simplicity: nothing to delete. The suppress(...) in plan.merge is a fail-closed fallback to the old last-writer behaviour and stays; the `local is not None` guard in sync.pull is redundant in effect but cheap and states the intent.

## Residual risk
Id collisions on sequentially allocated ids and cross-machine clock skew can still pick the wrong survivor in a rare multi-clone case; a crashed session holds its item for up to 6 hours.
