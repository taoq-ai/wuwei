# Tasks: The hero shows the tools behind each station (#431)

Test first: run each test task, see it fail for the stated reason, then do the task that
follows it. Run tests with `python -m pytest -q <file>` from the repository root using the
interpreter the task names. Exact data, functions, test code and strings are in plan.md.
The SVGs are only ever written by `python3 scripts/build-hero.py`. No em-dashes, no
emojis, no absolute local paths. Do not commit.

## Setup

- [X] T001 Run `python -m pytest -q tests/test_docs.py` on the branch before any change and note the count (the hero subset `-k "hero or notice or readme_lead or glossary or release_asset"` was 9 passed on main at ed77b30).
- [X] T002 From a scratch script outside the repository, fetch the 14 glyphs listed in plan.md (Technical Context) from Simple Icons 16.33.0 and keep each `d` attribute; confirm none contains `#`, `{` or `}`. Nothing is written to the repository in this task.

## US2 and US3: the table, solid versus planned, and the still copy

- [X] T003 [US2] In `tests/test_docs.py`, factor the loader of `test_hero_files_match_their_generator` into `_hero()`, add `OPEN_ISSUES` and `test_hero_tools_match_the_repository` (plan.md section 2). Run it: fails with `AttributeError` (the generator has no `ROWS`).
- [X] T004 [US1] In `tests/test_docs.py`, `test_hero_shows_the_current_day`: replace the 20000-byte cap with `20000 + icon path bytes + ALLOWANCE` (start with 12000), and add the no-external-reference assertions (every `href` starts with `#`, no `url(http`) (plan.md section 2). Run it: fails with `AttributeError` (no `ICONS`).
- [X] T005 [US2] In `scripts/build-hero.py`: add `ICONS` (from T002) and `ROWS`, `tool()` and `row()`; in `svg()` add the `<symbol>` defs, the `.still{display:none}` rule and the new reduced-motion rule, `<g class="tools">` with every row (no motion yet) and `<g class="still">` with every row, shared-centre rows stacked and scaled (plan.md section 1). Run `python3 scripts/build-hero.py`. Run T003, T004 and `tests/test_docs.py -k hero`: pass. Set `ALLOWANCE` to the measured overhead plus about 10 percent, never above 12000.

## US1: the rows move in the hero's rhythm

- [X] T006 [US1] In `test_hero_tools_match_the_repository`, assert one stepping highlight per row: `text.count('attributeName="x"') == len(hero.ROWS)`. Run it: fails (0 found).
- [X] T007 [US1] In `scripts/build-hero.py`, add per row the highlight rect with `window(..., attr='x', calc='discrete')`, and the opacity `window()` that alternates rows sharing a centre over `T` (plan.md section 1). Run `python3 scripts/build-hero.py`, then T006 and `tests/test_docs.py -k hero`: pass.
- [X] T008 [US1] Visual check, required: render both SVGs with `qlmanage` at 1200 and 830 px, and a scratch copy of each with the reduced-motion query forced to `@media all` (plan.md Technical Context). Look at every PNG: icons and labels legible at 830 px, no row over a node, path, gate marker, link or caption, the still copy readable. Adjust row centres, pitch or labels in `ROWS` and `row()` only (never nodes or paths), regenerate, re-render until clean. Check the highlight stepping and the row alternation once in a browser. Record here the final file size and any caption you moved.
  Result: both SVGs 45517 bytes (cap 46539). Final centres: Plan rows (124, 262), Build (365, 282),
  Review (722, 150), Close code host (1115, 418) right of Close, Close docs (1068, 552) below it,
  Phone and DM (378, 372), On-call (1050, 70). Close code host and Close docs got their own
  centres (the space below Close fits one row only), so only the two Plan rows take turns.
  Pitch is 60, widened per row so adjacent labels never touch. The built-in browser cannot
  script a local file, so the stepping and alternation were checked in the generated
  keyTimes and values instead.

## US4: alt text and the docs index

- [X] T009 [US4] In `test_hero_shows_the_current_day`, assert `hero.tools_text()` is in the raw `<desc>`, in the README hero alt, and in every hero `alt` in `docs/site/index.md` (plan.md section 2). Run it: fails with `AttributeError` (no `tools_text`).
- [X] T010 [US4] In `scripts/build-hero.py`, add `tools_text()` and append it to `<desc>`; regenerate. Append the same sentence to the alt in `README.md` line 5 and to both alts in `docs/site/index.md` lines 5-6, and add the one-sentence note after the two `<img>` tags in `docs/site/index.md` (plan.md section 3). Run T009 and `tests/test_docs.py -k "glossary or readme or hero"`: pass.

## US4: credit for the icon data

- [X] T011 [US4] In `test_notice_credits_match_readme_acknowledgements`, add `'Simple Icons'` to the names and assert `'16.33.0'` and `'CC0'` are in NOTICE. Run it: fails on `Simple Icons`.
- [X] T012 [US4] Add the Simple Icons entry to `NOTICE` under "Third-party code" and one bullet with the same URL to the README Acknowledgements (plan.md section 3). Run T011: passes.

## Finish

- [X] T013 Run `python3 scripts/build-hero.py` again and confirm both SVGs are unchanged (the generator is deterministic). Run the full suite `python -m pytest -q`: all pass. Check every file you changed for em-dashes, emojis and absolute local paths and remove any.
