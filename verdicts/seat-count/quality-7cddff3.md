Verdict: PASS
Gate: quality
Item: seat-count
PR: taoq-ai/wuwei
Head: 7cddff31c12e1fbbb4ad17a61f3cdda1f1ebd465
Confidence: medium
Breaking: no

## Findings
- [low] blocks: no. A launch whose tool_response is not a dict with agentId records seat.started with agent None; running() would then count that None id as running all day, since no stop row carries None. Not observed in real data (all 33 Agent results were dicts with agentId), so a note; a test for a response without agentId is missing.
- [low] blocks: no. Only async_launched Agent results exist in this workspace's transcripts; the foreground (completed) response shape is unmeasured here.

## Probes
- Suite in a git-archive copy at the head: 452 passed; runtime size 2,998 lines (cap 3,000).
- Vendored copy: setup.vendor() into an empty dir, diff -r against .claude/wuwei at the head showed no difference; cli/wuwei/hook.py is identical to the vendored hook.py.
- Mutant, seat.started moved back out of PostToolUse (block disabled): test_stop_stays_quiet_while_a_seat_is_running fails (run with -x, so the dedicated tests were not each shown).
- Mutant, agentId read replaced by None: test_stop_stays_quiet_while_a_seat_is_running fails (run with -x).
- Mutant, running() set difference removed: test_stop_stays_quiet_while_a_seat_is_running fails (run with -x).
- Mutant, running() back to row counts: test_running_counts_seats_by_agent_id_not_rows fails.
- Mutant, codex() id carry removed: test_a_spawned_codex_agent_is_a_running_seat fails.
- Acceptance: scenario 1 is covered by test_a_rejected_agent_launch_records_no_seat (it calls pre, which now writes nothing; a PostToolUse is never fired for a rejected launch). Scenario 2 is covered by test_an_accepted_launch_records_its_seat_with_the_agent_id. Scenario 3 is covered by test_running_counts_seats_by_agent_id_not_rows. Scenario 4 is covered by the size test, which passes.
- Real data, the builder's key assumption: 185 seat.stopped rows in .wuwei/ledger/*.jsonl (141 distinct agent ids; the key is `kind`). The transcripts under /root/.claude/projects/ hold 33 Agent toolUseResult dicts, all {status: async_launched, agentId}. 31 of those 33 agentIds appear exactly in seat.stopped rows. The other 2 have no stop yet (still running or in flight). The stopped ids absent from transcripts have role '' (unnamed seats, other sessions). The shape is a dict with agentId and the ids are the same, so the assumption holds.
- Simplicity: none. The five-line record moves into post_tool and running() is rewritten in place. The Codex id regex is the minimum the promise allows (net +1 line).

## Residual risk
A PostToolUse payload with a different tool_response shape than the transcripts' toolUseResult (not directly observed, since hook payloads are not logged) would leave a None-id seat counted as running. The failure would show up as Stop staying quiet.
