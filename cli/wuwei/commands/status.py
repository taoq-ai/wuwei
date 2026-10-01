"""Read-only status snapshots for the owner surfaces."""

from datetime import datetime, timedelta
import json
import sys

from wuwei import sessions, state, workspace
from wuwei.decision import answered
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
    """Attention rows, watch and listen state (alive, off, dead, unmeasured) and heartbeat health from one read of the day."""
    classified_state = classified_state or {**state.read_state(directory=directory),
                                              'now': workspace.now().isoformat()}
    today = workspace.now().date()
    current, clocks, replied, pin, beat = {}, {'watch': [], 'listen': []}, {}, None, None
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
                    if kind in ('watch: clock', 'listen: clock'):
                        clocks[kind.split(':')[0]].append(stamp)
                    if kind == 'heartbeat: clock':
                        beat = payload
                    if kind == 'decision.replied' and isinstance(payload, dict):
                        replied.setdefault(payload.get('id'), payload.get('option'))
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
                    if kind == 'steward.run':
                        current = {key: value for key, value in current.items() if key[0] != 'steward.due'}
                    if kind == 'remote.acknowledged' and isinstance(payload, dict):
                        for identifier in payload.get('ids', []):
                            current.pop(('remote.refused', identifier), None)
                        continue
                    if kind in SILENT:
                        continue
                    if kind == 'remote.refused' and isinstance(payload, dict) and 'pin' in payload:
                        if pin is None:
                            pin = workspace.load_config(directory.parents[2])['control_plane']['owner']
                        if payload['pin'] != pin:
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
                elif kind in ('decision.one_way', 'draft.created', 'remote.refused') and isinstance(payload, dict):
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
    health = {}
    for name, stamps in clocks.items():
        code, message = 0, ''
        # No clock line today and no installed unit is off: skip the watch import.
        if stamps or workspace.watch_unit(directory.parents[2], name=name)[1].exists():
            from wuwei import watch
            code, message = watch.health(directory.parents[2], stamps, name=name)
        if code:
            current[(f'{name}: health',)] = {'tier': 'page' if code == 1 else 'nudge',
                                             'source': f'{name}: health', 'lane': 'Work', 'reason': message}
        health[name] = {1: 'dead', 2: 'unmeasured'}.get(code, 'alive' if stamps else 'off')
    beat_health = None
    if beat is not None:
        beat_health = (beat['health'] if health['watch'] == 'alive' and isinstance(beat, dict)
                       and beat.get('health') in ('ok', 'degraded', 'unmeasured')
                       and isinstance(beat.get('page'), str) else 'unmeasured')
        if beat_health == 'degraded' and beat['page']:
            current[('heartbeat',)] = {'tier': 'page', 'source': 'heartbeat', 'lane': 'Work',
                                       'reason': beat['page']}
    for name, item in classified_state['items'].items():
        if item['phase'] == 'escalated':
            tier, lane = classify({'kind': 'item.escalated', 'payload': {'item': name}},
                                  classified_state)
            current[('item.escalated', name)] = {'tier': tier, 'source': 'item.escalated',
                                                 'lane': lane, 'reason': name}
    routes = classified_state.get('decision_routes', {})
    if not isinstance(routes, dict):
        raise ValueError('invalid decision ledger')
    for identifier in routes:
        if answered(classified_state, identifier) is None:
            source, reason = 'decision.pending', f'{identifier} pending owner decision'
            if option := replied.get(identifier):
                source, reason = 'decision.answered', (
                    f'{identifier} answered from the phone: option {option}, '
                    f'confirm with decision outcome {identifier} {option}')
            current[('decision.pending', identifier)] = {
                'tier': 'nudge', 'source': source, 'lane': 'Decisions', 'reason': reason}
    planner = classified_state.get('planner_session_id')
    if planner and planner in classified_state.get('sessions', {}):
        for row in sessions.rows(classified_state, datetime.fromisoformat(classified_state['now']),
                                 sessions.stale_seconds(directory.parents[2])):
            if row['role'] == 'planner' and row['stale']:
                current[('session.planner_stale',)] = {
                    'tier': 'nudge', 'source': 'session.planner_stale', 'lane': 'Work',
                    'reason': f'planner session {planner} stale: no hook activity for '
                              f'{row["idle_seconds"]}s; take over from the live session with: '
                              'wuwei plan session <session id> --take-over'}
    return list(current.values()), health['watch'], health['listen'], beat_health


def snapshot(directory):
    data = state.read_state(directory=directory)
    result = {'pages': 0, 'nudges': 0, 'cap': data['cap'], 'gate_approved': data['gate_approved'],
              'phases': {phase: count for phase in state.PHASES
                         if (count := sum(item['phase'] == phase for item in data['items'].values()))},
              'next_reply_due': None, 'next_meeting': None,
              'sessions': sum(not row['stale'] and 'stopped' not in row for row in sessions.rows(
                  data, workspace.now(), sessions.stale_seconds(directory.parents[2])))
              if data.get('sessions') else 0}
    result['gates'] = {name: row['gates'] for name, row in data['items'].items() if row['gates']}
    classified_state = {**data, 'now': workspace.now().isoformat()}
    active, result['watch'], result['listen'], result['health'] = scan(directory, classified_state)
    result['pages'] = sum(row['tier'] == 'page' for row in active)
    result['answered'] = [row['reason'] for row in active if row['source'] == 'decision.answered']
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
    if result['listen'] == 'off' and (config is None or config['adapters']['inbound'] == 'none'):
        result['listen'] = 'none'
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
        print(line(data))
    return CLEAN


def line(data):
    parts = [f'WUWEI pages {data["pages"]}', f'nudges {data["nudges"]}']
    if not data['gate_approved']:
        parts[0] = 'WUWEI no plan yet | ' + parts[0][6:]
    if data['watch'] != 'alive':
        parts.append(f'watch {data["watch"]}')
    if data['listen'] not in ('alive', 'none'):
        parts.append(f'listen {data["listen"]}')
    if data.get('health'):
        parts.append(f'health {data["health"]}')
    parts.extend(f'{phase} {count}/{data["cap"]}' for phase, count in data['phases'].items())
    if data['sessions']:
        parts.append(f'sessions {data["sessions"]}')
    if data['answered']:
        parts.append(f'phone answers {len(data["answered"])}')
    if data['next_reply_due']:
        parts.append(f'reply {data["next_reply_due"]}')
    parts.append(f'meeting {data["next_meeting"] or "unmeasured"}')
    return ' | '.join(parts)
