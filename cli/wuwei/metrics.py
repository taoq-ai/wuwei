"""Process measurements from recorded day state, events and traces."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, time
import json
from pathlib import Path
import re
from statistics import mean, median

from wuwei import registry, state, watch, workspace


UNMEASURED = 'unmeasured'


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
        raise ValueError('baseline must not be a symlink')
    if not path.exists():
        return {key: UNMEASURED for key in labels}
    content = path.read_text(encoding='utf-8')
    result = {}
    for key, label in labels.items():
        matches = re.findall(r'^' + re.escape(label) + r':[ \t]*([^\n]*)$', content, re.M)
        if len(matches) > 1:
            raise ValueError(f'duplicate {label} baseline')
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
            raise ValueError('transcript symlink')
        try:
            with path.open(encoding='utf-8') as source:
                cwd = None
                for line in source:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError('invalid transcript record')
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
            raise ValueError('transcript unreadable or invalid') from None
    if any(at.tzinfo is None for at in turns):
        raise ValueError('transcript timestamp needs timezone')
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


def _owner_intervention(root, config, now):
    turns = _human_times(root, config)
    headline = _attended(turns, 10, now)
    if headline == UNMEASURED or not headline:
        return UNMEASURED
    values = list(headline.values())
    return {'median_minutes': median(values), 'p25_minutes': _percentile(values, .25),
            'p75_minutes': _percentile(values, .75), 'per_weekday_minutes': headline,
            'sensitivity_minutes': {str(cut): median(_attended(turns, cut, now).values())
                                    for cut in (5, 15)}}


def _references(root):
    refs, items = set(), {}
    for directory in watch.days(root):
        data = _state(directory)
        if data is None:
            continue
        refs.update(data.get('raised_prs', []))
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
        raise ValueError('outcome evidence unavailable from adapter')
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
            raise ValueError('merge timestamp needs timezone')
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
            raise ValueError('invalid merge outcome')
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
                raise ValueError('empty review thread')
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
            raise ValueError('merge predates In Progress')
        leads.append((at - start).total_seconds() / 3600)
        creation = datetime.fromisoformat(_port(tracker.created, item, root=root))
        opened_at = datetime.fromisoformat(pr['created_at'])
        if at < creation or at < opened_at:
            raise ValueError('merge predates creation')
        created.append((at - creation).total_seconds() / 3600)
        opened.append((at - opened_at).total_seconds() / 3600)
    if not leads:
        return UNMEASURED
    return {'median_hours': median(leads), 'p75_hours': _percentile(leads, .75),
            'p90_hours': _percentile(leads, .9),
            'creation_to_merge_hours': median(created),
            'pr_open_to_merge_hours': median(opened)}


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
        raise ValueError('incomplete trace line')
    for line in raw.splitlines():
        row = json.loads(line)
        spans = row['resourceSpans']
        if not isinstance(spans, list):
            raise ValueError('invalid trace spans')
        rows.append(row)
    return rows


def _phase_time(events, now):
    entered, elapsed = {}, defaultdict(lambda: defaultdict(float))
    for event in events:
        at = datetime.fromisoformat(event['ts'])
        if event['kind'] in ('plan.approved', 'state.import'):
            planned = event['payload'].get('items', [])
            if not isinstance(planned, list):
                raise ValueError('invalid planned items')
            if event['kind'] == 'state.import':
                approved = event['payload'].get('approved_items', [])
                if not isinstance(approved, list):
                    raise ValueError('invalid approved items')
                planned += approved
            if any(not isinstance(item, str) for item in planned):
                raise ValueError('invalid planned items')
            for item in planned:
                entered.setdefault(item, ('planned', at))
        changes = event['payload'].get('phase_changes', {})
        if not isinstance(changes, dict):
            raise ValueError('invalid phase changes')
        for item, phase in changes.items():
            if not isinstance(item, str) or not isinstance(phase, str):
                raise ValueError('invalid phase change')
            if item in entered:
                old_phase, start = entered[item]
                seconds = (at - start).total_seconds()
                if seconds < 0:
                    raise ValueError('phase timestamps out of order')
                elapsed[item][old_phase] += seconds
            entered[item] = (phase, at)
    for item, (phase, start) in entered.items():
        seconds = (now - start).total_seconds()
        if seconds < 0:
            raise ValueError('phase timestamp in the future')
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
            raise ValueError('invalid seat usage')
        cost = usage.get('cost')
        if cost is None:
            continue
        if type(cost) not in (int, float) or cost < 0:
            raise ValueError('invalid seat cost')
        target = payload.get(key)
        if not isinstance(target, str) or not target:
            raise ValueError(f'missing usage {key}')
        totals[target] += cost
        seen = True
    return dict(totals) if seen else UNMEASURED


def _calibration(day, data, elapsed):
    path = day / 'proposal.json'
    if not path.exists() or data is None or elapsed == UNMEASURED:
        return UNMEASURED
    proposal = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(proposal, dict) or not isinstance(proposal.get('candidates'), list):
        raise ValueError('invalid proposal for size calibration')
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
            'verdict_lint_rejections': count('verdict.rejected'),
            'decisions_per_day': len(decisions),
            'owner_decisions_per_day': count('decision.routed'),
            'decisions_by_reversibility': dict(reversibility),
            'build_loop_iterations_per_item': dict(iterations),
            'stuck_parks_per_item': dict(parks), 'cost_per_item': item_cost,
            'cost_per_role': _costs(events, 'role'),
            'cost_per_day': {directory.name: sum(item_cost.values())} if isinstance(item_cost, dict) else UNMEASURED,
            'seat_decisions_owner_reversed': (count('decision.reversed')
                                              if any(row['kind'] == 'decision.reversed'
                                                     for row in events) else UNMEASURED),
        }
    if data is None or not data['items']:
        event_metrics['share_unplanned_work'] = UNMEASURED
    else:
        event_metrics['share_unplanned_work'] = sum(
            item.get('goal') == 'unplanned' for item in data['items'].values()) / len(data['items'])
    event_metrics['size_calibration'] = _calibration(directory, data, event_metrics['time_in_phase_seconds'])
    event_metrics['tool_calls'] = len(traces) if traces is not None else UNMEASURED
    event_metrics['baseline'] = _baseline(root)
    event_metrics['owner_intervention'] = _owner_intervention(root, config, now)
    refs, items = _references(root)
    prs = _host_prs(root, config, refs)
    event_metrics['escaped_defects'] = _escaped_defects(root, config, now, refs, prs)
    event_metrics['review_rework'] = _review_rework(root, config, refs, prs)
    event_metrics['lead_time'] = _lead_time(root, config, items, prs)
    return event_metrics
