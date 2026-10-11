"""Read-only status snapshots for the owner surfaces."""

from datetime import datetime, timedelta
import json
import re
import sys

from wuwei import state, workspace
from wuwei.exits import CLEAN, UNRUN, DAMAGED, ADAPTER_DATA
from wuwei.signal import SILENT, classify


def _alternation(words):
    """A regex alternation of literal words as a prefix tree: each character is tested once
    per level, not once per word (#346: the scan meets this once per line)."""
    if len(words) == 1:
        return re.escape(words[0])
    groups = {}
    for word in words:
        if word:
            groups.setdefault(word[0], []).append(word[1:])
    parts = [re.escape(head) + _alternation(tails) for head, tails in sorted(groups.items())]
    if len(parts) == 1 and '' not in words:
        return parts[0]
    return '(?:' + '|'.join(parts) + ')' + ('?' if '' in words else '')


WIDTH = 100  # status --line columns unless --width says otherwise (#521)
# #641: what the line calls each phase, in this order; CAP is shown on seats only.
WORDS = {'planned': 'planned', **dict.fromkeys(state.BUILD_PHASES, 'building'),
         **dict.fromkeys(('gate', 'delta', 'raised'), 'in review'),
         'merged': 'shipped', 'parked': 'parked', 'escalated': 'escalated'}
# Silent kinds the scan drops with no action.
SKIP = frozenset(SILENT)
# One match per line scan reads: a run of complete producer lines (state._append_jsonl:
# kind first, ts last) of a skipped kind, consumed in C, then the next line (group 1).
# Anything else, torn lines included, is decoded as before. Compiled on first scan.
LINES = (r'(?:\{"kind": "' + _alternation(sorted(SKIP))
         + r'", [^\n]*, "ts": "[^"\n]*"\}\n)*([^\n]*)\n?')


def register(subparsers):
    parser = subparsers.add_parser('status', help='show day status')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--line', action='store_true')
    output.add_argument('--json', action='store_true')
    parser.add_argument('--width', type=int, default=WIDTH)
    parser.set_defaults(func=run)


def attention(directory, classified_state=None):
    """Current page and warning causes from one read of the day's event stream."""
    classified_state = classified_state or {**state.read_state(directory=directory),
                                              'now': workspace.now().isoformat()}
    today = workspace.now().date()
    current = {}
    path = directory / 'events.jsonl'
    if path.exists():
        # read_text's universal newlines without its second full-size copy of the day (#346).
        text = path.read_bytes().decode('utf-8')
        if '\r' in text:
            text = text.replace('\r\n', '\n').replace('\r', '\n')
        number, counted = 0, 0
        for found in re.finditer(LINES, text):
            line = found[1]
            if not line.strip():
                continue
            # The line's index in the file, as enumerate over its lines gave it.
            number += text.count('\n', counted, found.start(1))
            counted = found.start(1)
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
                if kind in ('state.transition', 'item.escalated'):
                    continue
                if kind == 'pr.action' and isinstance(payload, dict) and 'tier' not in payload:
                    current.pop(('pr.action', payload.get('pr')), None)
                    continue
                if (kind == 'pr.action' and isinstance(payload, dict)
                        and payload.get('state') in ('merged', 'closed')):
                    current.pop(('merge.policy_blocked', payload.get('pr')), None)
                if kind in SILENT:
                    continue
            else:
                kind, payload, stamp = 'unreadable event', {}, None
            tier, lane = classify(event, classified_state)
            if kind in ('pr.action', 'merge.policy_blocked') and isinstance(payload, dict):
                key = (kind, payload.get('pr'))
            elif tier == 'page':
                key = (kind, number)
            else:  # #786: one row per subject, so a repeat folds in and a later silent event of the kind clears it
                subject = (payload.get('pr') or payload.get('item') or payload.get('reason', kind)) \
                    if isinstance(payload, dict) else kind
                key = (kind, str(subject))
            if tier == 'silent':
                current.pop(key, None)
            else:
                reason = payload.get('reason', kind) if isinstance(payload, dict) else kind
                current[key] = {'tier': tier, 'source': kind, 'lane': lane, 'reason': reason,
                                'count': current.get(key, {}).get('count', 0) + 1,
                                'ts': stamp if isinstance(stamp, str) else None}
    for name, item in classified_state['items'].items():
        if item['phase'] == 'escalated':
            tier, lane = classify({'kind': 'item.escalated', 'payload': {'item': name}},
                                  classified_state)
            current[('item.escalated', name)] = {'tier': tier, 'source': 'item.escalated',
                                                 'lane': lane, 'reason': name}
    return list(current.values())


def snapshot(directory, line=False):
    """The day's figures; line=True skips the fields status --line never renders (#562)."""
    data = state.read_state(directory=directory)
    result = {'pages': 0, 'cap': data['cap'], 'cap_bound': data['cap_bound'],
              'gate_approved': data['gate_approved'],
              'phases': {phase: count for phase in state.PHASES
                         if (count := sum(item['phase'] == phase for item in data['items'].values()))},
              'next_reply_due': None, 'next_meeting': None,
              'seats': {} if line else state.running_by_goal(data), 'running': state.in_flight(data)}
    result['gates'] = {name: row['gates'] for name, row in data['items'].items() if row['gates']}
    config_path = directory.parents[1] / 'config.toml'
    config = workspace.load_config(directory.parents[2]) if config_path.is_file() else None
    classified_state = {**data, 'now': workspace.now().isoformat()}
    active = attention(directory, classified_state)
    result['pages'] = sum(row['tier'] == 'page' for row in active)
    result['trace_gaps'] = sum(row.get('count', 1) for row in active if row['source'] == 'traces.gap')
    result['solo'] = any(row == [] for row in data.get('pr_reviewers', {}).values())
    result['plan'] = (directory / 'plan.md').is_file()
    for key, field, destination in () if line else (('reply_obligations', 'due', 'next_reply_due'),
                                                    ('meetings', 'start', 'next_meeting')):
        rows = data.get(key, [])
        if not isinstance(rows, list):
            raise ValueError(f'{key}: expected list; {DAMAGED}')
        dates = [row[field] for row in rows if isinstance(row, dict)
                 and isinstance(row.get(field), str)]
        if dates:
            parsed = [(datetime.fromisoformat(value), value) for value in dates]
            if any(instant.tzinfo is None for instant, _ in parsed):
                raise ValueError(f'{key}: expected timezone-aware timestamps; {DAMAGED}')
            result[destination] = min(parsed, key=lambda row: row[0])[1]
    result['enforce'] = config['guards']['enforce'] if config is not None else None
    from wuwei import integrity
    result['restart'] = integrity.restart(config) if config is not None else ''
    if line:
        return result
    if config is not None:
        result['checks_none'] = [repo['name'] for repo in config['repos'] if not repo['fast_checks']]  # #600
    result['plugin'] = integrity.version()
    result['template'] = config['template_version'] if config is not None else None
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
                    raise ValueError(f'calendar returned invalid events; {ADAPTER_DATA}')
                upcoming = []
                for event in measured.data:
                    if not isinstance(event, dict) or not isinstance(event.get('start'), str):
                        raise ValueError(f'calendar event missing start; {ADAPTER_DATA}')
                    start = datetime.fromisoformat(event['start'])
                    if start.tzinfo is None:
                        raise ValueError(f'calendar event needs timezone; {ADAPTER_DATA}')
                    if start >= now:
                        upcoming.append((start, event['start']))
                result['next_meeting'] = min(upcoming, default=(None, None))[1]
        except (OSError, ValueError, KeyError, TypeError, UnicodeError):
            pass
    return result


def run(args):
    try:
        data = snapshot(workspace.day_dir(), line=args.line and not args.json)
    except (OSError, ValueError, KeyError, TypeError, RecursionError, UnicodeError) as exc:
        if args.json:
            print(json.dumps({'status': 'unmeasured'}))
        else:
            print('WUWEI ? unmeasured')
        print(f'wuwei status: {exc}', file=sys.stderr)
        return UNRUN
    if args.json:
        print(json.dumps(data))
    elif args.line:
        print(line(data, args.width))
    else:
        print(full(data))
    return CLEAN


def _roles(data):
    """Roles of the running seats, oldest first; a fast check is not a seat."""
    return [role for _, role, _ in data.get('running', []) if role != 'checks']


def _groups(data, shown=None):
    """[now, work, attention] token lists: the one source of the line and of status (#521)."""
    now = []
    if data.get('restart'):
        now = [data['restart'].split(' (plugin ', 1)[0]]
    elif not data['gate_approved']:
        now = ['gate waiting' if data.get('plan') else 'no plan yet']
    counts = dict.fromkeys(WORDS.values(), 0)
    for phase, count in data['phases'].items():
        word = WORDS.get(phase, phase)
        counts[word] = counts.get(word, 0) + count
    work = [f'{count} {word}' for word, count in counts.items() if count]
    roles = _roles(data)
    if data['gate_approved'] or roles:
        names = roles[:shown] + ([f'+{len(roles) - shown} more'] if shown is not None and shown < len(roles) else [])
        work.append(f'seats {len(roles)}/{data["cap"]}' + (f' by {data["cap_bound"]}' if data.get('cap_bound') else '')
                    + (f' ({", ".join(names)})' if names else ''))  # #658: the bound names the rule
    attention = [f'pages {data["pages"]}']
    if data.get('enforce') is False:
        attention.append('observe')
    return [now, work, attention]


def _render(groups):
    return 'WUWEI ' + ' | '.join(' · '.join(group) for group in groups if group)


def line(data, width=WIDTH):
    """The groups that fit width: roles cut into +N more first, then whole tokens dropped from
    the right of work, then of attention; now and the first token always stay (#521)."""
    for shown in range(len(_roles(data)), -1, -1):
        groups = _groups(data, shown)
        if len(_render(groups)) <= width:
            return _render(groups)
    first = next((group for group in groups if group), [])
    while len(_render(groups)) > width:
        # work before attention, never now, and the first token stays
        victim = next((g for g in groups[1:] if g and (g is not first or len(g) > 1)), None)
        if victim is None:
            break
        victim.pop()
    return _render(groups)


def full(data):
    """The line's groups one per line with the detail the line drops (#521)."""
    now, work, attention = _groups(data)
    if data.get('restart'):
        now = [data['restart']]
    if split := state.goal_split(data.get('seats', {})):
        work.append(f'builders {split}')
    running = [[f'running {state.in_flight_text([row])}'] for row in data.get('running', [])]
    if data.get('trace_gaps'):
        attention.append(f'traces: {data.get("trace_gaps")} gaps')
    if data.get('solo'):
        from wuwei.obligations import SOLO
        attention.insert(-1 if data.get('trace_gaps') else len(attention), SOLO)
    calendar = [f'reply {data["next_reply_due"]}'] if data.get('next_reply_due') else []
    calendar.append(f'meeting {data["next_meeting"] or "unmeasured"}')
    versions = [f'plugin {data.get("plugin") or "unmeasured"}', f'template {data.get("template") or "none"}']
    from wuwei.fast_checks import NONE
    checks = [[f'{name} {NONE}'] for name in data.get('checks_none', [])]
    return 'WUWEI ' + '\n'.join(' · '.join(group) for group in (
        now, work, *running, attention, calendar, *checks, versions) if group)
