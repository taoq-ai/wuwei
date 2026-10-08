"""#559 confidence calibration (design 5.8.1): the Brier score of each class and role over the
taken records of the #558 window, the steward step that stores the uncalibrated sets, and the
report and retro lines."""

from datetime import datetime

from wuwei import workspace

FORECAST = {'high': 0.9, 'medium': 0.6, 'low': 0.3}


def measure(pairs, cruise):
    """(brier, state) of [(forecast, outcome)]: too few under calibration_min, uncalibrated above
    calibration_threshold, else calibrated; brier is None when nothing is scored."""
    if not pairs:
        return None, 'too few'
    brier = sum((forecast - outcome) ** 2 for forecast, outcome in pairs) / len(pairs)
    if len(pairs) < cruise['calibration_min']:
        return brier, 'too few'
    return brier, 'uncalibrated' if brier > cruise['calibration_threshold'] else 'calibrated'


def scored(root, config, now=None):
    """[{class, role, forecast, outcome, labels}] of the taken records with a stored confidence and
    a closed undo window; outcome is 0 when an undo, reversal, sample or escaped defect names it."""
    from wuwei import budget_classes
    now = now or workspace.now()
    answers, events = budget_classes.select(root, config['decisions']['cruise']['budget_window_days'], now, every=True)
    broke = {}
    for event in events:
        broke.setdefault((event['day'], event['id']), []).append(event['label'])
    return [{'class': answer['class'], 'role': answer['role'], 'forecast': FORECAST[answer['confidence']],
             'outcome': 0 if (answer['day'], answer['id']) in broke else 1,
             'labels': broke.get((answer['day'], answer['id']), [])}
            for answer in answers if answer['confidence'] in FORECAST
            and not (answer['undo_until'] and datetime.fromisoformat(answer['undo_until']) > now)]


def table(root, config, now=None):
    """Rows {kind, name, scored, brier, state, broke}: every class but merge, then every role with
    a scored record."""
    from wuwei import cruise
    found = scored(root, config, now)
    rows = []
    for kind, names in (('class', [name for name in cruise.CLASSES if name != 'merge']),
                        ('role', sorted({row['role'] for row in found if row['role']}))):
        for name in names:
            mine = [row for row in found if row[kind] == name]
            brier, state = measure([(row['forecast'], row['outcome']) for row in mine], config['decisions']['cruise'])
            rows.append({'kind': kind, 'name': name, 'scored': len(mine), 'brier': brier, 'state': state,
                         'broke': [label for row in mine for label in row['labels']]})
    return rows


def evaluate(root):
    """The steward step: store the uncalibrated classes and roles when they changed."""
    from wuwei import cruise, promotion
    rows = table(root, workspace.load_config(root))
    bad = [row for row in rows if row['state'] == 'uncalibrated']
    classes = [row['name'] for row in bad if row['kind'] == 'class']
    roles = [row['name'] for row in bad if row['kind'] == 'role']
    stored = cruise.running(root).get('calibration', {})
    if (stored.get('classes', []), stored.get('roles', [])) != (sorted(classes), sorted(roles)):
        promotion.calibration(root, classes, roles, 'calibration: ' + ('; '.join(
            f'{row["kind"]} {row["name"]} uncalibrated (Brier {row["brier"]:.2f}): ' + ', '.join(row['broke'])
            for row in bad) or 'every scored class and role calibrated'))
    return rows


def lines(root, config):
    """The report and retro section: one line per class or role with scored records."""
    found = []
    for row in table(root, config):
        if not row['scored']:
            continue
        line = f'- {row["kind"]} {row["name"]}: {row["state"]}, Brier {row["brier"]:.2f} over {row["scored"]}'
        if row['state'] == 'uncalibrated':
            line += ': ' + ', '.join(row['broke']) + '; run bin/wuwei cruise calibration'
        found.append(line)
    return found or ['none scored']
