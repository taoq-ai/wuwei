Verdict: PASS
Gate: security
Item: 1211-confirm
PR: taoq-ai/wuwei#1233
Head: b9b87ba73f128c16d096bd7ec30f2bca0063de4e
Confidence: high

## Findings
- [low] blocks: no. A Stop never blocks on an unrecorded answer; when the session ends at that Stop, no answer.unconfirmed row or note is written, only answer.pending, which no code reads. Nothing is recorded, so the doors fail closed; the owner asked for this in #1231 (unchanged since a71bcb1).
- [low] blocks: no. touch and rm on a pending answer entry pass the guard, so a session can age it past the 600 s bound (now also skipping the Stop's wait) or remove it; this suppresses only, and a replay with the real answers still records them.
- [low] blocks: no. Pre-existing, same on main: transcript_path comes from the payload and any file under ~/.claude/projects counts, so a real answer in another session's transcript whose id this ledger never recorded can be replayed, and a transcript append from a script file is unreadable to the static guard (the #962 limit).

## Probes
- Delta judged: fa48175e (hook.py _shown, _confirm, post_tool questions) and the merge 34600145's effect on hook.py. The merge brings only main's _replied (#1232) and exception_refs (#1228) changes; hook.py at b9b87ba against main d1419285 differs only in the 1211 lines. Both hook.py copies are identical.
- closed: [high] hook.py:321 deny error row read as text (owner review, plan, exception, breaking, goal forged from WUWEI's own deny echo) at b9b87ba. exploit_probe.py in a fresh git archive copy: deny/unclassed 0 of 15 and deny/unparsed breaking 0 of 15 recorded; each answer.unconfirmed says "the tool_result has no toolUseResult answers (str)" (31 rows).
- closed: [medium] hook.py:326 substring pair inside model-written or quoted text at b9b87ba. Carrier question text 0 of 5, carrier option label 0 of 5, owner free text with pair and period 0 of 5, without period 0 of 5; reason "no toolUseResult answers (NoneType)" (45 rows).
- closed: [low] hook.py:324 list question raising TypeError at b9b87ba: the list-question case records 0 hook.error rows. A cache entry written before the upgrade with a list question still raises once and is consumed with nothing recorded, as main d1419285 also raises (legacy_probe.py); not a regression.
- Exploit probe totals at b9b87ba: 61 cases, 0 forged yes recorded, 0 probe errors, 0 hook.error rows. The former text-only known-positive class now records nothing (5 of 5 unconfirmed): the fallback is gone, so that shape fails closed.
- Known positives with the answers dict (race_probe.py at b9b87ba): forged repeat while pending, the real answer recorded; replay after the bound with the real answers, recorded once. Forged answers after removal, after the bound or after a record: nothing recorded. Stop with an unrecorded answer: no block, entry kept for the next call.
- Reversed guard: a71bcb1's hook.py put into a fresh copy of b9b87ba (both copies); the 12 new tests selected by -k "pair_planted or no_toolUseResult_answers or not_a_string": 10 failed, including all three planted-pair tests (question text, label, deny error row); at b9b87ba 12 passed.
- Route corpus (route_diff.py under pytest's Python, TMPDIR in scratch, main d1419285 vs b9b87ba, same corpus): sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at both; 288 routes, 590 cases, 0 moved.
- Leak and infra: guards.py is untouched by fa48175e and the merge's hook.py lines, and the change no longer parses any text, so neither the parser nor the unreadable-command rule applies; not re-run this round (10 of 10 identical at a71bcb1).
- Not run this round, per the brief: the full suite (CI green at b9b87ba) and the builder's mutants.py. Scanner: the repository runs none; unmeasured.
- PR head read at start and end: b9b87ba73f128c16d096bd7ec30f2bca0063de4e.
- Confidence high: every forged class from round 1 records nothing at b9b87ba, the answers dict alone decides, and the reversed code fails the new tests.

## Residual risk
An answered row with no toolUseResult answers dict (the #1231 compaction hypothesis) is now unconfirmed rather than recorded. That fails closed but may leave #1231's acceptance unmet if such rows exist, which is for the goal gate.
