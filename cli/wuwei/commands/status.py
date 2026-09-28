"""Read-only status snapshots for the owner surfaces."""

from datetime import datetime
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


def snapshot(directory):
    if not (directory / 'state.json').is_file():
        raise FileNotFoundError('day state is missing')
    data = state.read_state(directory=directory)
    result = {'pages': 0, 'nudges': 0, 'cap': data['cap'],
              'phases': {phase: 0 for phase in state.BUILD_PHASES},
              'next_reply_due': None, 'next_meeting': None}
    for item in data['items'].values():
        phase = item['phase']
        if phase in result['phases']:
            result['phases'][phase] += 1
    events = directory / 'events.jsonl'
    classified_state = {**data, 'now': workspace.now().isoformat()}
    active = {}
    today = workspace.now().date()
    if events.exists():
        with events.open(encoding='utf-8') as stream:
            for number, line in enumerate(stream):
                if not line.strip():
                    continue
                if any(line.startswith(f'{{"kind": "{kind}"') for kind in SILENT):
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    event = None
                if isinstance(event, dict):
                    kind = event.get('kind')
                    payload = event.get('payload', {})
                    if isinstance(payload, dict):
                        stamp = event.get('ts')
                        if isinstance(stamp, str) and datetime.fromisoformat(stamp).date() != today:
                            continue
                        if kind == 'state.transition':
                            continue  # current item state below owns this condition
                        if kind == 'item.escalated':
                            continue
                tier, _ = classify(event, classified_state)
                if tier != 'silent':
                    active[(number, '')] = tier
    for name, item in data['items'].items():
        if item['phase'] == 'escalated':
            tier, _ = classify({'kind': 'item.escalated', 'payload': {'item': name}},
                               classified_state)
            active[('item.escalated', name)] = tier
    result['pages'] = sum(tier == 'page' for tier in active.values())
    result['nudges'] = sum(tier == 'nudge' for tier in active.values())
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
        parts.extend(f'{phase} {count}/{data["cap"]}' for phase, count in data['phases'].items())
        if data['next_reply_due']:
            parts.append(f'reply {data["next_reply_due"]}')
        if data['next_meeting']:
            parts.append(f'meeting {data["next_meeting"]}')
        print(' | '.join(parts))
    return CLEAN
