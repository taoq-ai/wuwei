"""Read discovery sources through ports for the morning plan."""

import json
from pathlib import Path
import re
from time import monotonic

from wuwei import obligations, registry, state, workspace
from wuwei.exits import ADAPTER_DATA, DAMAGED


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
            raise ValueError(f'{name}: expected candidate list; {ADAPTER_DATA}')
        measured[name] = f'measured: {len(rows)}'
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise ValueError(f'{name}: candidate id required; {ADAPTER_DATA}')
            if row['id'] not in seen:
                candidates.append({**row, 'source': name})
                seen.add(row['id'])
    return {'sources': measured, 'candidates': candidates}


def _shaped(rows, config):
    """#862 F1: cached rows carry the scanner adapter's own finding shape, or are re-audited."""
    try:
        registry.load('scanner', config)._report({'files_analyzed': 1, 'findings': rows})
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def discover(root=None, *, ports=None, repo=None):
    """Measure available sources; missing ports remain unmeasured. Each candidate whose id
    names a configured repository carries it as repo; repo narrows to one (#601)."""
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    project = config['tracker']['project'] if config['adapters']['tracker'] == 'github' else ''
    names = list(dict.fromkeys(name for name in (*(row['name'] for row in config['repos']), project) if name))
    if repo is not None and repo not in names:
        raise ValueError(f'--repo {repo} is not a configured repository; pass one of: {", ".join(names)}')
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
        raise ValueError(f'invalid day PR references; {DAMAGED}')
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
                    raise ValueError(f'invalid review-bot result; {DAMAGED}')
                if result.exit == 2:
                    complete = False
                    continue
                if not isinstance(result.data, list):
                    raise ValueError(f'invalid review-bot findings; {DAMAGED}')
                for row in result.data:
                    if not isinstance(row, dict) or 'id' not in row or not isinstance(row.get('body'), str):
                        raise ValueError(f'invalid review-bot finding; {DAMAGED}')
                    findings.append({'id': f'{ref}:bot:{row["id"]}', 'evidence': row['body']})
            if complete:
                sources['review_bot'] = findings
        if config['adapters']['code_host'] != 'none':
            for name in ('base_checks', 'follow_up_threads', 'pr_follow_ups'):
                sources[name] = 'unmeasured: code host read failed'
            host = ports.get('code_host') or registry.load('code_host', config)
            try:
                me = obligations._owner_login(config)
            except ValueError:
                me = None  # answered needs one owner login; without it every open thread stays
            followups = []
            pr_followups = []
            complete = True
            comments_complete = True
            for ref in sorted(set(refs)):
                result = host.threads(ref, root=root)
                if not isinstance(result, registry.Result) or result.exit not in (0, 1, 2):
                    raise ValueError(f'invalid code-host result; {ADAPTER_DATA}')
                if result.exit == 2:
                    complete = False
                    continue
                data = result.data
                if not isinstance(data, dict) or not isinstance(data.get('threads'), list):
                    raise ValueError(f'invalid follow-up threads; {DAMAGED}')
                if not isinstance(data.get('comments'), list):
                    comments_complete = False
                else:
                    for comment in data['comments']:
                        if (not isinstance(comment, dict) or type(comment.get('id')) is not int
                                or not isinstance(comment.get('body'), str)):
                            raise ValueError(f'invalid PR follow-up comment; {DAMAGED}')
                        if re.search(r'follow[ -]?up', comment['body'], re.I):
                            pr_followups.append({'id': f'{ref}:followup:{comment["id"]}',
                                                 'evidence': comment['body']})
                for row in data['threads']:
                    if not isinstance(row, dict) or type(row.get('resolved')) is not bool or not isinstance(row.get('id'), str):
                        raise ValueError(f'invalid follow-up thread; {DAMAGED}')
                    try:
                        owner_answered = me is not None and obligations.answered(row, me)
                    except (KeyError, TypeError, AttributeError) as exc:
                        raise ValueError(f'invalid follow-up thread comment; {DAMAGED}') from exc
                    if not row['resolved'] and not owner_answered:
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
                        raise ValueError(f'invalid PR result; {DAMAGED}')
                    if pr.exit == 2:
                        complete = False
                        continue
                    if not isinstance(pr.data, dict) or not isinstance(pr.data.get('base_sha'), str):
                        raise ValueError(f'invalid base SHA; {DAMAGED}')
                    checks = host.checks(ref, pr.data['base_sha'], root=root)
                    if not isinstance(checks, registry.Result) or checks.exit not in (0, 1, 2):
                        raise ValueError(f'invalid base-check result; {ADAPTER_DATA}')
                    if checks.exit == 2:
                        complete = False
                        continue
                    if not isinstance(checks.data, list):
                        raise ValueError(f'invalid base checks; {DAMAGED}')
                    for check in checks.data:
                        if (not isinstance(check, dict) or not isinstance(check.get('name'), str)
                                or not isinstance(check.get('conclusion'), (str, type(None)))):
                            raise ValueError(f'invalid base check; {DAMAGED}')
                        if check['conclusion'] in ('failure', 'timed_out', 'action_required'):
                            red.append({'id': f'{ref}:base:{check["name"]}',
                                        'evidence': check.get('url') or 'red base check'})
                if complete:
                    sources['base_checks'] = red
    missing, capped = [], []
    if config['repos'] and config['adapters']['scanner'] != 'none':
        scanner = ports.get('scanner') or registry.load('scanner', config)
        vcs = ports.get('vcs') or registry.load('vcs', config)
        # S4 (#862): one audit per repo and HEAD per day; a slow failure (a timeout) is paid once.
        # ponytail: two discoveries at once may both audit; the last write wins.
        cache_path = workspace.day_dir(root) / 'scanner-audit.json'
        try:
            cache = json.loads(cache_path.read_text(encoding='utf-8'))
            cache = cache if isinstance(cache, dict) else {}
        except (OSError, ValueError):
            cache = {}
        found = []
        for checkout in config['repos']:
            path = str((root / checkout['path']).resolve())
            head = vcs.head(path, root=root)
            head = head.data.get('sha') if isinstance(head, registry.Result) and head.exit == 0 \
                and isinstance(head.data, dict) else None
            entry = cache.get(checkout['name'])
            if not (isinstance(entry, dict) and entry.get('head') == head
                    and (isinstance(entry.get('reason'), str) or _shaped(entry.get('rows'), config))):
                started = monotonic()
                result = scanner.audit(path, root=root)
                valid = isinstance(result, registry.Result) and result.exit in (0, 1, 2)
                rows = (result.data.get('findings') if valid and result.exit != 2 and isinstance(result.data, dict)
                        else None)
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    entry = {'head': head, 'rows': rows}
                else:
                    entry = {'head': head, 'reason': (result.reason or 'scanner audit failed')
                             if valid and result.exit == 2 else 'invalid scanner result'}
                # A fast failure (ZIRAN missing) is retried at the next call.
                if 'rows' in entry or monotonic() - started >= 10:
                    cache[checkout['name']] = entry
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    workspace.atomic_write(cache_path, json.dumps(cache, sort_keys=True))
            if 'reason' in entry:
                missing.append(f'unmeasured: {checkout["name"]}: {" ".join(entry["reason"].split())}')
                continue
            # Rows are already validated by the adapter (ziran._report); S1: a file-level finding has no line.
            # P3: the owner's threshold, most severe first, a cap per repo, paths relative to the checkout.
            levels = ('critical', 'high', 'medium', 'low')
            limit = levels.index(config['scanner']['discovery_threshold'])
            rows = sorted((row for row in entry['rows'] if levels.index(row['severity']) <= limit),
                          key=lambda row: levels.index(row['severity']))
            cap = config['scanner']['discovery_rows']
            if len(rows) > cap:
                capped.append(f'{checkout["name"]}: {len(rows) - cap} more past scanner.discovery_rows')
            for row in rows[:cap]:
                file = Path(row['file'])
                file = str(file.relative_to(path)) if file.is_relative_to(path) else row['file']
                line = row.get('line')
                where = f'{file}:{line}' if line else file
                found.append({'id': f'{checkout["name"]}:scanner:{row["rule"]}:{file}:{line or 0}',
                              'evidence': ' '.join(f'{row["severity"]} {row["rule"]} {where}: {row["message"]}'.split())})
        sources['scanner'] = found
    found = dedupe(sources, day_ids=day['items'])
    if capped:
        found['sources']['scanner'] += '; ' + '; '.join(capped)
    if missing:  # S3: the measured repos' rows stay; each unmeasured repo is named
        from wuwei.scanner import OFF
        measured = found['sources']['scanner'] + '; ' if len(missing) < len(config['repos']) else ''
        found['sources']['scanner'] = measured + '; '.join(missing) + f'; run {OFF} to switch the scanner off'
    for candidate in found['candidates']:
        candidate.update({'repo': name for name in names if candidate['id'].startswith((name + '#', name + ':'))})
    if repo is not None:
        found['candidates'] = [row for row in found['candidates'] if row.get('repo', repo) == repo]
    return found
