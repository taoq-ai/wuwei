"""Fresh PR ownership state, action deadlines and verified owner dispositions."""

from datetime import timedelta
import json
import re

from wuwei import decision, obligations, registry, state, watch, workspace
from wuwei.references import pull_request
from wuwei.exits import ADAPTER_DATA, DAMAGED, RACE


def _verify(root, host, ref, record, config):
    kind, identifier, comment_id = record['kind'], record['decision'], record['comment_id']
    day = workspace.day_dir(root).name
    if (kind not in ('parked', 'carried') or record['day'] != day
            or type(comment_id) is not int or comment_id <= 0):
        raise ValueError(f'invalid PR disposition; {DAMAGED}')
    text = decision.today_path(identifier, root).read_text(encoding='utf-8')
    fields, _ = decision.evaluate(text)
    data = state.read_state(root)
    if (decision.route(fields) != 'owner' or fields['Decided-by'] != 'owner'
            or identifier in data.get('decision_outcomes', {}) and not decision.answered(data, identifier)):
        raise ValueError('disposition needs an owner-routed decision without a seat outcome; route it with bin/wuwei decision route D-n, wait for the owner answer, then rerun bin/wuwei pr disposition')
    if obligations._fingerprint(text) != record['decision_fingerprint']:
        raise ValueError('disposition decision changed; verify again; the owner posts a fresh marker comment, then rerun bin/wuwei pr disposition with its --comment id')
    discussion = obligations._read(host.threads, ref, root=root)
    comments = obligations._records(discussion['comments'])
    expected = f'WUWEI {kind} {ref} {identifier} {day} {record["decision_fingerprint"]}'
    owner = obligations._owner_login(config)
    if not any(row['id'] == comment_id and row['author'] == owner and not row['is_bot']
               and row['body'].strip() == expected for row in comments):
        raise ValueError(f'disposition needs a fresh owner-authored comment: {expected}; the owner posts it on the PR, then rerun bin/wuwei pr disposition with its --comment id')
    return kind


def record_disposition(root, ref, kind, identifier, comment_id):
    ref = pull_request(ref)
    config = workspace.load_config(root)
    host, refs = watch.owned(root, config)
    if ref not in refs:
        raise ValueError('PR must be raised or claimed today; check the ref (owner/repo#n), or claim it with bin/wuwei pr claim, then retry')
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


def _watched(root):
    """True only when the watch read every owned PR recently and no episode is overdue."""
    try:
        data = state.read_state(root)
        refs = {pull_request(ref) for ref in data['raised_prs'] + data['claimed_prs']}
        record = data.get('watch', {})
        age = (workspace.now() - obligations._time(record['measured_at'])).total_seconds()
        limit = 2 * workspace.load_config(root)['pr']['poll_seconds']
        actions = record.get('actions', {})
        return (bool(refs) and 0 <= age <= limit and refs <= record['prs'].keys()
                and all(ref not in actions
                        or obligations._time(actions[ref]['deadline']) >= workspace.now()
                        for ref in refs))
    except watch.ERRORS:
        return False


def check(root, *, closing=False, rows=None):
    """Stop checks fresh states, enforcing only overdue actions and day close."""
    if rows is None and not closing and _watched(root):
        return 0, ''
    if rows is None:
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
        raise ValueError(f'invalid merged evidence; {DAMAGED}')
    if pr['merged']:
        return 'merged'
    if pr['state'] == 'closed':
        return 'closed'
    if pr['mergeable'] is None:
        raise ValueError('mergeability unmeasured; wait a minute and rerun bin/wuwei pr state; if it persists, run bin/wuwei doctor')
    if pr['mergeable'] is False:
        return 'conflicted'
    red = False
    for check in checks:
        if check['state'] not in ('queued', 'in_progress', 'pending', 'waiting', 'requested', 'completed'):
            raise ValueError('unknown check state; read the checks on the PR by hand; if it persists, run bin/wuwei doctor and report the state name')
        if check['state'] == 'completed':
            if check['conclusion'] not in ('success', 'neutral', 'skipped', 'failure', 'error',
                    'cancelled', 'timed_out', 'action_required', 'stale', 'startup_failure'):
                raise ValueError('unknown check conclusion; read the checks on the PR by hand; if it persists, run bin/wuwei doctor and report the result name')
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
        raise ValueError(f'invalid PR disposition ledger; {DAMAGED}')
    disposition = (_verify(root, host, ref, dispositions[ref], config)
                   if ref in dispositions else None)
    row = {'pr': ref, 'state': current, 'disposition': disposition, 'parked': disposition == 'parked'}
    now = workspace.now()
    event = {'pr': ref, 'tier': 'silent', 'state': current}
    def update(data):
        value = data.setdefault('watch', {})
        actions, reviews = value.setdefault('actions', {}), value.setdefault('reviews', {})
        if not isinstance(actions, dict) or not isinstance(reviews, dict):
            raise ValueError(f'invalid PR action or review ledger; {DAMAGED}')
        episode = actions.get(ref)
        if episode is not None:
            created, deadline = (obligations._time(episode[key]) for key in ('created_at', 'deadline'))
            if (created > now or deadline <= created or episode['state'] not in ACTIONS
                    or episode['action'] != ACTIONS[episode['state']][0]
                    or episode.get('tier', 'silent') not in ('silent', 'nudge', 'page')):
                raise ValueError('invalid action record; run bin/wuwei pr state for a fresh action')
        head = measured['pr']['head']
        waiting = reviews.get(ref)
        if waiting is None or waiting['head'] != head:
            waiting = {'head': head, 'since': now.isoformat()}
        since = obligations._time(waiting['since'])
        for post in data.get('channel_posts', []):
            if post.get('pr') == ref and post.get('status') == 'posted' and post.get('head') == head:
                posted_at = obligations._time(post['posted_at'])
                if posted_at > now:
                    raise ValueError('review post is in the future; check the system clock and unset WUWEI_NOW, then run bin/wuwei doctor')
                if posted_at > since:
                    since = posted_at
                    waiting = {'head': head, 'since': since.isoformat()}
        if since > now:
            raise ValueError('review observation is in the future; check the system clock and unset WUWEI_NOW, then run bin/wuwei doctor')
        reviews[ref] = waiting
        if current == 'waiting' and now - since >= timedelta(minutes=config['pr']['review_window']):
            row['state'] = 'review_stale'
        action, dispatch = ACTIONS.get(row['state'], ('', {}))
        row.update(action=action, dispatch=dispatch, deadline=None, overdue=False)
        completed = False
        if action:
            if episode is None or episode['state'] != row['state']:
                episode = {'state': row['state'], 'action': action, 'created_at': now.isoformat(),
                           'deadline': (now + timedelta(minutes=config['pr']['action_minutes'])).isoformat()}
            created, deadline = (obligations._time(episode[key]) for key in ('created_at', 'deadline'))
            if created > now or deadline <= created:
                raise ValueError(f'invalid action deadline; {DAMAGED}')
            actions[ref] = episode
            row.update(deadline=episode['deadline'], overdue=now > deadline)
            done = data.get('pr_action_done', {}).get(ref)
            if done is not None and (not isinstance(done, dict) or not isinstance(done.get('head'), str)
                    or not isinstance(done.get('from_head'), str)
                    or not isinstance(done.get('created_at'), str)):
                raise ValueError(f'invalid PR action completion; {DAMAGED}')
            completed = (done is not None and done['created_at'] == episode['created_at']
                         and done['state'] == row['state']
                         and done['from_head'] == measured['pr']['head'])
            tier = ('page' if now >= deadline + (deadline - created) else
                    'nudge' if now > deadline else 'silent')
            if not completed and not row['parked'] and tier != 'silent' and episode.get('tier', 'silent') != tier:
                event.update(tier=tier, state=row['state'], action=action, deadline=episode['deadline'])
                episode['tier'] = tier
        else:
            actions.pop(ref, None)
        if completed:
            row.update(overdue=False, deadline=None, action='')
        row['exit'] = int(bool(action) and not row['parked'] and not completed)
        if current == 'merged':
            for name, item in data['items'].items():
                if item.get('pr') == ref and item['phase'] in ('raised', 'fix', 'delta'):
                    state._move(data, name, 'merged')
    state._write_state(update, root, reserved=False, kind='pr.action', payload=event)
    return row


def evaluate(root, refs=None):
    """Return per-PR results, preserving each unreadable PR and its reason."""
    rows = []
    try:
        if not (workspace.day_dir(root) / 'state.json').is_file():
            raise ValueError('day state missing; start the day with /wuwei:wuwei-plan (bin/wuwei plan propose, then bin/wuwei plan approve)')
        config = workspace.load_config(root)
        host, owned = watch.owned(root, config)
        if not owned:
            obligations._check_empty_day(workspace.day_dir(root))
        refs = owned if refs is None else sorted({pull_request(ref) for ref in refs})
        for ref in refs:
            try:
                if ref not in owned:
                    raise ValueError('PR must be raised or claimed today; check the ref (owner/repo#n), or claim it with bin/wuwei pr claim, then retry')
                measured = watch.evidence(host, ref, root)
                rows.append(observe(root, host, ref, config, measured))
            except watch.ERRORS as exc:
                rows.append({'pr': ref, 'exit': 2, 'reason': f'PR state unmeasured: {exc}'})
    except watch.ERRORS as exc:
        rows.append({'exit': 2, 'reason': f'PR state unmeasured: {exc}'})
    return max((row['exit'] for row in rows), default=0), rows


def _item(root, ref):
    matches = [(name, row) for name, row in state.read_state(root)['items'].items()
               if row.get('pr') == ref]
    if len(matches) != 1:
        raise ValueError('owned PR needs exactly one linked item; link exactly one item with bin/wuwei pr claim (bin/wuwei why shows duplicates)')
    name, item = matches[0]
    tree = item.get('worktree')
    if not isinstance(tree, str) or not tree:
        raise ValueError('linked item has no worktree; create one with bin/wuwei worktree add <item> and write the builder brief with --worktree')
    path = (root / tree).resolve(strict=True)
    if not path.is_dir():
        raise ValueError('linked item worktree is missing; create it again with bin/wuwei worktree add <item>, then retry')
    return name, path


def _rebase(root, ref, item, tree, *, resume=False):
    from wuwei import fast_checks, registry
    from wuwei.guards import commit_push
    config = workspace.load_config(root)
    host = registry.load('code_host', config)
    measured = watch.evidence(host, ref, root)
    pr = measured['pr']
    if pr['mergeable'] is not False:
        raise ValueError('PR is no longer conflicted; refresh its action; run bin/wuwei pr state and follow the new action')
    if (not re.fullmatch(r'[A-Za-z0-9_./-]+', pr['branch'])
            or pr['branch'].startswith('-') or '..' in pr['branch']):
        raise ValueError(f'invalid PR branch; {DAMAGED}')
    vcs = registry.load('vcs', config)
    repo, actual, _ = commit_push.context(tree, {}, {}, root)
    if repo['name'] != pr['repo']:
        raise ValueError('item worktree belongs to another PR repository; use the worktree made for this PR item (bin/wuwei worktree add <item>), then retry')
    local = commit_push.data(vcs.head(str(tree), root=root))['sha']
    if not resume and local != pr['head']:
        raise ValueError('item worktree HEAD differs from PR head; bring the worktree to the PR head first, then rerun bin/wuwei pr act --run')
    if resume and local == pr['head']:
        raise ValueError('resolved rebase has not changed the PR head; add the rebased commits to the worktree branch, then rerun bin/wuwei pr act --run')
    branch = commit_push.data(vcs.branch(str(tree), root=root))['name']
    if branch != pr['branch']:
        raise ValueError('item worktree branch differs from PR branch; switch it to the PR branch, then rerun bin/wuwei pr act --run')
    base_sha = pr['base_sha']
    if not isinstance(base_sha, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', base_sha):
        raise ValueError(f'invalid PR base SHA; {DAMAGED}')
    if not resume:
        fetched = commit_push.data(vcs.fetch(str(tree), config['brief']['remote'],
                                             pr['base'], base_sha, root=root))
        if fetched.get('sha') != base_sha:
            raise ValueError('fetched base differs from current PR base; rerun bin/wuwei pr act --run; if it repeats, the owner checks brief.remote with bin/wuwei config set in a host terminal')
        result = vcs.rebase(str(tree), base_sha, root=root)
        if isinstance(result, registry.Result) and result.exit == 1:
            print(result.reason or 'rebase did not complete')
            return 1
        commit_push.data(result)
    checked = fast_checks.record(tree)
    if checked:
        print('rebase fast checks did not pass')
        return checked
    head = commit_push.data(vcs.head(str(tree), root=root))['sha']
    if head == pr['head']:
        raise ValueError('rebase did not change PR head; run bin/wuwei pr state; the PR may already be on its base')
    base = commit_push.data(vcs.merge_base(str(tree), base_sha, root=root))['sha']
    if base != base_sha:
        raise ValueError('resolved rebase does not contain the current PR base; run bin/wuwei pr act --run again so the rebase starts from the current base')
    push = commit_push.data(vcs.push_context(str(tree), config['brief']['remote'],
        ['HEAD:refs/heads/' + pr['branch']], root=root))
    # The push context has no force refspec; the expected PR head is the lease guard.
    code, reason = commit_push.push_check(repo, actual, push, root, vcs)
    if code:
        print(reason)
        return code
    result = vcs.push(str(tree), config['brief']['remote'], pr['branch'], pr['head'], root=root)
    if result.exit:
        print(result.reason or 'push did not complete')
        return result.exit
    episode = state.read_state(root).get('watch', {}).get('actions', {}).get(ref)
    if not isinstance(episode, dict) or episode.get('state') != 'conflicted':
        raise ValueError(f'conflict action changed before completion; {RACE}')
    record = {'state': 'conflicted', 'head': head, 'from_head': pr['head'],
              'created_at': episode['created_at'],
              'item': item}
    state._write_state(lambda data: data.setdefault('pr_action_done', {}).update({ref: record}),
                       root, reserved=False, kind='pr.action.done', payload={'pr': ref, **record})
    print(json.dumps({'action': 'done', 'pr': ref, 'item': item, 'head': head}))
    return 0


def _fix(root, ref, item, measured, feedback=None):
    from wuwei.commands import build
    if state.read_state(root)['items'][item]['phase'] == 'delta':
        print(json.dumps({'action': 'gate', 'item': item, 'gate': 'arch_delta'}))
        return 1
    red = [row for row in measured['checks'] if row['state'] == 'completed'
           and row['conclusion'] not in ('success', 'neutral', 'skipped')]
    if feedback is None and red:
        feedback = '\n'.join(f'{row["name"]}: {row["conclusion"]} {row.get("url", "")}' for row in red)
    elif feedback is None:
        feedback = '\n'.join(row['body'] for row in measured['reviews']
                             if row['state'] == 'changes_requested' and row['body'].strip())
        if not feedback:
            raise ValueError('review fix request has no feedback; pass the review findings to the fix round, or run bin/wuwei pr state for a fresh action')
    action = build.open_fix(item, feedback, root=root)
    print(json.dumps(action, sort_keys=True))
    return 1


def _thread(root, ref, item, measured, reply=None):
    from wuwei import drafts, outward, registry
    config = workspace.load_config(root)
    me = obligations._owner_login(config)
    owed = obligations._replies(measured['reviews'], measured['threads'], me,
                                obligations._ledger(state.read_state(root)).get(ref, {}))
    pending = None
    for key in owed:
        surface, target = key.split(':', 1)
        if surface not in ('thread', 'review', 'comment'):
            continue
        thread = (next(row for row in measured['threads']['threads'] if row['id'] == target)
                  if surface == 'thread' else None)
        latest = (thread['comments'][-1] if thread else next(row for row in
                  (measured['reviews'] if surface == 'review' else measured['threads']['comments'])
                  if str(row['id']) == target))
        text, answer = latest['body'], {}
        if re.search(r'\b(scope|out of scope|disagree|instead)\b', text, re.I):
            fingerprint = obligations._fingerprint(latest)
            prior = state.read_state(root).get('pr_action_decisions', {}).get(ref, {}).get(key)
            if prior is None or prior.get('fingerprint') != fingerprint:
                text = (
                    f'Question: How should {ref} thread {target} change scope?\nClass: other\n'
                    f'Context: Reviewer wrote: {json.dumps(text)}\nOptions:\n| Option | Title | Rationale | Consequence |\n| --- | --- | --- | --- |\n'
                    '| change | Make the scope change | Fails the owner scope decision must. | '
                    'The PR scope changes without owner review. |\n'
                    '| defer | Defer to the owner | Passes every must and avoids unapproved scope. | '
                    'The thread waits for the owner. |\nMusts:\n'
                    '| Criterion | change | defer |\n| --- | --- | --- |\n'
                    '| Owner scope decision | fail | pass |\nWants:\n'
                    '| Criterion | Weight | change | defer |\n| --- | --- | --- | --- |\n'
                    '| Avoid unapproved scope | 10 | 0 | 10 |\nRecommendation: defer\n'
                    'Reasoning: Avoiding unapproved scope decided it; an owner approval would flip it.\n'
                    'Confidence: medium\nReversibility: unsure\nBlast radius: own PR\n'
                    'Pre-mortem: Scope changes without owner review.\n'
                    'Revisit: After owner decision.\nDecided-by: owner\nOutcome: pending\n')
                path = decision.write(text, root)
                decision.route_owner(path.stem, decision.evaluate(text)[0], root)
                relative = str(path.relative_to(root))
                state._write_state(lambda data: data.setdefault('pr_action_decisions', {})
                                   .setdefault(ref, {}).update({key: {'path': relative,
                                                                        'fingerprint': fingerprint}}),
                                   root, reserved=False, kind='pr.action.decision',
                                   payload={'pr': ref, 'surface': surface, 'target': target})
                print(json.dumps({'action': 'owner_decision', 'decision': str(path.relative_to(root))}))
                return 1
            path = root / prior['path']
            if not path.is_file():
                raise ValueError('recorded scope decision is missing; restore the decision file named in the day state; bin/wuwei doctor shows what is missing')
            option = decision.answered(state.read_state(root), path.stem)
            if option is None:
                pending = pending or ({'action': 'owner_decision', 'decision': prior['path']}, 1)
                continue
            if option == 'change':
                return _fix(root, ref, item, measured, feedback=text)
            answer = {'decision': prior['path'], 'option': option}
        elif re.search(r'\b(fix|change|update|correct)\b', text, re.I):
            return _fix(root, ref, item, measured, feedback=text)
        if reply is None:
            print(json.dumps({'action': 'reply', 'pr': ref, 'surface': surface,
                              'thread': target, 'question': text, **answer}))
            return 1
        if not reply.strip():
            raise ValueError('reply needs a nonempty body; pass a one-line answer: bin/wuwei pr act --reply "<answer>"')
        context = {'ref': ref, 'thread': target} if thread else {'ref': ref}
        channel_kind = 'code_host'
        code, tier = outward.classify(reply, root, config, context, kind=channel_kind)
        if type(code) is not int or code not in (0, 1, 2) or tier not in ('send', 'draft'):
            raise ValueError(f'invalid outward tier result; {ADAPTER_DATA}')
        if code == 0 and tier == 'send':
            return obligations.reply(ref, surface,
                thread['comments'][0]['id'] if thread else latest['id'], reply, root)
        draft = {'surface': surface, 'thread': target, 'body': reply, 'source_id': latest['id']}
        inputs = {'ref': ref, 'text': reply, 'thread': thread['comments'][0]['id'] if thread else None}
        existing = next((key for key, row in drafts.read(state.read_state(root)).items()
                         if row['status'] == 'pending' and row['channel'] == 'code_host'
                         and row['inputs'] == inputs), None)
        if existing is not None:
            pending = pending or ({'action': 'draft_reply', 'pr': ref, **draft, 'draft': existing}, 1)
            if code == 2:
                pending = (pending[0], 2)
            continue
        humanized, reason = outward.humanize_lint(inputs, root, config, {channel_kind}, draft=True)
        if humanized:
            print(reason)
            return humanized
        draft_id = drafts.create(root, config, channel_kind, 'comment', config['adapters']['code_host'],
                                 inputs, 'outward tier unmeasured; reply kept as a draft' if code == 2
                                 else outward.APPROVAL_REQUIRED)
        print(json.dumps({'action': 'draft_reply', 'pr': ref, **draft, 'draft': draft_id}))
        if code == 2:
            print('outward tier unmeasured; reply kept as a draft')
        return 2 if code == 2 else 1
    if pending is not None:
        action, code = pending
        print(json.dumps(action))
        if code == 2:
            print('outward tier unmeasured; reply kept as a draft')
        return code
    raise ValueError('no unanswered review thread found; drop --reply, or check the PR with bin/wuwei pr state')


def act(root, ref, *, run=False, complete=False, reply=None):
    """Execute safe PR actions and surface work requiring a builder or owner."""
    ref = pull_request(ref)
    _, rows = evaluate(root, [ref])
    row, = rows
    if row['exit'] == 2:
        print(row['reason'])
        return 2
    if row['exit'] == 0:
        return 0
    if (run or complete) and row['state'] != 'conflicted':
        print('--run and --complete require a conflicted PR')
        return 2
    if reply is not None and row['state'] not in ('changes_requested', 'threads_unanswered'):
        print('--reply requires an unanswered review question')
        return 2
    if row['parked'] or row['state'] in ('merged', 'waiting'):
        return 0
    if row['state'] == 'approved':
        from wuwei import merge
        result = merge.execute(ref, root=root)
        if result.exit:
            print(f'{ref}: owner merge decision required: {result.reason}')
        return result.exit
    if row['state'] == 'review_stale':
        from wuwei import shepherd
        return shepherd.post_review_request(root, ref)
    if row['state'] in ('conflicted', 'ci_red', 'changes_requested', 'threads_unanswered'):
        try:
            item, tree = _item(root, ref)
            if row['state'] == 'conflicted':
                if run or complete:
                    return _rebase(root, ref, item, tree, resume=complete)
                print(json.dumps({'action': 'rebase', 'pr': ref, 'item': item,
                                  'worktree': str(tree), 'steps': row['dispatch']['steps'],
                                  'run': f'wuwei pr act {ref} --run',
                                  'after_conflict': f'wuwei pr act {ref} --complete'}))
                return 1
            if run or complete:
                raise ValueError(f'--run and --complete apply only to a conflicted PR; run bin/wuwei pr act {ref} without them')
            config = workspace.load_config(root)
            measured = watch.evidence(registry.load('code_host', config), ref, root)
            if row['state'] == 'ci_red':
                return _fix(root, ref, item, measured)
            return _thread(root, ref, item, measured, reply)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f'{ref}: PR action unmeasured: {exc}')
            return 2
    print(f'{ref}: {row["action"]}')
    return 1
