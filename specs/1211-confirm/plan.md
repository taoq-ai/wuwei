# Implementation Plan: an owner answer the transcript shows late, or beside a differing answer in its batch, is still recorded

**Branch**: `leone/1211-confirm` | **Spec**: `specs/1211-confirm/spec.md` | **Issues**: #1211, #1231

## Summary

Changes in the answer-confirm path of `cli/wuwei/hook.py` (`_shown`, `_unconfirmed`, `_confirm`):
an answer with no tool_result row stays pending until a 10-minute bound; each question in a batch is
matched and recorded on its own; the reason names the check that failed; a row with no
`toolUseResult.answers` dict is read by the harness's own text in that row; and an answer that is not
recorded never blocks the planner's Stop.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py through `hook.handle`, with the real 2.1.308 rows of
`tests/fixtures/transcripts/ask-late.jsonl`. Runtime cap 3,400; main 6828776 is at 3,396.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no door added or changed; the confirm step fails open as before, and a Stop is
  blocked by fewer things, not more.
- IV. The owner decides only what matters: fewer re-asked questions; no new owner question.
- V. Test first: the new and updated tests ran red on base code (tasks T004, T014).
- VI. Budgets: no config key; runtime +10 (see Lines).
- VII. Security first: the trust check (tool_use id, AskUserQuestion, exact answer in the last
  tool_result row) is kept per question; the text match reads only the transcript and anchors each
  pair between the asked questions; a forged or replayed answer records nothing more.

## Design

- `_shown(kept)`:
  - `({}, reason)` for a path that is not a transcript (as before) or for no AskUserQuestion tool_use
    with the id;
  - None while no row holds a tool_result for the id;
  - else `(same, why)`. `said` is the last such row's `toolUseResult.answers` when that is a dict,
    else the payload's pairs that the row's text holds: `json.dumps(content)` contains the
    JSON-escaped `"<q>"="<a>"` followed by `, "<next asked q>"=` or `.`, for `q` in the tool_use's
    questions. `same` holds each payload question that `said` holds with an equal value. `why` names
    each other question with both values cut to 60 characters, prefixed in the text case by
    "its tool_result row holds no toolUseResult answers (<type>), and its text does not match", or
    is "the payload holds no answer" when nothing matched and nothing differs.
- `_confirm`: the Stop's wait loops while `_shown` is None. An entry with a reason stays pending
  when the call is a Stop, or when there is no row and the cache entry is younger than `BOUND` (600 s;
  `ws.cache_get` with that age). Otherwise it is claimed; with no row the reason is
  "no tool_result row in 10 minutes". After the claim, `why` records `answer.unconfirmed`; `same`
  records through `_answers` with only those questions, unless a `prompt` row already holds the id.
- `_unconfirmed(root, kept, why, same=())`: the row and the note name the questions not in `same`;
  the reason is kept to 600 characters.
- `WAIT, BOUND = 1.5, 600` share one line.

## Lines

hook.py +10: `_shown` +8 (the tool_use check, the pending return, the asked questions and their
neighbours, the text match, the per-question match, the reason), `_confirm` +2 (the claim of a partly
shown batch). `_unconfirmed` and the constants keep their line counts. Runtime 3,396 to 3,406: over
the cap until free-lines-6 (#1229) frees 23 lines.

## Guard testing (AGENTS.md)

- Route corpus `tests/fixtures/routes.json` and the payload corpus through `guards.bash` and
  `hook.handle` at main and at the head with its sha256
  (`specs/session-context-cap/route_diff.py`), listing moved cases.
- `answer_probe.py`: generated owner answers (5 question kinds, one with trailing text after
  "Proceed?", x 3 answer kinds: label, free text, label with a note; singles and ordered pairs:
  195 batches) x 9 row timings and shapes (present, late after a Stop, never, differing, forged
  first, replayed, text only, text against forged pairs, no tool_use): 1,755 cases per tree at main
  and at the head, with an oracle for holes, including a Stop that blocks on an unrecorded answer.
- `mutants.py`: 22 mutants of the new conditions in both copies, one at a time.
- No guard parsing change: `guards.py`, the door words and segments are untouched, so no command
  becomes unreadable and the parser probes do not apply.
