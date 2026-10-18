"""The plan as a view to approve (#990): one picture and one short question, from the same rows."""

from html import escape
from pathlib import Path
import re

from wuwei import plan, ws

FORMULA = {'wsjf': 'WSJF: (value + time + risk) / size', 'rice': 'RICE: reach x impact x confidence / effort'}
STYLE = '''<style>
.wv{--bg:#F4FAF8;--panel:#FFFFFF;--text:#183B37;--muted:#42615C;--accent:#00735F;--line:#D5E6E1;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:var(--text);
background:var(--bg);padding:16px;border-radius:14px;max-width:960px}
@media (prefers-color-scheme: dark){.wv{--bg:#102622;--panel:#193B35;--text:#ECF8F5;--muted:#B1CBC4;
--accent:#00C9A7;--line:#2B4F48}}
.wv h2{margin:0 0 12px;font-size:20px}.wv .tiles{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.wv .tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
.wv .tile b{display:block;font-size:18px;color:var(--accent)}.wv .tile span{font-size:12px;color:var(--muted)}
.wv .goal{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:8px 0}
.wv .goal h3{margin:0 0 6px;font-size:15px}.wv .goal small{color:var(--muted)}
.wv table{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}
.wv col.id{width:12%}.wv col.t{width:44%}.wv col.n{width:10%}.wv col.r{width:14%}
@media (max-width:560px){.wv .opt{display:none}.wv table{table-layout:auto}}.wv td,.wv th{text-align:left;padding:4px 6px;
border-top:1px solid var(--line)}.wv th{color:var(--muted);font-weight:600}
</style>'''


def goals(root):
    """{G-n: (outcome, date)} from goals.md, keys in any case."""
    path = Path(root) / ws.DIR / 'goals.md'
    text = path.read_text(encoding='utf-8') if path.is_file() else ''
    found = {}
    for block in re.split(r'^## ', text, flags=re.M)[1:]:
        name = block.split('\n', 1)[0].strip()
        field = lambda key: (re.search(rf'^{key}:[ \t]*(.+)$', block, re.M | re.I) or [None, ''])[1].strip()  # noqa: E731
        found[name] = (field('outcome'), field('date'))
    return found


def goal_status(root):
    """([(G-n, date)] past its ISO date, not ruled met nor kept open on or after it; [G-n ruled met]); the latest ruling counts (#975)."""
    ruled = {r['data'].get('goal'): (r['data'].get('approved'), r['ts'][:10]) for r in ws.rows(root, 'ruling') if r['data'].get('kind') == 'goal.met'}
    due = [(name, date) for name, (_, date) in goals(root).items() if re.fullmatch(r'G-[0-9]+', name, re.I) and re.fullmatch(
        r'[0-9]{4}-[0-9]{2}-[0-9]{2}', date) and not (seen := ruled.get(name.upper(), (False, '')))[0] and seen[1] < date < ws.today()]
    return due, sorted(goal for goal, (met, _) in ruled.items() if met)


def _size(item):
    scores = item.get('scores') or {}
    return scores.get('size', 0) if item.get('framework', 'wsjf') == 'wsjf' else scores.get('effort', 0)


def render(root):
    """(page, summary, line): the HTML page, a markdown summary of 30 lines or fewer, the question's line."""
    framework = ws.config(root)['prioritisation']
    known = goals(root)
    open_items = [i for i in plan.items(root) if i.get('status', 'open') == 'open']
    groups = {}
    for item in open_items:
        groups.setdefault(item.get('goal') or 'unplanned', []).append(item)
    planned = [g for g in groups if g != 'unplanned']
    effort = sum(_size(i) for i in open_items)
    unit = 'build hours (1 size point = 1 h)' if framework == 'wsjf' else 'seat-days of effort'
    line = (f'{len(open_items)} items on {len(planned)} goals'
            + (f' and {len(groups["unplanned"])} unplanned' if 'unplanned' in groups else '')
            + f', about {effort:g} {unit}; the plan is shown above.')
    tiles = [(FORMULA[framework], 'ranking'), (f'{effort:g}', unit), (str(len(open_items)), 'open items'),
             (str(sum(1 for i in open_items if not i.get('approved'))), 'awaiting approval')]
    cards, summary = [], [f'**Plan** ({FORMULA[framework]}): {line[:-len("; the plan is shown above.")]}', '']
    for goal in sorted(groups, key=lambda g: (g == 'unplanned', g)):
        outcome, date = known.get(goal, ('', ''))
        rows = sorted(groups[goal], key=lambda i: -i.get('score', 0))
        cells = ''.join(f'<tr><td>{escape(i["id"])}</td><td>{escape(i["title"])}</td><td>{escape(i.get("tier", ""))}</td>'
                        f'<td>{i.get("score", 0):g}</td><td class="opt">{_size(i):g}</td>'
                        f'<td class="opt">{escape(i.get("repo", ""))}</td>'
                        f'<td class="opt">{"approved" if i.get("approved") else "new"}</td></tr>' for i in rows)
        cards.append(f'<div class="goal"><h3>{escape(goal)} {escape(outcome)}</h3>'
                     + (f'<small>due {escape(date)}</small>' if date else '')
                     + '<table><colgroup><col class="id"><col class="t"><col class="n"><col class="n"><col class="n opt">'
                     '<col class="r opt"><col class="n opt"></colgroup><tr><th>Item</th><th>Title</th><th>Tier</th>'
                     f'<th>Score</th><th class="opt">Size</th><th class="opt">Repo</th><th class="opt">State</th></tr>'
                     f'{cells}</table></div>')
        summary += [f'{goal} {outcome}'.strip(), '| Item | Title | Tier | Score |', '|---|---|---|---|']
        summary += [f'| {i["id"]} | {i["title"][:50]} | {i.get("tier", "")} | {i.get("score", 0):g} |' for i in rows]
    if len(summary) > 30:
        summary = summary[:29] + [f'and {len(summary) - 29} more lines in .wuwei/plan.html']
    body = ''.join(f'<div class="tile"><b>{escape(value)}</b><span>{escape(label)}</span></div>' for value, label in tiles)
    fragment = f'{STYLE}<div class="wv"><h2>Plan</h2><div class="tiles">{body}</div>{"".join(cards)}</div>'
    page = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>WUWEI plan</title><style>body{margin:0;padding:16px;background:#F4FAF8}@media '
            f'(prefers-color-scheme: dark){{body{{background:#102622}}}}</style></head><body>{fragment}</body></html>')
    return page, '\n'.join(summary), line


def write(root):
    page, summary, line = render(root)
    path = Path(root) / ws.DIR / 'plan.html'
    ws.atomic_write(path, page)
    return path, summary, line
