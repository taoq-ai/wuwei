"""#558 error budget per decision class (design 5.8.1): the window reader (shared with #559),
the spend rule, and the steward step that lowers, restores and warns."""

from datetime import timedelta
import math
from pathlib import Path

from wuwei import state, watch, workspace


def select(root, days, now=None, every=False):
    """(answers, events) of the last `days` days, oldest first. answers are the cruise answers
    {day, id, class, at, items, option, confidence, role, undo_until}, and with every (#559) also
    the records a seat or the mandate took; events are what spends a class's budget {class, at,
    kind, label, day, id}, day and id naming the answer: an undo, an owner reversal, a weekly
    sample answered differently and an escaped defect (dated at its answer). A damaged event
    stream raises ValueError."""
    now = now or workspace.now()
    start = (now - timedelta(days=days)).isoformat()
    rows = [(day.name, row) for day in reversed(watch.days(Path(root)))
            if day.name >= start[:10] for row in watch.records(day / 'events.jsonl')]
    answers, events, cards = {}, [], {}
    for day, row in rows:
        kind, payload = row['kind'], row['payload']
        if kind == 'decision.decided' and (str(payload.get('rule', '')).startswith('cruise ')
                                           or every and payload.get('decided_by') in ('seat', 'mandate')):
            answers[day, payload['id']] = {'day': day, 'id': payload['id'], 'class': payload.get('class'),
                                           'at': row['ts'], 'items': payload.get('items', []),
                                           'option': payload['option'], 'confidence': payload.get('confidence'),
                                           'role': payload.get('role'), 'undo_until': payload.get('undo_until')}
        elif kind == 'decision.reversed' and (day, payload.get('id')) in answers:
            kind = 'undo' if payload.get('undo') else 'reversal'
            answer = answers[day, payload['id']]
            events.append({'class': answer['class'], 'at': row['ts'], 'kind': kind,
                           'label': f'{kind} {day} {answer["id"]}', 'day': day, 'id': answer['id']})
        elif kind == 'cruise.carded' and payload.get('kind') == 'sample':
            cards[day, payload['id']] = payload
        elif (kind == 'decision.decided' and payload.get('decided_by') == 'owner'
              and (day, payload.get('id')) in cards and payload['option'] != cards[day, payload['id']]['option']):
            card = cards.pop((day, payload['id']))
            source = Path(card['source'])  # .wuwei/days/<day>/decisions/<id>.md
            events.append({'class': card['class'], 'at': row['ts'], 'kind': 'sample',
                           'label': f'sample {day} {payload["id"]} of {source.parts[-3]} {source.stem}',
                           'day': source.parts[-3], 'id': source.stem})
    if any(answer['items'] for answer in answers.values()):
        from wuwei import metrics
        found = metrics._escaped(root)[1]
        # ponytail: an escaped defect has no detection time, so it is dated at its answer.
        events += [{'class': answer['class'], 'at': answer['at'], 'kind': 'escaped',
                    'label': f'escaped {item} {answer["day"]} {answer["id"]}',
                    'day': answer['day'], 'id': answer['id']}
                   for answer in answers.values() for item in answer['items'] if item in found]
    keep = [answer for answer in answers.values() if answer['at'] >= start]
    return keep, sorted((event for event in events if event['at'] >= start), key=lambda event: event['at'])


def measure(answered, spent, recent, cruise):
    """(allowance, burn, state) of one class: spent with more events than the allowance and at
    least two; warn when the last 48 hours burn at burn_warn times the window's pace."""
    allowance = cruise['budget_share'] * answered
    if allowance:
        burn = recent * cruise['budget_window_days'] / (2 * allowance)
    else:
        burn = math.inf if recent else 0.0
    if spent > allowance and spent >= 2:
        return allowance, burn, 'spent'
    return allowance, burn, 'warn' if burn >= cruise['burn_warn'] else 'ok'


def table(root, config, now=None):
    """One row per class but merge (the merge policy decides merges)."""
    from wuwei import cruise
    now = now or workspace.now()
    budget = config['decisions']['cruise']
    answers, events = select(root, budget['budget_window_days'], now)
    running, recent = cruise.running(root), (now - timedelta(hours=48)).isoformat()
    rows = []
    for name in cruise.CLASSES:
        if name == 'merge':
            continue
        mine = [event for event in events if event['class'] == name]
        allowance, burn, found = measure(sum(answer['class'] == name for answer in answers), len(mine),
                                         sum(event['at'] >= recent for event in mine), budget)
        rows.append({'class': name, 'level': cruise.level(config, name, running),
                     'answered': sum(answer['class'] == name for answer in answers), 'spent': len(mine),
                     'allowance': allowance, 'burn': burn, 'state': found,
                     'events': [event['label'] for event in mine], 'last': mine[-1] if mine else None,
                     'held': name in running.get('budget', {})})
    return rows


def evaluate(root):
    """The steward step: a spent class runs one level lower and holds the level it lost; a held
    class whose window refilled gets that level back; a fast burn writes one nudge a day."""
    from wuwei import cruise, promotion
    config = workspace.load_config(root)
    days = config['decisions']['cruise']['budget_window_days']
    rows = table(root, config)
    held = cruise.running(root).get('budget', {})
    burned = {row['payload'].get('class') for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
              if row['kind'] == 'cruise.burn'}
    for row in rows:
        name, tally = row['class'], f'{row["spent"]} events over {row["allowance"]:g} allowed'
        if row['state'] == 'spent' and name not in held and row['level'] > 0:
            event = row['last']
            promotion.cruise_level(
                root, name, row['level'] - 1,
                f'budget spent: {name}, {tally} in {days} days: ' + ', '.join(row['events']),
                f'.wuwei/days/{event["day"]}/decisions/{event["id"]}.md',
                hold=cruise.running(root)['levels'].get(name, cruise.CLASSES[name][0]))
        elif row['state'] != 'spent' and name in held:
            promotion.cruise_level(root, name, held[name], f'budget refilled: {name} back to L{held[name]}, {tally}',
                                   cruise.CRUISE)
        elif row['state'] == 'warn' and name not in burned:
            # The payload carries no float: the event writer refuses an infinite burn.
            state.append_event('cruise.burn', {'class': name, 'events': row['events'], 'reason': (
                f'{name} burns its error budget at {row["burn"]:.1f}x: ' + ', '.join(row['events']))}, root)
    return rows
