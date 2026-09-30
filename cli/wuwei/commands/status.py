"""Read-only status snapshots for the owner surfaces."""

from datetime import datetime, timedelta
import json
import sys

from wuwei import state, workspace
from wuwei.exits import CLEAN, UNRUN
from wuwei.signal import SILENT, classify


def register(subparsers):
    parser = subparsers.add_parser('status', help='show day status')
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--line', action='store_true')
    output.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def attention(directory, classified_state=None):
    """Current page and nudge causes from the day's event stream."""
    return scan(directory, classified_state)[0]


def scan(directory, classified_state=None):
    """Attention rows and watch state (alive, off, dead, unmeasured) from one read of the day."""
    classified_state = classified_state or {**state.read_state(directory=directory),
                                              'now': workspace.now().isoformat()}
    today = workspace.now().date()
    current, clocks = {}, []
    path = directory / 'events.jsonl'
    if path.exists():
        with path.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    event = None
                if isinstance(event, dict):
                    kind = event.get('kind')
                    payload = event.get('payload', {})
                    stamp = event.get('ts')
                    if isinstance(stamp, str) and datetime.fromisoformat(stamp).date() != today:
                        continue
                    if kind == 'watch: clock':
                        clocks.append(stamp)
                    if kind in ('state.transition', 'item.escalated'):
                        continue
                    if kind == 'mcp.checked' and isinstance(payload, dict) and payload.get('exit') == 0:
                        current = {key: value for key, value in current.items() if key[0] != 'mcp.finding'}
                        continue
                    if kind == 'pr.action' and isinstance(payload, dict) and 'tier' not in payload:
                        current.pop(('pr.action', payload.get('pr')), None)
                        continue
                    if kind == 'decision.decided' and isinstance(payload, dict):
                        current.pop(('decision.one_way', payload.get('id')), None)
                        continue
                    if kind in ('draft.sending', 'draft.sent', 'draft.failed', 'draft.dropped') \
                            and isinstance(payload, dict):
                        current.pop(('draft.created', payload.get('id')), None)
                    if (kind == 'pr.action' and isinstance(payload, dict)
                            and payload.get('state') in ('merged', 'closed')):
                        current.pop(('merge.policy_blocked', payload.get('pr')), None)
                    if kind in SILENT:
                        continue
                else:
                    kind, payload = 'unreadable event', {}
                if kind == 'watch: sweep' and isinstance(payload, dict):
                    current = {key: value for key, value in current.items() if key[0] != 'watch: sweep'}
                    fields = (('reply_owed', 'reply', 'nudge'),
                              ('visibility_owed', 'visibility', 'nudge'),
                              ('stale_owed', 'stale', 'nudge'),
                              ('watch_dead', 'watch', 'page'),
                              ('scanner_owed', 'scanner', 'page'),
                              ('integrity_owed', 'integrity', 'page'),
                              ('unreadable', 'unmeasured', 'nudge'))
                    # Absent counts are 0 (the obligations sweep has fewer), but owed must be covered.
                    counts = [payload.get(field, 0) for field, _, _ in fields]
                    if all(type(count) is int and count >= 0 for count in counts) and not (
                            type(payload.get('owed')) is int and payload['owed'] > sum(counts)):
                        for field, source, level in fields:
                            for index in range(payload.get(field, 0)):
                                current[('watch: sweep', source, index)] = {
                                    'tier': level, 'source': f'watch: sweep:{source}',
                                    'lane': 'Work', 'reason': source}
                        continue
                tier, lane = classify(event, classified_state)
                if kind == 'watch: sweep':
                    key = (kind, '')
                elif kind in ('pr.action', 'merge.policy_blocked') and isinstance(payload, dict):
                    key = (kind, payload.get('pr'))
                elif kind in ('decision.one_way', 'draft.created') and isinstance(payload, dict):
                    key = (kind, payload.get('id', number))
                else:
                    key = (kind, number)
                if tier == 'silent':
                    current.pop(key, None)
                else:
                    current[key] = {'tier': tier, 'source': kind, 'lane': lane,
                                    'reason': payload.get('reason', kind) if isinstance(payload, dict) else kind}
    # Live health, not the last sweep's count: a partial sweep event must not hide a dead watch.
    current = {key: value for key, value in current.items() if key[:2] != ('watch: sweep', 'watch')}
    code, message = 0, ''
    # A watch with no clock line today and no installed unit is off: skip the watch import.
    if clocks or workspace.watch_unit(directory.parents[2])[1].exists():
        from wuwei import watch
        code, message = watch.health(directory.parents[2], clocks)
    if code:
        current[('watch: health',)] = {'tier': 'page' if code == 1 else 'nudge',
                                       'source': 'watch: health', 'lane': 'Work', 'reason': message}
    for name, item in classified_state['items'].items():
        if item['phase'] == 'escalated':
            tier, lane = classify({'kind': 'item.escalated', 'payload': {'item': name}},
                                  classified_state)
            current[('item.escalated', name)] = {'tier': tier, 'source': 'item.escalated',
                                                 'lane': lane, 'reason': name}
    return list(current.values()), {1: 'dead', 2: 'unmeasured'}.get(code, 'alive' if clocks else 'off')


def snapshot(directory):
    data = state.read_state(directory=directory)
    result = {'pages': 0, 'nudges': 0, 'cap': data['cap'], 'gate_approved': data['gate_approved'],
              'phases': {phase: count for phase in state.PHASES
                         if (count := sum(item['phase'] == phase for item in data['items'].values()))},
              'next_reply_due': None, 'next_meeting': None}
    classified_state = {**data, 'now': workspace.now().isoformat()}
    active, result['watch'] = scan(directory, classified_state)
    result['pages'] = sum(row['tier'] == 'page' for row in active)
    result['nudges'] = sum(row['tier'] == 'nudge' for row in active)
    for key, field, destination in (('reply_obligations', 'due', 'next_reply_due'),
                                     ('meetings', 'start', 'next_meeting')):
        rows = data.get(key, [])
        if not isinstance(rows, list):
            raise ValueError(f'{key}: expected list')
        dates = [row[field] for row in rows if isinstance(row, dict)
                 and isinstance(row.get(field), str)]
        if dates:
            parsed = [(datetime.fromisoformat(value), value) for value in dates]
            if any(instant.tzinfo is None for instant, _ in parsed):
                raise ValueError(f'{key}: expected timezone-aware timestamps')
            result[destination] = min(parsed, key=lambda row: row[0])[1]
    config_path = directory.parents[1] / 'config.toml'
    config = workspace.load_config(directory.parents[2]) if config_path.is_file() else None
    if config is not None and config['adapters']['calendar'] != 'none':
        from wuwei import registry
        root = directory.parents[2]
        now = workspace.now()
        result['next_meeting'] = None
        try:
            measured = registry.load('calendar', config).events(
                now.isoformat(), (now + timedelta(days=7)).isoformat(), root=root)
            if measured.exit == 0:
                if not isinstance(measured.data, list):
                    raise ValueError('calendar returned invalid events')
                upcoming = []
                for event in measured.data:
                    if not isinstance(event, dict) or not isinstance(event.get('start'), str):
                        raise ValueError('calendar event missing start')
                    start = datetime.fromisoformat(event['start'])
                    if start.tzinfo is None:
                        raise ValueError('calendar event needs timezone')
                    if start >= now:
                        upcoming.append((start, event['start']))
                result['next_meeting'] = min(upcoming, default=(None, None))[1]
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            pass
    return result


def run(args):
    try:
        data = snapshot(workspace.day_dir())
    except (OSError, ValueError, KeyError, TypeError, RecursionError, UnicodeError) as exc:
        if args.line:
            print('WUWEI ? unmeasured')
        else:
            print(json.dumps({'status': 'unmeasured'}))
        print(f'wuwei status: {exc}', file=sys.stderr)
        return UNRUN
    if args.json:
        print(json.dumps(data))
    else:
        parts = [f'WUWEI pages {data["pages"]}', f'nudges {data["nudges"]}']
        if not data['gate_approved']:
            parts[0] = 'WUWEI no plan yet | ' + parts[0][6:]
        if data['watch'] != 'alive':
            parts.append(f'watch {data["watch"]}')
        parts.extend(f'{phase} {count}/{data["cap"]}' for phase, count in data['phases'].items())
        if data['next_reply_due']:
            parts.append(f'reply {data["next_reply_due"]}')
        parts.append(f'meeting {data["next_meeting"] or "unmeasured"}')
        print(' | '.join(parts))
    return CLEAN
