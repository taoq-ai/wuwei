Verdict: PASS
Gate: quality
Item: decisions-survive
PR: taoq-ai/wuwei#1239
Head: 8c332f5fe98e577279985339cd21ca2bf9aafbfc
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:434 blocks: no. The open-item test reads `i.get('approved')` (a missing key counts as unapproved) while cli/wuwei/board.py:113 reads `item.get('approved', True)`; a legacy item without the key would reopen a `plan:` question the board shows as approved. Plan items written by plan.add always carry the key, so this is a note only. The local name `shown` also reads as "plan shown" where `approved` would say what it holds.
- [low] cli/wuwei/hook.py:438 blocks: no. ws.answers sits inside the board's try block, so an unreadable ledger now also drops the board from the session context (the message was widened to "Answers or board unreadable"). The cost is small, since the ledger being unreadable is already a broken workspace.
- [low] cli/wuwei/ws.py:198 blocks: no. `rows()` is reflowed to one line with no change in behaviour (diff noise). The `kind == 'answer.unconfirmed' or kind == 'answer.pending' and ...` line in `answers` relies on `and` binding tighter than `or`; parentheses would show the intent.

## Probes
- Route differential (tests/fixtures/routes.json, sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1, identical on main and head, so the diff does not edit it). I ran `pytest -k "every_route or route_corpus"` on a `git archive` copy of origin/main and of 8c332f5: 289 passed at each. No route's verdict or reason moves, and no refusal names a different PR or repository. The change sits only in the AskUserQuestion branch of guards.pre_tool and does not touch bash parsing, so the combinatorial parser probe does not apply (it is not a guard-parsing change).
- tests/test_guards.py and tests/test_hook.py at the head, in a `git archive` copy: 2498 passed, 0 skipped, 0 failed (the planner already ran the full suite).
- Mutants, each applied to both cli/wuwei and .claude/wuwei/cli/wuwei with the vendored-drift test deselected, run one at a time. All 13 were killed by a behavioural test:
  - plan always shown (`(shown or ...)` replaced by True): test_a_plan_question_after_new_items_reaches_the_owner
  - `shown = True`: same test
  - the open-status filter removed: same test
  - the `plan:` prefix mistyped: same test
  - no casefold in ws.answers: test_the_latest_answer_to_a_question_is_the_one_given_back_and_an_empty_one_none
  - no casefold in the guard: same test
  - blank answers kept (`if a` removed): same test
  - older answer wins (`reversed(recent)` removed): same test
  - the 7-day window removed: test_an_answer_older_than_seven_days_is_neither_shown_nor_sent_back
  - a pending row never settled by a later id: test_session_start_lists_answers_pending_or_unconfirmed_with_their_reason
  - rows of any kind taken as answers (`kind == 'prompt'` removed): test_an_answer_not_yet_recorded_is_never_given_back_as_the_owners
  - the 12-answer cap removed: test_many_answers_take_a_bounded_share_of_the_cap_and_name_what_was_cut
  - oldest-first listing: same bounded-share test
- Tests failed before the code by construction: each new test calls ws.answers, the guard or session_start through hook.handle, with answers recorded by a real PostToolUse. A head-versus-sha mismatch, a quoted or extended question and a different case are each shown to reach the owner. A pending or forged `answer.pending` or `answer.unconfirmed` row is never given back as an answer.
- No wall-clock or network dependence found. The 7-day test patches ws.now. Machine-path sweep is not relevant (no path in the output).
- Simplicity: none to delete. The answer lookup is one 15-line function reused by the guard and the session start. The reflow of `rows()` could be reverted, which is cosmetic. Nothing here is trust-boundary validation or a data-loss safeguard to keep off a deletion list.

## Residual risk
A batch holding one answered question is denied whole; the reason names the answered one but does not say to resend the rest, so a model may need one extra turn. The 7-day window and the exact-text match are a design limit, stated in docs.
