"""Process measurements from recorded day state, events and traces."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, time
import json
from pathlib import Path
import re
from statistics import mean, median

from wuwei import registry, sessions, state, watch, workspace
from wuwei.exits import DAMAGED, SYMLINK, ADAPTER_DATA


UNMEASURED = 'unmeasured'
HOURS = ((5, 'morning'), (11, 'midday'), (14, 'afternoon'), (18, 'evening'))
AGES = ('0-49 turns', '50-199 turns', '200+ turns', 'compacted', 'no planner')
COUNTERS = ('gates', 'fix_verdicts', 'fix_rounds', 'lint_rejections', 'interventions')


def _percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)


def _baseline(root):
    path = root / '.wuwei/memory/notes/baseline.md'
    labels = {'escaped_defects': 'Escaped-defect-rate', 'review_rework': 'Review-rework',
              'owner_intervention': 'Owner-intervention', 'lead_time': 'Lead-time'}
    if path.is_symlink():
        raise ValueError(f'baseline must not be a symlink; {SYMLINK}')
    if not path.exists():
        return {key: UNMEASURED for key in labels}
    content = path.read_text(encoding='utf-8')
    result = {}
    for key, label in labels.items():
        matches = re.findall(r'^' + re.escape(label) + r':[ \t]*([^\n]*)$', content, re.M)
        if len(matches) > 1:
            raise ValueError(f'duplicate {label} baseline; {DAMAGED}')
        result[key] = matches[0].strip() if matches and matches[0].strip() else UNMEASURED
    if result['escaped_defects'] != UNMEASURED:
        from wuwei import merge
        merge.baseline(root)
    return result


def _human_times(root, config):
    location = Path(config['metrics']['transcripts']).expanduser()
    directory = location if location.is_absolute() else root / location
    if not directory.exists():
        return []
    allowed = [root.resolve(), *((root / repo['path']).expanduser().resolve()
                                  for repo in config['repos'])]
    turns = []
    if config['metrics']['transcripts'] == '~/.claude/projects':
        slugs = [re.sub(r'[^A-Za-z0-9-]', '-', str(base)) for base in allowed]
        folders = [child for child in directory.iterdir() if child.is_dir() and
                   any(child.name == slug or child.name.startswith(slug + '-') for slug in slugs)]
    else:
        folders = [directory]
    for path in (path for folder in folders for path in folder.rglob('*.jsonl')):
        if path.is_symlink():
            raise ValueError(f'transcript symlink; {SYMLINK}')
        try:
            with path.open(encoding='utf-8') as source:
                cwd = None
                for line in source:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError(f'invalid transcript record; {ADAPTER_DATA}')
                    cwd = row.get('cwd', cwd)
                    if row.get('type') != 'user' or row.get('isSidechain') or row.get('isMeta'):
                        continue
                    message = row.get('message')
                    if not isinstance(message, dict) or message.get('role') != 'user':
                        continue
                    blocks = message.get('content')
                    if isinstance(blocks, str):
                        prefixes = [blocks[:80]]
                    elif isinstance(blocks, list):
                        if any(not isinstance(block, dict) or block.get('type') != 'text'
                               for block in blocks):
                            continue
                        prefixes = [str(block.get('text', ''))[:80] for block in blocks]
                    else:
                        continue
                    if not prefixes or any(prefix.lstrip().startswith((
                            '<system-reminder>', '<local-command-caveat>', '<command-name>',
                            'This session is being continued')) for prefix in prefixes):
                        continue
                    if not isinstance(cwd, str) or not any(Path(cwd).resolve().is_relative_to(base)
                                                            for base in allowed):
                        continue
                    turns.append(datetime.fromisoformat(row['timestamp']))
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            # Transcript errors must never echo message bodies or session filenames.
            raise ValueError(f'transcript unreadable or invalid; {ADAPTER_DATA}') from None
    if any(at.tzinfo is None for at in turns):
        raise ValueError(f'transcript timestamp needs timezone; {ADAPTER_DATA}')
    return sorted(set(turns))


def _attended(turns, cut, now):
    if not turns:
        return UNMEASURED
    stretches = []
    start = last = turns[0]
    for at in turns[1:]:
        if at - last >= timedelta(minutes=cut):
            stretches.append((start - timedelta(minutes=cut / 2), last))
            start = at
        last = at
    stretches.append((start - timedelta(minutes=cut / 2), last))
    per_day = {}
    day = turns[0].date()
    while day < now.date() and day <= turns[-1].date():
        if day.weekday() < 5:
            begin = datetime.combine(day, time.min, tzinfo=now.tzinfo)
            end = begin + timedelta(days=1)
            per_day[day.isoformat()] = sum(max(0, (min(stop, end) - max(begin, start)).total_seconds())
                                                for start, stop in stretches) / 60
        day += timedelta(days=1)
    return per_day


def _owner_intervention(turns, now):
    headline = _attended(turns, 10, now)
    if headline == UNMEASURED or not headline:
        return UNMEASURED
    values = list(headline.values())
    return {'median_minutes': median(values), 'p25_minutes': _percentile(values, .25),
            'p75_minutes': _percentile(values, .75), 'per_weekday_minutes': headline,
            'sensitivity_minutes': {str(cut): median(_attended(turns, cut, now).values())
                                    for cut in (5, 15)}}


def _hour_band(at):
    return next((name for start, name in reversed(HOURS) if at.hour >= start), 'evening')


def _age_band(row):
    if row is None:
        return 'no planner'
    if row.get('compactions'):
        return 'compacted'
    turns = row.get('turns', 0)
    return AGES[0] if turns < 50 else AGES[1] if turns < 200 else AGES[2]


def _bands(days, turns, zone):
    """Quality counters per owner hour band and per planner session-age band."""
    table = {'hour': {name: dict.fromkeys(COUNTERS, 0) for _, name in HOURS},
             'session_age': {name: dict.fromkeys(COUNTERS, 0) for name in AGES}}
    seen = set()
    for name, events in days:
        # The registry is day state, so session ages restart every day.
        ages, planner = {}, None
        owner = [{'kind': 'owner.turn', 'ts': at.isoformat(), 'payload': {}} for at in turns
                 if at.astimezone(zone).date().isoformat() == name]
        for row in sorted([*events, *owner], key=lambda row: datetime.fromisoformat(row['ts'])):
            kind, payload = row['kind'], row['payload']
            if kind == 'plan.session':
                planner = payload.get('session_id')
                continue
            if kind == 'session.seen':
                sessions.count(ages.setdefault(payload.get('session_id'), {}), payload.get('hook'))
                continue
            hits = {'gates': kind == 'gate.received',
                    'fix_verdicts': kind == 'gate.received' and payload.get('verdict') == 'FIX',
                    'fix_rounds': sum(phase == 'fix' for phase in payload.get('phase_changes', {}).values()),
                    'interventions': kind == 'owner.turn', 'lint_rejections': False}
            if kind == 'verdict.rejected':
                key = (str(payload.get('file')), payload.get('sha256'))
                hits['lint_rejections'] = key not in seen
                seen.add(key)
            at = datetime.fromisoformat(row['ts']).astimezone(zone)
            for cell in (table['hour'][_hour_band(at)],
                         table['session_age'][_age_band(ages.get(planner, {}) if planner else None)]):
                for key, value in hits.items():
                    cell[key] += value
    for cell in (cell for cells in table.values() for cell in cells.values()):
        cell['fix_rate'] = cell['fix_verdicts'] / cell['gates'] if cell['gates'] else UNMEASURED
        if not turns:
            cell['interventions'] = UNMEASURED
    return table


def bands(root, days):
    """Quality by band over several day directories (the retro window)."""
    config = workspace.load_config(root)
    return _bands([(day.name, _events(day) or []) for day in days], _human_times(root, config),
                  workspace.zone(config))


def worst(table, margin):
    """(band, FIX rate, highest other rate) when one measured band beats all others by margin."""
    rates = sorted(((cell['fix_rate'], band) for band, cell in table.items() if cell['gates']),
                   reverse=True)
    if len(rates) < 2 or rates[0][0] - rates[1][0] < margin:
        return None
    return rates[0][1], rates[0][0], rates[1][0]


def band_lines(title, table):
    """A markdown table of one band dimension, for report and retro."""
    if table == UNMEASURED:
        return [f'{title}: unmeasured']
    rate = lambda value: value if value == UNMEASURED else f'{value:.2f}'
    return [f'| {title} | Gates | FIX rate | Fix rounds | Lint rejections | Interventions |',
            '| --- | ---: | ---: | ---: | ---: | ---: |',
            *(f'| {band} | {cell["gates"]} | {rate(cell["fix_rate"])} | {cell["fix_rounds"]} | '
              f'{cell["lint_rejections"]} | {cell["interventions"]} |' for band, cell in table.items())]


def _references(root):
    refs, items = set(), {}
    for directory in watch.days(root):
        data = _state(directory)
        if data is None:
            continue
        refs.update(data.get('raised_prs', []))
        refs.update(data.get('claimed_prs', []))
        refs.update(data.get('merges', {}))
        for item, record in data.get('items', {}).items():
            if isinstance(record.get('pr'), str):
                refs.add(record['pr'])
                items.setdefault(item, set()).add(record['pr'])
    return sorted(refs), items


def _port(operation, *args, root):
    result = operation(*args, root=root)
    if result.exit != 0 or isinstance(result.data, dict) and (
            'message' in result.data or 'errors' in result.data):
        raise ValueError(f'outcome evidence unavailable from adapter; {ADAPTER_DATA}')
    return result.data


def _host_prs(root, config, refs):
    if not refs or config['adapters']['code_host'] == 'none':
        return {}
    host = registry.load('code_host', config)
    return {ref: _port(host.pr, ref, root=root) for ref in refs}


def _escaped_defects(root, config, now, refs, prs):
    from wuwei import merge
    observed, journals = [], {}
    for directory in watch.days(root):
        data = _state(directory)
        if data is not None:
            journals.update(data.get('merges', {}))
    if config['adapters']['code_host'] == 'none' and any(ref not in journals for ref in refs):
        return UNMEASURED
    for ref in refs:
        entry = journals.get(ref)
        if entry is not None:
            if entry.get('status') != 'merged' or not entry.get('merged_at'):
                continue
            at = datetime.fromisoformat(entry['merged_at'])
        else:
            pr = prs.get(ref)
            if not pr or not pr.get('merged'):
                continue
            at = datetime.fromisoformat(pr['merged_at'])
        if at.tzinfo is None:
            raise ValueError(f'merge timestamp needs timezone; {ADAPTER_DATA}')
        if now - at < timedelta(days=14):
            continue
        if entry is not None:
            outcome = entry.get('outcome')
        else:
            repo = next((repo for repo in config['repos'] if ref.startswith(repo['name'] + '#')), None)
            if repo is None:
                return UNMEASURED
            host = registry.load('code_host', config)
            pr = prs[ref]
            files = _port(host.files, ref, root=root)
            history = _port(host.history, repo['name'], pr['merge_commit'], pr['base'], True, root=root)
            outcome = merge.outcome({'merged_at': pr['merged_at'],
                                     'merge_commit': pr['merge_commit'],
                                     'evidence': {'files': files}}, history['commits'], repo['merge'])
        if not isinstance(outcome, dict):
            return UNMEASURED
        if type(outcome.get('escaped')) is not bool or not all(
                isinstance(outcome.get(key), list) for key in ('reverts', 'fixes')):
            raise ValueError(f'invalid merge outcome; {DAMAGED}')
        observed.append({**outcome, 'reverts': [revert for revert in outcome['reverts']
                                                 if datetime.fromisoformat(revert['at']) <= at + timedelta(days=14)]})
    if not observed:
        return UNMEASURED
    reverts = sum(len(row['reverts']) for row in observed)
    fixes = sum(len(row['fixes']) for row in observed)
    return {'rate': sum(row['escaped'] for row in observed) / len(observed),
            'prs': len(observed), 'raw_count': reverts + fixes,
            'reverts': reverts, 'fixes': fixes}


def _review_rework(root, config, refs, prs):
    if not refs or config['adapters']['code_host'] == 'none':
        return UNMEASURED
    host = registry.load('code_host', config)
    counts = []
    for ref in refs:
        pr = prs[ref]
        if not pr.get('merged'):
            continue
        threads = _port(host.threads, ref, root=root)['threads']
        commits = _port(host.commits, ref, root=root)
        committed = [datetime.fromisoformat(row['at']) for row in commits]
        count = 0
        for thread in threads:
            comments = thread['comments']
            if not comments:
                raise ValueError(f'empty review thread; {ADAPTER_DATA}')
            first = comments[0]
            if first['is_bot'] or first['author'] == pr['author']:
                continue
            at = datetime.fromisoformat(first['created_at'])
            count += any(at < commit <= datetime.fromisoformat(pr['merged_at'])
                         for commit in committed)
        counts.append(count)
    if not counts:
        return UNMEASURED
    return {'mean_per_pr': mean(counts), 'median_per_pr': median(counts),
            'p90_per_pr': _percentile(counts, .9),
            'share_with_rework': sum(bool(count) for count in counts) / len(counts)}


def _lead_time(root, config, items, prs):
    if config['adapters']['tracker'] == 'none' or not items:
        return UNMEASURED
    tracker = registry.load('tracker', config)
    leads, created, opened = [], [], []
    for item, refs in items.items():
        merged = [prs[ref] for ref in refs if prs[ref].get('merged')]
        if not merged:
            continue
        pr = min(merged, key=lambda row: row['merged_at'])
        at = datetime.fromisoformat(pr['merged_at'])
        history = _port(tracker.history, item, root=root)
        starts = [datetime.fromisoformat(row['createdAt']) for row in history
                  if (row.get('toState') or {}).get('name') == 'In Progress']
        if not starts:
            return UNMEASURED
        start = min(starts)
        if at < start:
            raise ValueError(f'merge predates In Progress; {ADAPTER_DATA}')
        leads.append((at - start).total_seconds() / 3600)
        creation = datetime.fromisoformat(_port(tracker.created, item, root=root))
        opened_at = datetime.fromisoformat(pr['created_at'])
        if at < creation or at < opened_at:
            raise ValueError(f'merge predates creation; {ADAPTER_DATA}')
        created.append((at - creation).total_seconds() / 3600)
        opened.append((at - opened_at).total_seconds() / 3600)
    if not leads:
        return UNMEASURED
    return {'median_hours': median(leads), 'p75_hours': _percentile(leads, .75),
            'p90_hours': _percentile(leads, .9),
            'creation_to_merge_hours': median(created),
            'pr_open_to_merge_hours': median(opened)}


def _escaped_by_tier(root):
    """Merged items per computed tier, and how many a later builder brief names."""
    merged, briefs = {}, []
    for directory in watch.days(root):
        data = _state(directory)
        for name, row in (data['items'] if data else {}).items():
            if row['phase'] == 'merged' and row['gates']:
                merged.setdefault(name, row['gates']['computed'])
        briefs += [row['payload'] for row in _events(directory) or []
                   if row['kind'] == 'brief written' and row['payload'].get('role') == 'builder']
    if not merged:
        return UNMEASURED
    escaped = set()
    for payload in briefs:
        path = root / payload['path']
        # ponytail: an archived or missing brief is not read; its fix goes uncounted.
        if payload.get('item') not in merged or not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        escaped |= {name for name in merged if name != payload['item']
                    and re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', text)}
    result = {}
    for name, computed in merged.items():
        row = result.setdefault(computed, {'merged': 0, 'escaped': 0})
        row['merged'] += 1
        row['escaped'] += name in escaped
    return result


def _events(day):
    path = day / 'events.jsonl'
    if not path.exists():
        return None
    try:
        return watch.records(path)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise ValueError(f'events.jsonl: {exc}') from exc


def _state(day):
    return state.read_state(directory=day) if (day / 'state.json').exists() else None


def _traces(day):
    path = day / 'traces.jsonl'
    if not path.exists():
        return None
    rows = []
    raw = path.read_text(encoding='utf-8')
    if raw and not raw.endswith('\n'):
        raise ValueError(f'incomplete trace line; {DAMAGED}')
    for line in raw.splitlines():
        row = json.loads(line)
        spans = row['resourceSpans']
        if not isinstance(spans, list):
            raise ValueError(f'invalid trace spans; {DAMAGED}')
        rows.append(row)
    return rows


def _phase_time(events, now):
    entered, elapsed = {}, defaultdict(lambda: defaultdict(float))
    for event in events:
        at = datetime.fromisoformat(event['ts'])
        if event['kind'] in ('plan.approved', 'state.import'):
            planned = event['payload'].get('items', [])
            if not isinstance(planned, list):
                raise ValueError(f'invalid planned items; {DAMAGED}')
            if event['kind'] == 'state.import':
                approved = event['payload'].get('approved_items', [])
                if not isinstance(approved, list):
                    raise ValueError(f'invalid approved items; {DAMAGED}')
                planned += approved
            if any(not isinstance(item, str) for item in planned):
                raise ValueError(f'invalid planned items; {DAMAGED}')
            for item in planned:
                entered.setdefault(item, ('planned', at))
        changes = event['payload'].get('phase_changes', {})
        if not isinstance(changes, dict):
            raise ValueError(f'invalid phase changes; {DAMAGED}')
        for item, phase in changes.items():
            if not isinstance(item, str) or not isinstance(phase, str):
                raise ValueError(f'invalid phase change; {DAMAGED}')
            if item in entered:
                old_phase, start = entered[item]
                seconds = (at - start).total_seconds()
                if seconds < 0:
                    raise ValueError(f'phase timestamps out of order; {DAMAGED}')
                elapsed[item][old_phase] += seconds
            entered[item] = (phase, at)
    for item, (phase, start) in entered.items():
        seconds = (now - start).total_seconds()
        if seconds < 0:
            raise ValueError(f'phase timestamp in the future; {DAMAGED}')
        elapsed[item][phase] += seconds
    return {item: dict(phases) for item, phases in elapsed.items()}


def _costs(events, key):
    totals = defaultdict(float)
    seen = False
    for row in events:
        if row['kind'] != 'seat.usage':
            continue
        payload = row['payload']
        usage = payload.get('usage')
        if not isinstance(usage, dict):
            raise ValueError(f'invalid seat usage; {DAMAGED}')
        cost = usage.get('cost')
        if cost is None or cost == UNMEASURED:
            continue
        if type(cost) not in (int, float) or cost < 0:
            raise ValueError(f'invalid seat cost; {DAMAGED}')
        target = payload.get(key)
        if not isinstance(target, str) or not target:
            raise ValueError(f'missing usage {key}; {ADAPTER_DATA}')
        totals[target] += cost
        seen = True
    return dict(totals) if seen else UNMEASURED


def _calibration(day, data, elapsed):
    path = day / 'proposal.json'
    if not path.exists() or data is None or elapsed == UNMEASURED:
        return UNMEASURED
    proposal = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(proposal, dict) or not isinstance(proposal.get('candidates'), list):
        raise ValueError(f'invalid proposal for size calibration; {DAMAGED}')
    sizes = {row['id']: row.get('score', {}).get('job_size') for row in proposal['candidates']}
    return {item: {'predicted_size': sizes[item],
                   'actual_cycle_seconds': sum(phases.values())}
            for item, phases in elapsed.items() if item in sizes and sizes[item] is not None}


def collect(root=None, *, day=None):
    """Return named measurements; missing evidence never becomes a zero."""
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    directory = workspace.day_dir(root) if day is None else Path(day)
    events, data = _events(directory), _state(directory)
    from wuwei import drafts, outward
    voice, ai_tells = defaultdict(list), {}
    for row in drafts.read(data if data is not None else {}).values():
        if row['status'] == 'sent':
            voice[row['audience']].append(row)
        if isinstance(row.get('style'), list):
            ai_tells[row['id']] = len(row['style'])
    for path in sorted((directory / 'decisions').glob('D-*.md')):
        if not path.is_symlink():
            ai_tells[path.stem] = len(outward.tells(path.read_text(encoding='utf-8')))
    for index, row in enumerate(events or []):  # drafts count from their rows
        if row['kind'] == 'outward.ai_tells' and row['payload'].get('draft') is False:
            ai_tells[f'outward-{index}'] = len(row['payload']['tells'])
    traces = _traces(directory)
    now = workspace.now()
    if events is None:
        event_metrics = {name: UNMEASURED for name in (
            'fix_rounds_per_item', 'handbacks_per_pr', 'time_in_phase_seconds',
            'verdict_lint_rejections', 'decisions_per_day', 'decisions_by_reversibility',
            'owner_decisions_per_day',
            'build_loop_iterations_per_item', 'stuck_parks_per_item', 'cost_per_item',
            'cost_per_role', 'cost_per_day', 'seat_decisions_owner_reversed')}
    else:
        count = lambda kind: sum(row['kind'] == kind for row in events)
        fix = Counter(item for row in events for item, phase in
                      row['payload'].get('phase_changes', {}).items() if phase == 'fix')
        # ponytail: reply acknowledgements proxy review handbacks until PR cycle events exist.
        handbacks = Counter(row['payload']['pr'] for row in events
                            if row['kind'] == 'reply: acknowledged' and 'pr' in row['payload'])
        decisions = {row['payload'].get('id'): row['payload'] for row in events
                     if row['kind'] in ('decision.decided', 'decision.routed')}
        reversibility = Counter(row.get('reversibility', 'unknown')
                                for row in decisions.values())
        iterations = Counter(row['payload']['item'] for row in events
                             if row['kind'] == 'seat.usage' and 'item' in row['payload'])
        parks = Counter(row['payload']['item'] for row in events
                        if row['kind'] == 'build.parked' and 'item' in row['payload'])
        item_cost = _costs(events, 'item')
        event_metrics = {
            'fix_rounds_per_item': dict(fix), 'handbacks_per_pr': dict(handbacks),
            'time_in_phase_seconds': _phase_time(events, now),
            # One rejection per file version: a hook, a dispatch and a lint of the same content count once.
            'verdict_lint_rejections': len({(str(row['payload'].get('file')), row['payload'].get('sha256'))
                                            for row in events if row['kind'] == 'verdict.rejected'}),
            'decisions_per_day': len(decisions),
            'owner_decisions_per_day': count('decision.routed'),
            'decisions_by_reversibility': dict(reversibility),
            'build_loop_iterations_per_item': dict(iterations),
            'stuck_parks_per_item': dict(parks), 'cost_per_item': item_cost,
            'cost_per_role': _costs(events, 'role'),
            'cost_per_day': {directory.name: sum(item_cost.values())} if isinstance(item_cost, dict) else UNMEASURED,
            'seat_decisions_owner_reversed': (count('decision.reversed')
                                              if any(row['kind'] in ('decision.decided', 'build.parked')
                                                     for row in events) else UNMEASURED),
        }
    if data is None or not data['items']:
        event_metrics['share_unplanned_work'] = UNMEASURED
    else:
        event_metrics['share_unplanned_work'] = sum(
            item.get('goal') == 'unplanned' for item in data['items'].values()) / len(data['items'])
    if data is None:
        event_metrics['asks_per_item'] = event_metrics['unnecessary_asks'] = UNMEASURED
    else:
        from wuwei import decision
        routes = data.get('decision_routes', {})
        named = decision.naming(directory, list(data['items']))
        event_metrics['asks_per_item'] = dict(Counter(
            item for identifier in routes for item in (named.get(identifier) or ['day'])))
        event_metrics['unnecessary_asks'] = sum(
            decision.answered(data, identifier) == route.get('recommendation')
            for identifier, route in routes.items())
    event_metrics['size_calibration'] = _calibration(directory, data, event_metrics['time_in_phase_seconds'])
    event_metrics['tool_calls'] = len(traces) if traces is not None else UNMEASURED
    event_metrics['baseline'] = _baseline(root)
    turns = _human_times(root, config)
    event_metrics['owner_intervention'] = _owner_intervention(turns, now)
    event_metrics['quality_by_band'] = (UNMEASURED if events is None else _bands(
        [(directory.name, events)], turns, workspace.zone(config)))
    refs, items = _references(root)
    prs = _host_prs(root, config, refs)
    event_metrics['escaped_defects'] = _escaped_defects(root, config, now, refs, prs)
    event_metrics['escaped_defects_per_tier'] = _escaped_by_tier(root)
    event_metrics['review_rework'] = _review_rework(root, config, refs, prs)
    event_metrics['lead_time'] = _lead_time(root, config, items, prs)
    event_metrics['brief_drill_score'] = (data.get('brief_drill', UNMEASURED)
                                          if data is not None else UNMEASURED)
    event_metrics['voice_drafts'] = {
        audience: {'sent': len(rows),
                   'share_sent_unedited': sum(row['sent_unedited'] for row in rows) / len(rows),
                   'edit_sizes': [row['edit_size'] for row in rows if not row['sent_unedited']]}
        for audience, rows in voice.items()} if voice else UNMEASURED
    event_metrics['ai_tells'] = ai_tells
    return event_metrics
