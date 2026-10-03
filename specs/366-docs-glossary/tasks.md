# Tasks: A glossary, plain-word interview options and one newcomer walkthrough (#366)

Test first: run each test task, see it fail for the stated reason, then do the task that
follows it. Run tests with `python -m pytest -q <file>` from the repository root using the
interpreter the task names. Exact test code, strings and placement are in plan.md.
Humanizer checklist on every new sentence; no em-dashes, no emojis, no absolute local paths.

## Setup

- [X] T001 Run `python -m pytest -q tests/test_docs.py tests/test_interview.py tests/test_owner_edits.py`: 98 passed on main at 89b577e. Note the count.

## US2 first (code strings): interview options lead with plain words

- [X] T002 [US2] In `tests/test_docs.py`, add the `GLOSSARY` constant, `_prose` helper and `test_interview_options_lead_with_plain_words` (plan.md section 1). Run it: fails on the `gates` header `Gate floor` (the word `gate`) or the first row with a term before `(`.
- [X] T003 [US2] In `cli/wuwei/interview.py`, apply the string table of plan.md section 4: `SOAK`, headers, questions and descriptions only. Run T002: passes. Run `tests/test_interview.py`: passes unchanged (labels, effects and widgets untouched).

## US3 code: goals and voice edit say what they saved (F25)

- [X] T004 [US3] In `tests/test_owner_edits.py`, add `test_goals_and_voice_edit_say_what_they_saved` and the `result.stdout == ''` assertion in `test_invalid_goals_leave_history_and_target_unchanged` (plan.md section 2). Run them: the new test fails, stdout is `''` instead of `goals: 1 goal saved (G-1)\n`; the invalid case passes.
- [X] T005 [US3] In `cli/wuwei/commands/_owner_edit.py` `run`, print the success line (plan.md section 3). Run T004: passes. Run all of `tests/test_owner_edits.py` and `tests/test_owner_actions.py`: pass.

## US1: the glossary and first-use links

- [X] T006 [US1] In `tests/test_docs.py`, add `test_concepts_opens_with_the_glossary` (plan.md section 1). Run it: fails, the first `##` section of `concepts.md` is `Roles`.
- [X] T007 [US1] In `docs/site/concepts.md`, insert the `## Glossary` section of plan.md section 5 between `[Home](index.html)` and `## Roles`, checking each fact against the code cited in plan.md. Run T006: passes.
- [X] T008 [US1] In `tests/test_docs.py`, add `test_glossary_words_link_at_first_use` (plan.md section 1). Run it: fails on `README.md` for `Seat` (`A planner seat` in the comparison table, unlinked).
- [X] T009 [US1] In `README.md`, `docs/site/index.md` and `docs/site/daily.md`, link the first prose use of each term or reword the generic uses listed in plan.md section 6, rerunning T008 until it passes. Leave `daily.md` lines 56-62 alone where the test allows it. Run all of `tests/test_docs.py`: passes (front matter, headings, release asset links unchanged).

## US3 docs: a clean first day, shown

- [X] T010 [US3] In `tests/test_docs.py`, add `test_daily_shows_a_clean_first_day` (plan.md section 1). Run it: fails, `daily.md` section 2 has no `text` block with `plugin integrity: clean`.
- [X] T011 [US3] Capture a clean setup and first plan on this worktree with a scratch script outside the repository (plan.md "Capturing the output"), after T003 and T005 so the interview line and `goals: 1 goal saved (G-1)` are current. In `docs/site/daily.md`, add the section 2 and section 3 blocks and their success and failure sentences (plan.md section 7), placeholders for every path, digest, date and memory figure. Run T010 and T008: pass.

## Finish

- [X] T012 Run the full suite with `python -m pytest -q`: everything passes and no existing assertion was removed or loosened.
- [X] T013 Check every changed file for em-dashes (U+2014), emojis and absolute local paths; remove any. Confirm `git status` lists only `README.md`, `docs/site/concepts.md`, `docs/site/index.md`, `docs/site/daily.md`, `cli/wuwei/interview.py`, `cli/wuwei/commands/_owner_edit.py`, `tests/test_docs.py`, `tests/test_owner_edits.py` and `specs/366-docs-glossary/`.
