"""Raise and shepherd PRs through the existing ports and policies."""

from fnmatch import fnmatchcase
import json
import re
import sys

from wuwei import merge, obligations, registry, state, workspace
from wuwei.references import pull_request, repository
from wuwei.registry import Result
from wuwei.exits import DAMAGED


ERRORS = merge.ERRORS


def _settings(config, ref):
    repo = ref.split('#')[0]
    settings = next((row for row in config['repos'] if row['name'] == repo), None)
    if settings is None:
        raise ValueError('PR repository is not configured; the owner adds it with bin/wuwei config add-repo in a host terminal')
    return settings


def _source(path, config):
    if not isinstance(path, str) or not path or path.startswith('/') or '..' in path.split('/'):
        raise ValueError(f'invalid changed source path; {DAMAGED}')
    return not any(fnmatchcase(path, pattern) for pattern in config['shepherd']['source_exclude'])


def _logins(selected):
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', login) for login in selected):
        raise ValueError(f'invalid reviewer login; {DAMAGED}')
    return selected


def _rank(root, config, repo, branch, paths, author, source_path=None, explain=None):
    """Reviewers for changed paths; explain, when a list, receives the reasoning lines."""
    asked, explain = explain is not None, [] if explain is None else explain
    override = repo['shepherd']['reviewers'] or config['shepherd']['reviewers']
    if override:  # The owner's list: no history, no lead, no minimum, no email check.
        explain.append('shepherd.reviewers: ' + ' '.join(override))
        return _logins([login for login in dict.fromkeys(override)
                        if login.casefold() != author.casefold()])
    merge.require(paths, 'no changed source paths for reviewer selection; run '
                  "bin/wuwei config set shepherd.reviewers '[\"login\"]'")
    excluded = {login.casefold() for login in (author, *config['shepherd']['reviewers_exclude'])}
    mapping = config['shepherd']['authors']
    vcs = registry.load('vcs', config)
    host = registry.load('code_host', config)
    cache, fresh, unresolved = dict(state.read_state(root).get('author_logins', {})), {}, set()

    def login_of(email):
        """shepherd.authors, then today's cache, then the code host; None when it cannot resolve."""
        if email in mapping:
            return mapping[email]['login']
        if email not in cache:
            result = host.author_login(repo['name'], email, root=root)
            data = result.data
            if (result.exit == 0 and isinstance(data, dict) and 'message' not in data
                    and 'errors' not in data and isinstance(data.get('login', ''), str)):
                cache[email] = fresh[email] = data.get('login') or None
            elif result.exit and any(text in (result.reason or '') for text in
                                     ('author login unavailable', 'invalid author email')):
                cache[email] = fresh[email] = None
            else:
                raise ValueError(result.reason or 'author login unmeasured; retry; if it repeats, run '
                                 'bin/wuwei doctor, which tests the code host adapter')
        return cache[email]

    def tally(rows):
        if not isinstance(rows, list):
            raise ValueError(f'invalid authorship evidence; {DAMAGED}')
        counts = {}
        for row in rows:
            email, commits = row['email'].casefold(), row['commits']
            if not isinstance(email, str) or '@' not in email or type(commits) is not int or commits < 1:
                raise ValueError('invalid authorship record; run bin/wuwei doctor, which names the record')
            login = login_of(email)
            if login is None:
                unresolved.add(email.split('@', 1)[0])
            elif login.casefold() not in excluded and not login.casefold().endswith('[bot]'):
                counts[login] = counts.get(login, 0) + commits
        return counts

    source = str(source_path or (root / repo['path']).resolve())
    windows = config['shepherd']['author_windows_days']
    if not windows or windows != sorted(set(windows)):
        raise ValueError('authorship windows must increase; the owner sets increasing shepherd.author_windows_days with bin/wuwei config set in a host terminal')
    for days in (*windows, 0):
        counts = tally(merge.read(vcs.authorship, source, branch, paths, days, root=root))
        ranked = selected = sorted(counts, key=lambda login: (-counts[login], login))
        if len(selected) >= max(2, config['shepherd']['min_reviewers']):
            if (len(selected) >= 3 and counts[selected[1]] - counts[selected[2]]
                    <= config['shepherd']['tie_commits']):
                selected = selected[:3]
            else:
                selected = selected[:max(2, config['shepherd']['min_reviewers'])]
            break
    lead = config['shepherd']['lead_login']
    if lead and lead.casefold() not in excluded and lead not in selected:
        selected = [*selected, lead]  # A new list: ranked stays the ranking.
    explain.append(f'window: {days} days' if days else 'window: all history')
    if asked:  # Per-path counts are read only when asked for.
        by_path = {path: tally(merge.read(vcs.authorship, source, branch, [path], days, root=root))
                   for path in paths}
        for login in ranked:
            detail = ', '.join(f'{path} {by_path[path][login]}' for path in paths if login in by_path[path])
            explain.append(f'{login} {counts[login]}: {detail}' + ' (selected)' * (login in selected))
    if lead in selected and lead not in ranked:
        explain.append(f'{lead}: shepherd.lead_login (selected)')
    if unresolved:
        explain.append('unresolved: ' + ' '.join(sorted(unresolved)))
    if fresh:
        state._write_state(lambda data: data.setdefault('author_logins', {}).update(fresh),
                           root, reserved=False)
        for email in (email for email, login in fresh.items() if login is None):
            state.append_event('reviewer.unresolved',
                               {'repo': repo['name'], 'author': email.split('@', 1)[0]}, root)
    if selected and len(selected) < config['shepherd']['min_reviewers']:
        from wuwei.guards import REVIEWER_WAYS_OUT
        raise merge.Refused('fewer eligible reviewers than shepherd.min_reviewers; run ' + REVIEWER_WAYS_OUT)
    _logins(selected)
    # Logins named in shepherd.authors are checked against the code host; owner-named and
    # host-resolved logins are checked by the requested == selected comparison on request.
    emails = {row['login']: email for email, row in mapping.items()}
    for login in selected:
        if login in emails:
            verified = merge.read(host.author_login, repo['name'], emails[login], root=root)
            if verified['login'] != login:
                raise ValueError('configured reviewer login differs from code host; the owner fixes its login under shepherd.authors with bin/wuwei setup in a host terminal')
    return selected


def select_reviewers(root, ref, explain=None):
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    ref = pull_request(ref)
    settings = _settings(config, ref)
    host = registry.load('code_host', config)
    pr = merge.checked_pr(host, ref, root)
    files = merge.read(host.files, ref, root=root)
    if len(files) != pr['changed_files']:
        raise ValueError('incomplete changed files; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter')
    paths = [row['path'] for row in files if _source(row['path'], config)]
    return _rank(root, config, settings,
                 config['brief']['remote'] + '/' + pr['base'], paths, pr['author'], explain=explain)


def ping_gate(root, ref):
    """Production gate order: mergeability, CI, required contexts, bot, obligations."""
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        ref = pull_request(ref)
        settings = _settings(config, ref)
        host = registry.load('code_host', config)
        pr = merge.checked_pr(host, ref, root)
        merge.require(pr['state'] == 'open' and not pr['draft'], 'PR is not open for review')
        merge.require(pr['merge_state'] != 'dirty', 'mergeable_state=dirty: no CI can run')
        merge.require(pr['merge_state'] != 'behind', 'mergeable_state=behind: update base first')
        if pr['mergeable'] is None or pr['merge_state'] == 'unknown':
            raise ValueError('mergeability unmeasured; wait a minute and retry; if it persists, run bin/wuwei doctor')
        checks = merge.checks_at(host, ref, pr['head'], root)
        ignored = config['shepherd']['review_gate_check']
        checks = [row for row in checks if row['name'] != ignored]
        protection_result = host.protection(ref.split('#')[0], pr['base'], root=root)
        missing = protection_result.exit == 2 and 'branch protection absent' in protection_result.reason
        if protection_result.exit and not missing:
            raise ValueError(protection_result.reason or 'branch protection unmeasured; retry; if it repeats, run bin/wuwei config check, which reads the protection and names the source')
        if not missing and (not isinstance(protection_result.data, dict) or
                            'message' in protection_result.data or 'errors' in protection_result.data):
            raise ValueError('branch protection error body; retry; if it repeats, run bin/wuwei doctor, which tests the code host adapter')
        if ((missing or not protection_result.data.get('required_checks'))
                and pr['base'] != settings['default_branch']):
            protection_result = host.protection(ref.split('#')[0], settings['default_branch'], root=root)
        fallback = settings['review_required_checks']
        missing = protection_result.exit == 2 and 'branch protection absent' in protection_result.reason
        if protection_result.exit and not missing:
            raise ValueError(protection_result.reason or 'branch protection unmeasured; retry; if it repeats, run bin/wuwei config check, which reads the protection and names the source')
        if missing and fallback:
            protection = {'required_checks': []}
        else:
            protection = merge.read(lambda *args, root: protection_result, root=root)
        if not protection['required_checks'] and fallback:
            protection = {**protection, 'required_checks': [
                {'name': name, 'app_id': None} for name in fallback]}
        protection = {**protection, 'required_checks': [row for row in protection['required_checks']
                       if row['name'] != ignored]}
        merge.green(checks, protection)
        discussion = merge.read(host.threads, ref, root=root)
        obligations._records(discussion['comments'])
        for thread in obligations._list(discussion['threads']):
            obligations._records(thread['comments'])
        merge.bot_evidence(config, settings['merge'], discussion, ref, pr['head'], root)
        reviews = obligations._records(merge.read(host.reviews, ref, root=root), reviews=True)
        me = obligations._owner_login(config)
        acks = obligations._ledger(state.read_state(root)).get(ref, {})
        merge.require(not obligations._replies(reviews, discussion, me, acks),
                      'review replies are owed')
        fresh = merge.checked_pr(host, ref, root)
        merge.require(fresh['head'] == pr['head'] and fresh['merge_state'] == pr['merge_state'],
                      'PR changed during ping gate')
        return Result(0, {'pr': pr, 'checks': checks})
    except merge.Refused as exc:
        return Result(1, reason=str(exc))
    except ERRORS as exc:
        return Result(2, reason=f'ping gate unmeasured: {exc}')


def _mentions(config, reviewers):
    by_login = {row['login']: row['mention'] for row in config['shepherd']['authors'].values()}
    if any(login not in by_login or not re.fullmatch(r'[A-Z0-9]+', by_login[login])
           for login in reviewers):
        raise ValueError('reviewer needs a configured chat mention; the owner adds its mention under shepherd.authors with bin/wuwei setup in a host terminal')
    return ' '.join('<@' + by_login[login] + '>' for login in reviewers)


def post_review_request(root, ref):
    """Request and post the same reviewer set only while the fresh gate clears."""
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        ref = pull_request(ref)
        if ref not in state.read_state(root)['raised_prs'] + state.read_state(root)['claimed_prs']:
            raise ValueError('PR is not owned today; claim it with bin/wuwei pr claim, then retry')
        gate = ping_gate(root, ref)
        if gate.exit:
            print(gate.reason)
            return gate.exit
        reviewers = state.read_state(root).get('pr_reviewers', {}).get(ref)
        if reviewers is None:
            reviewers = select_reviewers(root, ref)
        if not isinstance(reviewers, list) or len(set(reviewers)) != len(reviewers):
            raise ValueError('invalid selected reviewer record; run bin/wuwei doctor, which names the record')
        if reviewers:
            host = registry.load('code_host', config)
            requested = merge.read(host.request_reviewers, ref, reviewers, root=root)
            if set(requested['requested']) != set(reviewers):
                raise ValueError('requested reviewer set differs from selected set; retry once, then request the missing reviewers on the PR')
        state._write_state(lambda data: data.setdefault('pr_reviewers', {}).update({ref: reviewers}),
                           root, reserved=False, kind='pr.reviewers_selected',
                           payload={'pr': ref, 'reviewers': reviewers})
        if not reviewers:
            print(obligations.SOLO)
            return 0
        gate = ping_gate(root, ref)
        if gate.exit:
            print(gate.reason)
            return gate.exit
        channel = config['shepherd']['review_channel']
        if not re.fullmatch(r'[A-Z0-9]+', channel):
            raise ValueError('shepherd.review_channel is required; the owner sets it with bin/wuwei config set in a host terminal')
        pr = gate.data['pr']
        text = f'PR #{pr["number"]} ready for review: <{pr["url"]}|#{pr["number"]}> {_mentions(config, reviewers)}'
        chat = registry.load('chat', config)
        posted = chat.post(channel, text, None, root=root)
        if posted.exit:
            print(posted.reason or 'review post was not sent')
            return posted.exit
        if posted.data['channel'] != channel or not re.fullmatch(r'[0-9]+\.[0-9]+', posted.data['ts']):
            raise ValueError(f'invalid chat post confirmation; {DAMAGED}')
        permalink = f'https://slack.com/archives/{channel}/p{posted.data["ts"].replace(".", "")}'
        def record(data):
            data.setdefault('channel_posts', []).append({'pr': ref, 'status': 'posted',
                'url': permalink, 'reviewers': reviewers, 'head': pr['head'],
                'posted_at': workspace.now().isoformat()})
        state._write_state(record, root, reserved=False, kind='pr.review_posted',
                           payload={'pr': ref, 'head': pr['head'], 'reviewers': reviewers})
        return 0
    except merge.Refused as exc:
        print(exc)
        return 1
    except ERRORS as exc:
        print(f'review post unmeasured: {exc}')
        return 2


def raise_pr(root, repo_name, base, title, body, item):
    """Raise a prepared, pushed branch after the existing pre-PR gate."""
    try:
        from wuwei.guards.pr import gate_check
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        repo_name = repository(repo_name)
        settings = _settings(config, repo_name + '#1')
        if not all(isinstance(v, str) and v.strip() for v in (base, title, body, item)):
            raise ValueError('raise needs base, title, body and item; pass the base, title, body and item')
        data = state.read_state(root)
        merge.require(item in data['items'] and item in data['approved_items'],
                      'PR item must be in the approved plan')
        merge.require(data['items'][item].get('pr') is None, 'item already links another PR')
        if config['adapters']['code_host'] == 'none':
            raise ValueError('code_host adapter is none; configure github; the owner sets adapters.code_host to github with bin/wuwei config set in a host terminal')
        tree = data['items'][item].get('worktree')
        if not isinstance(tree, str) or not tree:
            raise ValueError('item worktree is not recorded; write a brief with --worktree')
        repo_path = (root / tree).resolve()
        vcs = registry.load('vcs', config)
        configured_path = (root / settings['path']).resolve()
        if repo_path != configured_path:
            common = merge.read(vcs.repo_context, str(repo_path), root=root).get('common_dir')
            configured_common = merge.read(vcs.repo_context, str(configured_path), root=root).get('common_dir')
            merge.require(isinstance(common, str) and bool(common) and common == configured_common,
                          'item worktree does not belong to the raised repository')
        head = merge.read(vcs.head, str(repo_path), root=root)['sha']
        merge.sha(head)
        code, reason = gate_check(root, repo_path, config, sha=head, item=item)
        use = None
        if code == 1:  # #530: a warning, the owner's card or (strict) the refusal
            import shlex
            from wuwei import grants, sessions
            argv = ['bin/wuwei', 'pr', 'raise', repo_name, '--item', item]
            payload = {'session_id': sessions.current() or '', 'cwd': str(repo_path),
                       'tool_input': {'command': shlex.join(argv)}}
            code, reason = grants.evidence(payload, root, config, argv, reason, repo_name, record=True)
            use = reason if callable(reason) else None
        if code:
            print(reason)
            return code
        from wuwei import dispatch, outward
        row = data['items'][item]
        if row['gates']:
            body += f'\n\nReview tier: {row["gates"]["tier"]} ({", ".join(dispatch.gate_set(row))})'
        if hold := merge.owner_hold(row):  # #678: the PR's record of who keeps the merge
            body += f'\n\nOwner merges: owner_merge set by {hold[0]} on {hold[1]}'
        if not settings['fast_checks'] and 'checks: none configured' not in body:  # #600 acceptance 1
            body = body.rstrip() + '\n\nchecks: none configured'
        code, reason = outward.lint(title + '\n' + body, 'code_host', config, root=root)
        if not code:
            code, reason = outward.humanize_lint({'title': title, 'body': body}, root, config, {'code_host'})
        if code:
            print(reason)
            return code
        identity = merge.read(vcs.identity, str(repo_path), root=root)
        expected = settings['identity']
        if expected['email'] and identity['email'] != expected['email']:
            raise merge.Refused('repository identity does not match configured owner; use a worktree from bin/wuwei worktree add, which sets repos.<n>.identity')
        if expected['name'] and identity['name'] != expected['name']:
            raise merge.Refused('repository identity does not match configured owner; use a worktree from bin/wuwei worktree add, which sets repos.<n>.identity')
        if any(identity[key] != {'name': identity['name'], 'email': identity['email']}
               for key in ('author', 'committer')):
            raise merge.Refused('author and committer identity differ from configured repository identity; use a worktree from bin/wuwei worktree add, which sets repos.<n>.identity')
        branch = config['brief']['remote'] + '/' + base
        base_sha = merge.read(vcs.merge_base, str(repo_path), branch, root=root)['sha']
        merge.sha(base_sha)
        changes = merge.read(vcs.diff_stat, str(repo_path), base_sha, head, root=root)
        paths = [row['path'] for row in changes if _source(row['path'], config)]
        author = obligations._owner_login(config)
        reviewers = _rank(root, config, settings, branch, paths, author, repo_path)
        host = registry.load('code_host', config)
        head_branch = merge.read(vcs.branch, str(repo_path), root=root)['name']
        created = merge.read(host.create_pr, {'repo': repo_name, 'base': base,
            'head': head_branch, 'title': title, 'body': body}, root=root)
        ref = pull_request(f'{repo_name}#{created["number"]}')
        pr = merge.checked_pr(host, ref, root)
        if pr['head'] != head or pr['url'] != created['url']:
            raise ValueError('created PR does not match checked head and URL; run bin/wuwei pr state to read the PR before any retry')
        state.record_pr(root, item, ref, raised=True, head=head, reviewers=reviewers)
        if hold:
            merge.read(host.label, ref, merge.LABEL, True, root=root)
        if use:
            use()
        moved = dispatch.tracker_call(item, 'in_review', root)
        if config['adapters']['tracker'] != 'none' and moved.exit:  # #670: name why
            print(f'tracker: {moved.reason}', file=sys.stderr)
        if reviewers:
            requested = merge.read(host.request_reviewers, ref, reviewers, root=root)
            if set(requested['requested']) != set(reviewers):
                raise ValueError('reviewer request could not be verified; run bin/wuwei pr state to read the PR before any retry')
        print(ref)
        if not reviewers:
            print(obligations.SOLO)
        return 0
    except (merge.Refused, state.StateError) as exc:
        print(exc)
        return 1
    except ERRORS as exc:
        print(f'PR raise unmeasured: {exc}; check adapters.vcs and adapters.code_host, then retry wuwei pr raise')
        return 2


def claim_pr(root, ref, item=None, goal=None):
    """Claim a fresh, externally verified PR. With no item in the plan, create one (source
    adopted, #510) and adopt the PR branch's worktree when a clean one exists."""
    import json
    from pathlib import Path
    import sys
    from wuwei import plan
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        only = config['repos'][0]['name'] if len(config['repos']) == 1 else None
        ref = merge.reference(ref, root, config, repo=only)
        repo = _settings(config, ref)
        host = registry.load('code_host', config)
        pr = merge.checked_pr(host, ref, root)
        merge.require(pr['state'] == 'open' and not pr['merged'], 'PR is not open')
        data = state.read_state(root)
        linked = next((name for name, row in data['items'].items() if row.get('pr') == ref), None)
        item = item or linked or f'PR-{pr["number"]}'
        if item not in data['items']:
            goal = goal or (data['goals'][0] if len(data['goals']) == 1 else None)
            merge.require(goal, f'name the goal: bin/wuwei pr claim {ref} --goal <one of '
                                f'{", ".join(data["goals"]) or "the approved goals"}>')
            plan.add(item, root, goal=goal, title=pr['title'], source='adopted')
        state.record_pr(root, item, ref, raised=False, head=pr['head'])
        print(ref)
        if not state.read_state(root)['items'][item].get('worktree'):
            vcs = registry.load('vcs', config)
            path = workspace.branch_worktree(vcs, (root / Path(repo['path']).expanduser()).resolve(),
                                             pr['branch'], root)
            if path:
                try:
                    print(json.dumps(workspace.adopt_worktree(root, item, path, vcs)))
                except state.StateError as exc:
                    print(f'worktree not adopted: {exc}', file=sys.stderr)
        return 0
    except (merge.Refused, state.StateError) as exc:
        print(exc)
        return 1
    except ERRORS as exc:
        print(f'PR claim unmeasured: {exc}')
        return 2


_STOP = ' Never run wuwei merge. Stop after this action and report what ran.'
_TRIAGE = ('Run wuwei pr act {ref}. For a reply action run wuwei pr act {ref} --reply '
           '"<one-line acknowledgement>", which is stored as a draft; for owner_decision or '
           'fix_round stop.')
# The headless shepherd's brief per mechanical PR state; approved never starts a seat.
HEADLESS = {
    'conflicted': ('Run wuwei pr act {ref} --run. If it stops on a conflict, resolve the conflict '
                   'in the item worktree named in this brief and run wuwei pr act {ref} --complete.'),
    'ci_red': ('Run wuwei pr act {ref}; it opens the fix round brief with the failed checks as '
               'feedback. Do not build the fix.'),
    'changes_requested': _TRIAGE,
    'threads_unanswered': _TRIAGE,
    'review_stale': 'Run wuwei pr act {ref}; it re-requests review and drafts the channel post.',
}


def pending(root):
    """(ref, episode) pairs a headless shepherd would act on, oldest first, each episode once."""
    from wuwei import watch
    actions = watch.saved(root).get('actions', {})
    parked = {ref for ref, row in state.read_state(root).get('pr_dispositions', {}).items()
              if row.get('kind') == 'parked'}
    done = {(row['payload'].get('pr'), row['payload'].get('episode'))
            for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == 'shepherd.dispatched'}
    return sorted(((ref, episode) for ref, episode in actions.items()
                   if episode['state'] in HEADLESS and ref not in parked
                   and (ref, episode['created_at']) not in done),
                  key=lambda pair: pair[1]['created_at'])


def headless(root, ref, episode, *, runtime=None):
    """One headless shepherd seat for one PR action episode: 0 ran, 1 refused, 2 could not run."""
    import json
    import uuid
    from wuwei import brief, pr_actions, sessions, watch
    from wuwei.guards import agent_launch
    record = {'pr': ref, 'state': episode['state'], 'episode': episode['created_at']}
    # Recorded before any side effect: a crash drops an episode, it never runs one twice.
    state.append_event('shepherd.dispatched', record, root)

    def finish(code, text, **extra):
        watch.mark_wake(root, prs=[ref], summaries=[f'PR {ref}: shepherd {record["state"]}: {text}'],
                        kind='shepherd.finished', payload={**record, 'exit': code, **extra})
        return code

    try:
        item, tree = pr_actions._item(root, ref)
        name = 'shepherd-' + uuid.uuid4().hex[:12]
        relative = brief.write('shepherd', item, name, HEADLESS[record['state']].format(ref=ref) + _STOP,
                               pr=ref, root=root)
        # Fixed selection, as remote commands: headless sessions exist only in the Claude adapter.
        runtime = runtime or registry.load('runtime', {'adapters': {'runtime': 'claude'}})
        job = runtime.dispatch('shepherd', str(root / relative), str(tree or root), True, root=root)
        if job.exit or not isinstance(job.data, dict):
            reason = job.reason or 'invalid dispatch result'
            return finish(job.exit or 2, f'not started: {reason}', reason=reason)
        code, reason = agent_launch.check({'cwd': str(root), 'tool_input': {
            'subagent_type': 'wuwei:shepherd', 'name': name, 'description': f'shepherd {ref}',
            'prompt': job.data['prompt']}})
        if code:
            return finish(code, f'not started: {reason}', reason=reason)
        tools = json.loads((registry.ADAPTERS.parent / 'agents/allowlist.json').read_text(encoding='utf-8'))['shepherd']
        try:
            result = runtime.headless(job.data['prompt'], None, tools, root=root,
                                      variables={'WUWEI_SEAT_ROLE': 'shepherd'})
        finally:
            state.stop_seat(name, root)
        if result.exit == 2 or not isinstance(result.data, dict):
            reason = result.reason or 'invalid headless result'
            return finish(2, f'turn failed: {reason}', reason=reason)
        sid = result.data['session_id']
        sessions.touch(root, sid, hook=f'shepherd {record["state"]}', cwd=str(root), role='shepherd')
        from wuwei.guards.decision import unrecorded
        code, reason = unrecorded(str(result.data.get('result', '')), root)
        if code:
            return finish(code, f'asked without a decision record: {reason}', reason=reason, session=sid)
        return finish(result.exit, f'turn ended (exit {result.exit}, session {sid[:8]})', session=sid)
    except brief.Refused as exc:
        return finish(1, f'not started: {exc}', reason=str(exc))
    except watch.ERRORS as exc:
        return finish(2, f'not started: {exc}', reason=str(exc))


# #511: the CLI-only shepherd that runs without a session (no model, no seat, no reply).
HEADLESS_SECONDS = 900  # ponytail: fixed interval; a config key if an owner needs another


def owning_day(root, before=None):
    """The newest approved day directory (today included), or the newest one before that name.
    The watch writes clock state into every day, so state alone never makes a day the owner."""
    from wuwei import watch
    return next((day for day in watch.days(root) if (before is None or day.name < before)
                 and (day / 'state.json').is_file() and state.read_state(directory=day).get('gate_approved')), None)


def _live(root):
    """True when a registered, fresh planner session owns this day's state (heartbeat's rule)."""
    from wuwei import heartbeat
    return bool(state.read_state(root).get('planner_session_id')) and heartbeat._planner(root)[0] == 'ok'


def _evidence(root, config, ref, current):
    """The lines a morning seat needs for a queued PR: owed replies, red checks, conflict, closed."""
    from wuwei import pr_actions, watch
    if current in ('conflicted', 'closed'):
        return ['conflicts with its base' if current == 'conflicted' else 'closed without merge']
    measured = watch.evidence(registry.load('code_host', config), ref, root)
    if current == 'ci_red':
        return [f'check {row["name"]}: {row["conclusion"]}' for row in measured['checks']
                if row['state'] == 'completed' and row['conclusion'] not in ('success', 'neutral', 'skipped')]
    acks = obligations._ledger(state.read_state(root)).get(ref, {})
    lines = []
    for key in obligations._replies(measured['reviews'], measured['threads'],
                                    obligations._owner_login(config), acks):
        surface, target = key.split(':', 1)
        thread, latest = pr_actions._latest(measured, surface, target)
        path = (thread or {}).get('path')
        lines.append(f'{surface} {target} by {latest["author"]}' + (f' on {path}' if path else '')
                     + ': ' + ' '.join(str(latest['body']).split()))
    return lines


def overnight(root):
    """One CLI-only sweep of the owning day's PRs: check approved ones against the merge policy,
    ping stale reviews under the outward tiers, queue the rest for the morning. 0 clean, 1 queued,
    2 unmeasured."""
    from collections import Counter
    from wuwei import pr_actions, watch
    from wuwei.commands.doctor import _capture
    live = 'shepherd: planner live; the session shepherd owns the PRs'
    try:
        if _live(root):
            print(live)
            return 0
        day = owning_day(root)
        if day is None:
            print('shepherd: no owned PRs')
            return 0
        workspace._DAY = day.name
        try:
            if _live(root):
                print(live)
                return 0
            config = workspace.load_config(root)
            if not watch.owned(root, config)[1]:
                print('shepherd: no owned PRs')
                return 0
            _, rows = pr_actions.evaluate(root)
            last = {row['payload']['pr']: row['payload'] for row in watch.records(day / 'events.jsonl')
                    if row['kind'] == 'shepherd.overnight'}
            counts = Counter()
            for row in rows:
                if 'pr' not in row:
                    print(row['reason'])
                    counts['unmeasured'] += 1
                    continue
                ref, current, reason, evidence = row['pr'], row.get('state', 'unmeasured'), '', []
                if row['exit'] == 2:
                    outcome, reason = 'unmeasured', row['reason']
                elif row['parked'] or current == 'waiting' or last.get(ref, {}).get('outcome') == 'merged':
                    continue
                elif current == 'merged':
                    outcome = 'merged'
                elif current == 'approved':
                    # ponytail: check only, the morning merges; merge.execute comes back here once
                    # #524 (merge grants) is on main.
                    result = merge.check(ref, root)
                    outcome = ('queued', 'queued', 'unmeasured')[result.exit]
                    reason = result.reason or 'merge cleared by policy; merge waits for the morning (#524)'
                elif current == 'review_stale':
                    code, text = _capture(post_review_request, root, ref)
                    outcome, reason = ('pinged', 'queued', 'unmeasured')[code], text.strip()
                else:
                    try:
                        outcome, reason = 'queued', row['action']
                        evidence = _evidence(root, config, ref, current)
                    except watch.ERRORS as exc:
                        outcome, reason = 'unmeasured', f'evidence unmeasured: {exc}'
                counts[outcome] += 1
                if (last.get(ref, {}).get('state'), last.get(ref, {}).get('outcome')) != (current, outcome):
                    state.append_event('shepherd.overnight', {'pr': ref, 'state': current, 'outcome': outcome,
                                                              'reason': reason, 'evidence': evidence}, root)
            code = 2 if counts['unmeasured'] else 1 if _queue(watch.records(day / 'events.jsonl')) else 0
            summary = {'prs': len(rows), **{key: counts[key] for key in
                       ('merged', 'pinged', 'queued', 'unmeasured')}, 'exit': code}
            state.append_event('shepherd.swept', summary, root)
            workspace.atomic_write(day / 'overnight.md', '\n'.join(overnight_lines(day)) + '\n')
            print('shepherd: sweep ' + json.dumps(summary, sort_keys=True))
            return code
        finally:
            workspace._DAY = None
    except watch.ERRORS as exc:
        print(f'shepherd: sweep unmeasured: {exc}')
        return 2


def _queue(rows):
    """The latest overnight event per PR still owed to the owner, oldest first."""
    latest = {}
    for row in rows:
        if row['kind'] == 'shepherd.overnight':
            latest.pop(row['payload']['pr'], None)
            latest[row['payload']['pr']] = row
    return [row for row in latest.values() if row['payload']['outcome'] in ('queued', 'unmeasured')]


def overnight_lines(directory):
    """The Overnight report of one day, from producer-only events; [] when nothing ran."""
    from wuwei import watch
    rows = watch.records(directory / 'events.jsonl')
    events = [row for row in rows if row['kind'] == 'shepherd.overnight']
    if not events:
        return []
    sweeps = [row['ts'] for row in rows if row['kind'] == 'shepherd.swept']
    lines = [f'## Overnight (days/{directory.name}: {len(sweeps)} sweeps'
             + (f', last {sweeps[-1]})' if sweeps else ')'), '']
    for row in events:
        event = row['payload']
        lines.append(f'- {row["ts"]} {event["pr"]} {event["state"]}: {event["outcome"]}'
                     + (f': {event["reason"]}' if event['reason'] else ''))
    queue = _queue(rows)
    if queue:
        lines += ['', 'Morning queue (first items today):']
    for number, row in enumerate(queue, 1):
        event = row['payload']
        lines.append(f'{number}. {event["pr"]} {event["state"]}: {event["reason"] or event["outcome"]}. '
                     f'Run: bin/wuwei pr act {event["pr"]}')
        lines += [f'   - {line}' for line in event['evidence']]
    return lines + ['']


def loop(root=None, *, once=False):
    """The scheduled shepherd: one sweep every HEADLESS_SECONDS under .wuwei/shepherd.lock."""
    from wuwei import watch
    return watch.serve(workspace.find_workspace(root), 'shepherd', overnight,
                       0 if once else HEADLESS_SECONDS, once=once)


def last_swept(root):
    """The newest shepherd.swept time on the owning day, where the sweep writes, or None."""
    from wuwei import watch
    day = owning_day(root)
    stamps = [row['ts'] for row in (watch.records(day / 'events.jsonl') if day else ())
              if row['kind'] == 'shepherd.swept']
    return max(stamps, key=obligations._time, default=None)
