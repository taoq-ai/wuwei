# Implementation Plan: the README hero shows the system in its true models

**Branch**: `585-hero-system` | **Spec**: `spec.md`

## Summary

Redraw `scripts/build-hero.py` as the agentic engineering flow, left to right: you and the
ranked queue, three seat lanes (build-check loop glyph, three gate dots, one fix-delta
loop), the PR stack with the shepherd's sweep orbit, you again with the cards and the phone;
two dashed guidance loops under the flow, one day return arrow over it, the band under the
hood. Timing from tables, derived labels computed from them. Regenerate both SVGs, rewrite
the hero tests, swap the alt sentence in README.md and docs/site/index.md. No runtime code.

## Technical Context

Python 3.11+ stdlib only. Dev script loaded by the tests through `_hero()` in
`tests/test_docs.py`. SMIL for timed changes, CSS for the always-on spin and heartbeat.

## Constitution Check

- I stdlib: `sys` and `pathlib` only. Pass.
- III: one helper per animation shape; both themes from one `svg(p)`. Pass.
- IV test first: the hero tests are rewritten and run red against the #569 SVGs before the
  generator changes. Pass.
- V ponytail: reuse `PAL`, `pct`, `clock`, `blink`, `track`, `walk`, `holds`, `item`,
  `text`, the phone, the clock and the `{key}` substitution; delete the track-only parts.
  Pass.
- #530 and #551: no guard, command or skill changes; the guard indicator says "caught",
  not "refused". No invariant row (nothing in 9.2 changes). Pass.

## Changes

### `scripts/build-hero.py` (target 260 to 315 lines, hard cap 320)

Keep unchanged: `T`, `PAL`, `A`, `SANS`, `BEAT`, `pct`, `clock`, `blink`, `walk`, `item`,
`text`, the `{key}` substitution, the `__main__` writer, the day clock (hour texts and bar)
and the phone drawing.

Change:
- `track(stops, lane)`: items no longer change lanes, so it is folded into `walk(stops)`,
  which samples x only (built: one helper fewer than planned).
- `at(place, lane)`: `return PLACES[place], LANE_Y[lane]`.
- `holds(place)` becomes `holds(place, lane=None)`: the same merge, filtered to one lane
  when given. One shared helper drives the build glyphs `(lane, 'build')`, the gate dots
  `(lane, 'gates')` and nothing else needs a variant.
- docstring: names the flow, not the track.

Redefine (new values below): `GATE`, `PHONE`, `INDICATORS`, `PLACES`, `LANE_Y`, `ITEMS`,
`STILL_K`, `ALT`.

Delete: `STATIONS`, `SIDING`, `LOW`, `FIX_Y`, `AMBER`, `WAIT`, `LABELS`, `SIDING_LABEL`,
`EXIT_LABEL`, `CARD`, `TICKER`, `ticker`, `station`,
`bend`, the `belt` class and keyframes, the track, fix lane and exit lane drawing, the
Shipped column, the six-indicator row.

Add tables (k is a fraction of the day; checked in a scratch run: lanes all busy from 0.22
to 0.74, every lane at the expected place at `STILL_K`):

```python
STAGES = [  # (name, small line, icon key, x of the pill centre)
    ('Specs and plan', 'you approve, the lead ranks', 'you', 130),
    ('Agent team', '3 seats in parallel lanes', 'team', 400),
    ('Gates', 'arch · quality · security', 'gate', 620),
    ('Pull requests', 'the shepherd sweeps', 'pr', 890),
    ('Review and merge', 'cards: your final say', 'you', 1075),
]
ICONS = {  # 24-unit line icons, stroke only; starting shapes, refine after rendering
    'you': 'M12 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8M4 21c0-4 4-6 8-6s8 2 8 6',
    'team': 'M5 9h14v10H5zM12 5v4M9 13v1M15 13v1M9 16h6',
    'gate': 'M12 3l7 3v5c0 5-3 8-7 10c-4-2-7-5-7-10V6zM9 12l2 2l4-4',
    'pr': 'M6 4v12M6 20a2 2 0 1 0 0-4a2 2 0 1 0 0 4M18 8a2 2 0 1 0 0-4a2 2 0 1 0 0 4M18 8c0 5-12 4-12 8',
}
QUEUE = ['rate limits', 'login fix', 'docs page', 'retry policy', 'cache keys']   # rank order
PLACES = {'off': <x at the lanes panel's left edge>, 'build': <x>, 'gates': <x>, 'PR': <x>}
LANE_Y = [<y lane 1>, <y lane 2>, <y lane 3>]
ITEMS = [  # (name, lane, [(k, place)]); an item fades out at its last stop
    ('rate limits', 0, [(0, 'off'), (.16, 'off'), (.19, 'build'), (.40, 'build'), (.43, 'gates'),
                        (.58, 'gates'), (.61, 'PR'), (.64, 'PR')]),
    ('login fix', 1, [(0, 'off'), (.19, 'off'), (.22, 'build'), (.44, 'build'), (.47, 'gates'),
                      (.72, 'gates'), (.75, 'PR'), (.78, 'PR')]),
    ('docs page', 2, [(0, 'off'), (.22, 'off'), (.25, 'build'), (.58, 'build'), (.61, 'gates'),
                      (.68, 'gates'), (.71, 'PR'), (.74, 'PR')]),
    ('retry policy', 0, [(0, 'off'), (.64, 'off'), (.67, 'build'), (.86, 'build'), (.89, 'gates'), (1, 'gates')]),
    ('cache keys', 2, [(0, 'off'), (.74, 'off'), (.77, 'build'), (1, 'build')]),
]
FIX = ('login fix', .50, .70)          # amber dot, amber outline and the fix loop, one span
PRS = [('#142 rate limits', .64, .80), ('#143 docs page', .74, .86), ('#144 login fix', .78, .90)]
PR_LINES = [('ping reviewer · CI green?', 'muted', .65, .78), ('merge at the gated head', 'atext', .80, .91)]
DECISIONS = [  # (asked, answered, open text or None, closed text, by the phone)
    (.30, .31, None, 'D-1 under mandate', False),
    (.44, .45, None, 'D-2 under mandate', False),
    (.52, .62, 'D-3 client wants Friday?', 'D-3 answered: Allow once', True),
]
GATE = (.02, .12, .17)                 # gate card on, question becomes "Approved · 3 seats", card off
PHONE = [(.02, .12, 'accent')] + [(a, b, 'warm') for a, b, _, _, phone in DECISIONS if phone]
GUARD = (.36, .40)
CLOSE = .92                            # report, retro, return arrow, steward, carried
STILL_K = .55                          # 13:55, the reduced-motion frame
LOOPS = ['a seat asks through a decision record', 'you answer from the phone, or the mandate answers']
DAY = "tomorrow's plan carries what was learned"
INDICATORS = ['guards: every call checked, 1 caught', 'heartbeat',
              'lead: discovery when the queue runs low', 'steward: retro at close, you promote']
```

A decision the mandate takes has no open text; its closed line shows from `answered`.

Derived helpers (small, used by the drawing and by the tests):
- `popped(name)`: the item's last `'off'` k, when it leaves the queue.
- `waiting()`: the `(on, off)` span while every lane is occupied and an item is still in
  the queue: from the third lane's entry to the last pop (0.22 to 0.74 with these tables).
  A lane is occupied from an item's `popped` k to its last stop k.
- `shipped()`: `[(k, n)]`, n merges by k, from `PRS`. `carried()`: the items whose last
  place is not `'PR'` (2).
- `asked()`: `f'asked today: {sum(phone)} of {len(DECISIONS)}'`.
A helper used once is inlined instead; keep only what the tests and the drawing share.

Drawing (viewBox 1200 by 640; starting geometry, adjust after rendering so nothing
overlaps; colours only through `{key}`):
- Header: wordmark and subtitle as today; clock text and bar top right as today.
- Return arrow (`id="day-loop"`), y about 112: from above stage 5 up, left across the flow,
  down onto stage 1's icon, arrowhead pointing down; `DAY` centred on it in muted; a lit
  accent copy (`id="day-loop-lit"`) in `live` blinks on from `CLOSE` to 1 and in `still` it is off. It never
  moves.
- Stage row: icon (`id="icon-<i>"`, a `<path>` with `fill="none"`, accent stroke, scaled
  about 1.4) centred above each pill; pill (rounded, accent stroke 2, panel fill, bold 15 to
  16 px name); small line under it in muted 12 px. Stages 2 and 3 sit above the lanes panel
  (over the build column and the gate column).
- Panels, drawn outside `live` and `still` so the first frame shows them: `panel-queue`
  (x 40 to about 220), `panel-lanes` (about 250 to 790), `panel-prs` (about 810 to 975),
  `panel-cards` (about 990 to 1160), `panel-band` (bottom). An arrow from each panel to the
  next (queue to lanes, lanes to PRs). Text in the cards panel at 12 px must fit its width.
- Queue: five pills "1 · rate limits" to "5 · cache keys" in `live`, each with
  `blink('opacity', '1', [(popped, 1, '0')])` so they are visible at k 0; "waits: CAP 3
  seats" (`id="waits"`) in warm, on over `waiting()`; the Morning gate card (title, question, approved
  line) at the panel's bottom over `GATE`; "answers a card now and then" from `GATE[2]`.
- Lanes: two light separators; small heads "build ⟲ check" and "raise PR" in muted;
  per lane a static muted loop glyph (`id="build-<lane>"`, an arc with an arrowhead) and an
  accent copy with class `spin` whose opacity blinks over `holds('build', lane)`; three
  gate dots (`id="gate-<lane>-<n>"`), static and muted, each with an accent copy in `live`
  whose opacity blinks over `holds('gates', lane)`, and a warm copy of lane 2's quality dot
  over `FIX`; the fix loop
  (`id="fix-loop"`): a dashed warm arc from the gate dots back over the login fix pill with
  an arrowhead, and "fix ×1 → delta", on over `FIX` only. Items: `item()` pills moved by
  `walk`, fading in at `popped` and out at their last stop; login fix's stroke warm over
  `FIX`.
- PR stack: "PRS" pills stacked top down, each on from raised to merged (`blink`); the
  sweep orbit (`id="sweep"`): a circle arc with an arrowhead, class `spin`, "sweep" in its
  centre; `PR_LINES`; "shipped today: N" as one text per value, each on over its span;
  "carried to tomorrow: N" from `CLOSE`; "overnight: sweeps, never merges" static.
- Cards: the phone (reuse the #569 drawing; screen lit over `PHONE`); one line per decision
  slot, the open text (when there is one) over (asked, answered) in warm, the closed text
  from answered to 1; `asked()` from the phone decision's asked k to 1.
- Guidance loops under the flow: `id="ask-loop"` from the lanes panel bottom down, right
  and up into the cards panel, `id="answer-loop"` from the cards panel down, left and up
  into the lanes; both dashed (`stroke-dasharray`) muted with arrowheads, a lit accent copy
  of each (`id="ask-loop-lit"`, `id="answer-loop-lit"`) blinking over each decision's asked (ask loop) and answered (answer loop) k, plus
  0.02; `LOOPS` labels centred on their horizontal runs.
- Band: four indicators (dot plus text). Guards dot warm over `GUARD`; heartbeat dot class
  `beat`; lead dot (`id="lead"`) accent over the last pop to plus 0.06; steward dot accent from `CLOSE`.
  `f'{clock(CLOSE)} close: report written, retro done'` right aligned, on from `CLOSE`.
- Every element a test reads by id (`fix-loop`, `waits`, `lead`, `ask-loop-lit`,
  `answer-loop-lit`, `day-loop-lit`) carries its timing `<animate>` as its first child, so
  the tests read it with `_value_at` as the #569 station test did.
  Ids are unique: a shape that animates is drawn static (muted, with its id when the tests
  pin the shape) outside both groups, lit in `live` (the timing id), and lit again without
  an id in `still` when the mid-day frame shows it. No SMIL element sits outside `live`.
- Arrowheads: one `<marker>` per colour in `<defs>` (muted, accent, warm); `href`s stay
  `#` only, so `url(#id)` references are fine.
- CSS: `.still{display:none}`, `.spin{animation:spin 1.6s linear infinite;transform-box:fill-box;transform-origin:center}`,
  `@keyframes spin{to{transform:rotate(360deg)}}`, the `beat` rule as today, and
  `@media (prefers-reduced-motion:reduce){.live{display:none}.still{display:inline}.spin,.beat{animation:none}}`.
  The only classes are `live`, `still`, `spin` and `beat`.
- Still group at `STILL_K`: queue pills 4 and 5 and "waits"; rate limits at gates (lane 1
  dots lit), login fix at gates in warm with the fix loop and its label, docs page at build
  with its glyph lit; D-1 and D-2 closed lines, D-3 open line in warm, phone screen warm,
  `asked()`; the clock "13:55" and the bar at 13:55. Everything the still group shows is
  computed from the tables at `STILL_K`, not typed.
- `<title>` "WUWEI: agentic delivery, one day", `<desc>` `ALT`.

`ALT` (one sentence):

> A ranked queue you approve feeds an agent team working three parallel lanes that loop
> build and check, every candidate passes the gates with at most one fix round, pull
> requests wait in a stack the shepherd sweeps until they merge, and you answer the odd
> card from the phone while guards, heartbeat, lead and steward work under the hood and
> each day's retro feeds tomorrow's plan.

### `tests/test_docs.py`

- `test_readme_install_and_hero` (line 131): the station word pin becomes the five stage
  names.
- `test_hero_files_match_their_generator` and `test_hero_variants_share_geometry_and_motion`:
  unchanged (lane items keep `animateMotion`).
- Replace `test_hero_is_a_day_on_a_track` with `test_hero_shows_the_system`; rewrite
  `test_hero_only_moves_forward`; replace `test_hero_items_wait_and_park` with
  `test_hero_queue_lanes_and_cards`. Contents in tasks.md. Keep `_hero`, `_smil` and
  `_value_at` as they are.

### `README.md`, `docs/site/index.md`

Only the hero `alt` changes to `ALT` (one in README, two in the index).

### `docs/site/assets/hero-light.svg`, `hero-dark.svg`

Regenerated with `python3 scripts/build-hero.py`.

## What must not change

- `PAL` values and the accent `#00C9A7`; the picture tags, asset paths and the
  `#only-light` and `#only-dark` suffixes; every other README and index line (#561 owns the
  README prose, including the stale Simple Icons credit).
- `test_hero_files_match_their_generator`, `test_hero_variants_share_geometry_and_motion`,
  `_hero`, `_smil`, `_value_at`; any runtime code under `cli/`; `tests/test_invariants.py`.

## Verification

- `python -m pytest -q tests/test_docs.py` (the file holds every hero test).
- Render both SVGs with `qlmanage -t -s 1400 -o <scratch dir> <svg>`; a scratch copy with
  the two display rules swapped for the mid-day frame; a scratch copy with the viewBox
  shifted right (for example `600 0 600 640`) to see the right panels the thumbnail crops.
  Check against the prototype and the owner's references: five stages left to right, pills
  with icons, two dashed loops under, one arrow over, the band, nothing overlapping, card
  lines inside their panel. Scratch files stay outside the repository.
