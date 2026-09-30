"""One fresh-head merge decision and its durable post-merge supervision."""

from datetime import timedelta
from fnmatch import fnmatchcase
import hashlib
from pathlib import Path
import re

from wuwei import obligations, registry, state, workspace
from wuwei.references import pull_request
from wuwei.registry import Result

ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, RuntimeError, re.error)


class Refused(ValueError):
    """Measured policy finding, distinct from missing evidence."""


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value):
        raise ValueError('invalid head SHA')
    return value


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('expected nonnegative integer evidence')
    return value


def read(operation, *args, root):
    value = obligations._read(operation, *args, root=root)
    if isinstance(value, dict) and ('message' in value or 'errors' in value):
        raise ValueError('adapter returned an error body')
    return value


def reference(ref, root, config, cwd=None, repo=None):
    if isinstance(ref, str) and ref.isdecimal():
        if repo is None:
            cwd = Path(cwd or Path.cwd()).resolve()
            candidates = [r for r in config['repos'] if cwd.is_relative_to(
                (root / Path(r['path']).expanduser()).resolve())]
            if not candidates and any((p / '.git').exists() for p in (cwd, *cwd.parents)):
                vcs = registry.load('vcs', config)
                common = read(vcs.repo_context, str(cwd), root=root)['common_dir']
                candidates = [r for r in config['repos'] if read(vcs.repo_context,
                    str((root / Path(r['path']).expanduser()).resolve()), root=root)['common_dir'] == common]
            if len(candidates) != 1:
                raise ValueError('numeric PR requires an unambiguous configured repository')
            repo = candidates[0]['name']
        ref = f'{repo}#{ref}'
    if isinstance(ref, str):
        ref = re.sub(r'^https://github\.com/([^/]+/[^/]+)/pull/', r'\1#', ref)
    return pull_request(ref)


def journals(root):
    from wuwei.watch import days
    entries, breakers = [], {}
    for directory in days(root):
        data = state.read_state(directory=directory)
        for repo, item in data.get('merge_breakers', {}).items():
            breakers.setdefault(repo, item)
        for ref, item in data.get('merges', {}).items():
            if pull_request(ref) != ref or item['head'] != sha(item['head']):
                raise ValueError('invalid merge journal')
            obligations._time(item['at'])
            entries.append((directory, ref, item))
    return entries, breakers


def checked_pr(host, ref, root):
    pr = read(host.pr, ref, root=root)
    if f'{pr["repo"]}#{pr["number"]}' != ref:
        raise ValueError('PR identity differs from requested PR')
    sha(pr['head'])
    sha(pr['base_sha'])
    if type(pr['draft']) is not bool or type(pr['merged']) is not bool:
        raise ValueError('invalid PR boolean evidence')
    if not isinstance(pr['author'], str) or not pr['author']:
        raise ValueError('invalid PR author')
    obligations._time(pr['updated_at'])
    return pr


def checks_at(host, ref, head, root):
    checks = obligations._list(read(host.checks, ref, head, root=root))
    for check in checks:
        if (check['sha'] != head or not isinstance(check['name'], str) or not check['name']
                or check['state'] not in ('queued', 'pending', 'in_progress', 'completed', 'waiting', 'requested')
                or check['conclusion'] not in (None, 'success', 'failure', 'error', 'neutral',
                    'skipped', 'cancelled', 'timed_out', 'action_required', 'stale', 'startup_failure')):
            raise ValueError('invalid check evidence at head')
        if check.get('app_id') is not None:
            integer(check['app_id'])
    return checks


def green(checks, protection):
    required = obligations._list(protection['required_checks'])
    require(required, 'no required checks resolvable')
    for entry in required:
        if not isinstance(entry['name'], str) or not entry['name']:
            raise ValueError('invalid required check name')
        if entry['app_id'] is not None:
            integer(entry['app_id'])
        matches = [c for c in checks if c['name'] == entry['name'] and
                   (entry['app_id'] is None or c.get('app_id') == entry['app_id'])]
        require(matches and all(c['state'] == 'completed' and c['conclusion'] == 'success'
                                for c in matches), f'required check {entry["name"]} is not green')
    for check in checks:
        require(check['state'] == 'completed' and check['conclusion'] in ('success', 'neutral', 'skipped'),
                f'check {check["name"]} is failing or pending')


def quiet(policy, now):
    minute = now.hour * 60 + now.minute
    for window in policy['quiet_hours']:
        match = re.fullmatch(r'([0-2][0-9]):([0-5][0-9])-([0-2][0-9]):([0-5][0-9])', window)
        if not match or any(int(match[i]) > 23 for i in (1, 3)):
            raise ValueError('invalid quiet hours, expected HH:MM-HH:MM')
        start, end = int(match[1]) * 60 + int(match[2]), int(match[3]) * 60 + int(match[4])
        if start == end or (start <= minute < end if start < end else minute >= start or minute < end):
            return True
    return False


def item_evidence(root, ref, data):
    from wuwei.watch import records, days
    items = [(name, value) for name, value in data['items'].items() if value.get('pr') == ref]
    require(len(items) == 1, 'PR needs one linked item')
    name, item = items[0]
    require(name in data['approved_items'], 'item is not in the approved plan')
    rows = [row for directory in days(root) for row in records(directory / 'events.jsonl')]
    approved = [row['payload']['flags'][name] for row in rows
                if row['kind'] in ('plan.approved', 'state.import')
                and name in row['payload'].get('flags', {})]
    if not approved:
        raise ValueError('approved item risk evidence is missing; replan the item')
    for flags in [item['flags'], *approved]:
        if set(flags) != set(state.ITEM_DEFAULTS['flags']) or any(type(v) is not bool for v in flags.values()):
            raise ValueError('invalid item risk evidence')
        require(not any(flags.values()), 'item carries a risk flag')
    for phase in ('fix', 'delta'):
        count = sum((row['kind'].startswith('state.') and
                    row['payload'].get('phase_changes', {}).get(name) == phase)
                    if 'phase_changes' in row['payload'] else
                    (row['kind'] == 'state.transition' and row['payload'].get('item') == name
                     and row['payload'].get('phase') == phase) for row in rows)
        require(count <= 1, 'item exceeds cycle budget')
    return name


def bot_evidence(config, policy, discussion, ref, head, root):
    if config['adapters']['review_bot'] == 'none':
        return None
    login = policy['bot_login']
    if not login:
        raise ValueError('merge.bot_login required for a configured review bot')
    bot = registry.load('review_bot', config)
    score = read(bot.score, ref, root=root)
    integer(score)
    summaries = [row for row in discussion['comments'] if row['author'] == login and row['is_bot']]
    require(summaries, 'review bot has not reviewed yet')
    latest = max(summaries, key=lambda row: obligations._time(row.get('updated_at', row['created_at'])))
    scores = re.findall(policy['bot_score_pattern'], latest['body'])
    heads = re.findall(r'/commit/([0-9a-f]{40})(?![0-9a-f])', latest['body'])
    require(scores == [str(score)] and score >= policy['bot_min_score'] and heads == [head],
            'review bot score is insufficient or not at head')
    findings = obligations._list(read(bot.open_findings, ref, root=root))
    # Unclassified open findings are blocking, never silently dismissed.
    require(not findings, 'review bot has open findings')
    return {'score': score, 'head': head, 'summary': latest['id']}


def check(ref, root=None, *, cwd=None, repo=None):
    """Return 0 and evidence, 1 findings, or 2 unmeasured; never authorize overrides."""
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        ref = reference(ref, root, config, cwd, repo)
        repo_name = ref.split('#')[0]
        settings = next((r for r in config['repos'] if r['name'] == repo_name), None)
        require(settings is not None, 'merge policy requires a configured repository')
        policy = settings['merge']
        require(policy['auto'], 'merge.auto is off')
        require(settings['merge_deploys'] is False, 'explicit merge_deploys = false is required')
        entries, breakers = journals(root)
        breaker = breakers.get(repo_name)
        require(not breaker or policy['reset_epoch'] > integer(breaker['epoch']), 'repository circuit breaker is tripped')
        if any(r.split('#')[0] == repo_name and entry.get('monitor_error') for _, r, entry in entries):
            raise ValueError('post-merge observations are unmeasured; run the watch')
        require(not any(r == ref and entry['status'] != 'failed' for _, r, entry in entries), 'PR already has a merge intent')
        require(sum(directory == workspace.day_dir(root) and r.split('#')[0] == repo_name
                    for directory, r, entry in entries if entry['status'] != 'failed') < policy['max_per_day'],
                'repository daily merge cap reached')
        require(not quiet(policy, workspace.now()), 'merge is in quiet hours')
        data = state.read_state(root)
        item = item_evidence(root, ref, data)
        host = registry.load('code_host', config)
        pr = checked_pr(host, ref, root)
        head = pr['head']
        require(pr['state'] == 'open' and not pr['merged'], 'PR must be open')
        require(not pr['draft'], 'PR is a draft')
        if not isinstance(pr['base'], str) or not pr['base']:
            raise ValueError('missing base branch')
        require(not any(fnmatchcase(pr['base'], pattern) for pattern in config['environments']),
                'ineligible base branch')
        require(pr['merge_state'] != 'dirty', 'mergeable_state=dirty')
        protection = read(host.protection, repo_name, pr['base'], root=root)
        for key in ('strict', 'merge_queue', 'require_code_owner_reviews', 'require_last_push_approval',
                    'dismiss_stale_reviews', 'conversation_resolution', 'enforce_admins'):
            if type(protection[key]) is not bool:
                raise ValueError('invalid branch protection evidence')
        require(pr['merge_state'] != 'behind' or protection['merge_queue'], 'mergeable_state=behind')
        if pr['mergeable'] is None or pr['merge_state'] == 'unknown':
            raise ValueError('mergeability unmeasured')
        files = obligations._list(read(host.files, ref, root=root))
        if len(files) != integer(pr['changed_files']):
            raise ValueError('incomplete changed files')
        additions = sum(integer(f['additions']) for f in files)
        deletions = sum(integer(f['deletions']) for f in files)
        if additions != integer(pr['additions']) or deletions != integer(pr['deletions']):
            raise ValueError('incomplete diff size')
        require(additions + deletions <= policy['max_changed_lines'], 'diff exceeds max changed lines')
        for file in files:
            if not isinstance(file['path'], str) or not file['path']:
                raise ValueError('invalid changed file path')
            for path in (file['path'], file['previous_path']):
                if path is None:
                    continue
                if not isinstance(path, str) or not path or path.startswith('/') or '..' in Path(path).parts:
                    raise ValueError('invalid changed file path')
                parts = path.split('/')
                require(not any(fnmatchcase('/'.join(parts[i:]), pattern)
                        for i in range(len(parts)) for pattern in policy['never_auto_paths']),
                        f'never-auto path: {path}')
        from wuwei.guards.pr import gate_check, GATES
        code, reason = gate_check(root, root / settings['path'], config, sha=head, item=item)
        require(code == 0, reason)
        verdicts = []
        for gate in GATES:
            first = data['gate_verdicts'].get(f'{item}:{gate}:initial')
            selected = (data['gate_verdicts'].get(f'{item}:{gate}:delta')
                        if first and first['verdict'] == 'FIX' else first)
            path = (root / selected['file'] if selected else
                    workspace.day_dir(root) / 'decisions' / f'gate-{item}-{gate}.md')
            verdicts.append({'path': str(path.relative_to(root)),
                             'digest': hashlib.sha256(path.read_bytes()).hexdigest()})
        checks = checks_at(host, ref, head, root)
        green(checks, protection)
        require(pr['mergeable'] is True and pr['merge_state'] in
                (('clean', 'behind') if protection['merge_queue'] else ('clean',)),
                'branch protection not satisfied')
        reviews, discussion = obligations._evidence(host, ref, root)
        latest = {}
        for review in sorted(reviews, key=lambda r: (obligations._time(r['submitted_at']), r['id'])):
            if not review['is_bot'] and review['state'] != 'commented':
                latest[review['author']] = review
        require(not any(r['state'] == 'changes_requested' for r in latest.values()), 'outstanding changes requested')
        approvals = [r for r in latest.values() if r['state'] == 'approved'
                     and r['author'] != pr['author'] and r['sha'] == head]
        require(len(approvals) >= integer(protection['approvals']), 'required human approvals missing at head')
        me = obligations._owner_login(config)
        replies = obligations._replies(reviews, discussion, me, obligations._ledger(data).get(ref, {}))
        visibility = obligations._visibility(ref, pr, reviews, data, me, workspace.day_dir(root), config)
        require(not replies and not visibility, 'obligations: ' + ', '.join(replies + visibility))
        for thread in discussion['threads']:
            humans = [r for r in thread['comments'] if not r['is_bot']]
            answered = humans and max(humans, key=lambda r: (obligations._time(r['created_at']), r['id']))['author'] == me
            require(thread['resolved'] or (answered and not protection['conversation_resolution']),
                    f'unresolved thread: {thread["id"]}')
        bot = bot_evidence(config, policy, discussion, ref, head, root)
        last = max([obligations._time(pr['updated_at']),
                    *[obligations._time(r['submitted_at']) for r in approvals]])
        require(workspace.now() - last >= timedelta(minutes=policy['soak_minutes']), 'soak window has not passed')
        fresh = checked_pr(host, ref, root)
        require(all(fresh[key] == pr[key] for key in ('head', 'base_sha', 'base', 'updated_at',
                    'merge_state', 'mergeable', 'state', 'draft')), 'PR changed during check')
        require(workspace.load_config(root) == config, 'configuration changed during check')
        return Result(0, {'pr': ref, 'item': item, 'head': head, 'base': pr['base'],
            'base_sha': pr['base_sha'], 'at': workspace.now().isoformat(), 'verdicts': verdicts,
            'checks': checks, 'approvals': sorted(r['author'] for r in approvals),
            'protection': protection, 'bot': bot,
            'files': [{k: v for k, v in file.items() if k != 'patch'} for file in files]})
    except Refused as exc:
        return Result(1, None, f'merge policy: {exc}; the owner merges')
    except ERRORS as exc:
        return Result(2, None, f'merge policy unmeasured: {exc}; route to owner')


def locked(root):
    """Serialize merge and monitor decisions across day rollover."""
    from contextlib import contextmanager

    @contextmanager
    def hold():
        with (root / '.wuwei/merge.lock').open('a') as lock:
            state.lock_ex(lock, 'merge.lock')
            yield
    return hold()


def save_entry(root, directory, ref, entry, kind):
    state._write_state(lambda data: data.setdefault('merges', {}).update({ref: entry}),
                       root, directory=directory, reserved=False, kind=kind,
                       payload={'pr': ref, 'head': entry['head'], 'status': entry['status'],
                                'evidence': entry['evidence']})


def undo(root, directory, ref, entry):
    from wuwei.watch import records
    path = directory / 'undo.jsonl'
    existing = records(path)
    if not any(row['payload'].get('pr') == ref for row in existing):
        state.append_jsonl(path, {'kind': 'merge.undo', 'ts': workspace.now().isoformat(),
            'payload': {'pr': ref, 'head': entry['head'], 'operation': 'revert_pr'}})


def execute(ref, root=None, *, cwd=None):
    """Check and merge under one lock; persist intent before any external write."""
    try:
        root = workspace.find_workspace(root)
        with locked(root):
            result = check(ref, root, cwd=cwd)
            if result.exit:
                state.append_event('merge.policy_blocked', {'pr': str(ref), 'exit': result.exit,
                                                            'reason': result.reason}, root)
                return result
            evidence = result.data
            ref = evidence['pr']
            directory = workspace.day_dir(root)
            entry = {'head': evidence['head'], 'at': evidence['at'], 'status': 'intent',
                     'evidence': evidence}
            save_entry(root, directory, ref, entry, 'merge.intent')
            undo(root, directory, ref, entry)
            host = registry.load('code_host', workspace.load_config(root))
            accepted = read(host.merge, ref, evidence['head'], root=root)
            if accepted.get('accepted') is not True or accepted.get('sha') != evidence['head']:
                raise ValueError('merge result could not be verified')
            # Accepted can mean enqueued. The watch reads the actual merged commit.
            entry['status'] = 'accepted'
            save_entry(root, directory, ref, entry, 'merge.auto')
            return Result(0, evidence)
    except ERRORS as exc:
        return Result(2, None, f'merge unmeasured: {exc}; route to owner; watch will reconcile intent')


def trip(root, repo, policy, reason, *, ref=None, kind='merge.breaker', incident=None):
    _, breakers = journals(root)
    prior = breakers.get(repo)
    incident = incident or f'{kind}:{ref or reason}'
    seen = prior.get('incidents', []) if prior else []
    if incident in seen:
        return
    entry = {'epoch': max(policy['reset_epoch'], integer(prior['epoch']) if prior else 0),
             'reason': reason, 'at': workspace.now().isoformat(), 'incidents': [*seen, incident]}
    state._write_state(lambda data: data.setdefault('merge_breakers', {}).update({repo: entry}),
                       root, reserved=False, kind=kind,
                       payload={'repo': repo, 'pr': ref, 'reason': reason, 'tier': 'page'})


def edits(file):
    """Exact changed ranges from a complete unified patch; no context-line overlap."""
    patch = file['patch']
    if not isinstance(patch, str):
        raise ValueError('outcome unmeasured: missing text patch')
    result, old, new, old_end, new_end = [], None, None, None, None
    added = removed = 0
    for line in patch.splitlines():
        match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
        if match:
            if old is not None and (old != old_end or new != new_end):
                raise ValueError('truncated patch hunk')
            old_count = int(match[2]) if match[2] is not None else 1
            new_count = int(match[4]) if match[4] is not None else 1
            old = int(match[1]) + (old_count == 0)
            new = int(match[3]) + (new_count == 0)
            old_end, new_end = old + old_count, new + new_count
        elif line.startswith('\\'):
            continue
        elif old is None or not line or line[0] not in ' +-':
            raise ValueError('invalid patch evidence')
        elif line[0] == ' ':
            old += 1
            new += 1
        else:
            deletion, addition = int(line[0] == '-'), int(line[0] == '+')
            if result and result[-1][0] + result[-1][1] == old and result[-1][2] + result[-1][3] == new:
                result[-1][1] += deletion
                result[-1][3] += addition
            else:
                result.append([old, deletion, new, addition])
            old += deletion
            new += addition
            removed += deletion
            added += addition
    if (old != old_end or new != new_end or added != file['additions'] or removed != file['deletions']):
        raise ValueError('incomplete file patch')
    return result


def outcome(entry, history, policy):
    """Follow changed lines through linear history for the first fourteen days."""
    start = obligations._time(entry['merged_at'])
    end = start + timedelta(days=14)
    tracked = {}
    for file in entry['evidence']['files']:
        tracked[file['path']] = {line for _, _, at, count in edits(file)
                                 for line in range(at, at + max(1, count))}
    reverts, fixes = [], []
    for commit in obligations._list(history):
        at = obligations._time(commit['at'])
        sha(commit['sha'])
        if not isinstance(commit['message'], str):
            raise ValueError('invalid commit message evidence')
        if re.search(r'\bThis reverts commit ' + re.escape(entry['merge_commit']) + r'\.', commit['message']):
            reverts.append({'sha': commit['sha'], 'at': at.isoformat()})
        if at > end:
            continue
        if at < start:
            raise ValueError('nonchronological outcome history')
        touched = False
        for file in obligations._list(commit['files']):
            path = file['previous_path'] or file['path']
            if path not in tracked:
                continue
            changes = edits(file)
            changed = set()
            for line in tracked.pop(path):
                shift = 0
                for old, old_count, new, new_count in changes:
                    if old_count and old <= line < old + old_count:
                        touched = True
                        changed.update(range(new, new + max(new_count, 1)))
                        break
                    if old > line:
                        changed.add(line + shift)
                        break
                    shift = new + new_count - old - old_count
                else:
                    changed.add(line + shift)
            tracked[file['path']] = changed
        if touched and re.search(policy['fix_pattern'], commit['message']):
            fixes.append(commit['sha'])
    return {'reverts': reverts, 'fixes': fixes,
            'escaped': bool(fixes or any(obligations._time(r['at']) <= end for r in reverts))}


def baseline(root):
    text = (root / '.wuwei/memory/notes/baseline.md').read_text(encoding='utf-8')
    values = re.findall(r'^Escaped-defect-rate: *([0-9]+(?:\.[0-9]+)?) *$', text, re.M)
    if len(values) != 1 or not 0 <= float(values[0]) <= 1:
        raise ValueError('baseline needs one Escaped-defect-rate: fraction between 0 and 1')
    return float(values[0])


def monitor(root, directory, ref, entry, host, settings):
    policy = settings['merge']
    repo = settings['name']
    if entry['status'] == 'failed':
        return 0, None
    if entry.get('merged_at') and workspace.now() - obligations._time(entry['merged_at']) >= timedelta(days=28):
        return 0, None
    pr = checked_pr(host, ref, root)
    if not pr['merged']:
        if pr['head'] != entry['head'] or pr['state'] == 'closed':
            entry['status'] = 'failed'
            save_entry(root, directory, ref, entry, 'merge.failed')
            return 1, None
        return 0, None  # Still in the queue, or an uncertain request. Never retry mutation.
    if pr['head'] != entry['head'] or pr['base'] != entry['evidence']['base']:
        trip(root, repo, policy, 'merged identity differs from checked PR', ref=ref)
        raise ValueError('merged PR identity differs from checked evidence')
    merge_commit = sha(pr['merge_commit'])
    obligations._time(pr['merged_at'])
    if entry.get('merge_commit') not in (None, merge_commit):
        raise ValueError('merge commit changed')
    if 'merge_commit' not in entry:
        entry.update(status='merged', merge_commit=merge_commit, merged_at=pr['merged_at'])
        undo(root, directory, ref, entry)
        save_entry(root, directory, ref, entry, 'merge.completed')
        from wuwei import dispatch
        items = state.read_state(directory=directory)['items']
        item = next((name for name, row in items.items() if row.get('pr') == ref), None)
        if item is not None:
            dispatch.tracker_call(item, 'done', root)
        else:
            state.append_event('tracker.call', {'item': '', 'pr': ref, 'action': 'done',
                               'exit': 2, 'reason': 'no item linked to merged PR'}, root)
    age = workspace.now() - obligations._time(entry['merged_at'])
    if age >= timedelta(days=28):
        return 0, None
    check_error = None
    if entry['status'] == 'red':
        red = entry['red']
    else:
        try:
            checks = checks_at(host, ref, merge_commit, root)
            if not checks:
                raise ValueError('base checks unmeasured: no checks at merge commit')
        except ERRORS as exc:
            checks, check_error = [], exc
        red = [c['name'] for c in checks if c['conclusion'] in
               ('failure', 'error', 'cancelled', 'timed_out', 'action_required', 'stale', 'startup_failure')]
    if red:
        # Disable and page before trying the reversible remediation.
        trip(root, repo, policy, 'red base checks: ' + ', '.join(red), ref=ref, kind='base.red')
        entry.update(status='red', red=red)
        save_entry(root, directory, ref, entry, 'merge.red')
        if not entry.get('revert_pr'):
            result = read(host.revert_pr, ref, root=root)
            target = f'https://github.com/{repo}/pull/{integer(result["number"])}'
            if result['url'] != target or result['number'] <= 0 or target.endswith('/' + ref.split('#')[1]):
                raise ValueError('invalid revert PR result')
            entry['revert_pr'] = target
            save_entry(root, directory, ref, entry, 'merge.revert')
        return 1, {'reverts': [entry['revert_pr']], 'fixes': [], 'escaped': True}
    measure = age >= timedelta(days=14) and 'outcome' not in entry
    history = read(host.history, repo, merge_commit, pr['base'], measure, root=root)
    commits = obligations._list(history['commits'])
    reverted = any(re.search(r'\bThis reverts commit ' + re.escape(merge_commit) + r'\.',
                            c['message']) for c in commits)
    if reverted:
        trip(root, repo, policy, 'auto-merged PR was reverted', ref=ref)
    if check_error:
        raise check_error
    try:
        green(checks, entry['evidence']['protection'])
    except Refused as exc:
        if age >= timedelta(days=14):
            raise ValueError(f'base checks still incomplete: {exc}') from exc
        return int(reverted), None
    if measure:
        actual = {**entry, 'evidence': {**entry['evidence'], 'files': obligations._list(history['files'])}}
        entry['outcome'] = outcome(actual, history['commits'], policy)
        save_entry(root, directory, ref, entry, 'merge.observation')
    return int(reverted), entry.get('outcome')


def poll(root):
    """Reconcile merge intents and supervise base checks from the existing watch."""
    result, cohort, unreadable_repos = 0, {}, set()
    try:
        config = workspace.load_config(root)
        with locked(root):
            entries, _ = journals(root)
            if not entries:
                return 0
            host = registry.load('code_host', config)
            for directory, ref, entry in entries:
                repo = ref.split('#')[0]
                try:
                    settings = next(r for r in config['repos'] if r['name'] == repo)
                    code, measured = monitor(root, directory, ref, entry, host, settings)
                    if entry.pop('monitor_error', None) is not None:
                        save_entry(root, directory, ref, entry, 'merge.observation')
                    result = max(result, code)
                    if measured is not None:
                        age = workspace.now() - obligations._time(entry['merged_at'])
                        if timedelta(days=14) <= age < timedelta(days=28):
                            cohort.setdefault(repo, []).append({**measured, 'pr': ref})
                except (*ERRORS, StopIteration) as exc:
                    unreadable_repos.add(repo)
                    entry['monitor_error'] = str(exc)
                    save_entry(root, directory, ref, entry, 'merge.observation')
                    result = 2
                    state.append_event('merge.unmeasured', {'pr': ref, 'reason': str(exc)}, root)
                    print(f'merge watch unmeasured: {ref}: {exc}', flush=True)
            for repo, measurements in cohort.items():
                if repo in unreadable_repos:
                    continue
                rate = sum(m['escaped'] for m in measurements) / len(measurements)
                try:
                    expected = baseline(root)
                except ERRORS as exc:
                    result = 2
                    for directory, ref, entry in entries:
                        if ref in {m['pr'] for m in measurements}:
                            entry['monitor_error'] = str(exc)
                            save_entry(root, directory, ref, entry, 'merge.observation')
                    print(f'merge metric unmeasured: {exc}', flush=True)
                    continue
                state.append_event('merge.metric', {'repo': repo, 'rate': rate, 'baseline': expected,
                    'prs': len(measurements), 'reverts': sum(len(m['reverts']) for m in measurements),
                    'fixes': sum(len(m['fixes']) for m in measurements)}, root)
                if rate > expected:
                    settings = next(r for r in config['repos'] if r['name'] == repo)
                    trip(root, repo, settings['merge'], 'escaped defect rate exceeds baseline',
                         incident='metric:' + obligations._fingerprint(
                             sorted(m['pr'] for m in measurements if m['escaped'])))
                    result = max(result, 1)
    except ERRORS as exc:
        print(f'merge watch unmeasured: {exc}', flush=True)
        return 2
    return result
