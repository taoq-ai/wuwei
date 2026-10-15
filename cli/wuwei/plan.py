"""The plan: goal-linked items, ranked by WSJF or RICE. The plan file is the day's contract."""

import json
from pathlib import Path

from wuwei import ws

FIB = (1, 2, 3, 5, 8, 13, 20)
FIELDS = {'wsjf': ('value', 'time', 'risk', 'size'), 'rice': ('reach', 'impact', 'confidence', 'effort')}
TIERS = ('light', 'standard', 'full')


def _path(root):
    return Path(root) / ws.DIR / 'plan.json'


def items(root):
    try:
        return json.loads(_path(root).read_text(encoding='utf-8')).get('items', [])
    except (OSError, ValueError):
        return []


def find(root, item_id):
    return next((item for item in items(root) if item.get('id', '').lower() == str(item_id).lower()), None)


def score(framework, scores):
    if framework == 'wsjf':
        bad = [k for k in FIELDS['wsjf'] if scores.get(k) not in FIB]
        if bad:
            raise ValueError(f'WSJF scores use 1, 2, 3, 5, 8, 13, 20: check {", ".join(bad)}')
        return round((scores['value'] + scores['time'] + scores['risk']) / scores['size'], 2)
    missing = [k for k in FIELDS['rice'] if not isinstance(scores.get(k), (int, float)) or scores[k] <= 0]
    if missing:
        raise ValueError(f'RICE needs positive {", ".join(missing)}')
    return round(scores['reach'] * scores['impact'] * scores['confidence'] / scores['effort'], 2)


def save(root, rows):
    rows.sort(key=lambda item: (item.get('status') != 'open', -item.get('score', 0)))
    ws.atomic_write(_path(root), json.dumps({'items': rows}, indent=1) + '\n')


def add(root, item_id, title, goal, repo, tier, scores, why=''):
    if tier not in TIERS:
        raise ValueError(f'tier must be one of {", ".join(TIERS)}')
    if find(root, item_id):
        raise ValueError(f'{item_id} is already in the plan')
    framework = ws.config(root)['prioritisation']
    item = {'id': item_id, 'title': title, 'goal': goal, 'repo': repo, 'tier': tier, 'status': 'open',
            'framework': framework, 'scores': scores, 'score': score(framework, scores), 'why': why,
            'added': ws.today()}
    save(root, items(root) + [item])
    ws.record(root, 'item.added', {k: item[k] for k in ('id', 'goal', 'repo', 'tier', 'score')})
    return item


def mark(root, item_id, status, reason=''):
    rows = items(root)
    item = next((row for row in rows if row['id'].lower() == item_id.lower()), None)
    if item is None:
        raise ValueError(f'{item_id} is not in the plan')
    item['status'], item['reason'] = status, reason
    save(root, rows)
    ws.record(root, f'item.{status}', {'id': item['id'], 'reason': reason})
    return item


def followup(root, title, repo, goal, why):
    """A small item the process owes itself, such as closing an accepted exception."""
    taken = {item['id'] for item in items(root)}
    item_id = next(f'X-{n}' for n in range(1, len(taken) + 2) if f'X-{n}' not in taken)
    scores = ({'value': 3, 'time': 3, 'risk': 5, 'size': 1} if ws.config(root)['prioritisation'] == 'wsjf'
              else {'reach': 1, 'impact': 1, 'confidence': 1, 'effort': 0.5})
    return add(root, item_id, title, goal, repo, 'light', scores, why)
