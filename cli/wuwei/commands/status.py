"""Read-only status snapshots for the owner surfaces."""

from datetime import date, datetime, timedelta
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


SHADOW_NUDGE = ('Observe posture has run {days} days. To enforce, set '
                'security.posture = "guarded" in config.toml; to keep observing, raise guards.shadow_days. '
                'bin/wuwei shadow report lists what would have been refused.')
WIDTH = 100  # status --line columns unless --width says otherwise (#521)
# #641: what the line calls each phase, in this order; CAP is shown on seats only.
WORDS = {'planned': 'planned', **dict.fromkeys(state.BUILD_PHASES, 'building'),
         **dict.fromkeys(('gate', 'delta', 'raised'), 'in review'),
         'merged': 'shipped', 'parked': 'parked', 'escalated': 'escalated'}
# Silent kinds scan drops with no action; the rest of SILENT is read (clocks, replies,
# draft and decision closures, wake, steward and acknowledgements).
SKIP = frozenset(SILENT) - {
    'watch: clock', 'listen: clock', 'heartbeat: clock', 'decision.replied',
    'decision.decided', 'draft.sending', 'draft.sent', 'draft.dropped',
    'session: wake-seen', 'steward.run', 'remote.acknowledged'}
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
    """Current page and nudge causes from the day's event stream."""
    return scan(directory, classified_state)[0]


def scan(directory, classified_state=None, *, config=None):
    """Attention rows, watch and listen state (alive, off, dead, unmeasured), heartbeat health and negotiation loops from one read of the day."""
    classified_state = classified_state or {**state.read_state(directory=directory),
                                              'now': workspace.now().isoformat()}
    today = workspace.now().date()
    current, clocks, replied, pin, beat, loops = {}, {'watch': [], 'listen': []}, {}, None, None, 0
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
                loops += kind == 'negotiation.loop'
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
                if kind == 'session: wake-seen':
                    current = {key: value for key, value in current.items() if key[0] != 'pr.changed'}
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
            elif kind in ('pr.action', 'merge.policy_blocked', 'pr.changed') and isinstance(payload, dict):
                key = (kind, payload.get('pr'))
            elif kind in ('decision.one_way', 'draft.created', 'remote.refused') and isinstance(payload, dict):
                key = (kind, payload.get('id', number))
            elif kind == 'guard.would_refuse' and isinstance(payload, dict):
                key = (kind, payload.get('guard'))
            else:
                key = (kind, number)
            if tier == 'silent':
                current.pop(key, None)
            else:
                reason = payload.get('reason', kind) if isinstance(payload, dict) else kind
                if kind == 'pr.changed' and isinstance(payload, dict):
                    reason = payload.get('summary') or (
                        f'{payload.get("pr")} changed: {", ".join(map(str, payload.get("fields") or []))}')
                if kind == 'guard.would_refuse' and isinstance(payload, dict):
                    reason = (f'{payload.get("guard")}: {payload.get("reason")} '
                              f'(warn: security.areas.{payload.get("area")})')
                if kind == 'mcp.finding' and isinstance(payload, dict):
                    from wuwei import mcp  # #351: scanner text only if it is a name.
                    shown = [value if isinstance(value, str) and mcp.NAME.fullmatch(value) else 'unnamed'
                             for value in (payload.get('severity'), payload.get('drift_type'),
                                           payload.get('server_name'))]
                    waiting = mcp.pending(directory.parents[2])
                    reason = 'MCP {} {} finding on {}: run '.format(*shown) + (
                        mcp.command(waiting) if waiting else 'bin/wuwei mcp check')
                current[key] = {'tier': tier, 'source': kind, 'lane': lane, 'reason': reason}
    # Live health, not the last sweep's count: a partial sweep event must not hide a dead watch.
    current = {key: value for key, value in current.items() if key[:2] != ('watch: sweep', 'watch')}
    health = {}
    for name, stamps in clocks.items():
        code, message = 0, ''
        # No clock line today and no installed unit is off: skip the watch import.
        if stamps or workspace.unit_installed(directory.parents[2], name=name):
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
        raise ValueError(f'invalid decision ledger; {DAMAGED}')
    for identifier in routes:
        from wuwei.decision import answered  # Here: decision and outward cost a quiet day's line.
        if answered(classified_state, identifier) is None:
            source, reason = 'decision.pending', f'{identifier} pending owner decision'
            if option := replied.get(identifier):
                source, reason = 'decision.answered', (
                    f'{identifier} answered from the phone: option {option}, '
                    f'confirm with wuwei decide {identifier} {option}')
            current[('decision.pending', identifier)] = {
                'tier': 'nudge', 'source': source, 'lane': 'Decisions', 'reason': reason}
    for identifier, row in classified_state.get('decision_outcomes', {}).items():
        if isinstance(row, dict) and row.get('undo_until'):  # #283: an open undo window
            from wuwei import cruise
            if cruise.window(row, datetime.fromisoformat(classified_state['now'])):
                current[('decision.cruise', identifier)] = {
                    'tier': 'nudge', 'source': 'decision.cruise', 'lane': 'Decisions',
                    'reason': f'{identifier} taken as {row["option"]} by {row["rule"]}, '
                              f'undo until {cruise.clock(row["undo_until"])}'}
    planner = classified_state.get('planner_session_id')
    if planner and planner in classified_state.get('sessions', {}):
        from wuwei import sessions  # Here and in snapshot: only a day with sessions pays for it.
        for row in sessions.rows(classified_state, datetime.fromisoformat(classified_state['now']),
                                 sessions.stale_seconds(directory.parents[2])):
            if row['role'] == 'planner' and row['stale']:
                current[('session.planner_stale',)] = {
                    'tier': 'nudge', 'source': 'session.planner_stale', 'lane': 'Work',
                    'reason': f'planner session {planner} stale: no hook activity for '
                              f'{row["idle_seconds"]}s; take over from the live session with: '
                              'wuwei plan session <session id> --take-over'}
    if config is None and (directory.parents[1] / 'config.toml').is_file():
        config = workspace.load_config(directory.parents[2])
    if config is not None:
        guards = config['guards']
        if workspace.posture(config)[0] == 'observe' and guards['shadow_since']:
            days = (today - date.fromisoformat(guards['shadow_since'])).days
            if days >= guards['shadow_days']:
                current[('guards.shadow',)] = {'tier': 'nudge', 'source': 'guards.shadow', 'lane': 'Work',
                                               'reason': SHADOW_NUDGE.format(days=days)}
    rows = sorted(current.values(), key=lambda row: (row['source'] != 'decision.cruise', row['source'] != 'pr.changed'))
    return rows, health['watch'], health['listen'], beat_health, loops


def surfaced(directory, rows, data=None, config=None):
    """(mode, rows) the surfaces show under nudges.mode (#742): pages always; off drops every
    nudge; next keeps an unrecorded phone answer and adds a ready fix round and a pending close;
    all, or a day without config.toml, shows every row."""
    if config is None and (directory.parents[1] / 'config.toml').is_file():
        config = workspace.load_config(directory.parents[2])
    mode = 'all' if config is None else workspace.nudge_mode(config)
    if mode == 'all':
        return mode, rows
    shown = [row for row in rows if row['tier'] != 'nudge'
             or (mode == 'next' and row['source'] == 'decision.answered')]
    if mode == 'next':
        data = state.read_state(directory=directory) if data is None else data
        busy = {item for _, _, item in state.in_flight(data)}
        for name, item in data['items'].items():
            if item['phase'] == 'fix' and name not in busy:
                shown.append({'tier': 'nudge', 'source': 'round.ready', 'lane': 'Work',
                              'reason': f'{name} fix round is ready: run wuwei build next {name}'})
        phases = [data['items'][name]['phase'] for name in data['approved_items'] if name in data['items']]
        if (data['gate_approved'] and phases and not busy and not data.get('close_requested')
                and 'merged' in phases and all(phase in ('merged', 'parked', 'escalated') for phase in phases)):
            shown.append({'tier': 'nudge', 'source': 'close.ready', 'lane': 'Work',
                          'reason': f'{phases.count("merged")} merged and nothing left to build: run wuwei close'})
    return mode, shown


def snapshot(directory, line=False):
    """The day's figures; line=True skips the fields status --line never renders (#562)."""
    data = state.read_state(directory=directory)
    live = 0
    if data.get('sessions') and not line:
        from wuwei import sessions
        live = sum(not row['stale'] and 'stopped' not in row for row in sessions.rows(
            data, workspace.now(), sessions.stale_seconds(directory.parents[2])))
    result = {'pages': 0, 'nudges': 0, 'cap': data['cap'], 'cap_bound': data['cap_bound'],
              'pace': data.get('pace'),
              'gate_approved': data['gate_approved'],
              'phases': {phase: count for phase in state.PHASES
                         if (count := sum(item['phase'] == phase for item in data['items'].values()))},
              'next_reply_due': None, 'next_meeting': None, 'sessions': live,
              'seats': {} if line else state.running_by_goal(data), 'running': state.in_flight(data)}
    result['gates'] = {name: row['gates'] for name, row in data['items'].items() if row['gates']}
    config_path = directory.parents[1] / 'config.toml'
    config = workspace.load_config(directory.parents[2]) if config_path.is_file() else None
    classified_state = {**data, 'now': workspace.now().isoformat()}
    active, result['watch'], result['listen'], result['health'], result['loops'] = scan(
        directory, classified_state, config=config)
    result['pages'] = sum(row['tier'] == 'page' for row in active)
    result['answered'] = [row['reason'] for row in active if row['source'] == 'decision.answered']
    result['nudges_mode'], shown = surfaced(directory, active, data, config)
    result['nudges'] = sum(row['tier'] == 'nudge' for row in shown)
    result['trace_gaps'] = sum(row['source'] == 'traces.gap' for row in active)
    result['prs_changed'] = sum(row['source'] == 'pr.changed' for row in active)
    result['solo'] = any(row == [] for row in data.get('pr_reviewers', {}).values())
    result['plan'] = (directory / 'plan.md').is_file()
    result['decisions'] = []
    if routes := data.get('decision_routes'):  # scan checked it is a dict
        from wuwei.decision import answered
        result['decisions'] = [name for name in routes if answered(data, name) is None]
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
    result['posture'] = workspace.posture(config)[0] if config is not None else None
    from wuwei import integrity
    result['restart'] = integrity.restart(config) if config is not None else ''
    if line:
        return result
    if config is not None:  # #283: the cruise level; a damaged cruise.json is unmeasured
        from wuwei import cruise
        result['cruise'] = cruise.label(config, cruise.running(directory.parents[2]))
        result['checks_none'] = [repo['name'] for repo in config['repos'] if not repo['fast_checks']]  # #600
    result['plugin'] = integrity.version()
    result['template'] = config['template_version'] if config is not None else None
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
    elif data.get('decisions'):
        now = [f'decision {data["decisions"][0]} waiting']
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
    attention = [f'pages {data["pages"]}'] + (
        [] if data.get('nudges_mode') == 'off' else [f'nudges {data["nudges"]}'])  # #742
    if data.get('posture') not in (None, 'guarded'):
        attention.append(data['posture'])
    if data.get('pace') not in (None, 'steady'):  # #579
        attention.append(f'pace {data["pace"]}')
    if data.get('cap_bound') == 'load':
        attention.append('held by load')
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
    for shown, text in ((data.get('answered'), f'phone answers {len(data.get("answered") or [])}'),
                        (data.get('loops'), f'loops {data.get("loops")}'),
                        (data.get('prs_changed'), f'prs {data.get("prs_changed")} changed'),
                        (data.get('trace_gaps'), f'traces: {data.get("trace_gaps")} gaps')):
        if shown:
            attention.append(text)
    if data.get('solo'):
        from wuwei.obligations import SOLO
        attention.insert(-1 if data.get('trace_gaps') else len(attention), SOLO)
    health = [f'watch {data["watch"]}', f'listen {data["listen"]}']
    health += [f'health {data["health"]}'] if data.get('health') else []
    health.append(f'sessions {data["sessions"]}')
    calendar = [f'reply {data["next_reply_due"]}'] if data.get('next_reply_due') else []
    calendar.append(f'meeting {data["next_meeting"] or "unmeasured"}')
    cruise = [data['cruise'].replace(' | ', ', ')] if data.get('cruise') else []  # #283, status only
    versions = [f'plugin {data.get("plugin") or "unmeasured"}', f'template {data.get("template") or "none"}']
    from wuwei.fast_checks import NONE
    checks = [[f'{name} {NONE}'] for name in data.get('checks_none', [])]
    return 'WUWEI ' + '\n'.join(' · '.join(group) for group in (
        now, work, *running, attention, health, calendar, cruise, *checks, versions) if group)
