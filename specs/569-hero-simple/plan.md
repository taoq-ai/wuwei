# Implementation Plan: the README hero is a day on a track

**Branch**: `569-hero-simple` | **Spec**: `spec.md`

## Summary

Replace the drawing in `scripts/build-hero.py` with a port of the owner's corrected
reference prototype (three-lane track, five stations, a fix lane that is a siding under
Review, three items that only ever move right, Shipped column, gate card, phone,
under-the-hood panel, day clock), driven by timing tables at the top of the file.
Regenerate both SVGs, rewrite the hero content test, and swap the alt sentence in README.md
and docs/site/index.md. No runtime code changes.

## Technical Context

Python 3.11+ stdlib only. The generator is a dev script; tests load it with `_hero()` in
`tests/test_docs.py` and compare its output with the committed files.

## Constitution Check

- I stdlib: the generator imports only `sys` and `pathlib`. Pass.
- III one behaviour one function: one helper per animation shape (see below); both themes
  come from one `svg(p)`. Pass.
- IV test first: the content test is rewritten and fails on the first-cut output before the
  drawing changes. Pass.
- V ponytail: tables plus five small helpers; the first cut's curve, token and timeline
  helpers are deleted with the loop. Pass.
- #530 and #551: no guard, command or skill changes. The picture does not show a refusal
  under the default posture (guards: 1 caught). Pass.

## Changes

### `scripts/build-hero.py` (rewrite of the drawing, target 200 to 280 lines)

Keep: the docstring (updated to name the track), `PAL` (values unchanged; drop a key only if
no drawing uses it), `pct()`, the `{key}` placeholder substitution at the end of `svg()`,
the `__main__` writer, and `ALT` (new sentence, spec Assumptions).

Delete: `math`, `bez`, `blen`, `f`, `Seg`, `C`, `path`, the loop `STATIONS`, `pts`, `edge`,
`EDGES`, `Tok`, `motion`, `TOK`, `LINE`, `EASE`, `LIN`, `V`, the halo gradient, the glow and
the token.

Add at the top, as plain data (all times are fractions of `T = 16.0` seconds):

```python
STATIONS = ['Plan', 'Build', 'Check', 'Review', 'Merge']
PLACES = {'off': -140, 'Plan': 125, 'Build': 318, 'Check': 515, 'Review': 708, 'patch': 770,
          'delta check': 840, 'Merge': 900, 'Shipped': 1095}   # x of a pill's centre
SIDING = ('patch', 'delta check')           # places on the fix lane; every other place is on the item's lane
LANE_Y, FIX_Y = [230, 282, 334], 384        # lane centres top to bottom; the fix lane sits under the bottom lane
ITEMS = [  # (name, lane, [(k, place)]); the last stop is Shipped and holds to k 1
    ('rate limits', 0, [(0, 'off'), (.13, 'off'), (.17, 'Plan'), (.2, 'Plan'), (.3, 'Build'), (.33, 'Build'),
                        (.4, 'Check'), (.43, 'Check'), (.52, 'Review'), (.7, 'Review'), (.78, 'Merge'),
                        (.8, 'Merge'), (.86, 'Shipped')]),
    ('docs page', 1, [(0, 'off'), (.17, 'off'), (.21, 'Plan'), (.28, 'Plan'), (.38, 'Build'), (.42, 'Build'),
                      (.5, 'Check'), (.53, 'Check'), (.6, 'Review'), (.74, 'Review'), (.82, 'Merge'),
                      (.84, 'Merge'), (.9, 'Shipped')]),
    ('login fix', 2, [(0, 'off'), (.15, 'off'), (.19, 'Plan'), (.24, 'Plan'), (.34, 'Build'), (.37, 'Build'),
                      (.44, 'Check'), (.47, 'Check'), (.53, 'Review'), (.56, 'Review'), (.59, 'patch'),
                      (.66, 'patch'), (.69, 'delta check'), (.78, 'delta check'), (.84, 'Merge'),
                      (.88, 'Merge'), (.93, 'Shipped')]),
]
AMBER = (.54, .80)                          # login fix is amber from the FIX verdict until it has rejoined
LABELS = [('Build', 'tests first, then the code', 'atext', .2, .3),
          ('Check', 'fast checks green', 'atext', .33, .4),
          ('Review', 'arch · quality · security', 'atext', .43, .52),
          ('Review', 'quality: FIX, diverted to the fix lane', 'warm', .54, .63),
          ('Merge', 'merged at the gated head', 'atext', .7, .78)]
SIDING_LABEL = ('one fix round, then a delta check; forward only', .6, .78)
GATE = (.02, .125, .2)                      # card on, question becomes "Approved...", card off
PHONE = [(.02, .12, 'accent'), (.56, .66, 'warm')]   # screen lit: gate open, then the D-3 card
CARD = (.56, .66)                           # "D-3: client wants Friday. Allow once?"
INDICATORS = [('guards: 1 caught', 'warm', [(.36, .39)]), ('cards: 1 open', 'warm', [(.56, .66)]),
              ('heartbeat', None, []), ('shepherd: PR #142', 'accent', [(.68, .8)]),
              ('lead: 4 candidates ranked', 'accent', [(.1, .17)]), ('steward: retro', 'accent', [(.94, .98)])]
TICKER = [  # (on, off, slot, text), in day order; the stamp is clock(on)
    (.14, .30, 0, 'plan approved: 3 items, 3 seats (CAP 3), queue ranked by WSJF'),
    (.37, .52, 1, 'guard caught a force push; the seat pushed the branch without --force'),
    (.45, .56, 2, 'decision D-2 (Routine) taken under mandate: keep the retry, recorded for you'),
    (.55, .70, 0, 'review: quality FIX on login fix; diverted to the fix lane, one round, then a delta check'),
    (.67, .82, 2, 'decision D-3 (Consequential) answered from the phone: Allow once'),
    (.71, .86, 1, 'PR #142 merged at the gated head; required checks green; branch deleted'),
    (.94, .98, 0, 'close: report written, retro done, 2 rule changes proposed for you'),
]
STILL = {'rate limits': 'Review', 'docs page': 'Check', 'login fix': 'patch'}   # the reduced-motion frame
```

The item timings are the corrected prototype's (its login fix path: Review, a curve down to
the siding, pause, along, pause, a curve up to Merge), with the prototype's translate
offsets converted to pill centres. Lanes are reordered (login fix to the bottom) so the
siding crosses no lane; spec Assumptions.

Helpers (each used several times; nothing else):

- `clock(k)`: `'HH:MM'` for 09:00 plus `k * 9` hours, floored to five minutes; compute the
  minutes as `int(round(k * 540, 6))` so float error never floors a whole value down. Used
  by the ticker stamps. The day clock's hour texts are `f'{h:02d}:00'` for h 9 to 17, each
  shown from k `(h - 9) / 9` to `(h - 8) / 9`, built from the hour, not through `clock`.
- `blink(attr, off, spans)`: one `<animate>` whose value is `off` except inside each
  `(on, off_k, value)` span, with a 0.01 ramp; `keyTimes` from 0 to 1 (a span ends by 0.98
  or at exactly 1, which holds the value to the end of the loop with no ramp; the Shipped
  pills and the item fade-outs use that). Drives every label, gate line, ticker line,
  indicator, phone screen, station highlight, the amber stroke, item fade-outs and the
  Shipped pills.
- `at(place, lane)`: `(x, y)` of a place for an item on `lane`: `x = PLACES[place]`, `y =
  FIX_Y` for a `SIDING` place, else `LANE_Y[lane]`.
- `walk(stops, lane)`: one `<animateMotion>` with `values="dx,dy;..."` relative to the pill
  drawn at `(0, LANE_Y[lane])`, matching `keyTimes`, `calcMode="linear"`. Where two
  consecutive stops differ in y, it inserts 8 samples of the bend: x linear and y eased by
  `3t^2 - 2t^3`, keyTimes spread evenly between the two stops. animateMotion keeps the
  existing `test_hero_variants_share_geometry_and_motion` pin unchanged.
- `bend(x0, y0, x1, y1)`: the SVG fragment `C` for the same curve: a cubic with control
  points `(x0 + dx/3, y0)` and `(x0 + 2dx/3, y1)`, which is exactly x linear and y eased by
  `3t^2 - 2t^3`, so the moving pill follows the drawn branch. Used twice (divert and rejoin)
  in the siding path; `walk` and `bend` share the one curve definition in a comment.
- `holds(place)`: the `(on, off)` spans where any item's consecutive stops sit at `place`,
  merged where they overlap or touch within 0.02. Feeds the station highlights (FR-009).
- `item(name, lane, x, y, colour)`: the pill (rect plus centred text), reused by the live
  items and the still frame.

Drawing, `svg(p)`, viewBox 1200 by 600, system font stack as today, colours only through
`{key}`. Starting geometry (adjust after rendering; the rule is that nothing overlaps):

- Header: `无为 WUWEI` (WUWEI in `atext`) at baseline 58 and the subtitle at 86, "A team of
  agents runs your delivery day. You approve the plan and answer the odd card." Day clock
  top right: the hour text, a thin bar that fills over the loop (`<animate
  attributeName="width">` inside `live`), "18:00" at its right end.
- Owner row (y 104 to 160): the Morning gate card (x 40, 250 by 56: title, question,
  approved line) and the phone (x 316, 30 by 50) with "you, on the phone" and the card line
  to its right. Its bottom stays above the label row, which the prototype's phone overlaps.
- Label row: baseline 172, each label centred on its station's x.
- Stations: pills 26 high at y 180 centred on `PLACES[station]`, with dashed guides down the
  track; above each pill a highlight copy with `id="lit-<station>"` inside `live`, whose
  opacity blinks over `holds(station)`.
- Track: surface panel x 40 to 1000, y 194 to 408; lane separators between lanes; chevrons
  on each lane moving right by CSS (`.belt`, three durations through
  `style="animation-duration:..."`), clipped to the track (the clip-path sits on an outer
  group, the moving `.belt` group inside it, so the clip does not move).
- Fix lane: one dashed warm path `M 708 334` + `bend` to `(770, 384)` + `L 840 384` +
  `bend` to `(900, 334)`, built from `PLACES`, `LANE_Y[2]` and `FIX_Y`, with class `belt` so
  its dashes move right too. A static "fix lane" caption on the fix strip left of the
  branch, clear of the diverting pill. `SIDING_LABEL` centred under the siding between the
  track and the panel (the prototype puts it on the panel's top edge).
- Items: three pills, each in `live` with `walk`, a fade-out `blink` at its last stop's k,
  and login fix with an amber stroke `blink` over `AMBER`. Lanes top to bottom: rate limits,
  docs page, login fix.
- Shipped column (x 1030): title, three pills appearing in derived arrival order (sort
  ITEMS by their last stop's k), and "yesterday: 4 shipped, 1 carried".
- Under the hood (panel y 436 to 586): title "UNDER THE HOOD", six indicators (dot plus
  text; the heartbeat dot pulses by CSS `.beat`, the others by `blink` on `fill` from muted
  to their colour), three ticker slots in a monospace face, each line `clock(on) + '  ' +
  text`.
- Groups and classes: every SMIL element sits inside `<g class="live">`. `<g class="still">`
  draws the mid-day frame. Anything that animates (items, Shipped pills, labels, station
  highlights, gate, phone screen and line, indicator dots, ticker lines, clock text and bar)
  is drawn in `live` with its animation and, when the frame shows it, again in `still` in
  its mid-day state. The still frame: rate limits at Review, docs page at Check, login fix
  on the fix lane at `patch` in amber (per `STILL` and `at`), Review and Check lit, the
  labels "quality: FIX, diverted to the fix lane" and `SIDING_LABEL`, the phone lit warm
  with the D-3 line, the cards indicator lit, ticker lines D-2 and the FIX line, clock
  "14:00" with the bar at 14:00's position. Static parts (track, lanes, fix lane, stations,
  Shipped title, panel, indicator texts) are drawn once outside both groups. The only
  classes in the file are `live`, `still`, `belt` and `beat`.
- CSS: `.still{display:none}`, the `belt` and `beat` keyframes, and
  `@media (prefers-reduced-motion:reduce){.live{display:none}.still{display:inline}.belt,.beat{animation:none}}`.
- `<title>` "WUWEI: a day of delivery", `<desc>` = `ALT`, `role="img"` and
  `aria-labelledby` as today.

### Design check additions (FR-010, built after this plan was written)

- `ITEMS` gains csv export on the bottom lane: Plan, Build, then down an exit lane to
  `parked` (x 440 on the diverter strip, `LOW = SIDING + ('parked',)`), where it greys and
  fades. login fix follows it on the same lane, waits at Plan for the freed seat (`WAIT`,
  dashed outline, label "waits: CAP 3"), then runs as before from Build on.
- The exit lane is drawn like the siding (`bend` from Build, a dashed `belt` run, an end
  bar, caption "exit lane"); `EXIT_LABEL` "parked, carried to tomorrow" sits under it.
- The plan ticker line reads "4 items"; a ticker line for the parked item is added.
- `track(stops, lane)` returns the `(k, x, y)` samples that `walk` formats, so the tests can
  check that no two pills overlap.
- "yesterday: 4 shipped, 1 carried" is drawn on two lines so it fits the Shipped column.
- New test `test_hero_items_wait_and_park`.

### `tests/test_docs.py`

- `test_readme_install_and_hero`: the station word pin becomes
  `('Plan', 'Build', 'Check', 'Review', 'Merge')`; other pins unchanged.
- Replace `test_hero_is_one_simple_loop` with `test_hero_is_a_day_on_a_track`, reading the
  module tables and both SVGs: README and both index alts equal `ALT`, one sentence, equal
  to `<desc>`; the station texts in order; the three item names; `Shipped` and the
  yesterday line; the six indicator texts; every ticker line with its derived stamp,
  stamps strictly ascending, and no two overlapping lines in one slot (so at most three
  are on); the gate texts and the phone line; the clock texts 09:00 and 18:00; every SMIL
  element has an ancestor with class `live`; every class used appears in the
  reduced-motion block; the still group holds the three item names, the FIX label, the
  siding label and the D-3 line; every `keyTimes` starts at 0, ends at 1, never decreases
  and matches its `values` count; no tool or brand name (Linear, Jira, GitHub, Claude,
  Codex, Slack, Notion, Confluence, Discord, PagerDuty, Grafana, Sentry, Datadog, ZIRAN,
  pytest, spec-kit); only `#` hrefs; each SVG under 40000 bytes; the generator under 300
  lines.
- Add `test_hero_only_moves_forward`: for every item in `ITEMS`, `PLACES[place]` never
  decreases along its stops; in each SVG, the x of every `animateMotion` `values` pair never
  decreases; exactly one item visits the `SIDING` places, it rides the bottom lane, its
  stops run Review, the siding places in order, then Merge; the SVG holds "fix lane" and
  `SIDING_LABEL`; and for each station, the animate inside `id="lit-<station>"` is on at
  the midpoint of every hold there (value read by linear lookup in its keyTimes). The
  forward checks fail on the second-round tables, where login fix went from Review back to
  Build at k 0.6.
- `test_hero_files_match_their_generator` and `test_hero_variants_share_geometry_and_motion`
  stay as they are.

### `README.md`, `docs/site/index.md`

Only the hero `alt` attribute changes to `ALT` (one in README, two in the index).

### `docs/site/assets/hero-light.svg`, `hero-dark.svg`

Regenerated by `python3 scripts/build-hero.py`.

## What must not change

- The picture tags, asset paths, `#only-light` and `#only-dark` suffixes, and every other
  line of README.md and docs/site/index.md.
- The `PAL` colour values (dark palette as today) and the accent `#00C9A7`.
- The two generator tests named above, and any runtime code.

## Verification

- Focused: `python -m pytest -q tests/test_docs.py`; then the full suite in the background.
- Visual: render both SVGs to PNG with `qlmanage -t -s 1200 -o <scratch dir> <svg>` and
  look at them; also render a copy with `.live` hidden and `.still` shown (swap the two
  display rules in a scratch copy) to check the mid-day frame, and a copy with the items
  placed at k 0.57 (login fix mid-bend) to check the diverter reads as a curved branch with
  the amber pill on it. Compare with the prototype: nothing overlaps, labels sit above their
  stations, the siding label sits between the track and the panel, ticker lines fit the
  panel. Scratch files stay outside the repository.
