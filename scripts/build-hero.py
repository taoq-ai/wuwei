"""Generate docs/site/assets/hero-dark.svg and hero-light.svg from one drawing.

One working day as an agentic engineering flow, left to right: you and the ranked queue, the
agent team in three lanes, the gates, the pull requests the shepherd sweeps, you again with the
cards. Items only move forward; loops are drawn where the system loops. Edit the tables here,
then run `python3 scripts/build-hero.py` and commit both files. A test checks they match.
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

ALT = ('A ranked queue you approve feeds an agent team working three parallel lanes that loop build and '
       'check, every candidate passes the gates within the round cap, pull requests wait in a stack '
       'the shepherd sweeps until they merge, and you answer the odd card from the phone while guards, '
       "heartbeat, lead and steward work under the hood and each day's retro feeds tomorrow's plan.")

STAGES = [  # (name, small line, icon, x of the pill centre)
    ('Specs and plan', 'you approve, the lead ranks', 'you', 130),
    ('Agent team', '3 seats in parallel lanes', 'team', 398),
    ('Gates', 'arch · quality · security', 'gate', 572),
    ('Pull requests', 'the shepherd sweeps', 'pr', 887),
    ('Review and merge', 'cards: your final say', 'you', 1082),
]
ICONS = {  # 24-unit line icons, stroke only
    'you': 'M12 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8M4 21c0-4 4-6 8-6s8 2 8 6',
    'team': 'M5 9h14v10H5zM12 5v4M9 13v1M15 13v1M9 16.5h6M3 13v3M21 13v3',
    'gate': 'M12 3l7 3v5c0 5-3 8-7 10c-4-2-7-5-7-10V6zM9 12l2 2l4-4',
    'pr': 'M6 4v12M6 20a2 2 0 1 0 0-4a2 2 0 1 0 0 4M18 8a2 2 0 1 0 0-4a2 2 0 1 0 0 4M18 8c0 5-12 4-12 8',
}
QUEUE = ['rate limits', 'login fix', 'docs page', 'retry policy', 'cache keys']   # rank order
PLACES = {'off': 295, 'build': 360, 'gates': 530, 'PR': 710}           # x of a pill's centre
LANE_Y = [280, 334, 388]
ITEMS = [  # (name, lane, [(k, place)]); an item fades in at its last 'off' and out at its last stop
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
DECISIONS = [  # (asked, answered, open text or None, closed text, asked on the phone)
    (.30, .31, None, 'D-1 under mandate', False),
    (.44, .45, None, 'D-2 under mandate', False),
    (.52, .62, 'D-3 client wants Friday?', 'D-3 answered: Allow once', True),
]
GATE = (.02, .12, .17)                 # gate card on, question becomes "Approved", card off
PHONE = [(GATE[0], GATE[1], 'accent')] + [(a, b, 'warm') for a, b, _, _, phone in DECISIONS if phone]
GUARD = (.36, .40)
CLOSE = .92                            # report, retro, return arrow, steward, carried
STILL_K = .55                          # 13:55, the reduced-motion frame
LOOPS = ['a seat asks through a decision record', 'you answer from the phone, or the mandate answers']
DAY = "tomorrow's plan carries what was learned"
INDICATORS = ['guards: every call checked, 1 caught', 'heartbeat',
              'lead: discovery when the queue runs low', 'steward: retro at close, you promote']

A = f'dur="{T:g}s" repeatCount="indefinite"'
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
BEAT = ' class="beat"'
DOTS = [600, 620, 640]                 # x of the three gate dots: arch, quality, security
IND_X = [56, 322, 452, 772]            # x of the four indicators in the band


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
    return PLACES[place], LANE_Y[lane]


def walk(stops):
    """Items never change lanes: the motion is x only, from stop to stop."""
    s = [(k, PLACES[p]) for k, p in stops] + ([(1, PLACES[stops[-1][1]])] if stops[-1][0] < 1 else [])
    return (f'<animateMotion values="{";".join(f"{x},0" for _, x in s)}" '
            f'keyTimes="{";".join(pct(k) for k, _ in s)}" calcMode="linear" {A}/>')


def holds(place, lane=None):
    """(on, off) spans while any item (in this lane) sits at place, merged within .02."""
    out = []
    for a, b in sorted((a, b) for _, l, s in ITEMS if lane in (None, l)
                       for (a, p), (b, q) in zip(s, s[1:]) if p == q == place):
        if out and a <= out[-1][1] + .02:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def popped(stops):
    """The k an item leaves the queue for its lane."""
    return max(k for k, p in stops if p == 'off')


def item(name, x, y, stroke='{accent}', extra=''):
    return (f'<rect x="{x - 55}" y="{y - 15}" width="110" height="30" rx="15" fill="{{panel}}" stroke="{stroke}" '
            f'stroke-width="1.5">{extra}</rect><text x="{x}" y="{y + 5}" text-anchor="middle">{name}</text>')


def ta(x, y, colour='muted', size=12, attrs=''):
    return f' x="{x}" y="{y}" fill="{{{colour}}}" font-size="{size}"{attrs}'


def text(x, y, body, colour='muted', size=12, extra='', attrs=''):
    return f'<text{ta(x, y, colour, size, attrs)}>{extra}{body}</text>'


def orbit(cx, cy, r):
    """A loop glyph: three quarters of a circle and an arrowhead."""
    return f'M {cx + r} {cy} A {r} {r} 0 1 1 {cx} {cy - r} M {cx - 4} {cy - r - 4} L {cx} {cy - r} L {cx - 4} {cy - r + 4}'


def flick(tag, attrs, inner, spans, ident=''):
    """An element shown over spans: its live copy (the id, the timing first) and its still copy or ''."""
    idattr = f' id="{ident}"' if ident else ''
    live = f'<{tag}{idattr}{attrs} opacity="0">{blink("opacity", "0", [(a, b, "1") for a, b in spans])}{inner}</{tag}>'
    return live, f'<{tag}{attrs}>{inner}</{tag}>' if any(a <= STILL_K < b for a, b in spans) else ''


def svg(p):
    live, still = [], []

    def on(*args, **kw):
        lit, frame = flick(*args, **kw)
        live.append(lit)
        still.append(frame)
    pops = sorted(popped(s) for _, _, s in ITEMS)
    wait = (pops[len(LANE_Y) - 1], pops[-1])                    # every lane busy, an item still queued
    ask, answer = 'M 640 440 V 462 H 1050 V 446', 'M 1120 440 V 494 H 520 V 446'
    day = f'M {STAGES[-1][3]} 124 V 114 H {STAGES[0][3]} V 122'
    stroke = ' fill="none" stroke-width="{w}" stroke="{{{c}}}" marker-end="url(#m-{c})"'
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 640" role="img" aria-labelledby="title desc" '
        f'font-family="{SANS}" font-size="13">',
        '<title id="title">WUWEI: agentic delivery, one day</title>',
        f'<desc id="desc">{ALT}</desc>',
        '<style><![CDATA[',
        '.still{display:none}',
        '.spin{animation:spin 2s linear infinite;transform-box:fill-box;transform-origin:center}'
        '@keyframes spin{to{transform:rotate(360deg)}}',
        '.beat{animation:beat 2s ease-in-out infinite}@keyframes beat{50%{opacity:.25}}',
        '@media (prefers-reduced-motion:reduce){.live{display:none}.still{display:inline}.spin,.beat{animation:none}}',
        ']]></style>',
        '<defs>', *[f'<marker id="m-{c}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" '
                    f'orient="auto"><path d="M0 0L10 5L0 10z" fill="{{{c}}}"/></marker>' for c in ('muted', 'accent', 'warm')],
        '</defs>',
        '<rect width="1200" height="640" rx="28" fill="{bg}"/>',
        text(40, 54, '无为 <tspan fill="{atext}">WUWEI</tspan>', 'text', 38, attrs=' font-weight="700"'),
        text(40, 84, 'A team of agents runs your delivery day. You set the work and keep the final say.', size=16),
        '<rect x="960" y="70" width="200" height="4" rx="2" fill="{muted}" opacity="0.25"/>',
        text(960, 92, '09:00'), text(1160, 92, '18:00', attrs=' text-anchor="end"'),
        # the day: the return arrow over the flow
        f'<path id="day-loop" d="{day}"{stroke.format(w=1.5, c="muted")}/>',
        f'<rect x="{600 - 136}" y="105" width="272" height="18" fill="{{bg}}"/>',
        text(600, 118, DAY, attrs=' text-anchor="middle"'),
        # the five stages: icon, pill, small line
        *[f'<path id="icon-{i}" d="{ICONS[icon]}" transform="translate({x - 15} 126) scale(1.25)" fill="none" '
          f'stroke="{{accent}}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
          f'<rect x="{x - 18 - 4.5 * len(name):g}" y="160" width="{36 + 9 * len(name)}" height="30" rx="15" fill="{{panel}}" '
          f'stroke="{{accent}}" stroke-width="2"/>' + text(x, 181, name, 'text', 15, attrs=' text-anchor="middle" font-weight="700"')
          + text(x, 207, small, attrs=' text-anchor="middle"') for i, (name, small, icon, x) in enumerate(STAGES)],
        # the panels, so the first frame shows the system
        *[f'<rect id="panel-{n}" x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{{panel}}" stroke="{{muted}}" '
          f'stroke-opacity="0.25"/>' for n, x, y, w, h in (('queue', 40, 222, 180, 218), ('lanes', 240, 222, 530, 218),
                                                          ('prs', 790, 222, 195, 218), ('cards', 1005, 222, 155, 218),
                                                          ('band', 40, 526, 1120, 96))],
        *[f'<path d="M {a} 331 H {b}"{stroke.format(w=1.5, c="muted")}/>' for a, b in ((222, 236), (772, 786), (987, 1001))],
        # lanes: heads, separators, build loop glyphs, gate dots
        text(400, 242, 'build ⟲ check', attrs=' text-anchor="middle" font-weight="600"'),
        text(PLACES['PR'], 242, 'raise PR', attrs=' text-anchor="middle" font-weight="600"'),
        *[f'<line x1="240" y1="{y}" x2="770" y2="{y}" stroke="{{muted}}" stroke-opacity="0.18"/>' for y in (307, 361)],
        *[f'<path id="build-{lane}" d="{orbit(445, y, 9)}" fill="none" stroke="{{muted}}" stroke-opacity="0.5" stroke-width="2"/>'
          for lane, y in enumerate(LANE_Y)],
        *[f'<circle id="gate-{lane}-{n}" cx="{x}" cy="{y}" r="6" fill="{{muted}}" opacity="0.25"/>'
          for lane, y in enumerate(LANE_Y) for n, x in enumerate(DOTS)],
        # pull requests: the sweep orbit
        f'<path id="sweep" class="spin" d="{orbit(814, 344, 10)}" fill="none" stroke="{{accent}}" stroke-width="2"/>',
        text(832, 348, 'sweep', 'text', attrs=' font-weight="600"'),
        text(802, 370, 'overnight: sweeps, never merges', size=11),
        # cards: the phone
        '<rect x="1017" y="304" width="30" height="52" rx="6" fill="{panel}" stroke="{muted}" stroke-opacity="0.45" stroke-width="1.5"/>',
        '<rect x="1022" y="311" width="20" height="34" rx="3" fill="{muted}" opacity="0.2"/>',
        # the guidance loops under the flow
        f'<path id="ask-loop" stroke-dasharray="6 5" d="{ask}"{stroke.format(w=1.5, c="muted")}/>',
        f'<path id="answer-loop" stroke-dasharray="6 5" d="{answer}"{stroke.format(w=1.5, c="muted")}/>',
        text(845, 480, LOOPS[0], attrs=' text-anchor="middle"'), text(820, 512, LOOPS[1], attrs=' text-anchor="middle"'),
        # under the hood
        text(56, 548, 'UNDER THE HOOD', size=11, attrs=' letter-spacing="1"'),
        *[f'<circle cx="{x + 7}" cy="570" r="6" fill="{{{"accent" if i == 1 else "muted"}}}" '
          f'opacity="{1 if i == 1 else 0.3}"{BEAT if i == 1 else ""}/>' + text(x + 20, 574, t, 'text')
          for i, (x, t) in enumerate(zip(IND_X, INDICATORS))],
    ]
    # the queue: pills visible from the first frame, each leaves when it pops into a lane
    for i, (name, _, stops) in enumerate(sorted(ITEMS, key=lambda it: popped(it[2])), 1):
        pill = (f'<rect x="52" y="{202 + 32 * i}" width="156" height="26" rx="13" fill="{{panel}}" stroke="{{muted}}" '
                f'stroke-opacity="0.5"/><text x="66" y="{219 + 32 * i}" fill="{{text}}">{i} · {name}</text>')
        live.append(f'<g>{blink("opacity", "1", [(popped(stops), 1, "0")])}{pill}</g>')
        still.append(pill if popped(stops) > STILL_K else '')
    on('text', ta(66, 412, 'warm', attrs=' font-weight="600"'), 'waits: CAP 3 seats', [wait], 'waits')
    on('text', ta(52, 430, size=11), 'answers a card now and then', [(GATE[2], 1)])
    live.append(f'<g opacity="0">{blink("opacity", "0", [(GATE[0], GATE[2], "1")])}'
                '<rect x="52" y="394" width="156" height="42" rx="10" fill="{panel}" stroke="{accent}"/>'
                + text(62, 410, 'Morning gate', 'text', attrs=' font-weight="600"')
                + text(62, 428, "Approve today's plan?", size=11, extra=blink('opacity', '0', [(0, GATE[1], '1')]), attrs=' opacity="0"')
                + text(62, 428, 'Approved · 3 seats', 'atext', 11, blink('opacity', '0', [(GATE[1], GATE[2], '1')]),
                       ' opacity="0" font-weight="600"') + '</g>')
    # lanes: the lit glyphs and dots, the fix round, the items
    fixed = next(lane for name, lane, _ in ITEMS if name == FIX[0])
    for lane, y in enumerate(LANE_Y):
        on('path', f' class="spin" d="{orbit(445, y, 9)}" fill="none" stroke="{{accent}}" stroke-width="2"', '', holds('build', lane))
        for x in DOTS:
            on('circle', f' cx="{x}" cy="{y}" r="6" fill="{{accent}}"', '', holds('gates', lane))
    on('circle', f' cx="{DOTS[1]}" cy="{LANE_Y[fixed]}" r="6" fill="{{warm}}"', '', [FIX[1:]])
    y, g = LANE_Y[fixed], PLACES['gates']
    on('g', '', f'<path d="M {DOTS[1]} {y - 9} C {DOTS[1]} {y - 32} {g} {y - 32} {g} {y - 19}"'
                f'{stroke.format(w=2, c="warm")} stroke-dasharray="5 4"/>'
                + text(652, y + 5, 'fix ×1 → delta', 'warm', attrs=' font-weight="600"'), [FIX[1:]], 'fix-loop')
    for name, lane, stops in ITEMS:
        amber = blink('stroke', '{accent}', [(*FIX[1:], '{warm}')]) if name == FIX[0] else ''
        live.append(f'<g opacity="0" fill="{{text}}">{walk(stops)}{blink("opacity", "0", [(popped(stops), stops[-1][0], "1")])}'
                    f'{item(name, 0, LANE_Y[lane], extra=amber)}</g>')
        if popped(stops) <= STILL_K < stops[-1][0]:
            place = [q for k, q in stops if k <= STILL_K][-1]
            warm = name == FIX[0] and FIX[1] <= STILL_K < FIX[2]
            still.append(f'<g fill="{{text}}">{item(name, *at(place, lane), "{warm}" if warm else "{accent}")}</g>')
    # pull requests: the stack, the shepherd's lines, shipped and carried
    for i, (label, raised, merged) in enumerate(PRS):
        on('g', '', f'<rect x="802" y="{234 + 30 * i}" width="170" height="26" rx="13" fill="{{accent}}" fill-opacity="0.14" '
                    f'stroke="{{accent}}" stroke-width="1.5"/>' + text(816, 251 + 30 * i, label, 'text'), [(raised, merged)])
    for line, c, a, b in PR_LINES:
        on('text', ta(802, 392, c, 11), line, [(a, b)])
    merges = [0] + [m for *_, m in PRS] + [1]
    for n in range(len(PRS) + 1):
        on('text', ta(802, 412, 'atext', attrs=' font-weight="600"'), f'shipped today: {n}', [(merges[n], merges[n + 1])])
    carried = sum(1 for _, _, s in ITEMS if s[-1][1] != 'PR')
    on('text', ta(802, 430, 'warm', 11), f'carried to tomorrow: {carried}', [(CLOSE, 1)])
    # cards: the decisions, the phone, asked today
    for i, (asked, answered, opened, closed, _) in enumerate(DECISIONS):
        if opened:
            on('text', ta(1015, 248 + 20 * i, 'warm', 11, ' font-weight="600"'), opened, [(asked, answered)])
        on('text', ta(1015, 248 + 20 * i, 'text', 11), closed, [(answered, 1)])
    for a, b, c in PHONE:
        on('rect', f' x="1022" y="311" width="20" height="34" rx="3" fill="{{{c}}}"', '', [(a, b)])
    phone = [d for d in DECISIONS if d[4]]
    on('text', ta(1015, 380, 'text', attrs=' font-weight="600"'), f'asked today: {len(phone)} of {len(DECISIONS)}',
       [(phone[0][0], 1)])
    # the loops light on their events; the band's indicators and the close
    lit = stroke.format(w=2.5, c='accent')
    on('path', f' d="{ask}"{lit} stroke-dasharray="6 5"', '', [(d[0], d[0] + .02) for d in DECISIONS], 'ask-loop-lit')
    on('path', f' d="{answer}"{lit} stroke-dasharray="6 5"', '', [(d[1], d[1] + .02) for d in DECISIONS], 'answer-loop-lit')
    on('path', f' d="{day}"{lit}', '', [(CLOSE, 1)], 'day-loop-lit')
    on('circle', f' cx="{IND_X[0] + 7}" cy="570" r="6" fill="{{warm}}"', '', [GUARD])
    on('circle', f' cx="{IND_X[2] + 7}" cy="570" r="6" fill="{{accent}}"', '', [(pops[-1], pops[-1] + .06)], 'lead')
    on('circle', f' cx="{IND_X[3] + 7}" cy="570" r="6" fill="{{accent}}"', '', [(CLOSE, 1)])
    on('text', ta(1144, 604, 'atext', attrs=' text-anchor="end" font-weight="600"'),
       f'{clock(CLOSE)} close: report written, retro done', [(CLOSE, 1)])
    # the day clock
    live += [text(1160, 58, f'{h:02d}:00', 'text', 26, blink('opacity', '0', [((h - 9) / 9, (h - 8) / 9 if h < 17 else 1, '1')]),
                  ' opacity="0" text-anchor="end" font-weight="700"') for h in range(9, 18)]
    live.append(f'<rect x="960" y="70" width="0" height="4" rx="2" fill="{{accent}}">'
                f'<animate attributeName="width" values="0;200" keyTimes="0;1" {A}/></rect>')
    still += [text(1160, 58, clock(STILL_K), 'text', 26, attrs=' text-anchor="end" font-weight="700"'),
              f'<rect x="960" y="70" width="{200 * STILL_K:.0f}" height="4" rx="2" fill="{{accent}}"/>']
    parts += ['<g class="still">', *filter(None, still), '</g>', '<g class="live">', *live, '</g>', '</svg>']
    out = '\n'.join(parts) + '\n'
    for k, v in p.items():
        out = out.replace('{' + k + '}', v)
    return out


if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    for name, pal in PAL.items():
        (root / f'docs/site/assets/hero-{name}.svg').write_text(svg(pal))
