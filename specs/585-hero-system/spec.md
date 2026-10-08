# Feature Specification: the README hero shows the system in its true models

**Feature Branch**: `585-hero-system`

**Created**: 2026-10-08

**Status**: Draft

**Input**: Issue #585, "docs(hero): the README hero shows the system in its true models: a
ranked queue, three seat lanes with the build-check loop and the gate-fix-delta loop drawn
as loops, a PR queue the shepherd sweeps, a cards queue for the owner with the phone, and
the under-the-hood band with the day loop", plus the owner's comment of 2026-10-08 with four
reference images (composition from the agentic SE workflow figure, style from the dark hub
diagram, the day return arrow from the agile lifecycle, the naming discipline of the
components chart) and the orchestrator notes.

## Root cause

`scripts/build-hero.py` (the #569 version) draws one five-station track. `STATIONS` (line
22) and `PLACES` (lines 23 and 24) put every part of the day on that track, the fix round is
a siding diverter (`SIDING`, `LOW`, `FIX_Y`, lines 25 to 27; the path at lines 161 and 162),
and `svg()` (lines 160 to 254) draws no ranked queue, no build-check loop, no PR queue or
shepherd sweep, no cards queue and no owner on both ends. The owner's words: it "doesn't show
the shepherd and also how the build/review/fix cycle works", and the queues are missing. The
hero tests in `tests/test_docs.py` (`test_hero_is_a_day_on_a_track` at line 851,
`test_hero_only_moves_forward` at 901, `test_hero_items_wait_and_park` at 934 and the
station pin in `test_readme_install_and_hero` at 131) lock that track in, so the picture
cannot change without them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reader sees how an agentic engineering flow runs (Priority: P1)

A reader opens the README. Left to right, as in the agentic SE workflow figure, they see:
you set the work (the morning gate and a ranked queue), an agent team works three lanes in
parallel (each lane loops build and check, then passes three gates, with at most one fix
round drawn as a loop), pull requests wait in a stack the shepherd sweeps until they merge,
and you keep the final say through cards on the phone. Two dashed loops under the flow
carry the questions and answers; one return arrow over the flow carries the day into
tomorrow's plan; a band underneath shows guards, heartbeat, lead and steward. Large shapes,
few words, one accent.

**Why this priority**: it is the issue; the owner rejected the track because it hides the
queues, the loops and the shepherd.

**Independent Test**: regenerate both SVGs, run the hero tests in `tests/test_docs.py`, and
render both themes and the mid-day frame to PNG.

**Acceptance Scenarios**:

1. **Given** the regenerated hero, **then** the five parts are visible in their shapes: a
   stack (the ranked queue), three lanes with a loop glyph and three gate dots each, a stack
   with an orbit (pull requests and the shepherd's sweep), a queue with a phone (cards),
   and a band (under the hood).
2. **Given** the animation, **then** items only move forward (left to right), the fix round
   shows as a dashed loop over the item at the gates while the item holds still, and labels
   switch on and off with the events of the day.
3. **Given** both themes, **then** both render from one generator with the same geometry
   and motion, and each SVG is under 40 KB.
4. **Given** reduced motion, **then** the hero shows the mid-day frame: the queue with two
   items left and "waits", lane 1 at the gates, lane 2 amber with the fix loop on, lane 3
   building, D-3 open with the phone lit.
5. **Given** the docs tests, **then** they pass.

### User Story 2 - The first frame already shows the system (Priority: P1)

**Why this priority**: GitHub shows the image before a reader waits for anything to move.

**Independent Test**: parse the SVG; the panels, stage pills, lanes, queue items, PR panel
and cards panel are drawn either outside the animated groups or with an initial opacity of 1.

**Acceptance Scenarios**:

1. **Given** the README on GitHub, **then** the first frame already shows the queue (with
   its five ranked items), the lanes, the PR queue and the cards panel, so a reader sees the
   system before anything moves.

### Edge Cases

- A lane frees while the queue is empty: nothing starts; the lead's discovery indicator
  lights instead.
- Two items in one lane never overlap: the next item enters a lane only when the previous
  one has left it.
- The close frame comes while items are still in lanes: they are counted as carried to
  tomorrow, not shown as moving back.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The hero is drawn left to right in five stages named in the reader's words,
  each a pill with one line icon above it (drawn as SVG paths in the generator, no icon
  library, no brand glyph) and one small line under it that may use WUWEI's terms once:
  `Specs and plan` (you approve, the lead ranks), `Agent team` (3 seats in parallel lanes),
  `Gates` (arch · quality · security), `Pull requests` (the shepherd sweeps), `Review and
  merge` (cards: your final say). Each stage name is at most three words; each small line
  at most six. The first and last stage carry the same person icon (you at both ends).
- **FR-002**: Queue (stage 1, a stack): five numbered items in rank order (1 rate limits,
  2 login fix, 3 docs page, 4 retry policy, 5 cache keys). The top one pops into a lane when
  a lane frees; "waits: CAP 3 seats" shows while every lane is busy and an item waits; the
  Morning gate card sits at the bottom of this panel at the start (question, then "Approved
  · 3 seats"), then fades, and the line "answers a card now and then" stays for you.
- **FR-003**: Lanes (stages 2 and 3): three lanes in parallel, each carrying one item left
  to right through build, gates and "raise PR". Each lane has a "build ⟲ check" loop glyph
  that lights and spins while its lane builds, and three gate dots (arch, quality, security)
  that light while its lane is at the gates. One item (login fix, lane 2) gets one fix
  round: its quality dot and its outline turn amber and a dashed arc from the gates back
  over the item, labelled "fix ×1 → delta", is on only during the round; the item holds at
  the gates and then moves right. "raise PR" hands the item to the PR stack.
- **FR-004**: Pull requests (stage 4, a stack with an orbit): each raised item appears as
  "#142 rate limits" and so on at the moment it leaves its lane; a circular sweep arrow
  labelled "sweep" orbits the stack; "ping reviewer · CI green?" and "merge at the gated
  head" switch on and off; "shipped today: N" steps up by one at each merge, derived from
  the PR table; "carried to tomorrow: N" shows at close, N the items still in lanes;
  "overnight: sweeps, never merges" stays.
- **FR-005**: Review and merge (stage 5, a queue with the phone): "D-1 under mandate" and
  "D-2 under mandate" appear as they happen; "D-3 client wants Friday?" appears in amber with
  the phone screen lit, then becomes "D-3 answered: Allow once"; "asked today: 1 of 3"
  shows from the moment D-3 is asked, both numbers derived from the decision table.
- **FR-006**: Two dashed guidance loops under the flow, from a lane to the cards and back:
  "a seat asks through a decision record" and "you answer from the phone, or the mandate
  answers". Each lights when a decision is asked or answered.
- **FR-007**: One return arrow over the whole flow, from the last stage back to the first,
  labelled "tomorrow's plan carries what was learned". It lights at close, when "<clock>
  close: report written, retro done" switches on in the band; it does not move.
- **FR-008**: Under the hood (a band): four indicators that light on their events:
  "guards: every call checked, 1 caught" (amber pulse once), "heartbeat" (pulsing all
  day), "lead: discovery when the queue runs low" (lights when the queue empties),
  "steward: retro at close, you promote" (lights at close). The day clock at the top right
  runs 09:00 to 18:00 as today.
- **FR-009**: Forward only: every item's x never decreases, in the tables and in every
  `animateMotion`. Loops are drawn only where the system loops: build-check, the one
  fix-delta round, the shepherd sweep, the day return arrow and the two guidance loops.
- **FR-010**: Timing comes from tables at the top of the generator (`ITEMS`, `PRS`,
  `DECISIONS`, `FIX`, `CLOSE` and the rest); every derived label (waits, shipped, carried,
  asked, the close stamp) is computed from those tables, never typed twice.
- **FR-011**: Reduced motion hides the animated group and shows the mid-day frame of
  acceptance 1.4 at `STILL_K` (13:55); every animated class is stopped in the reduced-motion
  block; the still frame contains no `<animate`.
- **FR-012**: Both themes come from one `svg(p)` with `PAL` unchanged; one accent
  (`#00C9A7`) plus the existing warm colour for the fix round and the consequential card.
  No logos, no brands, no planned integrations, never the word treadmill.
- **FR-013**: `ALT` (the `<desc>`, the README alt and both index alts) is one sentence
  naming the five parts: the ranked queue, the agent team in parallel lanes, the gates,
  pull requests and the shepherd, the cards for you, and the band under the hood.
- **FR-014**: Budgets: each SVG under 40000 bytes; the generator under 320 lines.

### Key Entities

- **Item**: name, lane, stops `(k, place)` with place in off, build, gates, PR.
- **PR**: label, raised k (equals its item's last stop), merged k.
- **Decision**: id, asked k, answered k, open text, closed text, answered by you or by the
  mandate.

## Success Criteria *(mandatory)*

- **SC-001**: The hero tests in `tests/test_docs.py` pass against the regenerated SVGs.
- **SC-002**: The rendered light, dark and mid-day PNGs show the five stages left to right,
  two dashed loops under the flow, one return arrow over it and the band, with no
  overlapping text.
- **SC-003**: Static labels are the twelve named parts (five stages, two guidance loops,
  the return arrow, four indicators) plus each stage's small line and the station heads;
  everything else switches on and off.

## Assumptions

- The owner's reference-image comment refines the storyboard: the five storyboard panels
  are rearranged into the left-to-right story (owner left, team middle, owner right), the
  panel headings become the five stage pills, and the storyboard's lane caption ("a lane
  frees ... a seat never asks you") and the day line in the band are dropped: the first is
  drawn by the queue and the guidance loops (and "a seat never asks you" contradicts the
  owner's "a seat asks through a decision record"), the second is the return arrow.
- Stage names: the owner listed six reader words (specs and plan, agent team, gates, pull
  requests, review and merge, learn); five are the stages and "learn" is carried by the
  return arrow's label.
- Card lines are shortened ("D-1 under mandate" for "D-1 Routine · taken under mandate",
  "D-3 client wants Friday?", "D-3 answered: Allow once") so they fit a narrow right panel
  at a readable size; the owner asked for large type and few words.
- "shipped today" steps 0, 1, 2, 3 at each merge rather than the storyboard's 0, 2, 3: the
  prototype's counter ran ahead of its merges. Derived from the PR table.
- "carried to tomorrow: 2" replaces "parked, carried to tomorrow: 1": at close retry
  policy and cache keys are still in lanes, and nothing in this story is parked by the
  owner. The fifth queue item starts when docs page frees its lane, so "a lane frees, the
  next ranked item starts" holds all day, and the emptied queue is what lights the lead.
- The close stamp is derived from the clock (17:15 at `CLOSE` 0.92) rather than the
  storyboard's 17:50, so the close frame stays on screen long enough to read.
- "guards: every call checked, 1 caught" replaces "1 refused": under the default posture a
  guard is a warning or a card, never a refusal (#530), as #569 already decided.
- The fix loop and the amber colour share one span (`FIX`); the item holds at the gates for
  the whole round, then the dots turn green and it moves right.
- The build glyph spins through CSS (`.spin`, always) and only its lit copy blinks on, so
  "spins while the lane builds" needs no per-span rotate animation.
- The day clock stays at the top right (storyboard; it is the #569 code); the band holds the
  four indicators and the close line.
- The dark palette stays the #569 `PAL` (dark green ground, accent `#00C9A7`); the
  reference image's near-black is not copied, because the notes say to reuse the palette.
- viewBox 1200 by 640, as the prototype.
- Deferred: README Acknowledgements and NOTICE still credit Simple Icons glyphs "in the
  hero", which #569 already removed; the notes limit README edits to the alt text, so the
  credit is left for #561 (README prose) or a follow-up.
- No runtime code, guard, command or rule changes, so no new invariant row in design 9.2
  or in `tests/test_invariants.py`; #530 and #551 are not touched.
