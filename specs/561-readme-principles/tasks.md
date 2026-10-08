# Tasks: #561 README Principles section, comparison removed

Shipped earlier in #589 (kept as merged): the Mermaid diagram in "The basic workflow", its
test in `tests/test_docs.py`, and the removal of the step 3 "not built" note.

Run tests with `python -m pytest -q tests/test_docs.py tests/test_tone.py` (never the full suite).

## Phase 1: Tests first (red)

- [X] T001 [US1] `tests/test_docs.py`: replace `test_readme_compares_with_other_tools` with `test_readme_states_the_principles` and the module-level `PRINCIPLES` tuple (plan.md, change 1): no comparison or Philosophy heading, no table, nine one-line numbered items in order with their phrases and links, at most 110 words each, the word ban and the em dash check kept. Run it; it fails because `## Principles` is missing.
- [X] T002 [US2] `tests/test_docs.py`: add `test_readme_landing_marks_follow_main` (every "landing" sentence carries an issue link with no `specs/<n>-*` directory; principle 5 links #556 to #560 and says "landing" exactly for those without a feature directory). Run it; it fails because no landing sentence exists.
- [X] T003 [US1] `tests/test_docs.py`: in `test_readme_tells_the_day_in_superpowers_shape` swap `## Philosophy` for `## Principles`, drop `## How WUWEI compares` from the order, delete the philosophy block; in `test_docs_index_mirrors_the_readme_sections` pair `Principles` with `security`. Run both; they fail on the missing heading.
- [X] T004 [US3] `tests/test_docs.py`: in `test_readme_install_and_hero` drop `#00C9A7` from the README phrases and assert the README has neither `#00C9A7` nor "brand accent" and "What WUWEI is and is not" has no `deploy`; in `test_readme_first_day_and_shipped_areas` order on `## Principles` and add `docs/site/agent.md` to the ships links. Run both; they fail.
- [X] T005 [US3] `tests/test_docs.py`: add `OpenSpec`, `CISR`, `vGOAL`, `error budget` and `Brier` to the name tuple in `test_notice_credits_match_readme_acknowledgements`. Run it; it fails on NOTICE.

## Phase 2: Implementation (green)

- [X] T006 [US1] `README.md`: replace `## Philosophy` with `## Principles`, nine one-line numbered items (plan.md text). Run T001 and T003.
- [X] T007 [US1] `README.md`: delete `## How WUWEI compares` and `### How they compose`. Run T001.
- [X] T008 [US2] `README.md`: add the path line and the plain-words cruise sentence to "What ships today" and the closing "Landing next:" line. Run T002 and T004.
- [X] T009 [US3] `README.md`: rewrite "What WUWEI is and is not" without the brand accent and the deploy sentence. Run T004.
- [X] T010 [US3] `NOTICE` and `README.md` Acknowledgements: superpowers "principles"; OpenSpec entry; MIT CISR, vGOAL, error budgets and Brier score entries with their sources. Run T005.

## Phase 3: Verify

- [X] T011 Run `python -m pytest -q tests/test_docs.py tests/test_tone.py`; all pass, including `test_glossary_words_link_at_first_use`, the 300-line cap and the docs tone budget. Run `bin/wuwei lint tone README.md` and keep its nominalisation rate at or under today's 3.6 per 100 words.
- [X] T012 Check `README.md`, `NOTICE`, `tests/test_docs.py` and this feature directory for em dashes, emojis and absolute local paths.
