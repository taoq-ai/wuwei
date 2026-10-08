# Tasks: 569-hero-simple (a day on a track, forward only)

The first cut's tasks (one loop, one token) and the second round's step back to Build are
superseded by the owner's redesign and correction comments. The first cut's deletions stay
(ROWS, ICONS, the tool rows, `tools_text()`, the tools test, the alt pins in
`test_readme_lead_and_limits`); its drawing is replaced. All tests are written and seen
failing before the generator changes.

## Phase 1: tests first (all in tests/test_docs.py)

- [X] T001 Test: replace `test_hero_is_one_simple_loop` with `test_hero_is_a_day_on_a_track`
  asserting the five stations in order, the three item names, `Shipped` and "yesterday: 4
  shipped, 1 carried", the six indicator texts, the gate card texts, the phone line, the
  clock texts 09:00 and 18:00, no tool or brand names, only `#` hrefs, each SVG under 40000
  bytes and the generator under 300 lines. Change the station pin in
  `test_readme_install_and_hero` to Plan, Build, Check, Review, Merge.
- [X] T002 Test (same test): README alt and both index alts equal `hero.ALT`, one sentence,
  equal to each SVG's `<desc>`.
- [X] T003 Test (same test): every ticker line appears with stamp `clock(on)`, the stamps
  strictly ascend, two lines in one slot never overlap (so at most three are on), and every
  SMIL `keyTimes` starts at 0, ends at 1, never decreases and matches its `values` count.
- [X] T004 Test (same test): every SMIL element has an ancestor `<g class="live">`; every
  class in the file appears in the reduced-motion block; the `still` group holds the three
  item names, "quality: FIX, diverted to the fix lane", `SIDING_LABEL` and the D-3 line.
- [X] T005 Test: add `test_hero_only_moves_forward`: `PLACES[place]` never decreases along
  any item's stops; the x of every `animateMotion` `values` pair never decreases in either
  SVG; exactly one item visits the `SIDING` places, rides the bottom lane and runs Review,
  patch, delta check, Merge; both SVGs hold "fix lane" and `SIDING_LABEL`.
- [X] T006 Test (same test as T005): for each station the animate inside
  `id="lit-<station>"` is on at the midpoint of every hold there (FR-009).
- [X] T007 Run `python -m pytest -q tests/test_docs.py -k hero` and see T001 to T006 fail
  on the first-cut output (missing stations, items, tables, `live` group, fix lane).

## Phase 2: implementation

- [X] T008 Implement, scripts/build-hero.py: delete the loop geometry and token helpers; add
  the tables (`PLACES`, `SIDING`, `LANE_Y`, `FIX_Y`, `ITEMS` with login fix on the bottom
  lane, `LABELS`, `SIDING_LABEL` and the rest), `clock`, `blink`, `at`, `walk` (eased
  samples on a lane change), `bend`, `holds`, `item`, the new `ALT`, the station highlights,
  the fix lane path, the `live` and `still` groups, the CSS and the drawing in `svg(p)` per
  plan.md. Regenerate docs/site/assets/hero-light.svg and hero-dark.svg with
  `python3 scripts/build-hero.py`. T001, T003 to T006 pass.
- [X] T009 Implement, README.md and docs/site/index.md: set the hero alt to `ALT`; nothing
  else in either file changes. T002 passes.
- [X] T010 Run `test_hero_files_match_their_generator` and
  `test_hero_variants_share_geometry_and_motion` unchanged; both pass.

## Phase 2b: design check (FR-010, added after the spec)

- [X] T013 Test: add `test_hero_items_wait_and_park`: exactly one item ends at `parked`, it
  rides the bottom lane and leaves from Build; the label "waits: CAP 3" sits on Plan and is
  on while an item on that lane holds at Plan, and that item leaves Plan only after the
  parked item has left the lane; both SVGs hold "exit lane" and "parked, carried to
  tomorrow"; no two visible pills overlap at any k (sampled from `track`); "treadmill"
  appears in neither SVG nor the alt. Run it and see it fail.
- [X] T014 Implement: add csv export and the exit lane, move login fix behind it as the
  waiting item, the Plan label, `EXIT_LABEL`, the ticker line and "4 items" in the plan line.
  T013 passes. Covers acceptance 9.

## Phase 3: verification

- [X] T011 Render both SVGs, a still-frame copy and a copy frozen at k 0.57 (login fix on
  the divert bend) to PNG with `qlmanage` into a scratch directory outside the repository;
  check the diverter reads as a curved branch off the bottom lane with the amber pill on it
  and the rejoin before Merge; compare with the prototype and fix alignment, spacing and
  overlaps in `svg(p)` (phone versus Build label, siding label versus panel, items versus
  each other and the Shipped column); regenerate and rerun the hero tests.
- [X] T012 Run `python -m pytest -q tests/test_docs.py`, then the full suite in the
  background; check the changed files for em-dashes, emojis and absolute local paths.
