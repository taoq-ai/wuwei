# Feature Specification: the README hero is a day on a track

**Feature**: 569-hero-simple (GitHub issue #569)
**Created**: 2026-10-08, redesigned the same day after the owner's review of the first cut,
corrected the same day (forward only: the fix round is a diverter, not a step back)
**Status**: Ready for build (spec, plan, tasks, analysis)

## Promise

A newcomer who opens the README sees one working day of WUWEI in sixteen seconds: three work
items ride a three-lane track left to right through Plan, Build, Check, Review and Merge and
land in Shipped. Like bags on an airport belt, nothing ever comes back: the item that fails
review is diverted onto a fix lane, a siding under Review, where it is patched and
delta-checked while still moving right, then rejoins before Merge. Small labels switch on as
items reach a station, station pills light while an item is under them, the owner shows up
twice (the morning gate and one card on the phone), and an under-the-hood panel pulses as
guards, cards, the heartbeat, the shepherd, the lead and the steward do their work. A day
clock runs from 09:00 to 18:00. It reads as a sprint that runs without the owner pushing
it, not as a system diagram and not as a still loop.

## Root cause

- On `main`, `scripts/build-hero.py` (452 lines) draws every concept on one canvas: the
  Simple Icons paths in `ICONS` (line 22), eight tool rows with 24 logos in `ROWS` (line 43,
  eleven planned), the fix-round arrow, sweep, shepherd orbit, DM, phone pill, heartbeat and
  tier caption in `svg()` (line 312), and a paragraph of alt text from `tools_text()`
  (line 274). Each SVG is about 45 KB. The owner: overwhelming.
- The first cut in this worktree (uncommitted) swung to the other end: `STATIONS`
  (`scripts/build-hero.py` line 48) on one smooth closed loop built by `edge()` (line 51),
  one token (`TOK`, line 85) and one line of text in `svg()` (line 93), about 4 KB. The
  owner: "way too minimalist", "the cycle is not this smooth and a lot is happening under
  the hood", "more like a treadmill or sprint". A closed loop with one token cannot show
  parallel seats, a fix round, things switching on and off, or the work under the hood, so
  the drawing in `svg()` is replaced, not tuned.
- The second-round design drew the fix round as a step back from Review to Build (the
  prototype's first version). The owner corrected it: the process only goes forward, so a
  backwards move in any item's path is a defect, and the fix round must be its own lane.

## User scenarios

### US1: a newcomer sees a day happen, always moving forward (P1)

Given the README on GitHub, when the hero plays, then the newcomer sees a track with three
lanes and five stations, three named items moving right at different paces with pauses,
one item turning amber at Review and being diverted down a curved branch onto the fix lane,
pausing there for the patch and the delta check, then curving back onto its lane before
Merge, labels switching on and off above the stations, station pills lighting while an
item is under them, items landing one by one in Shipped, and the day clock advancing. No
item ever moves left.

### US2: the owner's part is small and visible (P1)

Given the hero, then the owner appears only twice: the Morning gate card at the start
("Approve today's plan as proposed?" switching to "Approved. 3 seats start (CAP 3).") which
then fades, and the phone whose screen lights while a card is open, with the card's one line
beside it ("D-3: client wants Friday. Allow once?"), going dark when answered.

### US3: the work under the hood is visible (P2)

Given the hero, then a panel under the track shows six indicators that pulse when their
event happens (guards, cards, heartbeat, shepherd, lead, steward) and a ticker of
timestamped event lines in day order, at most three visible at once.

### US4: reduced motion and both themes (P2)

Given a reader with reduced motion, then the hero shows one still mid-day frame (items at
Review, on the fix lane in amber, and at Check; the FIX label and the fix-lane label on; the
phone lit; two ticker lines) and nothing moves. Given light or dark mode, then the matching
SVG renders with the same geometry and motion.

## Acceptance scenarios

1. Given the regenerated hero, then it shows the track with three lanes, the five stations
   in order (Plan, Build, Check, Review, Merge), three moving items (rate limits, login fix,
   docs page), the fix lane as a siding under Review that rejoins before Merge with one item
   diverted onto it once, the Shipped column with "yesterday: 4 shipped, 1 carried", the
   Morning gate card and the phone, the under-the-hood panel with six indicators and the
   ticker, and the day clock from 09:00 to 18:00.
2. Given every item's stops and every `animateMotion` in the output, then the x position
   never decreases: nothing moves backwards.
3. Given `python3 scripts/build-hero.py`, then the committed `hero-light.svg` and
   `hero-dark.svg` match its output, the two differ only in colours, and the docs tests pass.
4. Given reduced motion, then every animated element sits in the `live` group or carries a
   class the reduced-motion rule stops, and the `still` group shows the mid-day frame.
5. Given each SVG, then it is under 40 KB, the generator is under 300 lines, and the picture
   carries no logos, no planned integrations and no brand name other than WUWEI.
6. Given README.md and docs/site/index.md, then the hero's alt text is one sentence equal to
   the SVG `<desc>`.
7. Given every SMIL animation in the output, then its `keyTimes` start at 0, end at 1, never
   decrease and match the count of its `values`, so no animation silently fails to run.
8. Given each station, then its highlight is on while an item is held under it.
9. Given the design check (FR-010), then one item (login fix) waits at Plan under "waits:
   CAP 3" with a dashed outline until a seat frees, one item (csv export) leaves Build down
   the exit lane to "parked, carried to tomorrow" and never rejoins, the waiting item takes
   the lane it freed, no two pills overlap at any moment, and the word "treadmill" appears
   in neither SVG nor the alt text.

## Requirements

- FR-001 One generator, `scripts/build-hero.py`, writes both themes from one drawing; the
  palettes are the existing `PAL` constants (dark as today).
- FR-002 The composition and the 16 s timing follow the owner's reference prototype (light
  theme, 1200x600, SMIL, the corrected version with the fix lane); the drawing is improved
  (alignment, spacing, type sizes, no overlaps), the concept is not reinvented.
- FR-003 Every timed element (item stops, labels, gate, phone, indicators, ticker, clock)
  takes its times from tables at the top of the generator; the shipped order, the station
  highlights and the ticker timestamps are derived from those tables, never typed twice.
- FR-004 The ticker timestamp of a line is the day clock at the moment the line fades in,
  so the ticker reads in day order and agrees with the clock.
- FR-005 Reduced motion: SMIL elements live only inside `<g class="live">`; CSS animations
  (belt chevrons, heartbeat) use classes the reduced-motion rule stops; `<g class="still">`
  holds the mid-day frame and is shown only under reduced motion.
- FR-006 Alt text and `<desc>`: one sentence (see Assumptions for the exact text).
- FR-007 The README and the docs index change only in the hero's alt text.
- FR-008 Forward only: an item's x never decreases. The fix round is a siding under Review:
  a curved branch off the item's lane, a short straight run where the item pauses for the
  patch and then the delta check, and a curved rejoin onto the same lane before Merge. The
  diverted item follows the drawn curve exactly, and the siding's dashes move right like
  the belts.
- FR-009 A station pill lights while an item is held under it (derived from the item
  stops).
- FR-010 Design check (owner, 2026-10-08): one item is held at Plan under the label "waits:
  CAP 3" until a lane frees, and one item is diverted off the track onto an exit lane
  ("parked, carried to tomorrow"), the counterpart of the fix diverter, so "1 carried" has a
  cause on screen. The exit lane branches down off the bottom lane at Build onto the same
  strip as the fix lane and never rejoins. The lane it frees is the one the waiting item
  takes. No two pills ever overlap. The word "treadmill" appears nowhere in the picture or
  the alt text.

## Assumptions

- The redesign comment and the correction comment on the issue replace the original
  Deliver and Acceptance sections; the first cut's deletions (ROWS, ICONS, the tool rows,
  `tools_text()`, the shipped-versus-planned tools test) and its test scaffolding stay; its
  drawing is replaced.
- The alt sentence is the prototype's `<desc>`, unchanged by the correction: "Work items
  move along a track through Plan, Build, Check, Review and Merge while guards, cards and
  the heartbeat work under the hood; you approve the plan once and answer a card
  from the phone." It says "you", not "the owner", because the docs pages address the reader (#362, test_pages_address_the_reader).
- The diverted item (login fix) rides the bottom lane and the fix lane sits below the three
  lanes, so the branch never crosses another lane. In the prototype login fix rides the
  middle lane and its siding cuts into the bottom lane, where its pill overlaps docs page at
  Review (about k 0.60 to 0.66). Lanes top to bottom: rate limits, docs page, login fix.
- The reduced-motion frame shows login fix on the fix lane, not at Build: the issue's
  "Build (amber)" predates the forward-only correction.
- Station labels keep the prototype's texts and timing, including "quality: FIX, diverted to
  the fix lane" above Review and "one fix round, then a delta check; forward only" under the
  siding. A label shows while the leading item rides into its station, as in the prototype.
- The prototype puts the fix-lane label at y 412 on the panel's top edge and the Build label
  over the phone's lower edge; both move so nothing overlaps.
- The guard indicator reads "guards: 1 caught" (the prototype says "1 refused") and its
  ticker line says the guard caught a force push and the seat pushed the branch without
  --force. Under the default guarded posture (#530, #555) a force push is a warning or a
  card, not a refusal, so "refused" would misstate the product; "caught" is true under every
  posture.
- The phone's card line names D-3 (the prototype shows D-2): D-3 is the Consequential
  decision the ticker says was answered from the phone; D-2 is the Routine one taken under
  mandate.
- The prototype's hand-typed ticker timestamps are out of day order (10:40 after 11:03) and
  disagree with the clock. They are derived instead (FR-004), floored to five minutes.
- The prototype's guard indicator pulses twice with one guard event; it pulses once.
- The cards indicator lights in the warm colour while the D-3 card is open, matching the
  phone screen (the prototype used the accent).
- The day clock shows the current hour (09:00 to 17:00) over a thin bar that fills across
  the loop, with 18:00 at the bar's right end.
- Items fade out as they land and their Shipped pill appears, instead of the moving pill
  overlapping the Shipped column.
- "Under 40 KB" means under 40000 bytes; "under 300 lines" counts the generator's lines.
- The Simple Icons credit in README Acknowledgements and NOTICE now credits glyphs the hero
  no longer uses. The orchestrator note limits README edits to the alt text (#561 edits README
  prose later), so the credit stays; listed under Deferred.
- The feature directory already existed from the first cut, so `create-new-feature.sh` was
  not run again; the branch stays 569-hero-simple.
- tests/test_invariants.py does not exist on this base and the item adds no product rule,
  so no invariant row is added.

- "yesterday: 4 shipped, 1 carried" stays verbatim (the owner's text). The parked item is
  today's carry, so the line and the exit lane tell the same story a day apart; rewording
  it is the owner's call, not this item's.

- Design check, four items instead of five: the note asks for "a fourth item that waits" and
  "a fifth that is parked". Under CAP 3 only three items hold seats; a waiting item gets a
  seat only when one frees, and the only seat that frees before late afternoon is the parked
  item's. So the parked item is a new fourth item (csv export) on the bottom lane, and the
  waiting item is login fix, which takes the freed lane and then takes the fix round. A
  separate fifth item would need a second free seat, which the day's timing does not have.
  The plan line reads "4 items, 3 seats (CAP 3)". The waiting pill is dimmed while it waits.

## Deferred

- Remove the Simple Icons credit from README Acknowledgements, NOTICE and the pin in
  `test_notice_credits_match_readme_acknowledgements` (fits #561 or a follow-up issue).
