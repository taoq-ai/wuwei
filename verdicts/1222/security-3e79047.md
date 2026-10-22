Verdict: PASS
Gate: security
Item: 1222
PR: taoq-ai/wuwei#1236
Head: 3e790478d3a3b8f3ec4879b10480045c161b5ef4
Confidence: medium

## Findings
- [low] cli/wuwei/hook.py:495 blocks: no. Residual case the builder names: a report is kept, its notification is cleared on cancel, and the same seat then hands back before a planner hook. The later hand-back row, stamped after the kept file, marks the cleared report as notified, so the planner gets a pointer on its next call and no Stop block. The planner did receive that seat's newer report (the hand-back message), the older one stays on disk behind the pointer, and only the seat itself can bring this about. No other seat can.
- [low] blocks: no. A seat can still write .wuwei/reports/pending (guards.py protects only the ledger and the cache below .wuwei; this is the same on main). With this change, setting another seat's pending file mtime into the past (touch -d) would let that seat's older notification rows count. A seat that can write there can already delete or rewrite the file, so this adds no new reach. It is an existing gap for a later item.
- [low] blocks: no. Only enqueue rows count now, so a lone absorbed_mid_turn remove row with no enqueue row is no delivery and the report is given in full. This fails closed; live transcripts pair every remove with an enqueue.

## Probes
- closed: stale hand-back row hides a later report whose notification was cleared, at 3e79047. The stamped probe case stale_handed_then_cleared blocks with the full report (it gave none and a pointer at 11fe141).
- Delta judged: commit 33bc3481 and the merge resolutions. `git diff 86b2e569 3e790478 -- cli/wuwei/hook.py` shows only deliver() and the HANDED constant differ from main. Main's `WAIT, BOUND = 1.5, 600` line and its uses in _confirm (lines 338-345) are unchanged, and `datetime` is imported. charters/_common.md differs from main only in the Report paragraph. The vendored hook.py is byte-identical (cmp).
- My first 13-case probe (test_zz_sec_probe.py) at 3e79047, in a fresh git archive copy: 13 of 13 block with the full report. Its rows carry no timestamp, though, and the new rule treats an unstamped row as no delivery, so at this head that probe no longer discriminates. I did not rely on it.
- Stamped probe (test_zz_sec_probe2.py, 19 cases, rows stamped in the live format, ms with a Z suffix; wuwei imported from each copy's cli, checked via __file__), run at 11fe141 and 3e79047. At 3e79047 all 11 cross-seat cases block with the full report: escaped, raw nested, raw hand-back, split hand-back, leading whitespace, an agent-message, prefix ids lead and lead11, a quoted kept-file name, a dequeue row with content, and an absorbed-only row. stale_handed_then_cleared, stale_equal_before_mtime and cleared_only also block with the full report. The four positive controls are told (no block, a pointer next): own equal, own hand-back, a stamp at the file's exact millisecond, and a +00:00 stamp. The residual case gives a pointer and no block (the first note).
- Stamp format: all 546 queue-operation rows in the live session transcript (read via `python3 -I stamps.py < transcript`) match `YYYY-MM-DDTHH:MM:SS.mmmZ`, so the comparison is fixed-width up to the milliseconds against `isoformat(timespec='milliseconds')` in UTC (`+00:00`). At an equal millisecond, 'Z' (0x5A) sorts after '+' (0x2B), so the row counts as at or after, which is what the code intends. The `>` mutant is equivalent for every live stamp. It would differ only on a `+00:00` stamp at the exact millisecond, which has not been seen live.
- tests/test_hook.py and tests/test_charters.py at 3e79047: 740 passed.
- Confidence is medium. The probes are discriminating and controlled, but the cleared_on_cancel row shape still comes only from the fixture.

## Residual risk
The rule depends on the harness stamping rows in UTC with a Z suffix and on the local file clock. A harness that writes local-offset stamps would compare wrongly; with a later offset, older rows could count as delivery.
