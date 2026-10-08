"""#283 cruise mode (design 5.8.1): when a taken record is a cruise answer, and how levels move."""

from datetime import timedelta
from pathlib import Path
import re

from wuwei import state, workspace
from wuwei.exits import DAMAGED, SYMLINK


# Design 5.8.1: class -> (default cruise level, ceiling). A new class is a design amendment.
CLASSES = {'approach': (2, 3), 'retry': (2, 3), 'park': (2, 3), 'accept-residual': (2, 3),
           'defer': (0, 3), 'scope-cut': (0, 3), 're-plan': (0, 3), 'dependency-bump': (0, 3),
           'design': (0, 3), 'boundary': (0, 3), 'refactor': (0, 3),
           'merge': (3, 3), 'message': (0, 1), 'other': (0, 1)}
CRUISE = '.wuwei/memory/cruise.json'  # running levels; written only by promotion.py (cruise_level, calibration)
SHADOW = ('running', 'passed', 'ended')  # #560
BLAST = re.compile(r'(?i)\s*(?:own branch|own pr|workspace)\b')


def running(root):
    """#283: the running levels {levels, changed} from memory/cruise.json, and #558 budget, the
    levels a spent error budget holds; damage fails closed."""
    import json
    path = Path(root) / CRUISE
    if any(part.is_symlink() for part in (path, path.parent, path.parent.parent)):
        raise ValueError(f'{CRUISE}: must not be a symlink; {SYMLINK}')
    if not path.exists():
        return {'levels': {}, 'changed': {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f'{CRUISE}: unreadable ({type(exc).__name__}); {DAMAGED}') from None
    if (not isinstance(data, dict) or not isinstance(data.get('levels'), dict)
            or not isinstance(data.get('changed'), dict)
            or not isinstance(data.get('budget', {}), dict)
            or any(name not in CLASSES or type(value) is not int or not 0 <= value <= 3
                   for name, value in [*data['levels'].items(), *data.get('budget', {}).items()])):
        raise ValueError(f'{CRUISE}: expected levels of known classes at 0 to 3; {DAMAGED}')
    stored = data.get('calibration', {})  # #559: the uncalibrated classes and roles
    if (not isinstance(stored, dict) or not isinstance(stored.get('classes', []), list)
            or not isinstance(stored.get('roles', []), list)
            or any(name not in CLASSES for name in stored.get('classes', []))
            or any(not isinstance(role, str) for role in stored.get('roles', []))):
        raise ValueError(f'{CRUISE}: expected calibration classes of known classes and roles as names; {DAMAGED}')
    shadow = data.get('shadow', {})  # #560
    if not isinstance(shadow, dict) or any(
            name not in CLASSES or not isinstance(row, dict) or type(row.get('level')) is not int
            or not 1 <= row['level'] <= 3 or not isinstance(row.get('started'), str)
            or any(type(row.get(key)) is not int or row[key] < 0 for key in ('scored', 'agreed'))
            or row.get('state') not in SHADOW for name, row in shadow.items()):
        raise ValueError(f'{CRUISE}: expected shadow rows of known classes at L1 to L3 with counts and a state; {DAMAGED}')
    return data


def level(config, name, running=None):
    """The cruise level a class runs at: 0 when cruise is off or supervised, else the running
    level (the 5.8.1 default when unset) capped by the configured level and the ceiling."""
    cruise = config['decisions']['cruise']
    if not cruise['enabled'] or config['autonomy']['mode'] == 'supervised':
        return 0
    default, ceiling = CLASSES[name]
    if name in (running or {}).get('calibration', {}).get('classes', []):
        ceiling = min(ceiling, 1)  # #559: an uncalibrated class runs at most L1
    return min((running or {}).get('levels', {}).get(name, default),
               cruise['levels'].get(name, ceiling), ceiling)


def rule(root, ident, fields, scores, config, data, run=None):
    """The cruise answer fields for a record the #530 mandate takes, or None: class at L2 or L3
    (merge stays with the merge policy), two-way, inside the workspace, margin, daily budget
    and no unplanned item."""
    from wuwei import decision
    name, cruise = fields.get('Class'), config['decisions']['cruise']
    if name is None or name == 'merge':
        return None
    level = decision.level(config, name, run or decision.running(root))
    if (level < 2 or fields['Reversibility'] != 'two-way' or not BLAST.match(fields['Blast radius'])
            or decision.margin(fields, scores) < cruise['margin']
            or sum('rule' in row for row in data.get('decision_outcomes', {}).values()) >= cruise['max_per_day']):
        return None
    items = data.get('items', {})
    named = decision.naming(workspace.day_dir(root), items).get(ident, [])
    if any(items[item].get('goal') == 'unplanned' for item in named):
        return None
    now = workspace.now()
    found = {'rule': f'cruise {name}@L{level}', 'class': name, 'level': level,
             'at': now.isoformat(), 'items': named}
    if level == 2:  # ponytail: the window runs from the answer; the listener has no delivery receipt.
        found['undo_until'] = (now + timedelta(minutes=cruise['undo_minutes'])).isoformat()
    return found


def shadow(root, ident, record, fields, scores, config, data):
    """#560: what a class running in shadow would have answered on a taken record, as a
    decision_shadows row; the live route is already written and never changes."""
    run = running(root)
    name = fields.get('Class')
    row = run.get('shadow', {}).get(name)
    if not row or row['state'] != 'running':
        return
    if rule(root, ident, fields, scores, config, data, {**run, 'levels': {**run['levels'], name: row['level']}}):
        seen = {'class': name, 'level': row['level'], 'option': record['option'], 'at': workspace.now().isoformat()}
        state._write_state(lambda current: current.setdefault('decision_shadows', {}).__setitem__(ident, seen),
                           root, reserved=False, kind='decision.shadow', payload={'id': ident, **seen})


def _scored(root, name, row, now):
    """(record path, final option, shadow option) of each shadow row of a running shadow whose
    live outcome is final: an owner answer, or a mandate answer whose undo window closed."""
    from datetime import datetime
    for day, data in reversed(_days(root, (now - datetime.fromisoformat(row['started'])).days + 1)):
        outcomes = data.get('decision_outcomes', {})
        for ident, seen in sorted(data.get('decision_shadows', {}).items(), key=lambda pair: int(pair[0][2:])):
            final = outcomes.get(ident)
            if (isinstance(seen, dict) and seen.get('class') == name and seen.get('level') == row['level']
                    and seen.get('at', '') >= row['started'] and isinstance(final, dict)
                    and (final.get('decided_by') == 'owner' or final.get('decided_by') == 'mandate' and not window(final, now))):
                yield f'.wuwei/days/{day.name}/decisions/{ident}.md', final.get('option'), seen.get('option')


def review_shadows(root):
    """#560, steward: score each running shadow against the final live outcomes. One
    disagreement ends it; shadow_days and shadow_min all agreeing pass it."""
    from datetime import datetime
    from wuwei import promotion
    run, now = running(root), workspace.now()
    cruise = workspace.load_config(root)['decisions']['cruise']
    for name, row in sorted(run.get('shadow', {}).items()):
        if row['state'] != 'running':
            continue
        pairs = list(_scored(root, name, row, now))
        scored, agreed = len(pairs), sum(final == seen for _, final, seen in pairs)
        counts = {**row, 'scored': scored, 'agreed': agreed}
        where = f'{name} at L{row["level"]}'
        wrong = next((pair for pair in pairs if pair[1] != pair[2]), None)
        if wrong:
            promotion.cruise_shadow(root, name, {**counts, 'state': 'ended', 'ended': now.isoformat(), 'record': wrong[0]},
                                    f'shadow ended: {where}: {wrong[0]} answered {wrong[1]}, shadow {wrong[2]}; '
                                    f'agreed {agreed} of {scored}', wrong[0])
        elif (now - datetime.fromisoformat(row['started']) >= timedelta(days=cruise['shadow_days'])
              and scored >= cruise['shadow_min']):
            promotion.cruise_shadow(root, name, {**counts, 'state': 'passed'}, f'shadow passed: {where}; agreed {agreed} of {scored}')
        elif counts != row:
            promotion.cruise_shadow(root, name, counts, f'shadow scored: {where}; agreed {agreed} of {scored}')


def shadow_lines(root):
    """#560: the report lines of the stored shadows, 'none' when there is none."""
    return [f'- {name} at L{row["level"]} since {row["started"][:10]}: agreed {row["agreed"]} of {row["scored"]}, {row["state"]}'
            for name, row in sorted(running(root).get('shadow', {}).items())] or ['none']


def thin(root, fields, scores, config):
    """An owner route of a class running at L2 or L3 whose margin is below the cruise margin."""
    from wuwei import decision
    name = fields.get('Class')
    return (name in decision.CLASSES and decision.level(config, name, decision.running(root)) >= 2
            and decision.margin(fields, scores) < config['decisions']['cruise']['margin'])


def label(config, running):
    """The status line part: the highest level a class but merge runs at with cruise on, and
    the classes a spent error budget holds lower (#558)."""
    cruise = config['decisions']['cruise']
    on = {**config, 'decisions': {**config['decisions'], 'cruise': {**cruise, 'enabled': True}}}
    top = max(level(on, name, running) for name in CLASSES if name != 'merge')
    held = f' · budget {", ".join(sorted(running["budget"]))} spent' if running.get('budget') else ''
    roles = running.get('calibration', {}).get('roles')
    held += f' · uncalibrated {", ".join(roles)}' if roles else ''  # #559
    shadows = sorted(name for name, row in running.get('shadow', {}).items() if row['state'] != 'ended')
    held += f' · shadow {", ".join(shadows)}' if shadows else ''  # #560
    return (f'cruise L{top}' if cruise['enabled'] else f'cruise off | L{top}') + held


def clock(stamp):
    """HH:MM of a stored timestamp, in the offset it was written with."""
    from datetime import datetime
    return datetime.fromisoformat(stamp).strftime('%H:%M')


def window(row, now=None):
    """The open undo deadline of a cruise answer row, else None."""
    from datetime import datetime
    until = row.get('undo_until') if isinstance(row, dict) and row.get('decided_by') == 'mandate' else None
    return until if until and datetime.fromisoformat(until) > (now or workspace.now()) else None


def answered(root, ident, option):
    """The owner answered ident: a raise card lands its level. #558: a weekly sample answered
    differently and a reversed cruise answer spend the class's error budget (budget_classes)."""
    from wuwei import decision, promotion
    card = state.read_state(root).get('cruise_cards', {}).get(ident)
    shadow = card.get('shadow') if isinstance(card, dict) else None
    if (isinstance(card, dict) and card['kind'] == 'raise' and option == 'raise'
            and isinstance(shadow, dict) and shadow.get('state') == 'passed'):  # #560: only after a passed shadow
        name, config = card['class'], workspace.load_config(root)
        ceiling = decision.CLASSES[name][1]
        if card['level'] <= min(ceiling, config['decisions']['cruise']['levels'].get(name, ceiling)):
            promotion.cruise_level(root, name, card['level'], f'raise approved {ident}; shadow agreed '
                                   f'{shadow["agreed"]} of {shadow["scored"]}', evidence(root, ident))


def _days(root, count):
    """(day directory, day state) for the last count days with state, newest first."""
    from wuwei import watch
    cutoff = (workspace.now().date() - timedelta(days=count)).isoformat()
    return [(day, state.read_state(directory=day)) for day in watch.days(Path(root))
            if day.name > cutoff and (day / 'state.json').exists()]


def agreements(root, name, config, running):
    """Answers of a class after its last change within promote_days that agree: an owner answer
    equal to the recommendation, or a cruise answer whose undo window closed."""
    ended = running.get('shadow', {}).get(name, {}).get('ended', '')  # #560: fresh agreements after a shadow
    since, now = max(running['changed'].get(name, ''), ended), workspace.now()
    return sum(1 for _, data in _days(root, config['decisions']['cruise']['promote_days'])
               for row in data.get('decision_outcomes', {}).values()
               if isinstance(row, dict) and row.get('class') == name and row.get('at', '') > since
               and (row['decided_by'] == 'owner' and row['option'] == row.get('recommendation')
                    or row.get('rule') and not window(row, now)))


def _card(root, text, row):
    from wuwei import decision
    ident = decision.write(text, root).stem
    fields, _ = decision.evaluate(text)
    decision.route_owner(ident, fields, root)
    row = {**row, 'at': workspace.now().isoformat()}
    state._write_state(lambda data: data.setdefault('cruise_cards', {}).__setitem__(ident, row),
                       root, reserved=False, kind='cruise.carded', payload={'id': ident, **row})
    return ident


def propose(root, config):
    """Design 5.8.1 promotion as owner cards: a raise after promote_agreements agreements with the
    error budget unspent and no budget event since the class's last change (#558) and the class
    calibrated (#559), and once a week one sample per class with a recent cruise answer. Returns
    the new D-n."""
    from wuwei import budget_classes, calibration_scores, decision, promotion
    from wuwei import grants
    cruise = config['decisions']['cruise']
    if config['autonomy']['mode'] != 'autonomous' or not cruise['enabled']:
        return []
    run = decision.running(root)
    week, window_days = 7, cruise['promote_days']
    blocked = {row['class'] for row in budget_classes.table(root, config) if row['state'] == 'spent'}
    blocked |= {event['class'] for event in budget_classes.select(root, window_days)[1]
              if event['at'] > run['changed'].get(event['class'], '')}
    blocked |= {row['name'] for row in calibration_scores.table(root, config)  # #559
                if row['kind'] == 'class' and row['state'] != 'calibrated'}
    carded = [(day.name, row) for day, data in _days(root, max(week, window_days))
              for row in data.get('cruise_cards', {}).values()]
    cutoff = {count: (workspace.now().date() - timedelta(days=count)).isoformat() for count in (week, window_days)}
    written = []
    for name, (_, ceiling) in decision.CLASSES.items():
        level, cap = decision.level(config, name, run), min(ceiling, cruise['levels'].get(name, ceiling))
        if (name == 'merge' or level >= cap or name in blocked
                or any(row['kind'] == 'raise' and row['class'] == name and day > cutoff[window_days]
                       for day, row in carded)):
            continue
        row = run.get('shadow', {}).get(name, {})
        if row.get('state') == 'running':
            continue
        count = agreements(root, name, config, run)
        if row.get('state') != 'passed':  # #560: a raise is shadowed before it is asked
            if count < cruise['promote_agreements']:
                continue
            # A raise to L1 changes no route (cruise answers from L2), so its shadow passes at once.
            row = {'level': level + 1, 'started': workspace.now().isoformat(), 'scored': 0, 'agreed': 0,
                   'state': 'running' if level + 1 >= 2 else 'passed'}
            promotion.cruise_shadow(root, name, row, f'shadow started: {name} at L{level + 1}')
            if row['state'] == 'running':
                continue
        ident = _card(root, grants._record(
            f'Raise {name} to L{level + 1}? {count} answers agreed with the recommendation; '
            f'its shadow agreed {row["agreed"]} of {row["scored"]}.',
            f'Ledger: .wuwei/memory/ledger.jsonl. {name} runs at L{level}, ceiling L{cap}.',
            [('raise', f'Raise {name} to L{level + 1}', 'The recent answers agreed with the recommendation.',
              f'{name} records are answered at L{level + 1}.', 9),
             ('keep', f'Keep {name} at L{level}', 'Nothing changes.', f'{name} records keep their route.', 3)],
            'Owner time saved', 'raise', 'The ledger shows agreement, its error budget is unspent and its confidence is calibrated.',
            f'cruise level of {name}.', 'A later answer of this class is wrong and lands without you.',
            'Reversals and escaped defects spend its error budget; a spent budget lowers it one level.'),
            {'kind': 'raise', 'class': name, 'level': level + 1, 'shadow': row})
        promotion.cruise_shadow(root, name, {**row, 'state': 'ended', 'ended': workspace.now().isoformat()},
                                f'shadow asked {ident}')
        written.append(ident)
    if any(row['kind'] == 'sample' and day > cutoff[week] for day, row in carded):
        return written
    latest = {}
    for day, data in _days(root, week):
        for ident, row in sorted(data.get('decision_outcomes', {}).items(), key=lambda pair: -int(pair[0][2:])):
            if isinstance(row, dict) and row.get('rule'):
                latest.setdefault(row['class'], (day, ident, row))
    for name, (day, ident, row) in sorted(latest.items()):
        source = promotion.safe_path(Path(root), f'.wuwei/days/{day.name}/decisions/{ident}.md', label='sample source')
        text = decision.decided_record(source.read_text(encoding='utf-8'), 'pending', 'owner')
        written.append(_card(root, text, {'kind': 'sample', 'class': name, 'option': row['option'],
                                          'source': f'.wuwei/days/{day.name}/decisions/{ident}.md'}))
    return written


def gate_widgets(root, config):
    """The unanswered cruise cards of today as widgets; a weekly sample hides the recommendation."""
    from wuwei import decision
    data = state.read_state(root)
    level = workspace.verbosity(config, 'decisions')
    widgets = []
    for ident, row in sorted(data.get('cruise_cards', {}).items(), key=lambda pair: int(pair[0][2:])):
        if decision.answered(data, ident) is None:
            fields, _ = decision.evaluate(decision.today_path(ident, root).read_text(encoding='utf-8'))
            widgets.append(decision.record_widget(ident, fields, level=level, hidden=row['kind'] == 'sample'))
    return widgets


def evidence(root, ident):
    return f'.wuwei/days/{workspace.day_dir(root).name}/decisions/{ident}.md'
