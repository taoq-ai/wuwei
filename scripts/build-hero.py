"""Generate docs/assets/hero-dark.svg and hero-light.svg from one geometry.

Path lengths set the token timings, so edit the drawing here, then run
`python3 scripts/build-hero.py` and commit both files. A test checks they match.
"""
import math, sys
from pathlib import Path

T = 18.0          # one cycle, seconds
V = 150.0         # travel speed, viewBox units per second
EASE = '0.3 0 0.7 1'
LIN = '0 0 1 1'

PAL = {
    'dark': dict(bg='#102622', panel='#193B35', text='#ECF8F5', muted='#B1CBC4', accent='#00C9A7',
                 atext='#00C9A7', warm='#F2B65E', coral='#FF8C7A', shadow='#000000', core='#ECF8F5'),
    'light': dict(bg='#F4FAF8', panel='#FFFFFF', text='#183B37', muted='#42615C', accent='#00C9A7',
                  atext='#00735F', warm='#935600', coral='#B73A28', shadow='#6E918A', core='#00806B'),
}

# ---- geometry helpers -------------------------------------------------------
def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u**3*a + 3*u*u*t*b + 3*u*t*t*c + t**3*d for a, b, c, d in zip(p0, p1, p2, p3))

def blen(p0, p1, p2, p3, n=200):
    pts = [bez(p0, p1, p2, p3, i/n) for i in range(n+1)]
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

def split(p0, p1, p2, p3, t):
    """Return the second part of a cubic split at t."""
    lerp = lambda a, b: tuple(x + (y-x)*t for x, y in zip(a, b))
    a, b, c = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
    d, e = lerp(a, b), lerp(b, c)
    f = lerp(d, e)
    return f, e, c, p3

f = lambda p: f'{p[0]:g} {p[1]:g}'

class Seg:
    """A path fragment without its M, plus start, end and length."""
    def __init__(self, d, start, end, length):
        self.d, self.start, self.end, self.length = d, start, end, length

def C(p0, c1, c2, p1):
    return Seg(f'C {f(c1)}, {f(c2)}, {f(p1)}', p0, p1, blen(p0, c1, c2, p1))

def L(p0, p1):
    return Seg(f'L {f(p1)}', p0, p1, math.dist(p0, p1))

def A(p0, p1, r, angle):
    return Seg(f'A {r} {r} 0 0 1 {f(p1)}', p0, p1, r*angle)

def path(*segs):
    return f'M {f(segs[0].start)} ' + ' '.join(s.d for s in segs)

def cat(*segs):
    d = ' '.join(s.d for s in segs)
    return Seg(d, segs[0].start, segs[-1].end, sum(s.length for s in segs))

# ---- layout -----------------------------------------------------------------
P, B, R, J = (180, 385), (455, 210), (730, 210), (965, 210)
OC, OR = (1052, 345), 36                     # shepherd orbit
OT, OB = (OC[0], OC[1]-OR), (OC[0], OC[1]+OR)
CL = (990, 488)
KC, KR = (455, 300), 30                       # build and check loop
KT, KB = (KC[0], KC[1]-KR), (KC[0], KC[1]+KR)
LANE = 62                                     # gate lane offset
GX = 882                                      # gate marker x
RX = R[0] + 75                                # Review right edge

pb_ctrl = (P, (180, 285), (330, 210), B)
seg_pb = C(*pb_ctrl)
seg_br = L(B, R)
seg_rj = L(R, J)
seg_jo = C(J, (1022, 210), (OT[0], 255), OT)
seg_ohalf = A(OT, OB, OR, math.pi)
seg_ofull = cat(A(OT, OB, OR, math.pi), A(OB, OT, OR, math.pi))
seg_oc = C(OB, (OB[0], 445), (1040, CL[1]), CL)
seg_mem = C(CL, (905, 585), (310, 590), P)
seg_check = cat(L(B, KT), A(KT, KB, KR, math.pi), A(KB, KT, KR, math.pi), L(KT, B))
fix_a = C(J, (1009, 140), (979, 96), (895, 96))
fix_b = L((895, 96), (565, 96))
fix_c = C((565, 96), (522, 96), (505, 132), (505, 182))
seg_fix = cat(fix_a, fix_b, fix_c, L((505, 182), B))
SW0 = (262, 172)
join = split(*pb_ctrl, 0.72)
seg_sweep = cat(C(SW0, (305, 172), (330, 192), join[0]), C(*join))

def lane(dy):
    y = R[1] + dy
    return cat(L(R, (RX, R[1])), C((RX, R[1]), (RX+40, R[1]), (GX-45, y), (GX, y)),
               C((GX, y), (GX+45, y), (J[0]-40, R[1]), J))
lane_top, lane_mid, lane_bot = lane(-LANE), seg_rj, lane(LANE)

def until_box(p0, c1, c2, p3, c, w, h=56):
    """Cubic cut where it first enters the node box centred at c."""
    t = next(i/400 for i in range(401) if abs(bez(p0, c1, c2, p3, i/400)[0]-c[0]) <= w/2+6
             and abs(bez(p0, c1, c2, p3, i/400)[1]-c[1]) <= h/2+6)
    lerp = lambda a, b: tuple(x + (y-x)*t for x, y in zip(a, b))
    a, b, cc = lerp(p0, c1), lerp(c1, c2), lerp(c2, p3)
    d, e = lerp(a, b), lerp(b, cc)
    return f'M {f(p0)} C {f(a)}, {f(d)}, {f(lerp(d, e))}'
arrow_mem = until_box(CL, (905, 585), (310, 590), P, P, 136)
arrow_close = until_box(OB, (OB[0], 445), (1040, CL[1]), CL, CL, 136)

# ---- token timelines --------------------------------------------------------
class Tok:
    def __init__(self, start):
        self.segs, self.keys, self.t, self.start = [], [(0.0, 0.0)], 0.0, start
        self.events, self.dist = {}, 0.0
    def move(self, seg, name=None, speed=V):
        self.segs.append(seg)
        self.dist += seg.length
        self.t += seg.length / speed
        self.keys.append((self.t, self.dist))
        if name: self.events[name] = self.t
        return self
    def wait(self, s, name=None):
        if name: self.events[name] = self.t
        self.t += s
        self.keys.append((self.t, self.dist))
        return self
    def mark(self, name):
        self.events[name] = self.t
        return self

def pct(x): return f'{x:.4f}'.rstrip('0').rstrip('.') or '0'

def motion(tok):
    """animateMotion for a token; local timeline padded to T."""
    assert tok.t <= T - 0.3, tok.t
    keys = tok.keys + [(T, tok.dist)]
    kt = ';'.join(pct(t/T) for t, _ in keys)
    kp = ';'.join(pct(d/tok.dist) for _, d in keys)
    ks = ';'.join(EASE if b[1] > a[1] else LIN for a, b in zip(keys, keys[1:]))
    d = path(*tok.segs)
    return (f'<animateMotion dur="{T:g}s" begin="{-tok.start:g}s" repeatCount="indefinite" calcMode="spline" '
            f'keyTimes="{kt}" keyPoints="{kp}" keySplines="{ks}" path="{d}"/>')

def window(times, values, begin, attr='opacity', calc='linear'):
    """Animate attr through values at local times (seconds), padded to 0 and T."""
    times, values = list(times), list(values)
    if times[0] > 0: times, values = [0] + times, [values[0]] + values
    if times[-1] < T: times, values = times + [T], values + [values[-1]]
    assert times == sorted(times) and 0 <= times[0] and times[-1] <= T, times
    return (f'<animate attributeName="{attr}" dur="{T:g}s" begin="{-begin:g}s" repeatCount="indefinite" '
            f'calcMode="{calc}" keyTimes="{";".join(pct(t/T) for t in times)}" values="{";".join(values)}"/>')

def fade(tok, t_in, t_out):
    return window([t_in, t_in + 0.5, t_out - 0.5, t_out], ['0', '1', '1', '0'], tok.start)

# A: build and check loop. B: three gates. C: FIX round. D: sweep and shepherd orbit.
A_ = Tok(start=0.0).wait(0.8).mark('gate').move(seg_pb).wait(0.3).move(seg_check, speed=110).wait(0.3) \
    .move(seg_br).wait(0.4).move(seg_rj).wait(0.3).move(cat(seg_jo, seg_ohalf, seg_oc)).mark('close').wait(0.8)
B_ = Tok(start=13.5).wait(0.6).move(seg_pb).wait(0.3).move(seg_br).mark('review').wait(0.6)
b_rj0 = B_.t
B_.move(seg_rj, speed=V*0.75)
b_rj1 = B_.t
B_.wait(0.4).move(cat(seg_jo, seg_ohalf, seg_oc)).wait(0.8)
C_ = Tok(start=5.0).wait(0.5).move(seg_br).wait(0.3).move(seg_rj).wait(0.4)  # emerges from Build
c_fix0 = C_.t
C_.move(seg_fix).wait(0.3)
c_fix1 = C_.t
C_.move(seg_br).wait(0.2).move(seg_rj).wait(0.3).move(cat(seg_jo, seg_ohalf, seg_oc)).wait(0.5)
D_ = Tok(start=9.0).wait(0.4).move(seg_sweep).wait(0.3).move(seg_br).wait(0.3).move(seg_rj).wait(0.3) \
    .move(seg_jo).move(seg_ofull, speed=90).move(seg_ohalf, 'merge').wait(0.6).move(seg_oc).wait(0.8)
MEM = Tok(start=0.0).move(seg_mem, speed=V*0.8)
MEM.start = (A_.start - MEM.t) % T      # memory reaches Plan as A leaves the morning gate
for name, tok in zip('ABCDM', (A_, B_, C_, D_, MEM)):
    print(name, f'{tok.t:.2f}s', f'{tok.dist:.0f}u', file=sys.stderr)

# ---- SVG --------------------------------------------------------------------
FONT = "font-family=\"-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif\""

def token(tok, extra='', core='core'):
    return (f'<g class="tok" opacity="0">{fade(tok, 0, tok.t)}{motion(tok)}'
            f'<circle r="22" fill="url(#glow)"/><circle r="7" fill="{{{core}}}" stroke="{{accent}}" stroke-width="3">{extra}</circle></g>')

def ghost(seg, tok, t0, t1):
    keys = [0, t0, t1, T]
    kt = ';'.join(pct(t/T) for t in keys)
    return (f'<g class="tok" opacity="0">'
            + window([t0 - 0.2, t0, t1, t1 + 0.2], ['0', '1', '1', '0'], tok.start)
            + f'<animateMotion dur="{T:g}s" begin="{-tok.start:g}s" repeatCount="indefinite" calcMode="spline" '
              f'keyTimes="{kt}" keyPoints="0;0;1;1" keySplines="{LIN};{EASE};{LIN}" path="{path(seg)}"/>'
            f'<circle r="22" fill="url(#glow)"/><circle r="7" fill="{{core}}" stroke="{{accent}}" stroke-width="3"/></g>')

def pulse(d, tok, t):
    return (f'<path class="pulse" d="{d}" fill="none" stroke="{{warm}}" stroke-width="3" opacity="0">'
            + window([t - 0.1, t + 0.4, t + 1.2, t + 2.4], ['0', '0.9', '0.9', '0'], tok.start) + '</path>')

def shield(x, y):
    return f'<use href="#shield" x="{x}" y="{y}"/>'

O = (600, 432)          # owner
OW = 128
links = {   # owner touchpoints: path, label, label position
    'gate':   (f'M {O[0]-OW/2:g} {O[1]} C 450 {O[1]+4}, 330 {P[1]+22}, {P[0]+60} {P[1]+26}', 'morning gate', (392, 452)),
    'review': (f'M {O[0]+20} {O[1]-24} C 640 330, {R[0]} 300, {R[0]} {R[1]+28}', 'decision', (756, 318)),
    'merge':  (f'M {O[0]+OW/2:g} {O[1]-8} C 830 {O[1]-12}, 960 410, {OC[0]-14} {OC[1]+33}', 'merge', (872, 440)),
    'close':  (f'M {O[0]+30} {O[1]+24} C 680 500, 820 {CL[1]+6}, {CL[0]-68} {CL[1]+6}', 'draft to send', (760, 520)),
}

def svg(p):
    ring = '<rect class="ring" x="22" y="22" width="1156" height="576" rx="22" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="2 7"/>'
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 620" role="img" aria-labelledby="title desc">',
        '<title id="title">WUWEI day loop</title>',
        '<desc id="desc">The WUWEI day is a loop. Plan, the owner\'s morning gate, leads to Build, where each item is built and checked until its checks pass. '
        'Review fans out to architecture, quality and security gates; a FIX verdict sends the item back to Build for one fix round and a delta check. '
        'A shepherd moves each pull request through CI, review threads and rebases until it merges, then Close runs the retro. '
        'Memory folds the learnings back into charters and notes so tomorrow\'s Plan starts from them. A sweep adds new work during the day. '
        'The owner is touched only at the morning gate, decisions, drafts to send and merges. Guards act at action time around every step.</desc>',
        '<style><![CDATA[',
        '.flow{stroke-dasharray:2 14;animation:flow 2.4s linear infinite}',
        '.slow{animation-duration:4s}',
        '@keyframes flow{to{stroke-dashoffset:-32}}',
        '.ring{animation:breathe 9s ease-in-out infinite}',
        '@keyframes breathe{0%,100%{opacity:.35}50%{opacity:.8}}',
        '@media (prefers-reduced-motion:reduce){.tok,.pulse{display:none}.flow,.ring{animation:none}}',
        ']]></style>',
        '<defs>',
        '<radialGradient id="halo" cx="50%" cy="58%" r="60%"><stop offset="0" stop-color="{accent}" stop-opacity="0.10"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="glow"><stop offset="0" stop-color="{accent}" stop-opacity="0.6"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>',
        '<marker id="ha" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="{accent}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>',
        '<marker id="hc" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="{coral}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>',
        '<g id="shield"><path d="M0 -9L7.5 -6V0.5C7.5 5 4.2 8 0 10C-4.2 8 -7.5 5 -7.5 0.5V-6Z" fill="{bg}" stroke="{accent}" stroke-width="1.6"/>'
        '<path d="M-3.2 0.4L-0.8 2.8L3.4 -1.8" fill="none" stroke="{accent}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></g>',
        '</defs>',
        '<rect width="1200" height="620" rx="28" fill="{bg}"/>',
        '<rect width="1200" height="620" rx="28" fill="url(#halo)"/>',
        ring,
        # guard ring label, cut into the ring
        '<rect x="930" y="12" width="232" height="22" fill="{bg}"/>',
        shield(952, 23),
        f'<text x="970" y="29" fill="{{muted}}" {FONT} font-size="16">Guards at action time</text>',
        # title
        f'<text x="56" y="80" fill="{{text}}" {FONT} font-size="40" font-weight="700">无为 <tspan fill="{{atext}}">WUWEI</tspan></text>',
        f'<text x="57" y="112" fill="{{muted}}" {FONT} font-size="18">A chartered team of agents, one calm day</text>',
        # owner links (under everything else)
        '<g fill="none" stroke="{warm}" stroke-width="1.6" stroke-dasharray="3 6" opacity="0.8">',
        *[f'<path d="{d}"/>' for d, _, _ in links.values()],
        '</g>',
        # edges
        '<g fill="none" stroke-linecap="round">',
        f'<path d="{path(seg_mem)}" stroke="{{accent}}" stroke-opacity="0.28" stroke-width="3"/>',
        f'<path d="{path(seg_pb, seg_br, seg_rj, seg_jo, seg_ohalf, seg_oc)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="3.5"/>',
        f'<path d="{path(lane_top)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="{path(lane_bot)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<circle cx="{OC[0]}" cy="{OC[1]}" r="{OR}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<circle cx="{KC[0]}" cy="{KC[1]}" r="{KR}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="M {f(B)} L {f(KT)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="{path(seg_sweep)}" stroke="{{accent}}" stroke-opacity="0.35" stroke-width="2"/>',
        f'<path d="{path(fix_a, fix_b, fix_c)}" stroke="{{coral}}" stroke-opacity="0.45" stroke-width="2"/>',
        # flowing dashes
        f'<path d="{arrow_mem}" stroke="{{accent}}" stroke-opacity="0" stroke-width="3" marker-end="url(#ha)"/>',
        f'<path d="{arrow_close}" stroke="{{accent}}" stroke-opacity="0" stroke-width="3" marker-end="url(#ha)"/>',
        f'<path class="flow slow" d="{path(seg_mem)}" stroke="{{accent}}" stroke-width="3"/>',
        f'<path class="flow" d="{path(seg_pb, seg_br, seg_rj, seg_jo, seg_ohalf, seg_oc)}" stroke="{{accent}}" stroke-width="3.5"/>',
        f'<path class="flow" d="{path(lane_top)}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="{path(lane_bot)}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="M {f(OT)} {seg_ofull.d}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="M {f(KT)} A {KR} {KR} 0 0 1 {f(KB)} A {KR} {KR} 0 0 1 {f(KT)}" stroke="{{accent}}" stroke-width="2.5"/>',
        f'<path class="flow" d="{path(seg_sweep)}" stroke="{{accent}}" stroke-width="2.5" marker-end="url(#ha)"/>',
        f'<path class="flow" d="{path(fix_a, fix_b, fix_c)}" stroke="{{coral}}" stroke-width="2.5" marker-end="url(#hc)"/>',
        '</g>',
        # owner pulses
        pulse(links['gate'][0], A_, A_.events['gate']),
        pulse(links['close'][0], A_, A_.events['close']),
        pulse(links['review'][0], B_, B_.events['review']),
        pulse(links['merge'][0], D_, D_.events['merge']),
        # tokens, under the nodes so they pass behind them
        token(MEM).replace('r="7"', 'r="5"'),
        token(A_), token(B_), ghost(lane_top, B_, b_rj0, b_rj1), ghost(lane_bot, B_, b_rj0, b_rj1),
        token(C_, window([c_fix0 - 0.1, c_fix0 + 0.4, c_fix1 - 0.4, c_fix1], ['{accent}', '{coral}', '{coral}', '{accent}'], C_.start, attr='stroke')),
        token(D_),
        # gate markers and labels
        f'<g fill="{{panel}}" stroke="{{accent}}" stroke-width="2">'
        + ''.join(f'<circle cx="{GX}" cy="{R[1]+dy}" r="8"/>' for dy in (-LANE, 0, LANE)) + '</g>',
        f'<g fill="{{muted}}" {FONT} font-size="16" text-anchor="middle">'
        f'<text x="{GX}" y="{R[1]-LANE-16}">architecture</text><text x="{GX}" y="{R[1]-16}">quality</text>'
        f'<text x="{GX}" y="{R[1]+LANE-16}">security</text></g>',
        # main nodes
        f'<g {FONT} font-size="24" font-weight="600" text-anchor="middle">',
        *[f'<g><rect x="{c[0]-w/2:g}" y="{c[1]-25}" width="{w}" height="56" rx="18" fill="{{shadow}}" opacity="0.22"/>'
          f'<rect x="{c[0]-w/2:g}" y="{c[1]-28}" width="{w}" height="56" rx="18" fill="{{panel}}" stroke="{{accent}}" stroke-width="2"/>'
          f'<text x="{c[0]}" y="{c[1]+8}" fill="{{text}}">{t}</text></g>'
          for c, w, t in ((P, 136, 'Plan'), (B, 136, 'Build'), (R, 150, 'Review'), (CL, 136, 'Close'))],
        '</g>',
        shield(B[0]+64, B[1]-28), shield(R[0]+71, R[1]-28), shield(OC[0]+26, OC[1]-26), shield(CL[0]+64, CL[1]-28),
        # owner node
        f'<rect x="{O[0]-OW/2:g}" y="{O[1]-21}" width="{OW}" height="48" rx="24" fill="{{shadow}}" opacity="0.22"/>',
        f'<rect x="{O[0]-OW/2:g}" y="{O[1]-24}" width="{OW}" height="48" rx="24" fill="{{panel}}" stroke="{{warm}}" stroke-width="2"/>',
        f'<text x="{O[0]}" y="{O[1]+7}" fill="{{warm}}" {FONT} font-size="20" font-weight="600" text-anchor="middle">Owner</text>',
        # captions
        f'<g fill="{{muted}}" {FONT} font-size="16">',
        f'<text x="{KC[0]}" y="{KC[1]+6}" text-anchor="middle">check</text>',
        f'<text x="{KC[0]+KR+12}" y="{KC[1]+6}">test first</text>',
        f'<text x="{OC[0]}" y="{OC[1]+6}" text-anchor="middle">PR</text>',
        f'<text x="{OC[0]-OR-14}" y="{OC[1]+2}" text-anchor="end">shepherd</text>',
        f'<text x="{OC[0]-OR-14}" y="{OC[1]+22}" text-anchor="end">CI, threads, rebase</text>',
        f'<text x="{SW0[0]-12}" y="{SW0[1]+6}" text-anchor="end">sweep: new work</text>',
        '</g>',
        f'<text x="742" y="84" fill="{{coral}}" {FONT} font-size="16" text-anchor="middle">FIX: one fix round, then a delta check</text>',
        f'<text x="585" y="584" fill="{{atext}}" {FONT} font-size="18" font-weight="600" text-anchor="middle">Memory across days</text>',
        f'<g fill="{{warm}}" {FONT} font-size="16" text-anchor="middle">'
        + ''.join(f'<text x="{x}" y="{y}">{t}</text>' for _, t, (x, y) in links.values()) + '</g>',
        '</svg>',
    ]
    out = '\n'.join(parts) + '\n'
    for k, v in p.items():
        out = out.replace('{' + k + '}', v)
    return out

if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    for name, pal in PAL.items():
        (root / f'docs/assets/hero-{name}.svg').write_text(svg(pal))
