"""Tracker hygiene (5.11): the ticket rule, the one ticket creator and the one comment writer.

Hook paths import this lazily; keep top-level imports to what they already load.
"""

import json
import re
import sys

from wuwei import state, workspace


CLASSES = workspace.TRACKER_CLASSES
KINDS = workspace.TRACKER_KINDS


def ticket(data, item):
    """The item's recorded ticket id, or None."""
    return data.get('tickets', {}).get(item, {}).get('id')


def in_force(config):
    return config['adapters']['tracker'] != 'none' and config['tracker']['required']


def pending(data, item):
    """A pending tracker draft that would open the item's ticket, or None."""
    return next((key for key, row in data.get('drafts', {}).items()
                 if row.get('status') == 'pending' and row.get('channel') == 'tracker'
                 and row.get('operation') == 'create'
                 and row.get('inputs', {}).get('draft', {}).get('category') == 'items'
                 and row['inputs']['draft'].get('item') == item), None)


def check(data, config, item, row=None):
    """The 5.11 rule, pure: (off|ticket|skipped|missing, reason)."""
    if not in_force(config):
        return 'off', ''
    if ticket(data, item):
        return 'ticket', ''
    row = row or {}
    if ((row.get('gates', {}).get('tier') or row.get('tier')) in config['tracker']['skip_tiers']
            or data.get('tickets', {}).get(item, {}).get('source') == 'none'):  # #636: the owner's none
        return 'skipped', ''
    strict = workspace.posture(config)[0] == 'strict'
    draft = pending(data, item)
    if draft:
        return 'missing', (f'{item} has no ticket: the owner runs bin/wuwei drafts approve {draft} '
                           'in a host terminal' if strict else
                           f'{item} has no ticket: draft {draft} opens it once the owner answers '
                           f'Send on its card (bin/wuwei drafts show {draft} --widget)')
    return 'missing', (f"{item} has no ticket: the owner runs bin/wuwei tracker create {item} (opens "
                       f"one from the item's record) or bin/wuwei plan set {item} ticket=<id> in a "
                       'host terminal' if strict else
                       f"{item} has no ticket: the planner proposes one on the item's card (an "
                       "existing ticket or a new one from its record) and records the owner's answer")


def _key(category, subject, title):
    return f'create:{category}:{subject}:{" ".join(title.lower().split())}'


def _candidate(root, data, item):
    path = workspace.day_dir(root) / 'proposal.json'
    rows = (json.loads(path.read_text(encoding='utf-8')).get('candidates', [])
            if path.is_file() and not path.is_symlink() else [])
    return next((row for row in rows if row.get('id') == item),
                data.get('discovery_candidates', {}).get(item))


def _held(root, config, subject, draft_id):
    """#644: a held ticket is the planner's card below strict, a host-terminal approve under strict."""
    from wuwei import drafts, outward
    rule = drafts.read(state.read_state(root))[draft_id]['tier_reason'].removeprefix(
        outward.APPROVAL_REQUIRED + ': ')
    if workspace.posture(config)[0] == 'strict':
        return (f'{subject}: ticket held ({rule}): the owner runs bin/wuwei drafts approve '
                f'{draft_id} in a host terminal')
    return (f'{subject}: ticket held ({rule}): the planner asks it on its card '
            f'(bin/wuwei drafts show {draft_id} --widget)')


def create(root, subject, category='items', title=None, evidence=(), row=None, seat=None):
    """The one ticket creator: tracker create <item> and --bug|--triage|--follow-up; row is
    an item record not in today's proposal (#636: an owner-named item from plan add); seat is
    the role a seat declares, recorded on the event (#644)."""
    from wuwei import profiles, registry
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    if config['adapters']['tracker'] == 'none':
        return registry.Result(2, reason='tracker adapter is none; the owner sets adapters.tracker '
                               '(linear, jira or github) with bin/wuwei config set in a host terminal')
    if category not in CLASSES:
        return registry.Result(2, reason=f'tracker create: unknown class {category}; '
                                         'use --bug, --triage or --follow-up')
    if category != 'items' and category not in config['tracker']['create']:
        allowed = json.dumps([*config['tracker']['create'], category])
        return registry.Result(1, reason=(
            f'tracker.create: {category} is not in tracker.create; the owner adds it with '
            f"bin/wuwei config set tracker.create '{allowed}' in a host terminal"))
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
    if any(profiles.ABSOLUTE.search(text) for text in (title, *lines)):
        return registry.Result(1, reason='tracker create: refused: absolute path in title or evidence; '
                                         'write paths relative to the repository, such as cli/x.py:12')
    draft = {'title': title, 'description': '\n'.join(lines), 'item': subject,
             'category': category, **({'parent': parent} if parent else {})}
    key = _key(category, subject, title)
    entry = data.get('tracker_log', {}).get(key)
    queued = next((row['id'] for row in data.get('drafts', {}).values()
                   if row.get('channel') == 'tracker' and row.get('status') in ('pending', 'sent')
                   and row.get('inputs', {}).get('draft') == draft), None)
    if entry and entry['outcome'] == 'written':
        return registry.Result(0, {'id': entry['ticket']}, f'{subject}: ticket {entry["ticket"]}')
    if entry and entry['outcome'] == 'refused':
        return registry.Result(1, reason=f'tracker create: refused: {entry["reason"]}; create the ticket by hand{by_hand}')
    if queued:
        return registry.Result(1, {'draft': queued}, _held(root, config, subject, queued))
    result = registry.load('tracker', config).create(draft, root=root)
    if result.exit == 0:
        record(draft, result.data, root=root, seat=seat)
        return registry.Result(0, result.data, f'{subject}: ticket {result.data["id"]} {result.data["url"]}')
    if result.exit == 1:
        stored = re.search(r'outward: draft (draft-[0-9a-f]+)', result.reason or '')
        outcome = ({'outcome': 'drafted', 'draft': stored[1]} if stored
                   else {'outcome': 'refused', 'reason': result.reason or 'refused'})
        state._write_state(lambda fresh: fresh.setdefault('tracker_log', {}).update({key: outcome}),
                           root, reserved=False, kind='tracker.logged',
                           payload={'key': key, 'outcome': outcome['outcome']})
        if stored:
            return registry.Result(1, {'draft': stored[1]}, _held(root, config, subject, stored[1]))
        return registry.Result(1, reason=f'tracker create: refused: {outcome["reason"]}; create the ticket by hand{by_hand}')
    return result


def _entries(day, data, kinds):
    """Today's comment entries (key, item, kind, text) for items with a ticket, in event order."""
    from datetime import date, timedelta
    from wuwei import decision, verdict, watch
    from wuwei.commands.why import question
    items = [name for name in data['items'] if ticket(data, name)]
    named = decision.naming(day, items)
    after = (date.fromisoformat(day.name) + timedelta(days=1)).isoformat()
    entries = []
    for n, row in enumerate(watch.records(day / 'events.jsonl'), 1):
        kind, payload, found = row['kind'], row['payload'], []
        for item, phase in payload.get('phase_changes', {}).items():
            if phase == 'merged':
                found.append((item, 'close', f'Merged in {data["items"][item].get("pr")}.'))
            else:
                found.append((item, 'progress', f'Phase: {phase}.'))
        if kind == 'decision.decided':
            verb, _, subject = str(payload.get('item_disposition', '')).partition(' ')
            if verb in ('carried', 'parked'):
                found.append((subject, 'close', f'Carried to {after} ({payload.get("id")}).'
                              if verb == 'carried' else f'Parked ({payload.get("id")}).'))
            else:
                text = question(day, payload.get('id'))
                text += '' if text.endswith(('.', '?', '!')) else '.'
                found.extend((item, 'decisions',
                              f'Decision {payload.get("id")}: {text} Outcome: {payload.get("option")}.')
                             for item in {payload.get('item'), *named.get(payload.get('id'), [])}
                             if item)
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
        elif kind in ('pr.raised', 'pr.claimed'):
            found.append((payload.get('item'), 'pr', f'Pull request: {payload.get("pr")}.'))
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
    from wuwei import profiles, registry
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
                          next((kind for kind in counts if kind not in settings['auto']),
                               next(iter(counts))),
                          [key for key, *_ in folded]))
        for key, kind, text, category, keys in sends:
            if profiles.ABSOLUTE.search(text):
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
            stored = re.search(r'outward: draft (draft-[0-9a-f]+)', result.reason or '')
            outcome = ({'outcome': 'written'} if result.exit == 0 else
                       {'outcome': 'drafted', 'draft': stored[1]} if stored else
                       {'outcome': 'refused', 'reason': result.reason or 'refused'})
            if outcome['outcome'] == 'refused':
                code = 1
                print(f'tracker log {key}: {outcome["reason"]}', file=sys.stderr)
            _settle(root, key, lambda rows: rows[key].update(outcome), outcome=outcome['outcome'])
    return code


def creates_labels(config):
    """#670 (I49): WUWEI creates a lifecycle label on its own only on the owner's tracker
    below strict; setup and init --upgrade from a host terminal create on any tracker."""
    from wuwei import outward
    return workspace.posture(config)[0] != 'strict' and not outward._external_tracker(config)


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
        return registry.Result(1, reason=(
            f'{item} not moved to {name}: the tracker label {quoted} is missing; the owner runs '
            'bin/wuwei init --upgrade in a host terminal, which creates it, then bin/wuwei '
            f'tracker move {item} in_review'))
    return failed


def ensure_labels(root, prefix, create):
    """The lines setup and init --upgrade print after creating the missing labels."""
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
