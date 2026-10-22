Verdict: PASS
Gate: quality
Item: 1211-confirm
PR: taoq-ai/wuwei#1233
Head: b9b87ba73f128c16d096bd7ec30f2bca0063de4e
Confidence: high

## Findings
- [low] cli/wuwei/hook.py:324 blocks: no. Partial mutant isinstance(done[0], dict) beside done[-1].get survives (535 passed): a first tool_result row of another type than the last is untested; it can only drop an answer or raise into hook.error, never record one. The full first-row mutant (both reads) is killed.
- [low] cli/wuwei/hook.py:347 blocks: no. At a Stop a partly matched batch still waits whole for the next tool call (its matched plan approval too); recorded assumption, unchanged from a71bcb1, main records nothing for it.

## Probes
- Scope: only fa48175e (hook.py, tests, probe, docs) and b9b87ba (spec docs); the merge of origin/main d1419285 not judged. Both hook.py copies identical at the head.
- closed: [high] text fallback forges an answer (hook.py:326) at b9b87ba. The fallback is gone; a row with no toolUseResult answers dict now records answer.unconfirmed "the tool_result has no toolUseResult answers (<type>)". embed_probe.py at b9b87ba: 0 prompt, 0 plan.approved in all 6 cases; embed_gen.py 520 cases: base d1419285 0 holes, head 0 holes (text only 0/260, toolUseResult 0/260), 0 hook.error.
- closed: [low] Stop waits past the bound (hook.py:347) at b9b87ba. fresh is read once per entry; past BOUND a Stop reads once with no wait and does not claim the entry. Mutant N1 (drop fresh from the wait loop) killed by test_a_stop_past_the_bound_rereads_once_and_leaves_the_answer_to_the_next_call, a call-count assertion, not wall clock.
- closed: [low] probe count conflated the new Stop rule. The compare now prints two columns: base (295 mis-recorded, 1170 Stop blocked), head (0, 0), 1560 cases, 0 hook.error at each, moved 1170.
- Base-versus-head diff of recorded outputs (my own script over the probe JSON, base d1419285): base records and head does not 0; head answer.unconfirmed where base none 0; head silent drop 0.
- Mutants on changed expressions, one at a time, both copies, fresh git archive: N1 Stop waits past the bound killed (1 failed); N2 no bound killed (20); N3 a non-string question kept killed by test_a_question_that_is_not_a_string_reads_as_no_question; N4 a list answers value read killed by test_a_tool_result_row_with_no_toolUseResult_answers_records_nothing_and_names_why; N6 a Stop claims past the bound killed (20); N5 partial first-row mutant survived (note above), re-run as the whole first-row mutant in a fresh copy: killed by test_the_answer_is_the_last_tool_result_row... (2 failed). Each kill is a ledger-row or call-count assertion.
- Full suite not run per coordinator (CI green).
- Confidence high: the forgery class and differential re-run from my own scripts at b9b87ba; every changed guard has a behavioural kill.
- Simplicity: none. The fix shrank _shown (fallback lines gone); fresh replaces the second cache_get, and each remaining changed expression has a killing mutant.

## Residual risk
The #1231 compaction shape stays unproven; a real text-only row now records answer.unconfirmed naming the check instead of the answer, so the owner may be re-asked in that shape.
