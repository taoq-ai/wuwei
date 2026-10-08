# Tasks: 585-hero-system (the agentic flow, each part in its model)

All tests live in `tests/test_docs.py` and are written and seen failing against the #569
SVGs before `scripts/build-hero.py` changes. Tests read the generator's tables through
`_hero()` and both SVGs; they never hard-code a timing the tables already hold.

## Phase 1: tests first

- [X] T001 Test, tests/test_docs.py `test_readme_install_and_hero`: replace the station
  word pin with the five stage names `Specs and plan`, `Agent team`, `Gates`, `Pull
  requests`, `Review and merge` (FR-001).
- [X] T002 Test, tests/test_docs.py, new `test_hero_shows_the_system` replacing
  `test_hero_is_a_day_on_a_track`: README alt and both index alts equal `hero.ALT`, one
  sentence (no ". "), ends with ".", equals each SVG's `<desc>`, names "queue", "agent
  team", "gates", "pull requests", "card" and "under the hood", no "treadmill" (FR-013).
- [X] T003 Test (same test): `hero.STAGES` has five entries in rising x, each name at most
  three words and each small line at most six; each SVG holds every stage name and small
  line in order of x, and `id="icon-0"` to `id="icon-4"` as `<path` elements with
  `fill="none"` (FR-001).
- [X] T004 Test (same test): first frame (US2): `id="panel-queue"`, `panel-lanes`,
  `panel-prs`, `panel-cards` and `panel-band` exist outside the `live` and `still` groups;
  the stage names, small lines, "build ⟲ check", "raise PR", "sweep", "overnight: sweeps,
  never merges", both `hero.LOOPS` labels, `hero.DAY` and the four `hero.INDICATORS` are
  drawn outside `live` and `still`; each queue pill "n · name" for `hero.QUEUE` sits in
  `live` without an `opacity="0"` start, so it shows at k 0.
- [X] T005 Test (same test): the shapes (FR-003 to FR-008): `id="build-0"` to `build-2`,
  `id="gate-<lane>-<n>"` for 3 lanes by 3 dots, `id="fix-loop"` with "fix ×1 → delta",
  `id="sweep"`, `id="ask-loop"` and `id="answer-loop"` each with `stroke-dasharray`,
  `id="day-loop"`; every `hero.PRS` label, every decision line, "Approved · 3 seats",
  "answers a card now and then", the close line `f'{hero.clock(hero.CLOSE)} close: report
  written, retro done'`, "09:00" and "18:00" appear in each SVG.
- [X] T006 Test (same test): hygiene and motion rules: no brand or tool name (the #569 list
  plus "treadmill"); only `#` hrefs and no `url(http`; each SVG under 40000 bytes; every
  SMIL element inside `live`; every `keyTimes` starts at 0, ends at 1, never decreases and
  matches its `values` count; the classes are exactly `live`, `still`, `spin`, `beat`, each
  named in the reduced-motion block; the generator under 320 lines (FR-011, FR-012,
  FR-014).
- [X] T007 Test, tests/test_docs.py `test_hero_only_moves_forward` rewritten: for every
  item, `PLACES[place]` never decreases and its k never decreases; in each SVG there is one
  `animateMotion` per item and its x values never decrease; `hero.FIX` names one item, that
  item holds at `'gates'` over the whole FIX span; the animate inside `id="fix-loop"` is on
  (value above 0.5 by `_value_at`) at the FIX midpoint and off 0.02 before and after it
  (FR-003, FR-009).
- [X] T008 Test, tests/test_docs.py, new `test_hero_queue_lanes_and_cards` replacing
  `test_hero_items_wait_and_park`: items leave the queue in `QUEUE` order; within a lane no
  two items overlap, and every item after the first three enters a lane at the k its
  previous occupant left it; the "waits: CAP 3 seats" animate is on at the midpoint of the
  span where all three lanes are occupied and an item still waits, and off at k 0.1 and 0.9
  (FR-002).
- [X] T009 Test (same test): each `PRS` entry's raised k equals the last stop k of the item
  it names; merges ascend; the shipped texts are `shipped today: 0` to `shipped today:
  len(PRS)`; "carried to tomorrow: N" with N the items whose last place is not `'PR'`;
  "asked today: X of Y" with X the phone decisions and Y `len(DECISIONS)`; the phone's warm
  span covers each phone decision's (asked, answered); by `_value_at`, `ask-loop-lit` is on
  just after each decision's asked k and `answer-loop-lit` just after each answered k,
  `id="lead"` is on just after the last pop and off at k 0.5, and `day-loop-lit` is on
  after `CLOSE` and off at k 0.5 (FR-004 to FR-008).
- [X] T010 Test (same test): the still group (FR-011): holds no `<animate`; holds
  `clock(STILL_K)`; the queue pills not yet popped at `STILL_K` and no other; "waits" because
  `STILL_K` lies in the waiting span; "fix ×1 → delta" because `STILL_K` lies in FIX; every
  decision line due at `STILL_K` (D-3's open text); and one item pill per item in a lane at
  `STILL_K`, drawn at `hero.at(place, lane)` for the place it holds then (rate limits and
  login fix at gates, docs page at build).
- [X] T011 Run `python -m pytest -q tests/test_docs.py -k hero` and the
  `test_readme_install_and_hero` test; see T001 to T010 fail against the #569 SVGs for the
  expected reasons (missing stage names, tables and ids).

## Phase 2: implementation

- [X] T012 Implement, scripts/build-hero.py: delete the track parts and redefine the tables
  per plan.md (`STAGES`, `ICONS`, `QUEUE`, `PLACES`, `LANE_Y`, `ITEMS`, `FIX`, `PRS`,
  `PR_LINES`, `DECISIONS`, `GATE`, `PHONE`, `GUARD`, `CLOSE`, `STILL_K`, `LOOPS`, `DAY`,
  `INDICATORS`, `ALT`); adapt `at`, `track` and `holds(place, lane=None)`; draw the panels,
  stage row, queue, lanes, PR stack, cards, guidance loops, return arrow, band, CSS, the
  `live` and `still` groups. Regenerate docs/site/assets/hero-light.svg and hero-dark.svg
  with `python3 scripts/build-hero.py`. T001 and T003 to T010 pass.
- [X] T013 Implement, README.md and docs/site/index.md: set the hero alt to `ALT` (one in
  README, two in the index); nothing else changes. T002 passes.
- [X] T014 Run `test_hero_files_match_their_generator` and
  `test_hero_variants_share_geometry_and_motion` unchanged; both pass.

## Phase 3: verification

- [X] T015 Render both SVGs, a mid-day copy (display rules swapped) and a right-half copy
  (viewBox shifted) to PNG with `qlmanage -t -s 1400` into a scratch directory outside the
  repository. Check: five stages left to right with icons over pills, two dashed loops
  under the flow, the return arrow over it, the band, card lines inside their panel, no
  overlapping text, the first frame (queue full, panels drawn) readable. Fix the geometry
  in `svg(p)`, regenerate, rerun the hero tests.
- [X] T016 Run `python -m pytest -q tests/test_docs.py`; check the changed files for
  em-dashes, emojis and absolute local paths.
