"""Fresh PR ownership state, action deadlines and verified owner dispositions."""

from datetime import timedelta
import json
import re
import shlex
import sys

from wuwei import obligations, registry, state, watch, workspace
from wuwei.references import pull_request
from wuwei.exits import DAMAGED, RACE


def _verify(root, host, ref, record, config):
    """The owner-authored marker comment WUWEI <kind> <ref> <day>; a marker posted before the
    upgrade, with its D-n and record fingerprint after the ref, still verifies."""
    kind, comment_id = record['kind'], record['comment_id']
    day = workspace.day_dir(root).name
    if (kind not in ('parked', 'carried') or record['day'] != day
            or type(comment_id) is not int or comment_id <= 0):
        raise ValueError(f'invalid PR disposition; {DAMAGED}')
    discussion = obligations._read(host.threads, ref, root=root)
    comments = obligations._records(discussion['comments'])
    expected = f'WUWEI {kind} {ref} {day}'
    legacy = re.compile(rf'WUWEI {kind} {re.escape(ref)} D-[1-9][0-9]* {day} [0-9a-f]{{64}}')
    owner = obligations._owner_login(config)
    if not any(row['id'] == comment_id and row['author'] == owner and not row['is_bot']
               and (row['body'].strip() == expected or legacy.fullmatch(row['body'].strip()))
               for row in comments):
        raise ValueError(f'disposition needs a fresh owner-authored comment: {expected}; the owner posts it on the PR, then rerun bin/wuwei pr disposition with its --comment id')
    return kind


def record_disposition(root, ref, kind, comment_id):
    ref = pull_request(ref)
    config = workspace.load_config(root)
    host, refs = watch.owned(root, config)
    if ref not in refs:
        raise ValueError('PR must be raised or claimed today; check the ref (owner/repo#n), or claim it with bin/wuwei pr claim, then retry')
    record = {'kind': kind, 'comment_id': comment_id, 'day': workspace.day_dir(root).name}
    _verify(root, host, ref, record, config)
    def update(data):
        data.setdefault('pr_dispositions', {})[ref] = record
    state._write_state(update, root, kind='pr.disposition',
                       payload={'pr': ref, **record})
    return 0


def check(root, *, closing=False, rows=None):
    """Check fresh states, enforcing only overdue actions and day close."""
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
            owed = f' ({", ".join(row["owed"])})' if row.get('owed') else ''
            todo = f'{row["action"]}{owed}; ' if row.get('action') else ''
            findings.append(f'{row["pr"]} {row["state"]}: {todo}must be merged, parked or carried to tomorrow')
    return code, '\n'.join(findings)


ACTIONS = {
    'conflicted': ('rebase, resolve, run fast checks, push',
                   {'worktree': 'item', 'steps': ['rebase', 'resolve', 'fast_checks', 'push']}),
    'ci_red': ('start a fix round', {'worktree': 'item', 'steps': ['fix_round']}),
    'changes_requested': ('triage review threads', {'routes': {
        'fix_request': 'fix_round', 'question': 'reply',
        'disagreement': 'owner_decision', 'scope_change': 'owner_decision'}}),
    'review_stale': ('re-request review, then post in the review channel',
                     {'steps': ['request_reviewers', 'post_review_channel']}),
    'approved': ('wuwei merge or merge decision',
                 {'steps': ['wuwei merge'], 'fallback': 'owner_decision'}),
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


def _base_red(host, ref, measured, root):
    """#728: the base_red reason when every red head check is red at the base commit too."""
    from wuwei import merge
    red = lambda checks: {c['name'] for c in checks if c['state'] == 'completed'
                          and c['conclusion'] not in ('success', 'neutral', 'skipped')}
    base, names = merge.sha(measured['pr']['base_sha']), red(measured['checks'])
    if names and names <= red(merge.checks_at(host, ref, base, root)):
        return f'base_red: {", ".join(sorted(names))} fails at {base} too'
    return None


def observe(root, host, ref, config, measured, as_of=None):
    """Produce an episode under the shared writer lock from a fresh port read; as_of, the time the
    read started, records a due shepherd duty done when no reply is owed (#906)."""
    data = state.read_state(root)
    me, acks = obligations._owner_login(config), obligations._ledger(data, root=root).get(ref, {})
    current = classify(measured, me, acks)
    if as_of and not obligations._replies(measured['reviews'], measured['threads'], me, acks):
        from wuwei import derive
        for duty in derive.duties(root, config, data=data):
            if duty['duty'] == 'shepherd' and (data['items'].get(duty['item']) or {}).get('pr') == ref:
                state.append_event('duty.done', {'item': duty['item'], 'duty': 'shepherd', 'as_of': as_of,
                                                 'evidence': f'no reply owed on {ref}'}, root)
    reason = _base_red(host, ref, measured, root) if current == 'ci_red' else None
    current = 'base_red' if reason else current
    dispositions = data.get('pr_dispositions', {})
    if not isinstance(dispositions, dict):
        raise ValueError(f'invalid PR disposition ledger; {DAMAGED}')
    disposition = (_verify(root, host, ref, dispositions[ref], config)
                   if ref in dispositions else None)
    row = {'pr': ref, 'state': current, 'disposition': disposition, 'parked': disposition == 'parked',
           'draft': measured['pr']['draft'] is True}
    if reason:
        row['reason'] = reason
    if current in ('changes_requested', 'threads_unanswered'):  # #847: close names what is owed
        row['owed'] = obligations._replies(measured['reviews'], measured['threads'], me, acks)
    now = workspace.now()
    event = {'pr': ref, 'tier': 'silent', 'state': current}
    merged = []

    def update(data):
        value = data.setdefault('watch', {})
        actions, reviews = value.setdefault('actions', {}), value.setdefault('reviews', {})
        if reason:  # #903 review F1: next leaves a head red at its base too to the gates
            value.setdefault('base_red', {})[ref] = measured['pr']['head']
        else:
            value.get('base_red', {}).pop(ref, None)
        if not isinstance(actions, dict) or not isinstance(reviews, dict):
            raise ValueError(f'invalid PR action or review ledger; {DAMAGED}')
        episode = actions.get(ref)
        if episode is not None:
            created, deadline = (obligations._time(episode[key]) for key in ('created_at', 'deadline'))
            if (created > now or deadline <= created or episode['state'] not in ACTIONS
                    or episode['action'] != ACTIONS[episode['state']][0]
                    or episode.get('tier', 'silent') not in ('silent', 'warn', 'page', 'nudge')):  # nudge: an episode written before #801
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
                    'warn' if now > deadline else 'silent')
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
                    merged.append(name)
    state._write_state(update, root, kind='pr.action', payload=event)
    import shutil
    for name in merged:  # #647: the item's scratch goes with the confirmed merge
        # ponytail: the host scratchpad's <item>/ is not removed; the host clears its session scratchpad
        shutil.rmtree(root / workspace.SCRATCH / name, ignore_errors=True)
    from wuwei import dispatch
    for name in merged:  # #842: a merge seen here (the owner merged on the host) runs the done duty
        dispatch.tracker_call(name, 'done', root)
    return row


def evaluate(root, refs=None, read=None):
    """Return per-PR results, preserving each unreadable PR and its reason. read: a dict that
    takes each PR's evidence, so the action that asked acts on this one read (#907)."""
    rows = []
    try:
        if not state.day_started(workspace.day_dir(root)):
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
                as_of = workspace.now().isoformat()
                measured = watch.evidence(host, ref, root)
                if read is not None:
                    read[ref] = measured
                rows.append(observe(root, host, ref, config, measured, as_of))
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
    if not tree:
        return name, None  # #510: shepherding needs no checkout; a fix round asks for one.
    if not isinstance(tree, str):
        raise ValueError(f'invalid item worktree; {DAMAGED}')
    path = (root / tree).resolve(strict=True)
    if not path.is_dir():
        raise ValueError('linked item worktree is missing; create it again with bin/wuwei worktree add <item>, then retry')
    return name, path


def _rebase(root, ref, item, tree, measured, *, resume=False):
    from wuwei import fast_checks, registry
    from wuwei import commit_push
    config = workspace.load_config(root)
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
    started = ((state.read_state(root).get('watch') or {}).get('actions', {}).get(ref) or {}).get('run_head')
    if resume and started != pr['head']:  # #903: the lease is the head --run started from
        raise ValueError(f'PR head moved to {pr["head"][:12]} since --run started from {str(started)[:12]}; '
                         'nothing is pushed, so a teammate commit is not overwritten. Bring the worktree to the '
                         'PR head, then rerun bin/wuwei pr act --run' if started else
                         'no --run started this conflict resolution, so its start head is unknown; reset the '
                         f'worktree to the PR head (git rebase --abort, or git reset --keep {pr["head"]}), '
                         'then run bin/wuwei pr act --run')
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
        def lease(data):
            episode = data.get('watch', {}).get('actions', {}).get(ref)
            if not isinstance(episode, dict) or episode.get('state') != 'conflicted':
                raise ValueError(f'conflict action changed before the rebase; {RACE}')
            episode['run_head'] = pr['head']
        state._write_state(lease, root, payload={'pr': ref, 'run_head': pr['head']})
        fetched = commit_push.data(vcs.fetch(str(tree), config['brief']['remote'],
                                             pr['base'], base_sha, root=root))
        if fetched.get('sha') != base_sha:
            raise ValueError('fetched base differs from current PR base; rerun bin/wuwei pr act --run. If it repeats, the owner checks brief.remote with bin/wuwei config set')
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
    code, reason = _push(root, tree, pr, repo, actual, vcs, config)
    if code:
        print(reason)
        return code
    episode = state.read_state(root).get('watch', {}).get('actions', {}).get(ref)
    if not isinstance(episode, dict) or episode.get('state') != 'conflicted':
        raise ValueError(f'conflict action changed before completion; {RACE}')
    record = {'state': 'conflicted', 'head': head, 'from_head': pr['head'],
              'created_at': episode['created_at'],
              'item': item}
    state._write_state(lambda data: data.setdefault('pr_action_done', {}).update({ref: record}),
                       root, kind='pr.action.done', payload={'pr': ref, **record})
    print(json.dumps({'action': 'done', 'pr': ref, 'item': item, 'head': head}))
    return 0


def _push(root, tree, pr, repo, actual, vcs, config, head=None):
    """(exit, reason) of pushing the item worktree's HEAD to the PR branch. The push context has
    no force refspec; the expected PR head is the lease guard. head: the HEAD that must be pushed."""
    from wuwei import commit_push
    push = commit_push.data(vcs.push_context(str(tree), config['brief']['remote'],
                                             ['HEAD:refs/heads/' + pr['branch']], root=root))
    if head is not None and push['head']['sha'] != head:  # #879 H3: a commit landed after the gate check
        return 1, (f'worktree HEAD {push["head"]["sha"][:12]} is not the head the gates passed ({head[:12]}); '
                   'run bin/wuwei next so the gates read it')
    code, reason = commit_push.push_check(repo, actual, push, root, vcs)
    if code:
        return code, reason
    result = vcs.push(str(tree), config['brief']['remote'], pr['branch'], pr['head'], root=root)
    return result.exit, result.reason or 'push did not complete'


def _gated_push(root, ref, item, tree):
    """#879, #903: a raised or claimed PR's fix reaches its branch only after every gate passed at
    the worktree head (the owner's gates hold on a taken-over PR too); the item is raised again."""
    from wuwei import commit_push, derive, dispatch, merge
    config, data = workspace.load_config(root), state.read_state(root)
    if tree is None:
        raise ValueError(f'--push applies to a PR item with a worktree; run bin/wuwei pr act {ref}')
    phase, gated = data['items'][item]['phase'], derive.head(tree)  # H3: the head the gates read
    found = (dispatch.decide(root, data, config, item) if phase in ('gate', 'delta')
             else {'step': phase, 'why': f'{item} is in {phase}'})
    kind, why = found['step'], found['why']
    if kind != 'raise':
        print(f'{ref}: no push before every gate passes ({why}); run bin/wuwei dispatch next {item}')
        return 1
    pr = merge.checked_pr(registry.load('code_host', config), ref, root)
    vcs = registry.load('vcs', config)
    repo, actual, _ = commit_push.context(tree, {}, {}, root)
    if repo['name'] != pr['repo'] or commit_push.data(vcs.branch(str(tree), root=root))['name'] != pr['branch']:
        raise ValueError(f'item worktree is not on {pr["branch"]} of {pr["repo"]}; switch it to the PR branch, then rerun bin/wuwei pr act {ref} --push')
    remote = config['brief']['remote']
    commit_push.data(vcs.fetch(str(tree), remote, pr['branch'], pr['head'], root=root))
    if commit_push.data(vcs.merge_base(str(tree), pr['head'], root=root))['sha'] != pr['head']:
        # H1: a teammate pushed after the round started; the lease would overwrite it. Merge it first.
        from wuwei.commands import build
        if cap := dispatch.capped(root, config, data, item):  # J1, K1: the owner's resume grants one
            reason = f'round cap {cap} reached: PR {ref} moved to {pr["head"][:12]} again'
            dispatch._parked(root, item, reason)
            print(f'{ref}: {reason}; nothing is pushed; {item} parks and the owner decides on the Owner '
                  f'step card of bin/wuwei plan resume {item}')
            return 1
        action = build.open_fix(item, _merge_feedback(root, ref, f'PR {ref} moved to {pr["head"][:12]} '
                                                      'while this round ran.', pr['branch']), root=root)
        print(f'{ref}: the PR moved to {pr["head"][:12]}, which this worktree does not contain; nothing '
              f'is pushed. A fix round merges it, the gates read it, then pr act --push:')
        print(json.dumps(action, sort_keys=True))
        return 1
    code, reason = _push(root, tree, pr, repo, actual, vcs, config, gated)
    if code:
        print(reason)
        return code
    state._write_state(lambda data: state._move(data, item, 'raised'), root, kind='pr.pushed',
                       payload={'pr': ref, 'item': item})  # next reads the listing again
    print(json.dumps({'action': 'pushed', 'pr': ref, 'item': item}))
    return 0


def _adopt(root, ref, item, pr, why):
    """The exact command that gives the item a checkout of the PR branch (#510, #551)."""
    print(json.dumps(_adoption(root, ref, item, pr, why)))
    return 1


def _adoption(root, ref, item, pr, why):
    from wuwei.shepherd import _settings
    repo = _settings(workspace.load_config(root), ref)  # #901: the one re-entry command
    command = ['bin/wuwei', 'build', 'reconcile', item, '--repo', repo['name'], '--branch', pr['branch']]
    return {'action': 'adopt', 'pr': ref, 'item': item, 'command': shlex.join(command),
            'why': f'{why} needs a checkout of {pr["branch"]}; the item has no worktree',
            'then': f'bin/wuwei pr act {ref}'}


def _merge_feedback(root, ref, why, branch):
    """#879: a claimed PR's conflict or moved head is a fix round: merge (a rebase would rewrite the
    teammate's commits), then the gates, then pr act --push."""
    remote = workspace.load_config(root)['brief']['remote']
    return (f'{why} Merge it: git fetch {remote} {branch}, then git merge FETCH_HEAD; resolve each '
            'conflict, commit the merge and run the fast checks. Do not rebase and do not push: once '
            f'the gates pass, wuwei pr act {ref} --push pushes it.')


def _conflict(root, ref, measured):
    return _merge_feedback(root, ref, f'PR {ref} conflicts with its base {measured["pr"]["base"]}.',
                           measured['pr']['base'])


def launch(root, ref):
    """#879, #903: next's fix step for a raised or claimed PR: the builder launch of its fix round,
    opened only for red checks or a claimed PR's conflict, else the pr act run the planner does
    (#906: a review thread is the shepherd seat's to classify, never a keyword's). It never
    merges, posts, replies or marks a PR ready (review F1)."""
    run = {'action': 'run', 'command': f'wuwei pr act {ref}'}
    read = {}
    _, rows = evaluate(root, [ref], read)
    row, = rows
    if row['exit'] != 1 or row['parked'] or row['state'] not in ('conflicted', 'ci_red') or (
            row['state'] == 'conflicted' and ref not in state.read_state(root)['claimed_prs']):
        return run  # #903: a raised PR's conflict is its rebase run
    try:
        item, tree = _item(root, ref)
        if tree is None:
            return run
        measured = read[ref]
        feedback = _conflict(root, ref, measured) if row['state'] == 'conflicted' else None
        _, action = _fix_round(root, ref, item, tree, measured, feedback)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return run
    if state.read_state(root)['items'][item]['phase'] == 'parked':  # G4: the cap parked it; no run parks again
        return {'action': 'parked', 'reason': action}
    return action if isinstance(action, dict) and action.get('action') in ('launch', 'continue') else run


def _fix(root, ref, item, tree, measured, feedback=None):
    code, out = _fix_round(root, ref, item, tree, measured, feedback)
    print(json.dumps(out, sort_keys=True) if isinstance(out, dict) else out)
    return code


def _fix_round(root, ref, item, tree, measured, feedback=None):
    """(exit, output) of a fix round: its builder action (a dict) or what stops it. The caller
    prints it; next's launch set returns the action (#879)."""
    from wuwei import derive, dispatch
    from wuwei.commands import build
    data = state.read_state(root)
    row = data['items'][item]
    if row['phase'] == 'delta' and (tree is None or derive.head(tree) != measured['pr']['head']):
        return 1, {'action': 'gate', 'item': item, 'gate': 'arch_delta'}  # #903: the fix on top is in review
    red = [check for check in measured['checks'] if check['state'] == 'completed'
           and check['conclusion'] not in ('success', 'neutral', 'skipped')]
    if feedback is None and red:
        feedback = '\n'.join(f'{check["name"]}: {check["conclusion"]} {check.get("url", "")}' for check in red)
    elif feedback is None:
        feedback = '\n'.join(review['body'] for review in measured['reviews']
                             if review['state'] == 'changes_requested' and review['body'].strip())
        if not feedback:
            raise ValueError('review fix request has no feedback; pass the review findings to the fix round, or run bin/wuwei pr state for a fresh action')
    if tree is None:
        return 1, _adoption(root, ref, item, measured['pr'], 'a fix round')
    if item not in data.get('builds', {}):
        # #510: an adopted item has no build to resume; its first builder brief is the fix. #879:
        # it builds in implement, so its gates run before pr act --push puts it on the PR.
        from wuwei import brief
        try:
            if not (workspace.day_dir(root) / 'briefs' / f'{item}-adopted-fix.md').exists():
                brief.write('builder', item, f'{item}-adopted-fix', f'Fix round on {ref}, an adopted PR.\n\n'
                            f'Fix feedback:\n{feedback}', worktree=str(tree), pr=ref, root=root)
            action = build.next_action(item, root=root)
        except brief.Refused as exc:
            return 1, str(exc)
        except build.PortExit as exc:
            return exc.code, f'{ref}: {exc}'
        state.transition(item, 'implement', root)
        return 1, action
    if row['phase'] == 'implement':  # #879: the claimed round in flight answers its current step
        return 1, build.next_action(item, root=root)
    if cap := dispatch.capped(root, workspace.load_config(root), data, item):  # #844: the owner decides on plan resume's card
        reason = f"round cap {cap} reached: PR {ref} still fails: {' '.join(feedback.split())[:200]}"
        dispatch._parked(root, item, reason)
        return 1, (f'{ref}: {reason}; {item} parks and the owner decides on the Owner step card of '
                   f'bin/wuwei plan resume {item}')
    return 1, build.open_fix(item, feedback, root=root)


def _owed(root, ref, measured):
    """[(surface, target, thread or None, the comment answered)] of every owed reply, in order."""
    me = obligations._owner_login(workspace.load_config(root))
    owed = obligations._replies(measured['reviews'], measured['threads'], me,
                                obligations._ledger(state.read_state(root), root=root).get(ref, {}))
    return [(surface, target, *_latest(measured, surface, target))
            for surface, target in (key.split(':', 1) for key in owed)
            if surface in ('thread', 'review', 'comment', 'bot-p1')]  # F4: a P1 bot thread is answered too


def _latest(measured, surface, target):
    """(thread or None, the comment an owed reply answers) for one owed key's surface and id."""
    thread = (next(row for row in measured['threads']['threads'] if row['id'] == target)
              if surface in ('thread', 'bot-p1') else None)
    latest = (thread['comments'][-1] if thread else next(row for row in
              (measured['reviews'] if surface == 'review' else measured['threads']['comments'])
              if str(row['id']) == target))
    return thread, latest


def _thread(root, ref, item, tree, measured, reply=None, target=None, fix=None, scope=None):
    """#906: the owed reply named by target (else the first) and the shepherd seat's answer to it:
    a reply posts first; a fix opens a round; a scope decision asks the owner's card. With none of
    them it prints the reply action; it never reads intent from the words."""
    owed = _owed(root, ref, measured)
    if not owed:
        raise ValueError('no unanswered review thread found; drop --reply, or check the PR with bin/wuwei pr state')
    chosen = next((row for row in owed if target in (None, row[1])), None)
    if chosen is None:
        raise ValueError(f'{target} is not owed a reply; run bin/wuwei pr act {ref} for the owed ones')
    surface, target, thread, latest = chosen
    text = latest['body']
    if not (fix if fix is not None else scope or 'reason').strip():
        raise ValueError('--fix and --scope need the reason against the item promise; pass it, for example '
                         f'bin/wuwei pr act {ref} --thread {target} --fix "<what the item promised and what is wrong>"')
    if reply is not None and surface == 'bot-p1':  # D3: no reply clears it; the fix outdates it
        raise ValueError(f'{target} is a P1 bot thread: use --fix; a P1 bot thread clears when the fix makes it outdated')
    if reply is not None:
        if not reply.strip():
            raise ValueError('reply needs a nonempty body; pass a one-line answer: bin/wuwei pr act --reply "<answer>"')
        # #838: posted through the code-host port, which runs the canary check and the lint.
        return obligations.reply(ref, surface, thread['comments'][0]['id'] if thread else latest['id'], reply, root)
    feedback = lambda why: f'Review {surface} {target} on {ref}: {text}\nShepherd: {why}'
    if fix is not None:
        return _fix(root, ref, item, tree, measured, feedback=feedback(fix))
    answer = {}
    if scope is not None:
        from wuwei import sessions  # the owner decides a scope change on the card of this command
        command = f'bin/wuwei pr act {ref} --thread {target} --scope {shlex.quote(scope)}'
        detail = (f'The shepherd asks a scope decision on {ref} ({target}): {json.dumps(text[:200])}; '
                  f'its reason: {scope[:200]}. Yes makes it in a fix round; No leaves the thread for you.')
        from wuwei import dispatch  # F6: a Yes opens one round; after it the same command asks again
        rounds = dispatch.rounds_used(state.read_state(root), item)
        token = f'{obligations._fingerprint(latest)[:12]}-r{rounds}'
        no = 'The planner replies that the thread is deferred to you.'
        if sessions.owner_answer(root, command, token) != 'No':
            if (refusal := sessions.needs_owner(root, command, detail, token, no)) is None:
                return _fix(root, ref, item, tree, measured, feedback=feedback(scope))
            print(refusal, file=sys.stderr)
            return 1
        answer = {'option': 'defer'}
    print(json.dumps({'action': 'reply', 'pr': ref, 'surface': surface, 'thread': target, 'question': text,
                      'owed': [f'{row[0]}:{row[1]}' for row in owed], **answer}))
    return 1


def _ready(root, ref, ready):
    """#726: mark an owned draft ready when asked or once the owner cleared owner_merge."""
    from wuwei import merge
    items = [row for row in state.read_state(root)['items'].values() if row.get('pr') == ref]
    cleared = any(row.get('owner_merge') is not None and merge.owner_hold(row) is None for row in items)
    if not (ready or cleared):
        return None
    host = registry.load('code_host', workspace.load_config(root))
    merge.read(host.ready, ref, root=root)
    if merge.checked_pr(host, ref, root)['draft']:
        raise ValueError('PR is still a draft after ready; run bin/wuwei pr state, then retry')
    print(json.dumps({'action': 'ready', 'pr': ref}))
    return 0


def act(root, ref, *, run=False, complete=False, reply=None, ready=False, push=False, thread=None,
        fix=None, scope=None):
    """Execute safe PR actions and surface work requiring a builder or owner."""
    ref = pull_request(ref)
    read = {}
    _, rows = evaluate(root, [ref], read)
    row, = rows
    if row['exit'] == 2:
        print(row['reason'])
        return 2
    if push:
        try:
            return _gated_push(root, ref, *_item(root, ref))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f'{ref}: PR action unmeasured: {exc}')
            return 2
    if ready and not row.get('draft'):
        print(f'{ref}: already ready for review')
        return 0
    if row.get('draft') and row['state'] not in ('closed', 'merged'):
        try:
            if (code := _ready(root, ref, ready)) is not None:
                return code
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f'{ref}: PR action unmeasured: {exc}')
            return 2
    if row['exit'] == 0:
        return 0
    if (run or complete) and row['state'] != 'conflicted':
        print('--run and --complete require a conflicted PR')
        return 2
    if (reply, thread, fix, scope) != (None,) * 4 and row['state'] not in ('changes_requested', 'threads_unanswered'):
        print('--reply, --thread, --fix and --scope require an unanswered review question')
        return 2
    if row['parked'] or row['state'] in ('merged', 'waiting'):
        return 0
    if row['state'] == 'approved':
        from wuwei import merge
        result = merge.execute(ref, root=root)
        if result.exit:
            print(f'{ref}: {result.reason}')  # #816: the wait, or the owner's Owner step card
        return result.exit
    if row['state'] == 'review_stale':
        from wuwei import shepherd
        return shepherd.post_review_request(root, ref)
    if row['state'] in ('conflicted', 'ci_red', 'changes_requested', 'threads_unanswered'):
        try:
            item, tree = _item(root, ref)
            measured = read[ref]
            if row['state'] == 'conflicted' and tree is None:
                return _adopt(root, ref, item, measured['pr'], 'a rebase')
            if row['state'] == 'conflicted':
                if run or complete:
                    return _rebase(root, ref, item, tree, measured, resume=complete)
                if ref in state.read_state(root)['claimed_prs']:  # #879: a builder rebases a taken-over PR
                    return _fix(root, ref, item, tree, measured, feedback=_conflict(root, ref, measured))
                print(json.dumps({'action': 'rebase', 'pr': ref, 'item': item,
                                  'worktree': str(tree), 'steps': row['dispatch']['steps'],
                                  'run': f'wuwei pr act {ref} --run',
                                  'after_conflict': f'wuwei pr act {ref} --complete'}))
                return 1
            if run or complete:
                raise ValueError(f'--run and --complete apply only to a conflicted PR; run bin/wuwei pr act {ref} without them')
            if row['state'] == 'ci_red':
                return _fix(root, ref, item, tree, measured)
            return _thread(root, ref, item, tree, measured, reply, thread, fix, scope)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f'{ref}: PR action unmeasured: {exc}')
            return 2
    print(f'{ref}: {row["action"]}')
    return 1


def _pending(root):
    """{(item, kind, why): line} of every step wuwei next returns for an item with a PR."""
    from wuwei import derive
    from wuwei.commands.next import step
    data, row = state.read_state(root), step(root)
    pulls = derive.listing(workspace.day_dir(root))['pulls']
    prs = {name: item['pr'] for name, item in data['items'].items() if item.get('pr')}
    # F5: a merge or a close on the host is a step even when it brings no launch or duty
    ended = {name: 'merged' if data['items'][name]['phase'] == 'merged' else (pulls.get(pr) or {}).get('state')
             for name, pr in prs.items()}
    steps = [(name, state_, f'PR {prs[name]} is {state_}') for name, state_ in ended.items()
             if state_ in ('merged', 'closed')]
    if row['state'] == 'set':
        steps += [(launch['item'], launch['kind'], launch['why']) for launch in row['launches']]
        steps += [(duty['item'], duty['duty'], duty['prompt']) for duty in row['duties']]
        steps += [(row['decision']['item'], 'owner', row['decision']['why'])] if row['decision'] else []
    return {(item, kind, why): f'{item} {kind} {prs[item]}: {why}' for item, kind, why in steps if item in prs}


def _reset(failed):
    """Seconds until the reset a #899 rate-limit refusal names (GitHub rate limit until HH:MM:SS UTC),
    else None. A time more than 12 hours behind is tomorrow's."""
    from datetime import timezone
    found = re.search(r'rate limit until (\d\d):(\d\d):(\d\d) UTC', failed or '')
    if not found:
        return None
    now = workspace.now().astimezone(timezone.utc)
    at = now.replace(hour=int(found[1]), minute=int(found[2]), second=int(found[3]), microsecond=0)
    at += timedelta(days=1) if at < now - timedelta(hours=12) else timedelta()
    return max(0, int((at - now).total_seconds()) + 1)


def wait(root, timeout):
    """#887: block until a raised or claimed PR changes in a way wuwei next acts on; print one line
    per new step (item, kind, PR, why) and exit 1, or exit 0 at the timeout. A tick reads the listing
    only of the repositories holding such a PR, only once pr.poll_seconds old (derive.stale): one
    GraphQL request per repository, whatever the PR count. A rate limit holds it until the reset.
    ponytail: one request per repository; an aliased multi-repository query if days carry many."""
    import time
    from wuwei import derive
    config = workspace.load_config(root)
    deadline = workspace.now() + timedelta(seconds=timeout)
    seen = _pending(root)  # what next saw: a change before the first read is still reported
    while True:
        data, pulls = state.read_state(root), derive.listing(workspace.day_dir(root))['pulls']
        repos = {ref.rsplit('#', 1)[0] for ref in data['raised_prs'] + data['claimed_prs']
                 if (pulls.get(ref) or {}).get('state') in (None, 'open')}
        if not repos:
            print('wuwei pr wait: no raised or claimed PR to wait on', file=sys.stderr)
            return 0
        due = [name for name in derive.stale(root, config, data) if name in repos]
        failed = derive.refresh(root, config, due) if due else None
        found = _pending(root)
        if lines := [line for key, line in found.items() if key not in seen]:
            print('\n'.join(lines), flush=True)
            return 1
        seen = found  # a step that leaves and comes back is new again
        left = (deadline - workspace.now()).total_seconds()
        if left <= 0:
            return 0
        pause = max(config['pr']['poll_seconds'], _reset(failed) or 0)
        if failed:
            print(f'wuwei pr wait: listing not read ({failed}); next read in {pause} s', file=sys.stderr)
        time.sleep(min(pause, left))
