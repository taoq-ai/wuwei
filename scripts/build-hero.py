"""Generate docs/site/assets/hero-dark.svg and hero-light.svg from one drawing.

One working day on a track: items ride the lanes left to right and never come back; the fix
round and parking are diverters. Edit the tables here, then run `python3 scripts/build-hero.py`
and commit both files. A test checks they match.
"""
import sys
from pathlib import Path

T = 16.0          # one day, seconds; every k below is a fraction of it

PAL = {
    'dark': dict(bg='#102622', panel='#193B35', text='#ECF8F5', muted='#B1CBC4', accent='#00C9A7',
                 atext='#00C9A7', warm='#F2B65E'),
    'light': dict(bg='#F4FAF8', panel='#FFFFFF', text='#183B37', muted='#42615C', accent='#00C9A7',
                  atext='#00735F', warm='#935600'),
}

ALT = ('Work items move along a track through Plan, Build, Check, Review and Merge while guards, cards '
       'and the heartbeat work under the hood; you approve the plan once and answer a card from the phone.')

STATIONS = ['Plan', 'Build', 'Check', 'Review', 'Merge']
PLACES = {'off': -140, 'Plan': 125, 'Build': 318, 'parked': 440, 'Check': 515, 'Review': 708, 'patch': 770,
          'delta check': 840, 'Merge': 900, 'Shipped': 1095}     # x of a pill's centre
SIDING = ('patch', 'delta check')           # places on the fix lane
LOW = SIDING + ('parked',)                  # places on the strip under the bottom lane
LANE_Y, FIX_Y = [230, 282, 334], 384        # lane centres top to bottom, then the diverter strip
ITEMS = [  # (name, lane, [(k, place)]); an item fades out at its last stop
    ('rate limits', 0, [(0, 'off'), (.13, 'off'), (.17, 'Plan'), (.2, 'Plan'), (.3, 'Build'), (.33, 'Build'),
                        (.4, 'Check'), (.43, 'Check'), (.52, 'Review'), (.7, 'Review'), (.78, 'Merge'),
                        (.8, 'Merge'), (.86, 'Shipped')]),
    ('docs page', 1, [(0, 'off'), (.17, 'off'), (.21, 'Plan'), (.28, 'Plan'), (.38, 'Build'), (.42, 'Build'),
                      (.5, 'Check'), (.53, 'Check'), (.6, 'Review'), (.74, 'Review'), (.82, 'Merge'),
                      (.84, 'Merge'), (.9, 'Shipped')]),
    ('csv export', 2, [(0, 'off'), (.11, 'off'), (.15, 'Plan'), (.18, 'Plan'), (.22, 'Build'), (.27, 'Build'),
                       (.31, 'parked'), (.38, 'parked')]),
    ('login fix', 2, [(0, 'off'), (.19, 'off'), (.23, 'Plan'), (.31, 'Plan'), (.36, 'Build'), (.38, 'Build'),
                      (.44, 'Check'), (.47, 'Check'), (.53, 'Review'), (.56, 'Review'), (.59, 'patch'),
                      (.66, 'patch'), (.69, 'delta check'), (.78, 'delta check'), (.84, 'Merge'),
                      (.88, 'Merge'), (.93, 'Shipped')]),
]
AMBER = (.54, .80)                          # login fix is amber from the FIX verdict until it has rejoined
WAIT = (.23, .31)                           # login fix waits at Plan for a seat (dashed outline)
LABELS = [('Plan', 'waits: CAP 3', 'warm', *WAIT),
          ('Build', 'tests first, then the code', 'atext', .2, .3),
          ('Check', 'fast checks green', 'atext', .33, .4),
          ('Review', 'arch · quality · security', 'atext', .43, .52),
          ('Review', 'quality: FIX, diverted to the fix lane', 'warm', .54, .63),
          ('Merge', 'merged at the gated head', 'atext', .7, .78)]
SIDING_LABEL = ('one fix round, then a delta check; forward only', .6, .78)
EXIT_LABEL = ('parked, carried to tomorrow', .29, .4)
GATE = (.02, .125, .2)                      # card on, question becomes "Approved...", card off
PHONE = [(.02, .12, 'accent'), (.56, .66, 'warm')]   # screen lit: gate open, then the D-3 card
CARD = (.56, .66)
INDICATORS = [('guards: 1 caught', 'warm', [(.36, .39)]), ('cards: 1 open', 'warm', [CARD]),
              ('heartbeat', None, []), ('shepherd: PR #142', 'accent', [(.68, .8)]),
              ('lead: 4 candidates ranked', 'accent', [(.1, .17)]), ('steward: retro', 'accent', [(.94, .98)])]
TICKER = [  # (on, off, slot, text), in day order; the stamp is clock(on)
    (.14, .30, 0, 'plan approved: 4 items, 3 seats (CAP 3), queue ranked by WSJF'),
    (.30, .44, 2, 'csv export parked: blocked on a client answer, carried to tomorrow'),
    (.37, .52, 1, 'guard caught a force push; the seat pushed the branch without --force'),
    (.45, .56, 2, 'decision D-2 (Routine) taken under mandate: keep the retry, recorded for you'),
    (.55, .70, 0, 'review: quality FIX on login fix; diverted to the fix lane, one round, then a delta check'),
    (.67, .82, 2, 'decision D-3 (Consequential) answered from the phone: Allow once'),
    (.71, .86, 1, 'PR #142 merged at the gated head; required checks green; branch deleted'),
    (.94, .98, 0, 'close: report written, retro done, 2 rule changes proposed for you'),
]
STILL = {'rate limits': 'Review', 'docs page': 'Check', 'login fix': 'patch'}   # the reduced-motion frame
STILL_K = 5 / 9                             # 14:00

A = f'dur="{T:g}s" repeatCount="indefinite"'
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
BEAT = ' class="beat"'
MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'


def pct(x): return f'{x:.4f}'.rstrip('0').rstrip('.') or '0'


def clock(k):
    """Day clock at k, 09:00 to 18:00, floored to five minutes."""
    m = int(round(k * 540, 6)) // 5 * 5
    return f'{9 + m // 60:02d}:{m % 60:02d}'


def blink(attr, off, spans):
    """One <animate>: `off`, except `value` inside each (on, end, value); a span ends by .98 or at 1."""
    pts = [(0, off)]
    for on, end, value in spans:
        pts += [(on, off), (on + .01, value), (end, value)] + ([(end + .01, off)] if end < 1 else [])
    if pts[-1][0] < 1:
        pts.append((1, off))
    return (f'<animate attributeName="{attr}" values="{";".join(v for _, v in pts)}" '
            f'keyTimes="{";".join(pct(k) for k, _ in pts)}" {A}/>')


def at(place, lane):
    return PLACES[place], FIX_Y if place in LOW else LANE_Y[lane]


def track(stops, lane):
    """(k, x, y) samples of an item; a lane change is the bend() curve: x linear, y eased 3t^2-2t^3."""
    out = []
    for (k0, p0), (k1, p1) in zip(stops, stops[1:]):
        (x0, y0), (x1, y1) = at(p0, lane), at(p1, lane)
        n = 8 if y0 != y1 else 1
        out += [(k0 + (k1 - k0) * i / n, x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * (3 * (i / n) ** 2 - 2 * (i / n) ** 3))
                for i in range(n)]
    out.append((stops[-1][0], *at(stops[-1][1], lane)))
    return out + [(1, *out[-1][1:])] if out[-1][0] < 1 else out


def walk(stops, lane):
    s = track(stops, lane)
    values = ';'.join(f'{round(x, 1):g},{round(y - LANE_Y[lane], 1):g}' for _, x, y in s)
    return f'<animateMotion values="{values}" keyTimes="{";".join(pct(k) for k, _, _ in s)}" calcMode="linear" {A}/>'


def bend(x0, y0, x1, y1):
    """The cubic that track() samples: control points at a third and two thirds of the x span."""
    dx = x1 - x0
    return f'C {round(x0 + dx / 3, 1):g} {y0} {round(x0 + 2 * dx / 3, 1):g} {y1} {x1} {y1}'


def holds(place):
    """(on, off) spans while any item sits at place, merged within .02."""
    out = []
    for a, b in sorted((a, b) for _, _, s in ITEMS for (a, p), (b, q) in zip(s, s[1:]) if p == q == place):
        if out and a <= out[-1][1] + .02:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def item(name, x, y, stroke='{accent}', extra=''):
    return (f'<rect x="{x - 55}" y="{y - 15}" width="110" height="30" rx="15" fill="{{panel}}" stroke="{stroke}" '
            f'stroke-width="1.5">{extra}</rect><text x="{x}" y="{y + 5}" text-anchor="middle">{name}</text>')


def text(x, y, body, colour='muted', size=12, extra='', attrs=''):
    return f'<text x="{x}" y="{y}" fill="{{{colour}}}" font-size="{size}"{attrs}>{body}{extra}</text>'


def station(name, lit=''):
    w = 30 + 9 * len(name)
    x = PLACES[name] - w / 2
    if lit:
        return (f'<rect id="lit-{name}" x="{x:g}" y="180" width="{w}" height="26" rx="13" fill="{{accent}}" '
                f'fill-opacity="0.18" stroke="{{accent}}" stroke-width="2" opacity="{lit}">')
    return (f'<rect x="{x:g}" y="180" width="{w}" height="26" rx="13" fill="{{panel}}" stroke="{{muted}}" '
            f'stroke-opacity="0.45" stroke-width="1.5"/>'
            f'<text x="{PLACES[name]}" y="198" text-anchor="middle" font-weight="600" fill="{{text}}">{name}</text>')


def ticker(slot, line, on, extra='', attrs=''):
    return text(56, 512 + 24 * slot, f'{clock(on)}  {line}', extra=extra, attrs=f' font-family="{MONO}"{attrs}')


def svg(p):
    fix = (f'M {PLACES["Review"]} {LANE_Y[2]} {bend(PLACES["Review"], LANE_Y[2], PLACES["patch"], FIX_Y)} '
           f'L {PLACES["delta check"]} {FIX_Y} {bend(PLACES["delta check"], FIX_Y, PLACES["Merge"], LANE_Y[2])}')
    exit_ = f'M {PLACES["Build"]} {LANE_Y[2]} {bend(PLACES["Build"], LANE_Y[2], PLACES["parked"], FIX_Y)} L 540 {FIX_Y}'
    shipped = sorted((s[-1][0], name) for name, _, s in ITEMS if s[-1][1] == 'Shipped')
    lanes = {name: lane for name, lane, _ in ITEMS}
    xs = [56, 236, 396, 536, 716, 936]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" role="img" aria-labelledby="title desc" '
        f'font-family="{SANS}" font-size="13">',
        '<title id="title">WUWEI: a day of delivery</title>',
        f'<desc id="desc">{ALT}</desc>',
        '<style><![CDATA[',
        '.still{display:none}',
        '.belt{animation:belt 1.2s linear infinite}@keyframes belt{to{stroke-dashoffset:-24}}',
        '.beat{animation:beat 2s ease-in-out infinite}@keyframes beat{50%{opacity:.25}}',
        '@media (prefers-reduced-motion:reduce){.live{display:none}.still{display:inline}.belt,.beat{animation:none}}',
        ']]></style>',
        '<rect width="1200" height="600" rx="28" fill="{bg}"/>',
        text(40, 58, '无为 <tspan fill="{atext}">WUWEI</tspan>', 'text', 38, attrs=' font-weight="700"'),
        text(40, 86, 'A team of agents runs your delivery day. You approve the plan and answer the odd card.', size=16),
        '<rect x="960" y="70" width="200" height="4" rx="2" fill="{muted}" opacity="0.25"/>',
        text(960, 92, '09:00'), text(1160, 92, '18:00', attrs=' text-anchor="end"'),
        # the owner: the phone (the gate card is drawn in live, it leaves after the morning)
        '<rect x="316" y="104" width="30" height="52" rx="6" fill="{panel}" stroke="{muted}" stroke-opacity="0.45" stroke-width="1.5"/>',
        '<rect x="321" y="111" width="20" height="34" rx="3" fill="{muted}" opacity="0.2"/>',
        text(358, 124, 'you, on the phone'),
        # the track: three lanes, the diverter strip under them
        '<rect x="40" y="194" width="960" height="214" rx="14" fill="{panel}" stroke="{muted}" stroke-opacity="0.25"/>',
        *[f'<line x1="40" y1="{y}" x2="1000" y2="{y}" stroke="{{muted}}" stroke-opacity="0.18"/>' for y in (256, 308, 360)],
        *[f'<line x1="{PLACES[s]}" y1="206" x2="{PLACES[s]}" y2="408" stroke="{{muted}}" stroke-opacity="0.25" stroke-dasharray="3 5"/>'
          for s in STATIONS],
        *[f'<line class="belt" x1="56" y1="{y}" x2="984" y2="{y}" stroke="{{muted}}" stroke-opacity="0.35" stroke-width="2" '
          f'stroke-dasharray="10 14" style="animation-duration:{d}s"/>' for y, d in zip(LANE_Y, (1.2, 1.4, 1.1))],
        f'<path class="belt" d="{fix}" fill="none" stroke="{{warm}}" stroke-opacity="0.7" stroke-width="2" stroke-dasharray="6 6"/>',
        f'<path class="belt" d="{exit_}" fill="none" stroke="{{muted}}" stroke-opacity="0.6" stroke-width="2" stroke-dasharray="6 6"/>',
        f'<line x1="546" y1="374" x2="546" y2="394" stroke="{{muted}}" stroke-opacity="0.6" stroke-width="2"/>',
        text(556, 388, 'exit lane'), text(698, 388, 'fix lane', 'warm', attrs=' text-anchor="end"'),
        *[station(s) for s in STATIONS],
        text(1030, 198, 'Shipped', 'text', 14, attrs=' font-weight="600"'),
        text(1095, 376, 'yesterday:', attrs=' text-anchor="middle"'),
        text(1095, 394, '4 shipped, 1 carried', attrs=' text-anchor="middle"'),
        # under the hood
        '<rect x="40" y="436" width="1120" height="150" rx="14" fill="{panel}" stroke="{muted}" stroke-opacity="0.25"/>',
        text(56, 460, 'UNDER THE HOOD', attrs=' letter-spacing="1"'),
        *[f'<circle cx="{x + 8}" cy="482" r="7" fill="{{{"accent" if c is None else "muted"}}}" opacity="{1 if c is None else 0.3}"'
          f'{BEAT if c is None else ""}/>' + text(x + 22, 486, t, 'text') for x, (t, c, _) in zip(xs, INDICATORS)],
        # reduced motion: one mid-day frame
        '<g class="still" fill="{text}">',
        *[item(n, *at(STILL[n], lanes[n]), '{warm}' if n == 'login fix' else '{accent}') for n in STILL],
        *[station(s, '1') + '</rect>' for s in ('Check', 'Review')],
        *[text(PLACES[s], 172, t, c, 13, attrs=' text-anchor="middle" font-weight="600"') for s, t, c, *_ in LABELS if 'FIX' in t],
        text(805, 426, SIDING_LABEL[0], 'warm', attrs=' text-anchor="middle"'),
        '<rect x="321" y="111" width="20" height="34" rx="3" fill="{warm}"/>',
        text(358, 146, 'D-3: client wants Friday. Allow once?', 'warm'),
        f'<circle cx="{xs[1] + 8}" cy="482" r="7" fill="{{warm}}"/>',
        *[ticker(s, line, on) for on, off, s, line in TICKER if on <= STILL_K <= off],
        text(1160, 58, clock(STILL_K), 'text', 26, attrs=' text-anchor="end" font-weight="700"'),
        f'<rect x="960" y="70" width="{200 * STILL_K:.0f}" height="4" rx="2" fill="{{accent}}"/>',
        '</g>',
        '<g class="live">',
        f'<g opacity="0">{blink("opacity", "0", [(GATE[0], GATE[2], "1")])}'
        '<rect x="40" y="104" width="256" height="56" rx="10" fill="{panel}" stroke="{muted}" stroke-opacity="0.45"/>',
        text(56, 126, 'Morning gate', 'text', 14, attrs=' font-weight="600"'),
        text(56, 148, "Approve today's plan as proposed?", extra=blink('opacity', '0', [(0, GATE[1], '1')]), attrs=' opacity="0"'),
        text(56, 148, 'Approved. 3 seats start (CAP 3).', 'atext', extra=blink('opacity', '0', [(GATE[1], GATE[2], '1')]),
             attrs=' opacity="0" font-weight="600"'),
        '</g>',
        *[f'<rect x="321" y="111" width="20" height="34" rx="3" fill="{{{c}}}" opacity="0">{blink("opacity", "0", [(a, b, "1")])}</rect>'
          for a, b, c in PHONE],
        text(358, 146, 'D-3: client wants Friday. Allow once?', 'warm', extra=blink('opacity', '0', [(*CARD, '1')]), attrs=' opacity="0"'),
        *[text(PLACES[s], 172, t, c, 13, blink('opacity', '0', [(a, b, '1')]), ' opacity="0" text-anchor="middle" font-weight="600"')
          for s, t, c, a, b in LABELS],
        text(805, 426, SIDING_LABEL[0], 'warm', extra=blink('opacity', '0', [(*SIDING_LABEL[1:], '1')]), attrs=' opacity="0" text-anchor="middle"'),
        text(PLACES['parked'], 426, EXIT_LABEL[0], extra=blink('opacity', '0', [(*EXIT_LABEL[1:], '1')]), attrs=' opacity="0" text-anchor="middle"'),
        *[station(s, '0') + blink('opacity', '0', [(a, b, '1') for a, b in holds(s)]) + '</rect>' for s in STATIONS],
    ]
    for name, lane, stops in ITEMS:
        enter = max(k for k, p in stops if p == 'off')
        stroke = blink('stroke', '{accent}', [(*AMBER, '{warm}')]) if name == 'login fix' else ''
        stroke += blink('stroke-dasharray', 'none', [(*WAIT, '4 4')]) if name == 'login fix' else ''
        stroke += blink('stroke', '{accent}', [(min(k for k, p in stops if p == 'parked'), stops[-1][0], '{muted}')]) if stops[-1][1] == 'parked' else ''
        parts.append(f'<g opacity="0" fill="{{text}}">{walk(stops, lane)}{blink("opacity", "0", [(enter, stops[-1][0], "1")])}'
                     f'{item(name, 0, LANE_Y[lane], extra=stroke)}</g>')
    for i, (k, name) in enumerate(shipped):
        parts.append(f'<g opacity="0" fill="{{text}}">{blink("opacity", "0", [(k, 1, "1")])}'
                     f'<rect x="1030" y="{LANE_Y[i] - 15}" width="130" height="30" rx="15" fill="{{accent}}" fill-opacity="0.14" '
                     f'stroke="{{accent}}" stroke-width="1.5"/><text x="1095" y="{LANE_Y[i] + 5}" text-anchor="middle">{name}</text></g>')
    parts += [f'<circle cx="{x + 8}" cy="482" r="7" fill="{{{c}}}" opacity="0">{blink("opacity", "0", [(a, b, "1") for a, b in s])}</circle>'
              for x, (_, c, s) in zip(xs, INDICATORS) if c]
    parts += [ticker(s, line, on, blink('opacity', '0', [(on, off, '1')]), ' opacity="0"') for on, off, s, line in TICKER]
    parts += [text(1160, 58, f'{h:02d}:00', 'text', 26, blink('opacity', '0', [((h - 9) / 9, (h - 8) / 9 if h < 17 else 1, '1')]),
                   ' opacity="0" text-anchor="end" font-weight="700"') for h in range(9, 18)]
    parts += [f'<rect x="960" y="70" width="0" height="4" rx="2" fill="{{accent}}">'
              f'<animate attributeName="width" values="0;200" keyTimes="0;1" {A}/></rect>', '</g>', '</svg>']
    out = '\n'.join(parts) + '\n'
    for k, v in p.items():
        out = out.replace('{' + k + '}', v)
    return out


if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    for name, pal in PAL.items():
        (root / f'docs/site/assets/hero-{name}.svg').write_text(svg(pal))
