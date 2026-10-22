"""The plan: goal-linked items, ranked by WSJF or RICE. The plan file is the day's contract."""

import contextlib
import json
import re
from pathlib import Path

from wuwei import ws

FIB = (1, 2, 3, 5, 8, 13, 20)
FIELDS = {'wsjf': ('value', 'time', 'risk', 'size'), 'rice': ('reach', 'impact', 'confidence', 'effort')}
TIERS = ('light', 'smart', 'standard', 'full')
CLASSES = ('expedite', 'fixed-date', 'standard', 'intangible')  # Kanban classes of service, most urgent first
HOSTS = ('agent', 'session')  # where an item's builder runs: an Agent-tool seat here, or its own session; gates always here


def _path(root):
    return Path(root) / ws.DIR / 'plan.json'


def items(root):
    try:
        return json.loads(_path(root).read_text(encoding='utf-8')).get('items', [])
    except (OSError, ValueError):
        return []


def find(root, item_id):
    return next((item for item in items(root) if item.get('id', '').lower() == str(item_id).lower()), None)


def delay(framework, scores):  # the cost of delay: the score's numerator
    if framework == 'wsjf':
        if bad := [k for k in FIELDS['wsjf'] if scores.get(k) not in FIB]:
            raise ValueError(f'WSJF scores use 1, 2, 3, 5, 8, 13, 20: check {", ".join(bad)}')
        return scores['value'] + scores['time'] + scores['risk']
    if missing := [k for k in FIELDS['rice'] if not isinstance(scores.get(k), (int, float)) or scores[k] <= 0]:
        raise ValueError(f'RICE needs positive {", ".join(missing)}')
    return scores['reach'] * scores['impact'] * scores['confidence']


def score(framework, scores, waiting=0):
    return round((delay(framework, scores) + waiting) / scores['size' if framework == 'wsjf' else 'effort'], 2)


def cost(item, rows, days=None):
    """The score now: WSJF time criticality one Fibonacci step higher per day in progress (days by id), plus the cost of
    delay of each open item that waits on this one. A score the scale refuses stays as stored."""
    def aged(row):
        found, step = dict(row.get('scores') or {}), (days or {}).get(row['id'], 0)
        if row.get('framework', 'wsjf') == 'wsjf' and found.get('time') in FIB:
            found['time'] = FIB[min(FIB.index(found['time']) + step, len(FIB) - 1)]
        return found
    try:
        waiting = sum(delay(r.get('framework', 'wsjf'), aged(r)) for r in rows
                      if r.get('status') == 'open' and item['id'].lower() in {str(a).lower() for a in r.get('after') or ()})
        return score(item.get('framework', 'wsjf'), aged(item), waiting)
    except (ValueError, KeyError, TypeError):
        return item.get('score', 0)


def save(root, rows):
    for row in rows:
        row['score'] = cost(row, rows) if row.get('scores') else row.get('score', 0)
    old = {o.get('id'): o for o in items(root)}  # a changed item is stamped, unless it brings another clone's stamp (merge)
    [r.update(changed=ws.now().isoformat()) for r in rows if {**r, 'score': 0} != {**(was := old.get(r.get('id'), {})), 'score': 0}
     and r.get('changed') == was.get('changed')]  # a score is derived from the scores and the waiters: no edit
    rows.sort(key=lambda item: (item.get('status') != 'open', -item.get('score', 0)))
    ws.atomic_write(_path(root), json.dumps({'items': rows}, indent=1) + '\n')


def merge(root, data):  # another clone's plan.json merged into this one by item id: the newer change to each item wins, this clone's on a tie
    with contextlib.suppress(OSError, ValueError, TypeError, KeyError, AttributeError):  # None for a file that is not a plan: last writer wins, as before
        return save(root, list({r['id']: r for r in sorted(json.loads(data)['items'] + json.loads(_path(root).read_bytes())['items'], key=lambda r: r.get('changed') or '')}.values())) or True


def expedite(rows, item_id):  # at most one expedite item is in progress (open)
    if other := next((r['id'] for r in rows if r.get('class') == 'expedite' and r.get('status') == 'open'
                      and r['id'].lower() != str(item_id).lower()), None):
        raise ValueError(f'{other} is already expedite: at most one expedite item is in progress; finish it first')


# The names a lead may give its scores, mapped to the framework's own.
ALIASES = {'business_value': 'value', 'user_business_value': 'value', 'time_criticality': 'time',
           'risk_reduction': 'risk', 'opportunity_enablement': 'risk', 'job_size': 'size'}


def add(root, item_id, title, goal, repo, tier, scores, why='', promise='', acceptance=(), prs=(), domain='', in_doubt=False,
        cls=None, after=(), host='agent'):
    """Add an item, or update it in place when its id is already in the plan (a parked or dropped
    item reopens). The promise and acceptance travel with it, so every seat reads them here."""
    if tier not in TIERS or cls not in (None, *CLASSES):
        raise ValueError(f'tier must be one of {", ".join(TIERS)}; a class of service one of {", ".join(CLASSES)}')
    if host not in HOSTS:
        raise ValueError(f'host must be one of {", ".join(HOSTS)}, not {host!r}')
    if domain and not re.fullmatch(r'(clear|complicated|complex):[ \t]*\S.*', domain):  # the Cynefin domain and one line of why
        raise ValueError(f'domain must read "clear|complicated|complex: <one line of evidence>", not {domain!r}')
    (cls or (find(root, item_id) or {}).get('class')) == 'expedite' and expedite(items(root), item_id)
    after, waits = [after] if isinstance(after, str) else list(after), {r['id'].lower(): r.get('after') or () for r in items(root)}

    def reaches(a, seen):  # a is this item or waits on it through the stored after lists; each id is walked once (a merged cycle)
        key = str(a).lower()
        return key == str(item_id).lower() or key not in seen and not seen.add(key) and any(reaches(b, seen) for b in waits.get(key, ()))
    if missing := [a for a in after if find(root, a) is None or reaches(a, set())]:
        raise ValueError(f'{", ".join(missing)} is not in the plan, or is this item or waits on it: a wait never closes a cycle')
    framework = ws.config(root)['prioritisation']
    scores = {ALIASES.get(k, k): v for k, v in scores.items()}
    fields = {'title': title, 'goal': goal, 'repo': repo, 'tier': tier, 'framework': framework, 'scores': scores,
              'score': score(framework, scores), 'why': why, 'promise': promise, 'acceptance': list(acceptance), 'prs': list(prs), 'domain': domain, 'in_doubt': bool(in_doubt),
              'class': cls, 'after': [find(root, a)['id'] for a in after], 'host': host}
    rows = items(root)
    item = next((row for row in rows if row.get('id', '').lower() == str(item_id).lower()), None)
    if item is not None:
        if any(fields[k] and fields[k] != item.get(k) for k in ('promise', 'acceptance')):
            item['approved'] = False  # the owner approved the old contract, not this one
        item.update({k: v for k, v in fields.items() if v or k in ('scores', 'score', 'tier')}, status='open',
                    prs=list(dict.fromkeys(item.get('prs', []) + fields['prs'])))  # a re-add keeps the PRs linked before
        save(root, rows)
        ws.record(root, 'item.updated', {k: item[k] for k in ('id', 'goal', 'repo', 'tier', 'score')})
        return item
    item = {'id': item_id, **fields, 'status': 'open', 'added': ws.today(), 'approved': False}
    save(root, rows + [item])
    ws.record(root, 'item.added', {k: item[k] for k in ('id', 'goal', 'repo', 'tier', 'score')})
    return item


def add_from(root, path):
    """Add the lead's candidates from its JSON file: a list, or {"candidates": [...]}."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = data.get('candidates') if isinstance(data, dict) else data
    if not isinstance(rows, list) or not all(isinstance(c, dict) and c.get('id') and c.get('title') for c in rows):
        raise ValueError(f'{path}: expected a list or {{"candidates": [{{"id", "title", ...}}]}}; nothing added')
    found = []
    for c in rows:
        scores = c.get('scores') or {k: c[k] for k in (*FIELDS['wsjf'], *FIELDS['rice'], *ALIASES) if k in c}
        found.append(add(root, c['id'], c['title'], c.get('goal', ''), c.get('repo') or c.get('repository', ''),
                         c.get('tier', 'smart'), scores, c.get('why', ''), c.get('promise', ''),
                         c.get('acceptance') or c.get('scenarios') or c.get('accept') or (), (), c.get('domain', ''), c.get('in_doubt'),
                         c.get('class'), c.get('after') or (), c.get('host') or 'agent'))
    return found


def mark(root, item_id, status, reason='', **fields):
    rows = items(root)
    if (item := next((row for row in rows if row['id'].lower() == item_id.lower()), None)) is None:
        raise ValueError(f'{item_id} is not in the plan')
    status == 'open' != item.get('status') and item.get('class') == 'expedite' and expedite(rows, item['id'])  # a restore starts it
    item.update(fields, status=status, reason=reason)
    save(root, rows)
    ws.record(root, f'item.{status}', {'id': item['id'], 'reason': reason})
    return item


def followup(root, title, repo, goal, why):
    """A small item the process owes itself, such as closing an accepted exception."""
    taken = {item['id'] for item in items(root)}
    item_id = next(f'X-{n}' for n in range(1, len(taken) + 2) if f'X-{n}' not in taken)
    scores = ({'value': 3, 'time': 3, 'risk': 5, 'size': 1} if ws.config(root)['prioritisation'] == 'wsjf'
              else {'reach': 1, 'impact': 1, 'confidence': 1, 'effort': 0.5})
    item = add(root, item_id, title, goal, repo, 'light', scores, why)
    rows = items(root)
    next(r for r in rows if r['id'] == item_id)['approved'] = True  # the owner accepted the exception
    save(root, rows)
    return item


def approve(root, answer):
    """The owner approved the plan as shown: every open item is approved."""
    rows = items(root)
    ids = [row['id'] for row in rows if row.get('status', 'open') == 'open']
    for row in rows:
        if row['id'] in ids:
            row['approved'] = True
    save(root, rows)
    ws.record(root, 'plan.approved', {'items': ids, 'answer': answer})
    return ids


def owe(root, where, what, who, within='4h', due=None):
    """A reply someone is waiting for: where (a thread link or id), what was asked, who asked, when due.
    One open reply per place; a send into that place closes it (hook.post_tool)."""
    import datetime
    rows = items(root)
    if found := next((r for r in rows if r.get('kind') == 'reply' and r.get('status') == 'open' and r['where'] == where), None):
        return found
    if due is None:
        unit = {'m': 'minutes', 'h': 'hours', 'd': 'days'}[within[-1]]
        due = (ws.now() + datetime.timedelta(**{unit: int(within[:-1])})).isoformat(timespec='seconds')
    taken = {row['id'] for row in rows}
    item = {'id': next(f'R-{n}' for n in range(1, len(taken) + 2) if f'R-{n}' not in taken), 'kind': 'reply',
            'title': what, 'where': where, 'who': who, 'due': due, 'status': 'open', 'score': 0, 'approved': True,
            'added': ws.today(), 'opened': ws.now().isoformat(timespec='seconds')}
    save(root, rows + [item])
    ws.record(root, 'reply.owed', {'id': item['id'], 'where': where, 'who': who, 'due': due})
    return item
