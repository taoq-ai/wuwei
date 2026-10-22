Verdict: PASS
Gate: quality
Item: flow-board
PR: taoq-ai/wuwei#1252
Head: edcd07ab55d2bc5d863e4e4caecda6afcb324201
Confidence: medium
Breaking: no
Supersedes: flow-board/quality-23ba522.md

## Findings
none

## Probes
- Delta 23ba522..edcd07ab: 9e32b828 (ceiling duty actionable=False, one assertion pinning [True, False]) and the merge of main af8fb51e (builder-host #1251). Flow-board's own lines in the merge: compute reads running(root, hosted=True) for the team row, queue() reads running(root, STALE_HOURS, hosted=True). hook.py and guards.py are untouched by the delta.
- Hosted seats and the ceiling: a hosted builder carries its own recorded session id, so it counts 1 in that session in the team row's per-session maximum and cannot lift the planner session over 8; the hook's launch note still reads the default running() and is unaffected (hosted seats are not in it). Confirmed by test_the_team_row_names_work_over_the_wip_limit_and_seats_over_the_ceiling (9 seats, [True, False]) and the seat-ceiling hook test passing at the head.
- Hosted seat in progress: test_a_builder_seat_counts_only_while_live_and_under_four_hours now has a host-session X with a recorded session that queues Y (red with hosted=False, mutant H1). The item set is deduplicated with the PR and seat sets, so an item with a PR and a hosted seat counts once.
- Mutants, one at a time on both trees against test_watch.py, the two hook tests and test_status_perf.py: 24 run (all earlier ones re-run on the merged code, plus H1 queue without hosted, H2 team row without hosted, H3 ceiling duty actionable again), 24 killed by a behavioural test: H1 by the builder-seat test, H2 by the host-session test, H3 by the team-row test. No survivors.
- Targeted suites at the head in a git archive copy: test_watch, test_status_perf, test_flow, test_plan 160 passed; hook ceiling and ten-line tests 2 passed. Builder reports the full suite 3758 passed, 5 skipped; I did not re-run it.
- Route corpus: routes.json sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at the head and unchanged against main (af8fb51e). 288 routes through guards.bash and hook.handle(PreToolUse) at 0 and 9 builder seats: byte-identical between main and the head, 0 moves.
- Vendored board.py, plan.py, __main__.py and hook.py identical to the cli/wuwei copies. Runtime lines: cli/wuwei/*.py is 3744, under the cap of 3800 now in AGENTS.md.
- Note (blocks: no): a hosted seat carries no timestamp, so unlike a seat.started builder it holds a WIP slot past 4 hours; builder-host surfaces a dead session as a `stale: ... no PR from builder session` gap after 4 hours, which keeps it visible to the owner. Say so in the PR notes if the owner reads the limit as a time-bound count.
- closed: ceiling duty listed in another session's Stop at edcd07a (arch note); actionable=False plus the pinning assertion.
Simplicity: none to delete; the delta adds no new code beyond one flag at two call sites and one keyword.

## Residual risk
Hosted seats and WIP slots interact through builder-host's record rather than a tested time bound; a long-dead session item keeps a slot until the owner closes or marks it. Medium confidence because the full suite was not re-run here.
