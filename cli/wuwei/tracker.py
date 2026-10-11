"""Tracker hygiene (5.11): the lifecycle duties, the one ticket creator and the one comment writer.

Hook paths import this lazily; keep top-level imports to what they already load.
"""

import json
import re
import sys

from wuwei import state, workspace


CLASSES = workspace.TRACKER_CLASSES
KINDS = workspace.TRACKER_KINDS
# ponytail: a one-segment /name (a slash command) is not a path; a path-shaped CODEOWNERS key
# such as /src/api/ is dropped, which is conservative.
ABSOLUTE = re.compile(r'''(?:^|[\s"'`=(,])(?:~/|[A-Za-z]:[\\/]|/[^\s/]+/)''')


def ticket(data, item):
    """The item's recorded ticket id, or None."""
    return data.get('tickets', {}).get(item, {}).get('id')


def full_id(config, ticket):
    """#741: a bare GitHub issue number becomes <tracker repository>#<n> (design 5.11:
    tracker.project, else the first configured repository); every other id is kept."""
    if config['adapters']['tracker'] != 'github' or not re.fullmatch(r'[1-9][0-9]*', str(ticket)):
        return ticket
    repo = config['tracker']['project'] or next((row['name'] for row in config['repos']), '')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise ValueError(f'ticket {ticket} names no repository; pass owner/repo#{ticket}, or the '
                         'owner sets tracker.project to the GitHub owner/repo with bin/wuwei '
                         'config set tracker.project <owner/repo>')
    return f'{repo}#{ticket}'


def upgrade(root, config, write=True):
    """#741, once: the latest day's bare GitHub ticket ids become <repo>#<n>; the lines say what
    changed (or why an id stays). Earlier days are history and are not rewritten."""
    from wuwei import watch
    if config['adapters']['tracker'] != 'github':
        return []
    day = next((path for path in watch.days(root) if (path / 'state.json').exists()), None)
    if day is None:
        return []
    try:
        tickets = state.read_state(directory=day).get('tickets', {})
    except (OSError, ValueError) as exc:
        return [f'{day.name}/state.json: tickets unread: {exc}']
    lines = []
    for item, row in tickets.items():
        old = row.get('id')
        if not isinstance(old, str) or not re.fullmatch(r'[1-9][0-9]*', old):
            continue
        try:
            new = full_id(config, old)
        except ValueError as exc:
            lines.append(f'{day.name}/state.json: ticket {item} {old} unchanged: {exc}')
            continue
        if write:
            def update(data, item=item, old=old, new=new):
                if data['tickets'][item]['id'] == old:
                    data['tickets'][item]['id'] = new
            state._write_state(update, root, reserved=False, kind='plan.set', directory=day,
                               payload={'item': item, 'ticket': new, 'was': old})
        lines.append(f'{day.name}/state.json: ticket {item} {old} to {new}')
    return lines


def _duties(rows):
    """{(item, duty): (last duty kind, its payload)} over event rows, in first due order."""
    last = {}
    for row in rows:
        if row.get('kind') in ('duty.due', 'duty.done', 'duty.skipped'):
            payload = row['payload']
            key = (payload.get('item'), payload.get('duty'))
            if key in last or row['kind'] == 'duty.due':
                last[key] = (row['kind'], payload)
    return last


def open_duties(rows):
    """#842, pure: the (item, duty, command) of each duty.due with no later duty.done or
    duty.skipped for the same pair, in due order."""
    return [(item, duty, payload.get('command', ''))
            for (item, duty), (kind, payload) in _duties(rows).items() if kind == 'duty.due']


def duty_done(root, item, duty, ticket):
    """#842: True when any day's events hold duty.done for (item, duty) on this ticket, so a duty
    run again by merge.monitor, pr state or a carried day never posts twice, while a later item
    reusing the id with another ticket still gets its update."""
    for path in (root / '.wuwei/days').glob('*/events.jsonl'):
        for text in path.read_text(encoding='utf-8').splitlines():
            if '"duty.done"' in text:
                payload = json.loads(text).get('payload') or {}
                if (payload.get('item'), payload.get('duty'), payload.get('ticket')) == (item, duty, ticket):
                    return True
    return False


def duty_comment(root, config, port, number, key, kind, text):
    """#842: a duty's comment through tracker log's ledger: claimed before the send, so a retry
    after a crash never posts it twice, and within tracker.max_per_item_per_day."""
    from wuwei import registry
    logged = state.read_state(root).get('tracker_log', {})
    entry = logged.get(key)
    if entry and entry['outcome'] == 'written':
        return registry.Result(0)
    if entry and entry['outcome'] == 'sending':
        return registry.Result(1, reason=f'{key}: an earlier send was interrupted, so it is not posted '
                                         f'again; check ticket {number} and add the line there if it is missing')
    if entry:
        return registry.Result(1, reason=f'{key}: {entry.get("reason", "refused")}')
    used = sum(row.get('ticket') == number and 'kind' in row
               and row['outcome'] in ('sending', 'written', 'drafted') for row in logged.values())
    if used >= config['tracker']['max_per_item_per_day']:
        return registry.Result(1, reason=f'{key}: ticket {number} already has its '
                                         'tracker.max_per_item_per_day comments today; retry the duty tomorrow with the '
                                         'command the day report names')

    def claim(fresh):
        rows = fresh.setdefault('tracker_log', {})
        if key in rows:
            raise state.StateError(f'tracker: {key} already claimed; another run is writing it, '
                                   'so wait for it to finish')
        rows[key] = {'outcome': 'sending', 'ticket': number, 'kind': kind}
    state._write_state(claim, root, reserved=False, kind='tracker.logged', payload={'key': key})
    result = port.comment(number, text, kind, root=root)
    if result.exit == 2:
        _settle(root, key, lambda rows: rows.pop(key, None), exit=2)
        return result
    outcome = ({'outcome': 'written'} if result.exit == 0 else
               {'outcome': 'refused', 'reason': result.reason or 'refused'})
    _settle(root, key, lambda rows: rows[key].update(outcome), outcome=outcome['outcome'])
    return result


def skipped_duties(rows):
    """#842, pure: the duty.skipped payloads still standing, for the report."""
    return [payload for kind, payload in _duties(rows).values() if kind == 'duty.skipped']


def _key(category, subject, title):
    return f'create:{category}:{subject}:{" ".join(title.lower().split())}'


def _candidate(root, data, item):
    path = workspace.day_dir(root) / 'proposal.json'
    rows = (json.loads(path.read_text(encoding='utf-8')).get('candidates', [])
            if path.is_file() and not path.is_symlink() else [])
    found = data.get('seat_findings', {}).get(item)  # #646: a seat's finding added as an item
    return next((row for row in rows if row.get('id') == item),
                found and {**found, 'goal': data['items'].get(item, {}).get('goal', 'unplanned')})


def create(root, subject, category='items', title=None, evidence=(), row=None, seat=None):
    """The one ticket creator: tracker create <item> and --bug|--triage|--follow-up; row is
    an item record not in today's proposal (#636: an owner-named item from plan add); seat is
    the role a seat declares, recorded on the event (#644)."""
    from wuwei import registry
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    if config['adapters']['tracker'] == 'none':
        return registry.Result(2, reason='tracker adapter is none; the owner sets adapters.tracker '
                               '(linear, jira or github) with bin/wuwei config set')
    if category not in CLASSES:
        return registry.Result(2, reason=f'tracker create: unknown class {category}; '
                                         'use --bug, --triage or --follow-up')
    if category != 'items' and category not in config['tracker']['create']:
        allowed = json.dumps([*config['tracker']['create'], category])
        return registry.Result(1, reason=(
            f'tracker.create: {category} is not in tracker.create; the owner adds it with '
            f"bin/wuwei config set tracker.create '{allowed}'"))
    data = state.read_state(root)
    parent = None
    by_hand = (f', then run bin/wuwei plan set {subject} ticket=<id>' if category == 'items'
               else ' in the tracker')
    if category == 'items':
        if ticket(data, subject):
            return registry.Result(0, {'id': ticket(data, subject)},
                                   f'{subject}: ticket {ticket(data, subject)}')
        row = row or _candidate(root, data, subject)
        if not isinstance(row, dict) or not isinstance(row.get('scope'), str):
            return registry.Result(2, reason=f'tracker create: unknown item {subject}; use an id '
                                             "from today's plan or proposal (bin/wuwei status lists them)")
        title = ' '.join(row['scope'].split())
        lines = [f'Evidence: {row.get("evidence", "")}', f'Goal: {row.get("goal", "unplanned")}',
                 f'Track: {row.get("track", "")}']
    else:
        if not isinstance(title, str) or not title.strip():
            return registry.Result(2, reason=(
                'tracker create: a title is required; pass it after the subject, for example '
                f'bin/wuwei tracker create --{category.rstrip("s")} {subject} "<title>"'))
        title = ' '.join(title.split())
        lines = [f'Evidence: {line}' for line in evidence]
        parent = ticket(data, subject)
    if any(ABSOLUTE.search(text) for text in (title, *lines)):
        return registry.Result(1, reason='tracker create: refused: absolute path in title or evidence; '
                                         'write paths relative to the repository, such as cli/x.py:12')
    draft = {'title': title, 'description': '\n'.join(lines), 'item': subject,
             'category': category, **({'parent': parent} if parent else {})}
    key = _key(category, subject, title)
    entry = data.get('tracker_log', {}).get(key)
    if entry and entry['outcome'] == 'written':
        return registry.Result(0, {'id': entry['ticket']}, f'{subject}: ticket {entry["ticket"]}')
    if entry and entry['outcome'] == 'refused':
        return registry.Result(1, reason=f'tracker create: refused: {entry["reason"]}; create the ticket by hand{by_hand}')
    result = registry.load('tracker', config).create(draft, root=root)
    if result.exit == 0:
        record(draft, result.data, root=root, seat=seat)
        return registry.Result(0, result.data, f'{subject}: ticket {result.data["id"]} {result.data["url"]}')
    if result.exit == 1:
        outcome = {'outcome': 'refused', 'reason': result.reason or 'refused'}
        state._write_state(lambda fresh: fresh.setdefault('tracker_log', {}).update({key: outcome}),
                           root, reserved=False, kind='tracker.logged',
                           payload={'key': key, 'outcome': outcome['outcome']})
        return registry.Result(1, reason=f'tracker create: refused: {outcome["reason"]}; create the ticket by hand{by_hand}')
    return result


def _entries(day, data, kinds):
    """Today's comment entries (key, item, kind, text) for items with a ticket, in event order."""
    from datetime import date, timedelta
    from wuwei import verdict, watch
    items = [name for name in data['items'] if ticket(data, name)]
    after = (date.fromisoformat(day.name) + timedelta(days=1)).isoformat()
    entries = []
    for n, row in enumerate(watch.records(day / 'events.jsonl'), 1):
        kind, payload, found = row['kind'], row['payload'], []
        for item, phase in payload.get('phase_changes', {}).items():
            if phase != 'merged':  # #842: the done duty writes the merged note
                found.append((item, 'progress', f'Phase: {phase}.'))
        if kind == 'plan.disposed':
            reason = payload.get('reason')
            found.append((payload.get('item'), 'close', f'Carried to {after}.' if payload.get('outcome') == 'carried'
                          else f'Parked: {reason}.' if reason else 'Parked.'))
        elif kind in ('seat launched', 'seat stopped'):
            seat = data['seats'].get(payload.get('name'), {})
            role = str(seat.get('role', ''))
            verb = 'started' if kind == 'seat launched' else 'stopped'
            if role == 'builder':
                found.append((seat.get('item'), 'progress', f'Build {verb}.'))
            elif role.startswith('sentinel-'):
                found.append((seat.get('item'), 'progress', f'Review {role[9:]} {verb}.'))
        elif kind == 'build.checked' and 'passed' in payload:
            found.append((payload.get('item'), 'progress',
                          f'Fast checks: {payload["passed"]} passed, {payload["failed"]} failed.'))
        elif kind == 'gate.received':
            item, role, round_name = payload.get('item'), payload.get('role'), payload.get('round')
            record = data['gate_verdicts'].get(f'{item}:{role}:{round_name}', {})
            blocking = sum(bool(re.search(verdict.BLOCKS_YES, finding, re.I))
                           for finding in record.get('findings', []))
            found.append((item, 'verdicts', f'Review {role} ({round_name}): '
                          f'{payload.get("verdict")}, {blocking} blocking findings.'))
        seen = {}
        for item, entry_kind, text in found:
            if item in items and entry_kind in kinds:
                key = f'{entry_kind}:{item}:{n}'
                seen[key] = seen.get(key, 0) + 1
                entries.append((key + (f':{seen[key]}' if seen[key] > 1 else ''), item,
                                entry_kind, f'[{day.name} {item}] {text}'))
    return entries


def _settle(root, key, update, **payload):
    state._write_state(lambda fresh: update(fresh.setdefault('tracker_log', {})), root,
                       reserved=False, kind='tracker.logged', payload={'key': key, **payload})


def log(root):
    """The only comment writer: today's story per ticket, once per key, with the daily cap.
    Each comment is claimed before the port call, so a crash is never posted twice."""
    from wuwei import registry
    config = workspace.load_config(root)
    if config['adapters']['tracker'] == 'none':
        return 0
    settings = config['tracker']
    day = workspace.day_dir(root)
    data = state.read_state(root)
    logged = data.get('tracker_log', {})
    by_ticket = {}
    for entry in _entries(day, data, settings['log']):
        if entry[0] not in logged:
            by_ticket.setdefault(ticket(data, entry[1]), []).append(entry)
    port, code = None, 0
    for number, entries in by_ticket.items():
        used = sum(row.get('ticket') == number and 'kind' in row
                   and row['outcome'] in ('sending', 'written', 'drafted') for row in logged.values())
        allowed = settings['max_per_item_per_day'] - used
        cut = len(entries) if len(entries) <= allowed else max(allowed - 1, 0)
        sends = [(key, kind, text, kind, ()) for key, _, kind, text in entries[:cut]]
        folded = entries[cut:]
        if folded and allowed <= 0:
            _settle(root, f'fold:{number}', lambda rows: rows.update(
                {key: {'outcome': 'folded', 'ticket': number} for key, *_ in folded}))
        elif folded:
            counts = {kind: sum(entry[2] == kind for entry in folded) for kind in KINDS
                      if any(entry[2] == kind for entry in folded)}
            summary = ', '.join(f'{kind} {count}' for kind, count in counts.items())
            sends.append((f'fold:{number}:{folded[0][0]}', 'fold',
                          f'[{day.name} {folded[0][1]}] Folded {len(folded)} updates: {summary}.',
                          next(iter(counts)),
                          [key for key, *_ in folded]))
        for key, kind, text, category, keys in sends:
            if ABSOLUTE.search(text):
                code = 1
                print(f'tracker log: {key}: refused: absolute path in the comment; remove the path '
                      'from the record it quotes (this comment is not retried)', file=sys.stderr)
                _settle(root, key, lambda rows: rows.update({key: {
                    'outcome': 'refused', 'ticket': number, 'kind': kind, 'reason': 'absolute path'}}),
                    outcome='refused')
                continue

            def claim(fresh):
                rows = fresh.setdefault('tracker_log', {})
                if key in rows:
                    raise state.StateError(f'tracker log: {key} already claimed; another tracker log '
                                           'run is writing it, so wait for it to finish')
                rows[key] = {'outcome': 'sending', 'ticket': number, 'kind': kind}
                rows.update({name: {'outcome': 'folded', 'ticket': number} for name in keys})
            if keys:
                state._write_state(claim, root, reserved=False, kind='tracker.folded', payload={
                    'item': folded[0][1], 'ticket': number, 'counts': counts})
            else:
                state._write_state(claim, root, reserved=False, kind='tracker.logged',
                                   payload={'key': key})
            port = port or registry.load('tracker', config)
            result = port.comment(number, text, category, root=root)
            if result.exit == 2:
                _settle(root, key, lambda rows: [rows.pop(name, None) for name in (key, *keys)],
                        exit=2)
                print(f'tracker log: {result.reason}', file=sys.stderr)
                return 2
            outcome = ({'outcome': 'written'} if result.exit == 0 else
                       {'outcome': 'refused', 'reason': result.reason or 'refused'})
            if outcome['outcome'] == 'refused':
                code = 1
                print(f'tracker log {key}: {outcome["reason"]}', file=sys.stderr)
            _settle(root, key, lambda rows: rows[key].update(outcome), outcome=outcome['outcome'])
    return code


def creates_labels(config):
    """#670 (I49): WUWEI creates a lifecycle label on its own only on the owner's tracker;
    init --upgrade creates one on an external tracker only from a tty."""
    from wuwei import outward
    return not outward._external_tracker(config)


def labels(root, config, create, port=None):
    """The port's lifecycle labels, {'created': [...], 'missing': [...]}, checked."""
    from wuwei import registry
    from wuwei.exits import ADAPTER_DATA
    if config['adapters']['tracker'] == 'none':
        return registry.Result(0, {'created': [], 'missing': []})
    try:
        result = (port or registry.load('tracker', config)).labels(create, root=root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return registry.Result(2, reason=f'tracker labels unmeasured: {exc}')
    if (not isinstance(result, registry.Result) or result.exit not in (0, 1, 2)
            or result.exit == 0 and not (isinstance(result.data, dict) and all(
                isinstance(result.data.get(key), list) for key in ('created', 'missing')))):
        return registry.Result(2, reason=f'tracker labels: {ADAPTER_DATA}')
    return result


def relabel(port, root, config, item, ticket, failed):
    """A failed in-review move: create a missing label when WUWEI may and move once more,
    or name the label and the owner's commands; any other failure comes back unchanged."""
    from wuwei import registry
    name = config['tracker']['states']['in_review']
    found = labels(root, config, creates_labels(config), port)
    if found.exit:
        return failed
    if found.data['created']:
        return port.transition(ticket, name, root=root)
    if found.data['missing']:
        quoted = ', '.join(f'"{label}"' for label in found.data['missing'])
        if not creates_labels(config):  # #842: someone else's tracker; its owner adds the label
            return registry.Result(1, reason=(
                f'{item} not moved to {name}: the tracker label {quoted} is missing on a tracker '
                'WUWEI does not own. The duty stays skipped in the day report until its owner adds '
                f'it; ask them to, then run bin/wuwei tracker move {item} in_review'))
        return registry.Result(1, reason=(
            f'{item} not moved to {name}: the tracker label {quoted} is missing; run '
            'bin/wuwei init --upgrade, which creates it, then bin/wuwei '
            f'tracker move {item} in_review'))
    return failed


def ensure_labels(root, prefix, create):
    """The lines init --upgrade prints after creating the missing labels."""
    result = labels(root, workspace.load_config(root), create)
    if result.exit:
        return [f'tracker labels not created: {result.reason}; run bin/wuwei doctor']
    return [f'{prefix} tracker label "{name}"' for name in result.data['created']]


def record(draft, created, *, root=None, directory=None, seat=None):
    """The only writer of a confirmed creation: tickets (items), tracker_log and the event."""
    if (not isinstance(created, dict) or not isinstance(created.get('id'), str)
            or not created['id'] or not isinstance(created.get('url'), str)):
        raise ValueError('tracker: adapter returned no ticket id and url; run bin/wuwei doctor '
                         'and read its tracker row')
    category, subject, parent = draft['category'], draft['item'], draft.get('parent')

    def update(data):
        if category == 'items':
            data.setdefault('tickets', {})[subject] = {'id': created['id'], 'source': 'create'}
        data.setdefault('tracker_log', {})[_key(category, subject, draft['title'])] = {
            'outcome': 'written', 'ticket': created['id']}
    state._write_state(update, root, reserved=False, kind='tracker.created', directory=directory,
                       payload={'class': category, 'subject': subject,
                                'ticket': created['id'], 'parent': parent, **({'seat': seat} if seat else {})})
