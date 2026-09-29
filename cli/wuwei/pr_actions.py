"""Fresh PR ownership state, action deadlines and verified owner dispositions."""

from datetime import timedelta

from wuwei import decision, obligations, state, watch, workspace
from wuwei.references import pull_request


def _verify(root, host, ref, record, config):
    kind, identifier, comment_id = record['kind'], record['decision'], record['comment_id']
    day = workspace.day_dir(root).name
    if (kind not in ('parked', 'carried') or record['day'] != day
            or type(comment_id) is not int or comment_id <= 0):
        raise ValueError('invalid PR disposition')
    text = decision.today_path(identifier, root).read_text(encoding='utf-8')
    fields, _ = decision.evaluate(text)
    if (decision.route(fields) != 'owner' or fields['Decided-by'] != 'owner'
            or identifier in state.read_state(root).get('decision_outcomes', {})):
        raise ValueError('disposition needs an owner-routed decision without a seat outcome')
    if obligations._fingerprint(text) != record['decision_fingerprint']:
        raise ValueError('disposition decision changed; verify again')
    discussion = obligations._read(host.threads, ref, root=root)
    comments = obligations._records(discussion['comments'])
    expected = f'WUWEI {kind} {ref} {identifier} {day} {record["decision_fingerprint"]}'
    owner = obligations._owner_login(config)
    if not any(row['id'] == comment_id and row['author'] == owner and not row['is_bot']
               and row['body'].strip() == expected for row in comments):
        raise ValueError('disposition needs a fresh owner-authored comment: ' + expected)
    return kind


def record_disposition(root, ref, kind, identifier, comment_id):
    ref = pull_request(ref)
    config = workspace.load_config(root)
    host, refs = watch.owned(root, config)
    if ref not in refs:
        raise ValueError('PR must be raised or claimed today')
    text = decision.today_path(identifier, root).read_text(encoding='utf-8')
    record = {'kind': kind, 'decision': identifier, 'comment_id': comment_id,
              'day': workspace.day_dir(root).name,
              'decision_fingerprint': obligations._fingerprint(text)}
    _verify(root, host, ref, record, config)
    def update(data):
        data.setdefault('pr_dispositions', {})[ref] = record
    state._write_state(update, root, reserved=False, kind='pr.disposition',
                       payload={'pr': ref, **record})
    return 0


def check(root, *, closing=False):
    """Stop checks fresh states, enforcing only overdue actions and day close."""
    _, rows = evaluate(root)
    findings, code = [], 0
    for row in rows:
        if row['exit'] == 2:
            code = 2
            findings.append(f'{row.get("pr", "PR actions")} {row["reason"]}')
            continue
        if row['state'] == 'merged' or row['parked'] or closing and row['disposition'] == 'carried':
            continue
        if row['overdue']:
            code = max(code, 1)
            findings.append(f'{row["pr"]} {row["state"]}: overdue action: {row["action"]}')
        if closing:
            code = max(code, 1)
            findings.append(f'{row["pr"]} {row["state"]}: must be merged, parked or carried to tomorrow')
    return code, '\n'.join(findings)


ACTIONS = {
    'conflicted': ('rebase, resolve, run fast checks, push',
                   {'worktree': 'item', 'steps': ['rebase', 'resolve', 'fast_checks', 'push']}),
    'ci_red': ('start a fix round', {'worktree': 'item', 'steps': ['fix_round']}),
    'changes_requested': ('triage review threads', {'routes': {
        'fix_request': 'fix_round', 'question': 'outbound_tier_then_reply',
        'disagreement': 'owner_decision', 'scope_change': 'owner_decision'}}),
    'review_stale': ('re-request review, then post in the review channel',
                     {'steps': ['request_reviewers', 'post_review_channel']}),
    'approved': ('wuwei merge or merge decision',
                 {'steps': ['wuwei merge'], 'fallback': 'merge_decision'}),
    'closed': ('owner decision for closed unmerged PR', {'steps': ['owner_decision']}),
}
ACTIONS['threads_unanswered'] = ACTIONS['changes_requested']


def classify(measured, me, acks):
    """Classify current evidence only; waiting becomes stale in the timed producer."""
    pr, reviews, discussion, checks = (measured[key] for key in ('pr', 'reviews', 'threads', 'checks'))
    if type(pr['merged']) is not bool or pr['merged'] and pr['state'] != 'closed':
        raise ValueError('invalid merged evidence')
    if pr['merged']:
        return 'merged'
    if pr['state'] == 'closed':
        return 'closed'
    if pr['mergeable'] is None:
        raise ValueError('mergeability unmeasured')
    if pr['mergeable'] is False:
        return 'conflicted'
    red = False
    for check in checks:
        if check['state'] not in ('queued', 'in_progress', 'pending', 'waiting', 'requested', 'completed'):
            raise ValueError('unknown check state')
        if check['state'] == 'completed':
            if check['conclusion'] not in ('success', 'neutral', 'skipped', 'failure', 'error',
                    'cancelled', 'timed_out', 'action_required', 'stale', 'startup_failure'):
                raise ValueError('unknown check conclusion')
            red |= check['conclusion'] not in ('success', 'neutral', 'skipped')
    if red:
        return 'ci_red'
    latest = {}
    for row in sorted(reviews, key=lambda r: (obligations._time(r['submitted_at']), r['id'])):
        if not row['is_bot'] and row['state'] != 'commented':
            latest[row['author']] = row
    if any(row['state'] == 'changes_requested' for row in latest.values()):
        return 'changes_requested'
    if obligations._replies(reviews, discussion, me, acks):
        return 'threads_unanswered'
    if any(row['state'] == 'approved' and row['author'] != pr['author']
           and row['sha'] == pr['head'] for row in latest.values()):
        return 'approved'
    return 'waiting'


def observe(root, host, ref, config, measured):
    """Produce an episode under the shared writer lock from a fresh port read."""
    data = state.read_state(root)
    current = classify(measured, obligations._owner_login(config), obligations._ledger(data).get(ref, {}))
    dispositions = data.get('pr_dispositions', {})
    if not isinstance(dispositions, dict):
        raise ValueError('invalid PR disposition ledger')
    disposition = (_verify(root, host, ref, dispositions[ref], config)
                   if ref in dispositions and current != 'merged' else None)
    row = {'pr': ref, 'state': current, 'disposition': disposition, 'parked': disposition == 'parked'}
    now = workspace.now()
    event = {'pr': ref, 'tier': 'silent'}
    def update(data):
        value = data.setdefault('watch', {})
        actions, reviews = value.setdefault('actions', {}), value.setdefault('reviews', {})
        if not isinstance(actions, dict) or not isinstance(reviews, dict):
            raise ValueError('invalid PR action or review ledger')
        episode = actions.get(ref)
        if episode is not None:
            created, deadline = (obligations._time(episode[key]) for key in ('created_at', 'deadline'))
            if (created > now or deadline <= created or episode['state'] not in ACTIONS
                    or episode['action'] != ACTIONS[episode['state']][0]
                    or episode.get('tier', 'silent') not in ('silent', 'nudge', 'page')):
                raise ValueError('invalid action record')
        head = measured['pr']['head']
        waiting = reviews.get(ref)
        if waiting is None or waiting['head'] != head:
            waiting = {'head': head, 'since': now.isoformat()}
        since = obligations._time(waiting['since'])
        if since > now:
            raise ValueError('review observation is in the future')
        reviews[ref] = waiting
        if current == 'waiting' and now - since >= timedelta(minutes=config['pr']['review_window']):
            row['state'] = 'review_stale'
        action, dispatch = ACTIONS.get(row['state'], ('', {}))
        row.update(action=action, dispatch=dispatch, deadline=None, overdue=False)
        if action:
            if episode is None or episode['state'] != row['state']:
                episode = {'state': row['state'], 'action': action, 'created_at': now.isoformat(),
                           'deadline': (now + timedelta(minutes=config['pr']['action_minutes'])).isoformat()}
            created, deadline = (obligations._time(episode[key]) for key in ('created_at', 'deadline'))
            if created > now or deadline <= created:
                raise ValueError('invalid action deadline')
            actions[ref] = episode
            row.update(deadline=episode['deadline'], overdue=now > deadline)
            tier = ('page' if now >= deadline + (deadline - created) else
                    'nudge' if now > deadline else 'silent')
            if not row['parked'] and tier != 'silent' and episode.get('tier', 'silent') != tier:
                event.update(tier=tier, state=row['state'], action=action, deadline=episode['deadline'])
                episode['tier'] = tier
        else:
            actions.pop(ref, None)
        row['exit'] = int(bool(action) and not row['parked'])
    state._write_state(update, root, reserved=False, kind='pr.action', payload=event)
    return row


def evaluate(root, refs=None):
    """Return per-PR results, preserving each unreadable PR and its reason."""
    rows = []
    try:
        if not (workspace.day_dir(root) / 'state.json').is_file():
            raise ValueError('day state missing')
        config = workspace.load_config(root)
        host, owned = watch.owned(root, config)
        if not owned:
            obligations._check_empty_day(workspace.day_dir(root))
        refs = owned if refs is None else sorted({pull_request(ref) for ref in refs})
        for ref in refs:
            try:
                if ref not in owned:
                    raise ValueError('PR must be raised or claimed today')
                measured = watch.evidence(host, ref, root)
                rows.append(observe(root, host, ref, config, measured))
            except watch.ERRORS as exc:
                rows.append({'pr': ref, 'exit': 2, 'reason': f'PR state unmeasured: {exc}'})
    except watch.ERRORS as exc:
        rows.append({'exit': 2, 'reason': f'PR state unmeasured: {exc}'})
    return max((row['exit'] for row in rows), default=0), rows
