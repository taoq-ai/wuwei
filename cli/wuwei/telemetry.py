"""Design 5.13: the weekly aggregate off the hook path, its proposals, the shared payload and
the owner's OpenTelemetry export.

Top-level imports are stdlib only and every wuwei import sits inside a function, so the
collector (scripts/telemetry-worker/) can bundle this file and call validate on its own.
"""

from collections import Counter
from datetime import date, datetime, timedelta
import json
import math
import re
import sys
import time

SCHEMA = 1
BUDGET_SECONDS = 10
MAX_DAY_BYTES = 20_000_000
WEEKS = 4
MAX_PAYLOAD = 16_384
UNMEASURED = 'unmeasured'
METRICS = ('days', 'tool_calls', 'refusals', 'unmeasured', 'warnings', 'refusal_rate', 'unmeasured_rate',
           'first_hour_refusals', 'hook_latency_ms', 'seats_launched', 'seats_lost', 'seat_minutes',
           'phase_entries', 'plan_to_merge_hours', 'gate_rounds_per_item', 'fix_rounds_per_item',
           'gate_tiers', 'long_loops', 'stuck_parks', 'decisions', 'decisions_by_class', 'decided_by',
           'reversals', 'owner_wait_hours', 'owner_asks_per_item', 'unnecessary_asks', 'owner_actions',
           'escaped_by_tier', 'aggregation_ms')
# Vocabularies as literals; tests/test_telemetry.py pins each to its source in the wuwei package.
GUARDS = ('agent_launch', 'commit_push', 'decision', 'deploy', 'integrity', 'lifecycle', 'outward', 'pr',
          'protect_state', 'spec', 'stop', 'traces', 'verdict')
PHASES = ('planned', 'spec', 'implement', 'gate', 'fix', 'delta', 'raised', 'parked', 'escalated', 'merged')
TIERS = ('light', 'standard', 'full')
CLASSES = ('approach', 'retry', 'park', 'accept-residual', 'defer', 'scope-cut', 're-plan',
           'dependency-bump', 'merge', 'message', 'other')
AREAS = ('integrity', 'mcp', 'publish', 'records', 'outward', 'seats')
POSTURES = ('observe', 'guarded', 'strict')
PROFILES = ('strict', 'standard')
OS = ('darwin', 'linux', 'other')
ADAPTERS = {'tracker': ('linear', 'none'), 'chat': ('none', 'slack'), 'review_bot': ('greptile', 'none'),
            'runtime': ('claude', 'codex', 'none'), 'scanner': ('none', 'ziran'), 'code_host': ('github', 'none'),
            'vcs': ('git',), 'host': ('local', 'none'), 'checks': ('local', 'none'), 'tts': ('none', 'say'),
            'calendar': ('ics', 'none'), 'transcripts': ('none',), 'inbound': ('none', 'slack'),
            'redactor': ('builtin',), 'docs': ('confluence', 'markdown', 'none', 'notion')}
INNER = frozenset((*GUARDS, 'config', *PHASES, *TIERS, *CLASSES, *AREAS, 'p50', 'p75', 'p90', 'p95', 'max',
                   'merged', 'escaped', 'owner', 'seat', 'cruise'))
OWNER_KINDS = ('remote.acknowledged', 'state.recovered', 'integrity_confirmation', 'mcp.decided',
               'draft.sending', 'draft.dropped')
PROBES = ('refused', 'allowed', 'state_write', 'read_loop')
SPAN_EVENTS = ('decision.routed', 'decision.decided', 'decision.reversed', 'negotiation.loop', 'gate.received',
               *OWNER_KINDS)
VERSION = re.compile(r'\d+\.\d+(\.\d+)?')
WEEK = re.compile(r'\d{4}-W\d{2}')
TOKEN = re.compile(r'[0-9a-f]{32}')
KEYS = {'schema', 'week', 'versions', 'config', 'metrics'}


class Skipped(Exception):
    def __init__(self, reason, day):
        super().__init__(reason)
        self.reason, self.week = reason, week_of(day)


def week_of(day):
    """The ISO week of a YYYY-MM-DD day name."""
    year, week, _ = date.fromisoformat(day).isocalendar()
    return f'{year}-W{week:02d}'


def _time(text):
    return datetime.fromisoformat(text)


def read_days(root, start):
    """{day name: (directory, rows)} oldest first; Skipped past the byte cap or the budget."""
    from wuwei import watch
    found = {}
    for directory in reversed(watch.days(root)):
        if time.monotonic() - start > BUDGET_SECONDS:
            raise Skipped('time', directory.name)
        path = directory / 'events.jsonl'
        if path.exists() and path.stat().st_size > MAX_DAY_BYTES:
            raise Skipped('size', directory.name)
        found[directory.name] = directory, watch.records(path)
    return found


def _percentiles(values, *names):
    from wuwei.metrics import _percentile
    if not values:
        return UNMEASURED
    fractions = {'p50': .5, 'p75': .75, 'p90': .9, 'p95': .95}
    return {name: max(values) if name == 'max' else _percentile(values, fractions[name]) for name in names}


def _rate(part, whole):
    return part / whole if whole and whole != UNMEASURED else UNMEASURED


def aggregate(root, config, week, days, start):
    """Every 5.13 metric of one week, and the evidence the proposal rules need."""
    from wuwei import decision, integrity, metrics as day_metrics, verdict, workspace
    inside = {name: value for name, value in days.items() if week_of(name) == week}
    rows = [(name, row) for name, (_, records) in inside.items() for row in records]
    every = [(name, row) for name, (_, records) in days.items() for row in records]

    def kind(*kinds):
        return [row['payload'] for _, row in rows if row['kind'] in kinds]

    refusals, unmeasured = Counter(), Counter()
    for payload in kind('hook.refusal'):
        for refusal in payload.get('refusals') or [{'guard': 'config', 'exit': 2}]:
            (unmeasured if refusal.get('exit', 1) == 2 else refusals)[refusal['guard']] += 1
    warnings = Counter(payload['guard'] for payload in kind('guard.would_refuse'))
    traces = [directory / 'traces.jsonl' for directory, _ in inside.values()
              if (directory / 'traces.jsonl').exists()]
    tool_calls = sum(path.read_bytes().count(b'\n') for path in traces) if traces else UNMEASURED
    found = {'days': len(inside), 'tool_calls': tool_calls, 'refusals': dict(refusals),
             'unmeasured': dict(unmeasured), 'warnings': dict(warnings)}
    refused, failed, warned = sum(refusals.values()), sum(unmeasured.values()), sum(warnings.values())
    found['refusal_rate'] = _rate(refused, tool_calls if tool_calls == UNMEASURED else tool_calls + refused)
    found['unmeasured_rate'] = _rate(failed, refused + failed + warned)
    if days and week_of(min(days)) == week:
        first = days[min(days)][1]
        if first:
            end = _time(first[0]['ts']) + timedelta(hours=1)
            found['first_hour_refusals'] = sum(
                len(row['payload'].get('refusals') or [None]) if row['kind'] == 'hook.refusal' else 1
                for row in first if row['kind'] in ('hook.refusal', 'guard.would_refuse')
                and _time(row['ts']) <= end)
    found['hook_latency_ms'] = _percentiles(
        [probe['ms'] for payload in kind('heartbeat: clock') for name, probe in payload.get('probes', {}).items()
         if name in PROBES and isinstance(probe.get('ms'), int)], 'p50', 'p95', 'max')
    launched = [(name, row['payload']['name']) for name, row in rows if row['kind'] == 'seat launched']
    stopped = {(name, row['payload']['name']) for name, row in rows if row['kind'] == 'seat stopped'}
    found['seats_launched'] = len(launched)
    found['seats_lost'] = sum(seat not in stopped for seat in launched)
    durations = [payload['usage']['duration'] / 60 for payload in kind('seat.usage')
                 if type(payload.get('usage', {}).get('duration')) in (int, float)]
    found['seat_minutes'] = _percentiles(durations, 'p50', 'p90')
    found['phase_entries'] = dict(Counter(
        phase for _, row in rows for phase in row['payload'].get('phase_changes', {}).values()))
    approved = {}
    for _, row in every:
        payload = row['payload']
        items = (payload.get('items', []) + payload.get('approved_items', [])
                 if row['kind'] in ('plan.approved', 'state.import')
                 else [payload.get('item')] if row['kind'] == 'plan.added' else [])
        for item in items:
            approved.setdefault(item, _time(row['ts']))
    merged = [(item, _time(row['ts'])) for _, row in rows
              for item, phase in row['payload'].get('phase_changes', {}).items() if phase == 'merged']
    found['plan_to_merge_hours'] = _percentiles(
        [(at - approved[item]).total_seconds() / 3600 for item, at in merged if item in approved], 'p50', 'p75')
    rounds = Counter(payload['item'] for payload in kind('gate.received'))
    fixes = Counter(item for _, row in rows for item, phase in row['payload'].get('phase_changes', {}).items()
                    if phase == 'fix')
    found['gate_rounds_per_item'] = _percentiles(list(rounds.values()), 'p50', 'max')
    found['fix_rounds_per_item'] = _percentiles([fixes[item] for item in rounds], 'p50', 'max')
    found['gate_tiers'] = dict(Counter(payload['computed'] for payload in kind('gate.tiered')))
    found['long_loops'] = len(kind('negotiation.loop'))
    found['stuck_parks'] = len(kind('build.parked'))
    seen = {}
    for name, row in rows:
        if row['kind'] in ('decision.routed', 'decision.decided'):
            seen.setdefault(row['payload']['id'], name)
    found['decisions'] = len(seen)
    classes = Counter()
    for identifier, name in seen.items():
        path = inside[name][0] / 'decisions' / f'{identifier}.md'
        text = path.read_text(encoding='utf-8') if path.is_file() and not path.is_symlink() else ''
        named = (verdict.rows(verdict.active_text(text), 'Class') or [''])[0].strip()
        classes[named if named in CLASSES else 'other'] += 1
    found['decisions_by_class'] = dict(classes)
    by = [str(payload.get('decided_by')) for payload in kind('decision.decided')]
    found['decided_by'] = dict(Counter('cruise' if who.startswith('cruise') else who
                                       for who in by if who in ('owner', 'seat') or who.startswith('cruise')))
    found['reversals'] = len(kind('decision.reversed'))
    routed, waits, external = {}, [], []
    zone = workspace.zone(config)
    for name, row in every:
        payload = row['payload']
        if row['kind'] == 'decision.routed':
            routed[payload['id']] = _time(row['ts']), 'item' in payload
        elif (row['kind'] in ('decision.decided', 'decision.reversed') and payload.get('decided_by') == 'owner'
              and payload.get('id') in routed and week_of(name) == week):
            at, outside = routed.pop(payload['id'])
            waits.append((_time(row['ts']) - at).total_seconds() / 3600)
            if outside:
                external.append(decision.weekday_hours(at, _time(row['ts']), zone))
    found['owner_wait_hours'] = _percentiles(waits, 'p50', 'p90')
    asks, unnecessary = Counter(), 0
    for directory, _ in inside.values():
        data = day_metrics._state(directory)
        if data is None:
            continue
        routes = data.get('decision_routes', {})
        named = decision.naming(directory, list(data['items']))
        asks.update(item for identifier in routes for item in named.get(identifier, []))
        unnecessary += sum(decision.answered(data, identifier) == route.get('recommendation')
                           for identifier, route in routes.items())
    found['owner_asks_per_item'] = sum(asks.values()) / len(asks) if asks else UNMEASURED
    found['unnecessary_asks'] = unnecessary
    found['owner_actions'] = sum(row['kind'].startswith('remote.') or row['kind'] in OWNER_KINDS for _, row in rows)
    found['escaped_by_tier'] = day_metrics._escaped_by_tier(root)
    found['aggregation_ms'] = round((time.monotonic() - start) * 1000)
    plugin = integrity.version()
    return {'schema': SCHEMA, 'week': week,
            'versions': {'plugin': plugin, 'python': f'{sys.version_info[0]}.{sys.version_info[1]}',
                         'os': sys.platform if sys.platform in ('darwin', 'linux') else 'other'},
            'config': {'posture': workspace.posture(config)[0], 'profile': config['profile'],
                       'adapters': dict(config['adapters']), 'repositories': len(config['repos'])},
            'metrics': {key: found[key] for key in METRICS if key in found},
            'evidence': {'verdict_items': len(rounds), 'external_wait_hours': external}}


def _round(value):
    if isinstance(value, dict):
        return {key: _round(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_round(inner) for inner in value]
    if isinstance(value, float):
        value = round(value, 2)
        return int(value) if value.is_integer() else value
    return value


def current_week(root):
    from wuwei import workspace
    return week_of(workspace.day_dir(root).name)


def _path(root, week):
    from pathlib import Path
    if not WEEK.fullmatch(week):
        raise ValueError(f'invalid week {week!r}; pass a week such as 2026-W40')
    return Path(root) / '.wuwei/metrics' / f'{week}.json'


def load_week(root, week):
    """A week's file, or None when absent."""
    path = _path(root, week)
    if not path.is_file():
        return None
    found = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(found, dict) or found.get('week') != week:
        raise ValueError(f'{path.name} is not a week file; remove it, then run bin/wuwei metrics --week {week}')
    return found


def save_week(root, found):
    from wuwei import workspace
    path = _path(root, found['week'])
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(path, json.dumps(found, indent=2, sort_keys=True) + '\n')


def week_file(root, config, week, days=None, *, start=None, write=True):
    """Compute one week: final with proposals before the current week; keeps shared, ready, presented and otlp."""
    start = time.monotonic() if start is None else start
    days = read_days(root, start) if days is None else days
    found = _round(aggregate(root, config, week, days, start))
    found['final'] = week < current_week(root)
    if found['final']:
        found['proposals'] = proposals(found, config)
    previous = load_week(root, week) or {}
    found.update({key: previous[key] for key in ('shared', 'ready', 'presented', 'otlp') if key in previous})
    if write:
        save_week(root, found)
    return found


def weeks(root):
    """Week names with a file, newest first."""
    from pathlib import Path
    return sorted((path.stem for path in (Path(root) / '.wuwei/metrics').glob('*.json')
                   if WEEK.fullmatch(path.stem)), reverse=True)


def latest_final(root):
    return next((found for found in map(lambda week: load_week(root, week), weeks(root)) if found.get('final')), None)


def proposals(found, config):
    """Design 5.13's five rules; each {rule, evidence, command}."""
    from wuwei import guards, workspace
    from wuwei.metrics import _percentile
    metrics, evidence, result = found['metrics'], found['evidence'], []

    def floor(rule, tier, line, target, at):
        for index, repo in enumerate(config['repos']):
            if at(TIERS.index(repo['gates']['floor'])):
                result.append({'rule': rule, 'evidence': line, 'command':
                               f"bin/wuwei config set repos.{index}.gates.floor '\"{target}\"'"})

    tiers = metrics['escaped_by_tier'] if isinstance(metrics['escaped_by_tier'], dict) else {}
    for tier, row in tiers.items():
        if tier in TIERS[:-1] and row['merged'] >= 5 and row['escaped'] / row['merged'] >= 0.2:
            floor('floor-raise', tier, f"{tier}: {row['escaped']} of {row['merged']} merged items escaped",
                  TIERS[TIERS.index(tier) + 1], lambda at, tier=tier: at <= TIERS.index(tier))
    full = tiers.get('full', {'merged': 0, 'escaped': 1})
    if full['merged'] >= 10 and full['escaped'] == 0:
        floor('floor-lower', 'full', f"full: {full['merged']} merged items, none escaped", 'standard',
              lambda at: at == TIERS.index('full'))
    warned = {guards.AREAS.get(guard) for guard in metrics['warnings']}
    # ponytail: an area no guard module maps to (mcp applies its own posture) is never proposed.
    for area, level in workspace.posture(config)[1].items():
        if level == 'warn' and metrics['days'] >= 3 and area in guards.AREAS.values() and area not in warned:
            result.append({'rule': 'area-block', 'evidence': f"{area} at warn, no warning in {metrics['days']} days",
                           'command': f"bin/wuwei config set security.areas.{area} '\"block\"'"})
    waits, limit = evidence['external_wait_hours'], config['decisions']['wait_hours']
    if len(waits) >= 3 and _percentile(waits, .9) < limit / 2:
        p90 = round(_percentile(waits, .9), 2)
        result.append({'rule': 'wait-hours', 'evidence': f'{len(waits)} external waits, p90 {p90} h under {limit / 2:g} h',
                       'command': f'bin/wuwei config set decisions.wait_hours {max(4, math.ceil(p90 * 1.5))}'})
    fixes = metrics['fix_rounds_per_item']
    if evidence['verdict_items'] >= 5 and isinstance(fixes, dict) and fixes['p50'] >= 1:
        result.append({'rule': 'fast-checks', 'evidence': f"{evidence['verdict_items']} items with a verdict, "
                       f"fix rounds p50 {fixes['p50']}", 'command': 'bin/wuwei calibrate --measure'})
    return result


def payload(found, *, token=None):
    """The shareable subset of a final week: never final, evidence, proposals or marks."""
    return {**{key: found[key] for key in KEYS}, **({'token': token} if token else {})}


def _number(value):
    return (type(value) is int and value >= 0) or (type(value) is float and value >= 0 and math.isfinite(value)
                                                    and round(value, 2) == value)


def _leaf(value):
    return _number(value) or value == UNMEASURED


def validate(found):
    """Raise ValueError(rule) unless the payload keeps to the 5.13 anonymisation rules."""
    if not isinstance(found, dict) or set(found) not in (KEYS, KEYS | {'token'}):
        raise ValueError('top-level keys; remove .wuwei/metrics/<week>.json, then run bin/wuwei metrics --week <week>')
    if found['schema'] != SCHEMA or not isinstance(found['week'], str) or not WEEK.fullmatch(found['week']):
        raise ValueError('schema or week; remove .wuwei/metrics/<week>.json, then run bin/wuwei metrics --week <week>')
    if 'token' in found and not (isinstance(found['token'], str) and TOKEN.fullmatch(found['token'])):
        raise ValueError('token')
    versions, config = found['versions'], found['config']
    if (not isinstance(versions, dict) or set(versions) != {'plugin', 'python', 'os'}
            or not all(isinstance(versions[key], str) and VERSION.fullmatch(versions[key]) for key in ('plugin', 'python'))
            or versions['os'] not in OS):
        raise ValueError('versions')
    if (not isinstance(config, dict) or set(config) != {'posture', 'profile', 'adapters', 'repositories'}
            or config['posture'] not in POSTURES or config['profile'] not in PROFILES
            or type(config['repositories']) is not int or config['repositories'] < 0
            or not isinstance(config['adapters'], dict)
            or any(port not in ADAPTERS or name not in ADAPTERS[port] for port, name in config['adapters'].items())):
        raise ValueError('config')
    metrics = found['metrics']
    if not isinstance(metrics, dict) or not set(metrics) <= set(METRICS):
        raise ValueError('metric keys; remove .wuwei/metrics/<week>.json, then run bin/wuwei metrics --week <week>')

    def check(value, depth):
        if isinstance(value, dict) and depth < 2:
            for key, inner in value.items():
                if key not in INNER:
                    raise ValueError('metric inner keys; remove .wuwei/metrics/<week>.json, then run bin/wuwei metrics --week <week>')
                check(inner, depth + 1)
        elif not _leaf(value):
            raise ValueError('metric values; remove .wuwei/metrics/<week>.json, then run bin/wuwei metrics --week <week>')
    for value in metrics.values():
        check(value, 0)
    if len(json.dumps(found, sort_keys=True).encode()) > MAX_PAYLOAD:
        raise ValueError('payload over 16 KB; remove .wuwei/metrics/<week>.json, then run bin/wuwei metrics --week <week>')
    return found


def _leaves(value, prefix=''):
    if isinstance(value, dict):
        return [row for key, inner in value.items() for row in _leaves(inner, f'{prefix}{key}.')]
    return [(prefix[:-1], value)]


def issue(found):
    """(title, body) of the attributed issue: a two-column table of the payload, never the token."""
    found = {key: value for key, value in found.items() if key != 'token'}
    rows = sorted(_leaves(found))
    return (f"telemetry: {found['week']}",
            '| key | value |\n|---|---|\n' + ''.join(f'| {key} | {value} |\n' for key, value in rows))


def token(root):
    """The workspace's anonymous id, created once with secrets."""
    import secrets
    from pathlib import Path
    from wuwei import workspace
    path = Path(root) / '.wuwei/metrics/token'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        workspace.atomic_write(path, secrets.token_hex(16) + '\n', mode=0o600)
    value = path.read_text(encoding='utf-8').strip()
    if not TOKEN.fullmatch(value):
        raise ValueError('.wuwei/metrics/token: expected 32 hex characters; remove it and WUWEI writes a new one')
    return value


def _attributes(**values):
    return [{'key': f'wuwei.{key}', 'value': {'stringValue': str(value)}}
            for key, value in values.items() if value is not None]


def _nanos(text):
    return str(int(_time(text).timestamp() * 1_000_000_000))


def spans(root, config, mark):
    """OTLP/HTTP JSON traces for the records after mark ({day, offset}), and the new mark."""
    import hashlib
    from wuwei import watch, workspace
    # ponytail: allowed calls live in traces.jsonl with their tool arguments and are not exported;
    # hook-call spans are the refusal and warning records only.
    posture, today = workspace.posture(config)[0], workspace.day_dir(root).name
    mark = mark or {'day': today, 'offset': 0}
    result, new = [], dict(mark)
    for directory in reversed(watch.days(root)):
        if directory.name < mark['day']:
            continue
        path = directory / 'events.jsonl'
        data = path.read_bytes() if path.exists() else b''
        offset = mark['offset'] if directory.name == mark['day'] else 0
        trace = hashlib.sha256(f'{root}/{directory.name}'.encode()).hexdigest()[:32]
        batch, events, launched = [], [], {}

        def span(name, at, start, end, **values):
            batch.append({'traceId': trace, 'spanId': hashlib.sha256(f'{directory.name}:{at}'.encode()).hexdigest()[:16],
                          'name': name, 'kind': 1, 'startTimeUnixNano': start, 'endTimeUnixNano': end,
                          'attributes': _attributes(**values)})
        for line in data[offset:].splitlines(keepends=True):
            if not line.endswith(b'\n'):
                break
            row, at = json.loads(line), offset
            offset += len(line)
            payload, kind, stamp = row['payload'], row['kind'], _nanos(row['ts'])
            if kind == 'hook.refusal':
                for index, refusal in enumerate(payload.get('refusals') or [{'guard': 'config', 'exit': 2}]):
                    code = refusal.get('exit', 1)
                    span('wuwei.hook', f'{at}:{index}', stamp, stamp, event='PreToolUse', guard=refusal['guard'],
                         outcome='unmeasured' if code == 2 else 'refuse', reason_code=f"{refusal['guard']}.{code}",
                         posture=posture)
            elif kind == 'guard.would_refuse':
                span('wuwei.hook', at, stamp, stamp, event=kind, guard=payload.get('guard'), outcome='warn',
                     reason_code=f"{payload.get('guard')}.{payload.get('exit', 1)}", posture=payload.get('posture'),
                     item=payload.get('item'))
            elif kind == 'seat launched':
                launched[payload.get('name')] = stamp, payload.get('item')
            elif kind == 'seat stopped' and payload.get('name') in launched:
                start, item = launched.pop(payload['name'])
                span('wuwei.seat', at, start, stamp, item=item)
            elif kind in SPAN_EVENTS or kind.startswith('remote.'):
                events.append({'timeUnixNano': stamp, 'name': kind, 'attributes': _attributes(item=payload.get('item'))})
        if events:
            span('wuwei.day', 'day', events[0]['timeUnixNano'], events[-1]['timeUnixNano'])
            batch[-1]['events'] = events
        result += batch
        new = {'day': directory.name, 'offset': offset}
    body = {'resourceSpans': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'wuwei'}}]},
                               'scopeSpans': [{'scope': {'name': 'wuwei'}, 'spans': result}]}]}
    return body, new


def otlp_metrics(found, now):
    """OTLP/HTTP JSON metrics of a week: counts as sums, percentiles and rates as gauges."""
    stamp = str(int(now.timestamp() * 1_000_000_000))
    rows = []
    for key, value in found['metrics'].items():
        points = [(inner, leaf) for inner, leaf in _leaves(value) if leaf != UNMEASURED]
        if not points:
            continue
        gauge = isinstance(value, float) or (isinstance(value, dict) and set(value) <= {'p50', 'p75', 'p90', 'p95', 'max'})
        data = [{'timeUnixNano': stamp, **({'asInt': str(leaf)} if type(leaf) is int else {'asDouble': leaf}),
                 'attributes': _attributes(key=inner) if inner else []} for inner, leaf in points]
        rows.append({'name': f'wuwei.{key}', **({'gauge': {'dataPoints': data}} if gauge else
                                                 {'sum': {'dataPoints': data, 'aggregationTemporality': 1,
                                                          'isMonotonic': True}})})
    return {'resourceMetrics': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'wuwei'}}]},
                                 'scopeMetrics': [{'scope': {'name': 'wuwei'}, 'metrics': rows}]}]}


def _ok(status):
    return 200 <= status < 300


def _share(root, config):
    from wuwei import registry, state
    share = config['telemetry']['share']
    finals = [found for found in (load_week(root, week) for week in weeks(root)) if found.get('final')][:WEEKS]
    for found in finals:
        week = found['week']
        if share == 'attributed' and not found.get('ready'):
            save_week(root, {**found, 'ready': True})
            state.append_event('telemetry.ready', {'week': week}, root)
        if share != 'anonymous' or found.get('shared'):
            continue
        endpoint, reason = config['telemetry']['endpoint'], None
        try:
            if not endpoint.startswith('https://'):
                raise LookupError('no endpoint; set telemetry.endpoint to an https URL')
            body = validate(payload(found, token=token(root)))
        except (LookupError, ValueError) as exc:
            reason = str(exc) if not isinstance(exc, KeyError) else 'payload'
        else:
            try:
                status = registry.watch_service().post(endpoint, body)
                reason = None if _ok(status) or status == 409 else f'HTTP {status}'
            except (OSError, ValueError) as exc:
                reason = type(exc).__name__
        if reason:
            state.append_event('telemetry.unsent', {'week': week, 'mode': 'anonymous', 'reason': reason}, root)
        else:
            save_week(root, {**found, 'shared': 'anonymous'})
            state.append_event('telemetry.shared', {'week': week, 'mode': 'anonymous'}, root)


def _otlp(root, config):
    """Every sweep: post the spans since the saved mark and each of the newest final weeks not yet posted."""
    import os
    from wuwei import env, registry, state, watch, workspace
    otlp = config['telemetry']['otlp']
    env.load(root)
    raw = os.environ.get(otlp['headers_env'], '') if otlp['headers_env'] else ''
    headers = dict(pair.split('=', 1) for pair in raw.split(',') if '=' in pair)
    base, service = otlp['endpoint'].rstrip('/'), registry.watch_service()

    def post(path, body, week=None):
        try:
            status = service.post(base + path, body, headers)
            reason = None if _ok(status) else f'HTTP {status}'
        except (OSError, ValueError) as exc:
            reason = type(exc).__name__
        if reason:
            state.append_event('telemetry.unsent', {**({'week': week} if week else {}), 'mode': 'otlp',
                                                    'reason': reason}, root)
        return reason is None
    saved = watch.saved(root)
    mark = saved.get('otlp_at') or watch.previous(root).get('otlp_at')
    body, new = spans(root, config, mark)
    # Nothing to send keeps the mark, so the save's own event does not trigger another save next sweep.
    if not body['resourceSpans'][0]['scopeSpans'][0]['spans']:
        new = mark
    elif not post('/v1/traces', body):
        new = None
    if new is not None and saved.get('otlp_at') != new:
        watch.save(root, {'otlp_at': new})
    finals = [found for found in (load_week(root, week) for week in weeks(root)) if found.get('final')][:WEEKS]
    for found in finals:
        if not found.get('otlp') and post('/v1/metrics', otlp_metrics(found, workspace.now()), found['week']):
            save_week(root, {**found, 'otlp': True})


def step(root, config):
    """The watch sweep's telemetry step: the aggregate at most once a day, the OTLP export every sweep."""
    if not config['telemetry']['enabled']:
        return 'off'
    status = _daily(root, config)
    if config['telemetry']['otlp']['endpoint']:
        _otlp(root, config)
    return status


def _daily(root, config):
    from wuwei import obligations, watch, workspace
    saved, now = watch.saved(root), workspace.now()
    prior = saved.get('telemetry_at')
    if prior is not None and (now - obligations._time(prior)).total_seconds() < 86400:
        return 'not due'
    start, current = time.monotonic(), current_week(root)
    try:
        days = read_days(root, start)
        earlier = sorted({week_of(name) for name in days if week_of(name) < current}, reverse=True)[:WEEKS]
        due = [current] + [week for week in earlier if not (load_week(root, week) or {}).get('final')]
        found = [week_file(root, config, week, days, start=start, write=False) for week in due]
        if time.monotonic() - start > BUDGET_SECONDS:
            raise Skipped('time', workspace.day_dir(root).name)
    except Skipped as skipped:
        watch.save(root, {'telemetry_at': now.isoformat(), 'telemetry': {'week': skipped.week, 'skipped': skipped.reason}},
                   kind='telemetry.skipped', payload={'week': skipped.week, 'reason': skipped.reason})
        return f'skipped: {skipped.reason}'
    for week in found:
        save_week(root, week)
    _share(root, config)
    watch.save(root, {'telemetry_at': now.isoformat(), 'telemetry': {'week': current}})
    return current
