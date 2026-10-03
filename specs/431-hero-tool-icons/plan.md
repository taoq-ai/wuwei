# Implementation Plan: The hero shows the tools behind each station

**Branch**: `431-hero-tool-icons` | **Spec**: [spec.md](spec.md) | **Issue**: #431

## Summary

Add one table (`ROWS`) and one glyph dict (`ICONS`) to `scripts/build-hero.py`, a
`tool()` drawing and a `tools_text()` sentence, and emit two groups in `svg()`: animated
rows (class `tools`) and a still copy (class `still`) that only reduced motion shows.
Motion reuses `window()` over the existing cycle `T`. The tests check the table against
the repository, the titles, the still copy, external references, alt text, NOTICE and a
new size cap. README, `docs/site/index.md`, NOTICE get text; both SVGs are regenerated.
No node or path moves.

## Technical Context

- Generator: `scripts/build-hero.py`, stdlib only, run as `python3 scripts/build-hero.py`
  from the repository root; writes `docs/site/assets/hero-{dark,light}.svg`.
- Tests: `tests/test_docs.py`, pytest; run with the pipeline's interpreter
  (`python -m pytest -q`). Plain `python3` on this machine has no pytest.
- Icon data: Simple Icons 16.33.0. Fetch each glyph once with a scratch script outside the
  repository from `https://cdn.jsdelivr.net/npm/simple-icons@16.33.0/icons/<slug>.svg`,
  take the `d` attribute, paste it into `ICONS`. The generator never touches the network.
  Glyphs needed: linear, jira, github, claude, pytest, gitlab, notion, confluence,
  markdown, discord, pagerduty, grafana, sentry, datadog (about 14 KB of path data;
  grafana and datadog are the large ones).
- Rendering for the visual check: `qlmanage -t -s 1200 -o <scratch dir> <svg>` writes a
  square PNG with the hero centred (viewBox y = image y - 290 at size 1200); `-s 830`
  approximates the README width. For reduced motion, render a scratch copy with
  `@media (prefers-reduced-motion:reduce)` replaced by `@media all`. QuickLook runs SMIL
  at t = 0, so the default render shows the first row of each station.
- The WUWEI hooks may refuse compound shell lines; put multi-step commands in a script
  file and run it with `bash <file>` or `python3 <file>`.

## Constitution Check

- I. Stdlib only: the generator stays stdlib; no change under `cli/` or `adapters/`. Pass.
- III/IV. One behaviour, one test, test first: every behaviour below has its test task
  before its implementation task in `tasks.md`. Pass.
- V. Ponytail: one table drives the drawing, the alt sentence and the test; one `tool()`
  serves both the animated rows and the still copy; one highlight per row instead of one
  animate per icon; glyphs defined once and reused with `<use>`; `window()` reused. No
  class, no config. Pass.
- VII. Security: no external references in the SVG (new test), no script. Pass.

## Changes

### 1. `scripts/build-hero.py`

Data, after `PAL`:

```python
# Simple Icons 16.33.0 (CC0-1.0, https://github.com/simple-icons/simple-icons): 24x24 path data
ICONS = {'linear': '...', 'jira': '...', ...}   # 14 glyphs, one per slug

# Tools per row, one source for the drawing, the alt text and the shipped-versus-planned test.
# (row caption, row centre, [(name, label, glyph, proof, issue)]): glyph is an ICONS key or a
# two-letter badge; proof is the repository path that shows the tool ships, None when planned;
# issue is the issue that will ship a planned tool, or None. Rows sharing a centre alternate.
ROWS = [
    ('Plan tracker', (124, 262), [
        ('Linear', 'Linear', 'linear', 'adapters/tracker/linear.py', None),
        ('Jira', 'Jira', 'jira', None, '#417'),
        ('GitHub Projects', 'Projects', 'github', None, '#417')]),
    ('Plan spec engine', (124, 262), [
        ('spec-kit', 'spec-kit', 'SK', None, '#412'),
        ('superpowers', 'superpowers', 'SP', None, '#412'),
        ('OpenSpec', 'OpenSpec', 'OS', None, '#412')]),
    ('Build runtime', (365, 282), [
        ('Claude Code', 'Claude', 'claude', 'adapters/runtime/claude.py', None),
        ('Codex', 'Codex', 'CX', 'adapters/runtime/codex.py', None)]),
    ('Review gate tools', (722, 150), [
        ('ZIRAN', 'ZIRAN', 'ZI', 'adapters/scanner/ziran.py', None),
        ('pytest', 'pytest', 'pytest', 'cli/wuwei/calibrate.py', None)]),
    ('Close code host', (1115, 418), [
        ('GitHub', 'GitHub', 'github', 'adapters/code_host/github.py', None),
        ('GitLab', 'GitLab', 'gitlab', None, '#370')]),
    ('Close docs', (1068, 552), [
        ('Notion', 'Notion', 'notion', None, '#419'),
        ('Confluence', 'Confluence', 'confluence', None, '#419'),
        ('Markdown', 'Markdown', 'markdown', None, '#419')]),
    ('Phone and DM', (378, 372), [
        ('Slack', 'Slack', 'SL', 'adapters/chat/slack.py', None),
        ('Claude mobile', 'Mobile', 'claude', 'cli/wuwei/control_plane.py', None),
        ('Teams', 'Teams', 'TE', None, None),
        ('Discord', 'Discord', 'discord', None, None)]),
    ('On-call', (1050, 70), [
        ('PagerDuty', 'PagerDuty', 'pagerduty', None, '#415'),
        ('Grafana', 'Grafana', 'grafana', None, '#415'),
        ('Sentry', 'Sentry', 'sentry', None, '#415'),
        ('Datadog', 'Datadog', 'datadog', None, '#415')]),
]
```

The centres are starting points read from a render of the current hero (spec, Current
state). Move them, and the pitch between icons, until the rendered PNGs show no overlap;
never move a node, path, orbit or gate marker.

As built: the space below Close fits one row, so Close code host sits right of Close and
only the two Plan rows share a centre. Glyphs are pre-scaled `<path id="i-{slug}">` defs (one
`<use x>` each) and the label paint sits on the `tools` and `still` groups, to stay under the
size cap. The pitch is 60, widened per row so adjacent labels never touch.

Functions (new, next to `shield()`):

- `tool(name, label, glyph, planned, x, y)`: one `<g>` with `<title>{name}</title>` or
  `<title>{name} (planned)</title>`, the glyph as `<use href="#i-{glyph}" .../>` sized 20
  (18 to 22 allowed) or a two-letter badge (rounded rect plus text) when `glyph` is not in
  `ICONS`, and the one-word label under it (font-size 12 or 13, `{muted}`). Shipped:
  solid, `fill="{text}"`. Planned: `fill="none" stroke="{muted}"` with a thin stroke; the
  label sets its own `fill` and `stroke="none"` so it stays readable inside a planned
  group.
- `row(caption, centre, tools, scale=1)`: the caption (font-size 13, `{muted}`) and the
  tools centred on `centre` at a fixed pitch; used by both groups below.
- `tools_text()`: the alt sentence, built from `ROWS` only:

  ```python
  def tools_text():
      def clause(caption, tools):
          shipped = [t[0] for t in tools if t[3]]
          planned = [t[0] for t in tools if not t[3]]
          parts = [', '.join(shipped)] if shipped else []
          parts += ['planned ' + ', '.join(planned)] if planned else []
          return f'{caption}: {"; ".join(parts)}.'
      return 'Tools, outlined when planned. ' + ' '.join(clause(c, t) for c, _, t in ROWS)
  ```

  Output: "Tools, outlined when planned. Plan tracker: Linear; planned Jira, GitHub
  Projects. Plan spec engine: planned spec-kit, superpowers, OpenSpec. Build runtime:
  Claude Code, Codex. Review gate tools: ZIRAN, pytest. Close code host: GitHub; planned
  GitLab. Close docs: planned Notion, Confluence, Markdown. Phone and DM: Slack, Claude
  mobile; planned Teams, Discord. On-call: planned PagerDuty, Grafana, Sentry, Datadog."

Changes inside `svg(p)`:

- `<desc>`: the existing text plus `' ' + tools_text()`.
- CSS: add `.still{display:none}` before the media query; the reduced-motion rule becomes
  `.tok,.pulse,.beat,.tools{display:none}.flow,.ring{animation:none}.still{display:inline}`.
  `test_hero_shows_the_current_day` already requires every class in that block.
- `<defs>`: one `<symbol id="i-{slug}" viewBox="0 0 24 24"><path d="..."/></symbol>` per
  `ICONS` entry.
- After the captions (so rows draw above the edges): `<g class="tools">` with, per row,
  a `<g>` holding a highlight rect (`fill="{accent}"`, low opacity, rounded) and
  `row(...)`. Rows that share a centre get an opacity `window()` so row k of n is shown
  during `[k*T/n, (k+1)*T/n]` with a 0.4 s fade (begin 0). The highlight gets
  `window(times, xs, 0, attr='x', calc='discrete')` stepping across the row's tools,
  evenly over the time the row is shown.
- Then `<g class="still">` with every row drawn by `row(...)` with no animation; rows that
  share a centre are stacked (the second offset downwards) at a smaller scale (about 0.8)
  so both fit the same region.

Not changed: `T`, `V`, `PAL`, every segment, token, pulse, ghost, node, orbit, gate marker
and link; the `__main__` writer.

### 2. `tests/test_docs.py`, written first

- Factor the loader of `test_hero_files_match_their_generator` (lines 312-315) into
  `_hero()` and use it there and in the new tests.
- New `test_hero_tools_match_the_repository` (the shipped-versus-planned rule):

  ```python
  OPEN_ISSUES = {'#370', '#412', '#415', '#417', '#419'}  # issues that ship planned hero tools

  def test_hero_tools_match_the_repository():
      hero = _hero()
      text = (SITE / 'assets/hero-light.svg').read_text()
      for _, _, tools in hero.ROWS:
          for name, _, glyph, proof, issue in tools:
              slug = name.lower().replace(' ', '_').replace('-', '')
              assert glyph in hero.ICONS or re.fullmatch(r'[A-Z]{2}', glyph), name
              if proof:
                  assert (ROOT / proof).is_file() and issue is None, name
                  assert text.count(f'<title>{name}</title>') == 2, name
              else:
                  assert not list(ROOT.glob(f'adapters/*/{slug}.py')), name
                  assert issue is None or issue in OPEN_ISSUES, name
                  assert text.count(f'<title>{name} (planned)</title>') == 2, name
  ```

  The count of 2 proves each tool is in the animated rows and in the still copy, and that
  its title carries the right status.
- `test_hero_shows_the_current_day`: the size cap at line 702 becomes
  `20000 + sum(len(d) for d in hero.ICONS.values()) + ALLOWANCE` with a literal allowance
  no larger than 12000 (set from the measured size, with a small margin); add
  `all(h.startswith('#') for h in re.findall(r'href="([^"]*)"', text))` and
  `'url(http' not in text`; add `hero.tools_text() in desc` (raw desc, before lowering)
  and, for the README alt and every `alt="..."` of a hero `<img>` in `docs/site/index.md`,
  `hero.tools_text() in alt`.
- `test_notice_credits_match_readme_acknowledgements`: add `'Simple Icons'` to the names
  tuple and assert `'16.33.0'` and `'CC0'` are in NOTICE. The existing URL check then
  requires the README Acknowledgements to carry the same URL.

### 3. Text

- `NOTICE`, "Third-party code": Simple Icons, Source
  `https://github.com/simple-icons/simple-icons`, Licence CC0-1.0 for the icon data; the
  brands themselves remain trademarks of their owners. Used: monochrome glyph path data
  (simple-icons 16.33.0) embedded in `scripts/build-hero.py` for the hero.
- `README.md`: the `alt` at line 5 gets `' ' + tools_text()` appended; Acknowledgements
  gains one bullet for Simple Icons with the same URL (CC0).
- `docs/site/index.md`: both alts (lines 5-6) get the same sentence; one sentence after
  the two `<img>` tags, for example "The icons under each station are the tools WUWEI works
  with: solid ones ship today, outlined ones are planned." Keep glossary words (gate,
  tier, page and the rest of `GLOSSARY`) out of it, or link them, or
  `test_glossary_words_link_at_first_use` fails.
- Regenerate both SVGs with `python3 scripts/build-hero.py`.

## Risks

- Crowding: the canvas is full; labels at 12 units are about 8 px at README width. If a
  row cannot fit legibly, shorten the label (one word is the rule) or tighten the pitch
  before touching anything else; record any moved caption in tasks.md.
- SMIL `x` on a rect with `calcMode="discrete"`: keyTimes must start at 0, which `window()`
  already pads. Check the stepping in a browser once (the built-in browser or Safari).
- The hex-mask test: icon data and highlight values carry no `#`; badge text is letters.

## Project Structure

Files touched: `scripts/build-hero.py`, `tests/test_docs.py`,
`docs/site/assets/hero-light.svg`, `docs/site/assets/hero-dark.svg`, `README.md`,
`docs/site/index.md`, `NOTICE`. No `research.md`, `data-model.md` or `contracts/`: the
table above is the whole data model, and the spec records the research.
