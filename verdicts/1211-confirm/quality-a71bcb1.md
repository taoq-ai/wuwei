Verdict: FIX
Gate: quality
Item: 1211-confirm
PR: taoq-ai/wuwei#1233
Head: a71bcb19bdae8d65bd240619d7799f1a06e63545
Confidence: high

## Findings
- [high] cli/wuwei/hook.py:326 blocks: yes. Failure: on a tool_result row with no toolUseResult answers dict, the text needle matches inside planner-written question text, so a hand-made PostToolUse (another session id, the real tool_use id) claiming plan: Approve records prompt and plan.approved when the owner answered Change, if one question embeds '"<plan q>"="Approve".'; the same finding arch and security hold, which the fix round closes by dropping the text fallback (CWE-345, item promise "Security holds")
- [low] cli/wuwei/hook.py:347 blocks: no. A pending entry whose row never comes makes every Stop wait up to WAIT (1.5 s) inside the 10 minutes, and also after BOUND until a non-Stop planner call claims it, because a Stop always defers (final). The cost is real but small, and only for entries with no row: in the real flows the row lands in the same second as PostToolUse. The spec states the cost under How this fails 2.
- [low] cli/wuwei/hook.py:347 blocks: no. At a Stop, a batch that is partly matched records nothing, including its matched plan approval, until the next tool call. If the session ends at that Stop, the approval stays only as answer.pending. This is an assumption the PR records, and main records nothing for a partial batch either.
- [low] blocks: no. PR body: the probe's "main 1,365 holes" counts the new contract. 780 of them (classes never, forged first, text forged pairs, no tool_use, 195 each) are only "a Stop blocked on an unrecorded answer", which was main's rule, not an answer main got wrong.

## Probes
- Scope narrowed at the coordinator's instruction mid-review. Fallback work stopped after the first probe, and the outside-fallback checks and mutants listed below were already done.
- Green: `pytest -q tests/test_hook.py tests/test_codex.py` in a git-archive copy of a71bcb1: 508 passed. Full suite, run before the scope note: 3239 passed, 2 skipped, 1 failed (test_the_runtime_holds_its_size_budget, 3406 > 3400). Both match the builder's counts.
- Red: the head tests run against main's hook.py (both copies) gave 157 failed, 338 passed. The builder reported 137 + 47 in two stages, which is consistent.
- Builder answer probe re-run (specs/1211-confirm/answer_probe.py) at main 6828776 and at the head: 1755 cases, 0 hook.error at each, main 1365 holes, head 0, moved 1365. Every class reproduces.
- Cases main got right and the head gets wrong, by my own diff of the probe outputs: no case where main recorded a question or plan.approved and the head did not; no case where the head records answer.unconfirmed and main did not; no case where the head drops an answer silently. Result: 0.
- New class, text with an embedded pair (scratch probes/embed_gen.py, generated over batches of 2 and 3 x target x host x shape): 520 cases. Main 0 holes; head 260/260 holes on the text-only shape and 0/260 when toolUseResult answers exist. This is the blocking finding above.
- Mutants, one at a time, both hook.py copies, the wall-clock Stop test deselected: 25 of 25 killed. These are the builder's 22, all reproduced, plus mine. M23 (a differing answer waits for the bound) was killed by test_a_differing_free_text_answer... rows. M24 (the bound inverted) was killed by test_the_real_flow_records_the_answer_on_the_planner_call_after_the_harness_writes_it. M25 (a raw text needle) was killed by the shapes test. M21 and M23 were first killed by the fixture replay test, which asserts prose. Re-running both without -x showed record-asserting kills too: test_a_transcript_with_no_askuserquestion_tool_use_for_the_id_says_so_at_once and the forged-answer class.
- Bound: BOUND = 600 is checked through ws.cache_get on the cache entry's mtime. cache_put writes that entry once, at the first PostToolUse for the session and id (atomic_write), and a repeat never rewrites it, so the mtime is when the answer was kept. 600 s against the real flows (row in the same second as answer.pending) is ample. This is right.
- Tests changed for the old contract:
  - The forged class 'other answers' now uses OTHER_FLOW (REAL_Q answered No). Under ASK_FLOW, the per-question rule correctly records REAL_Q=Yes, which the owner gave. The change keeps the case's intent ("answers the transcript does not hold") and follows promise (2), not the code. Forged extras beside a real answer are pinned by test_a_forged_first_answer_kept_past_a_stop_records_only_what_the_transcript_shows.
  - The Stop-wait test now asserts pending after the wait, which is promise (1).
  - The cache-name test now installs a tool_use with the id so the entry stays pending; its file-name assertion is unchanged.
  - The NOTED table adds the two new fixtures' notes.
  - None of these was bent to fit the code.
- Confidence high: every count above is from my own runs at a71bcb1, and the forgery reproduces in both a hand probe and a generated one.
- Simplicity: the text fallback in _shown (the asked/after line 324, the text branch of line 326 and the "(not own)" prefix at 330) can be deleted. It is not equivalent: it removes the text-only behaviour that the SHAPES, FORGED_TEXT and batch-text tests pin, and removing it saves about 3 runtime lines. Outside it, nothing can be deleted without losing a pinned behaviour: every changed expression has a killing mutant.

## Residual risk
Once the fallback is dropped, the hole closes. #1231's compaction cause stays unproven: no real compacted row exists, and the unrecorded answer now names its check, which is how it would show.
