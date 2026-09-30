"""Read discovery sources through ports and decide intraday eligibility."""

from fnmatch import fnmatchcase
import re

from wuwei import registry, state, workspace


SOURCES = ('tracker', 'base_checks', 'review_bot', 'scanner', 'follow_up_threads',
           'metric_regressions', 'pr_follow_ups')


def dedupe(sources, *, tracker_ids=(), day_ids=()):
    """Keep first occurrence by stable id and preserve unavailable measurements."""
    seen = set(tracker_ids) | set(day_ids)
    candidates = []
    measured = {}
    for name in SOURCES:
        rows = sources.get(name)
        if isinstance(rows, str):
            measured[name] = rows
            continue
        if rows is None:
            measured[name] = 'unmeasured: source unavailable'
            continue
        if not isinstance(rows, list):
            raise ValueError(f'{name}: expected candidate list')
        measured[name] = f'measured: {len(rows)}'
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise ValueError(f'{name}: candidate id required')
            if row['id'] not in seen:
                candidates.append({**row, 'source': name})
                seen.add(row['id'])
    return {'sources': measured, 'candidates': candidates}


def start_decision(item, config, confirmed_goals, *, within_budget, above_cut):
    """Return start or owner; dispatch is the planner's responsibility."""
    mode = config['discovery']['autostart']
    if mode not in ('off', 'strict', 'goal'):
        raise ValueError('invalid discovery.autostart')
    paths = item.get('paths')
    flags = item.get('flags')
    if paths is None or flags is None:
        return 'owner'
    if not isinstance(flags, dict) or any(type(value) is not bool for value in flags.values()):
        raise ValueError('invalid candidate risk flags')
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise ValueError('invalid candidate paths')
    never_auto = [pattern for repo in config['repos'] for pattern in repo['merge']['never_auto_paths']]
    if (item.get('goal') not in confirmed_goals or
            any(flags.values()) or not within_budget or
            any(fnmatchcase('/'.join(path.split('/')[i:]), pattern)
                for path in paths for i in range(len(path.split('/'))) for pattern in never_auto)):
        return 'owner'
    if item.get('track') not in ('SLICE', 'FULL'):
        raise ValueError('invalid candidate track')
    if mode == 'off':
        return 'tomorrow'
    if item.get('track') != 'SLICE' or mode == 'strict' and not above_cut:
        return 'owner'
    return 'start'


def discover(root=None, *, ports=None):
    """Measure available sources; missing ports remain unmeasured."""
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    day = state.read_state(root)
    ports = {} if ports is None else ports
    sources = {name: 'not applicable: no open PRs' for name in SOURCES}
    sources.update(tracker='not configured: tracker adapter',
                   metric_regressions='not implemented: metric regression source',
                   scanner=('not configured: scanner adapter' if config['adapters']['scanner'] == 'none'
                            else 'not applicable: no repositories'))
    if config['adapters']['tracker'] != 'none':
        sources['tracker'] = 'unmeasured: tracker backlog read failed'
        tracker = ports.get('tracker') or registry.load('tracker', config)
        result = tracker.backlog(config['tracker']['backlog_filter'], root=root)
        if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
            sources['tracker'] = 'unmeasured: invalid tracker backlog result'
        elif result.exit:
            sources['tracker'] = 'unmeasured: ' + (result.reason or 'tracker backlog unmeasured')
        elif isinstance(result.data, list):
            sources['tracker'] = result.data
        else:
            sources['tracker'] = 'unmeasured: invalid tracker backlog data'
    refs = day.get('raised_prs', []) + day.get('claimed_prs', [])
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        raise ValueError('invalid day PR references')
    if refs:
        if config['adapters']['review_bot'] == 'none':
            sources['review_bot'] = 'not configured: review bot adapter'
        if config['adapters']['code_host'] == 'none':
            for name in ('base_checks', 'follow_up_threads', 'pr_follow_ups'):
                sources[name] = 'not configured: code host adapter'
        if config['adapters']['review_bot'] != 'none':
            sources['review_bot'] = 'unmeasured: review bot read failed'
            bot = ports.get('review_bot') or registry.load('review_bot', config)
            findings = []
            complete = True
            for ref in sorted(set(refs)):
                result = bot.open_findings(ref, root=root)
                if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
                    raise ValueError('invalid review-bot result')
                if result.exit == 2:
                    complete = False
                    continue
                if not isinstance(result.data, list):
                    raise ValueError('invalid review-bot findings')
                for row in result.data:
                    if not isinstance(row, dict) or 'id' not in row or not isinstance(row.get('body'), str):
                        raise ValueError('invalid review-bot finding')
                    findings.append({'id': f'{ref}:bot:{row["id"]}', 'evidence': row['body']})
            if complete:
                sources['review_bot'] = findings
        if config['adapters']['code_host'] != 'none':
            for name in ('base_checks', 'follow_up_threads', 'pr_follow_ups'):
                sources[name] = 'unmeasured: code host read failed'
            host = ports.get('code_host') or registry.load('code_host', config)
            followups = []
            pr_followups = []
            complete = True
            comments_complete = True
            for ref in sorted(set(refs)):
                result = host.threads(ref, root=root)
                if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
                    raise ValueError('invalid code-host result')
                if result.exit == 2:
                    complete = False
                    continue
                data = result.data
                if not isinstance(data, dict) or not isinstance(data.get('threads'), list):
                    raise ValueError('invalid follow-up threads')
                if not isinstance(data.get('comments'), list):
                    comments_complete = False
                else:
                    for comment in data['comments']:
                        if (not isinstance(comment, dict) or type(comment.get('id')) is not int
                                or not isinstance(comment.get('body'), str)):
                            raise ValueError('invalid PR follow-up comment')
                        if re.search(r'follow[ -]?up', comment['body'], re.I):
                            pr_followups.append({'id': f'{ref}:followup:{comment["id"]}',
                                                 'evidence': comment['body']})
                for row in data['threads']:
                    if not isinstance(row, dict) or type(row.get('resolved')) is not bool or not isinstance(row.get('id'), str):
                        raise ValueError('invalid follow-up thread')
                    if not row['resolved']:
                        followups.append({'id': f'{ref}:thread:{row["id"]}', 'evidence': 'open review thread'})
            if complete:
                sources['follow_up_threads'] = followups
                if comments_complete:
                    sources['pr_follow_ups'] = pr_followups
            if hasattr(host, 'pr') and hasattr(host, 'checks'):
                red = []
                complete = True
                for ref in sorted(set(refs)):
                    pr = host.pr(ref, root=root)
                    if not isinstance(pr, registry.Result) or pr.exit not in (0, 1, 2):
                        raise ValueError('invalid PR result')
                    if pr.exit == 2:
                        complete = False
                        continue
                    if not isinstance(pr.data, dict) or not isinstance(pr.data.get('base_sha'), str):
                        raise ValueError('invalid base SHA')
                    checks = host.checks(ref, pr.data['base_sha'], root=root)
                    if not isinstance(checks, registry.Result) or checks.exit not in (0, 1, 2):
                        raise ValueError('invalid base-check result')
                    if checks.exit == 2:
                        complete = False
                        continue
                    if not isinstance(checks.data, list):
                        raise ValueError('invalid base checks')
                    for check in checks.data:
                        if (not isinstance(check, dict) or not isinstance(check.get('name'), str)
                                or not isinstance(check.get('conclusion'), (str, type(None)))):
                            raise ValueError('invalid base check')
                        if check['conclusion'] in ('failure', 'timed_out', 'action_required'):
                            red.append({'id': f'{ref}:base:{check["name"]}',
                                        'evidence': check.get('url') or 'red base check'})
                if complete:
                    sources['base_checks'] = red
    if config['repos'] and config['adapters']['scanner'] != 'none':
        sources['scanner'] = 'unmeasured: scanner read failed'
        scanner = ports.get('scanner') or registry.load('scanner', config)
        found = []
        complete = True
        for repo in config['repos']:
            result = scanner.audit(str((root / repo['path']).resolve()), root=root)
            if result.exit == 2:
                complete = False
                break
            if not isinstance(result.data, list):
                raise ValueError('invalid scanner findings')
            found.extend(result.data)
        if complete:
            sources['scanner'] = found
    return dedupe(sources, day_ids=day['items'])


def when_seat_frees(root=None, *, queue_size):
    root = workspace.find_workspace(root)
    if queue_size < workspace.load_config(root)['discovery']['min_queue']:
        return discover(root)
    return None


def intake(root=None, *, trigger, found=None):
    """Persist discovery evidence, then apply the same gate as plan add."""
    if trigger not in ('sweep', 'seat-free'):
        raise ValueError('unknown discovery trigger')
    root = workspace.find_workspace(root)
    found = discover(root) if found is None else found
    if not isinstance(found, dict) or not isinstance(found.get('candidates'), list):
        raise ValueError('invalid discovery result')
    candidates = {}
    for row in found['candidates']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            raise ValueError('invalid discovery candidate')
        candidates[row['id']] = row

    def save(data):
        data.setdefault('discovery_candidates', {}).update(candidates)
    state._write_state(save, root, reserved=False, kind='discovery.intake',
                       payload={'trigger': trigger, 'items': sorted(candidates)})
    result = {'started': [], 'owner': [], 'tomorrow': []}
    day = state.read_state(root)
    if not day['gate_approved']:
        return result
    from wuwei import plan
    from wuwei.steward import SAFE_ID
    for item in candidates:
        if (item in day['items'] or item in day.get('intraday_proposals', {})
                or not SAFE_ID.fullmatch(item)):
            continue
        try:
            action = plan.add(item, root)['action']
        except ValueError as exc:
            def propose(data):
                data.setdefault('intraday_proposals', {})[item] = {
                    'decision': 'owner', 'candidate': candidates[item], 'reason': str(exc)}
            state._write_state(propose, root, reserved=False, kind='plan.proposed',
                               payload={'item': item, 'decision': 'owner', 'reason': str(exc)})
            action = 'owner'
        if action == 'build next':
            from wuwei.commands import build
            try:
                build.next_action(item, root=root)
            except ValueError as exc:
                if str(exc) != 'no logged builder brief for item':
                    raise
                state.append_event('build.requested', {'item': item}, root)
        result['started' if action == 'build next' else action].append(item)
    return result
