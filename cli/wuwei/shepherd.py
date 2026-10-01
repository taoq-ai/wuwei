"""Raise and shepherd PRs through the existing ports and policies."""

from fnmatch import fnmatchcase
import re

from wuwei import merge, obligations, registry, state, workspace
from wuwei.references import pull_request, repository
from wuwei.registry import Result


ERRORS = merge.ERRORS


def _settings(config, ref):
    repo = ref.split('#')[0]
    settings = next((row for row in config['repos'] if row['name'] == repo), None)
    if settings is None:
        raise ValueError('PR repository is not configured')
    return settings


def _source(path, config):
    if not isinstance(path, str) or not path or path.startswith('/') or '..' in path.split('/'):
        raise ValueError('invalid changed source path')
    return not any(fnmatchcase(path, pattern) for pattern in config['shepherd']['source_exclude'])


def _rank(root, config, repo, branch, paths, author, source_path=None):
    mapping = config['shepherd']['authors']
    vcs = registry.load('vcs', config)
    host = registry.load('code_host', config)
    resolved = {}
    selected = []
    windows = config['shepherd']['author_windows_days']
    if not windows or windows != sorted(set(windows)):
        raise ValueError('authorship windows must increase')
    for days in (*windows, 0):
        rows = merge.read(vcs.authorship, str(source_path or (root / repo['path']).resolve()), branch,
                          paths, days, root=root)
        if not isinstance(rows, list):
            raise ValueError('invalid authorship evidence')
        counts = {}
        for row in rows:
            email, commits = row['email'].casefold(), row['commits']
            if not isinstance(email, str) or '@' not in email or type(commits) is not int or commits < 1:
                raise ValueError('invalid authorship record')
            if email in mapping:
                login = mapping[email]['login']
            else:
                if email not in resolved:
                    try:
                        resolved[email] = merge.read(host.author_login, repo['name'], email,
                                                     root=root)['login']
                    except ERRORS as exc:
                        raise ValueError(f'shepherd.authors has no mapping for {email}: {exc}')
                    if not isinstance(resolved[email], str) or not resolved[email]:
                        raise ValueError(f'shepherd.authors has no mapping for {email}')
                login = resolved[email]
            if login.casefold() != author.casefold() and not login.casefold().endswith('[bot]'):
                counts[login] = counts.get(login, 0) + commits
        selected = sorted(counts, key=lambda login: (-counts[login], login))
        if len(selected) >= max(2, config['shepherd']['min_reviewers']):
            if (len(selected) >= 3 and counts[selected[1]] - counts[selected[2]]
                    <= config['shepherd']['tie_commits']):
                selected = selected[:3]
            else:
                selected = selected[:max(2, config['shepherd']['min_reviewers'])]
            break
    lead = config['shepherd']['lead_login']
    if lead and lead != author and lead not in selected:
        selected.append(lead)
    if len(selected) < config['shepherd']['min_reviewers']:
        raise merge.Refused('fewer eligible reviewers than shepherd.min_reviewers')
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', login) for login in selected):
        raise ValueError('invalid reviewer login')
    emails = {login: email for email, login in resolved.items()}
    emails.update({row['login']: email for email, row in mapping.items()})
    for login in selected:
        if login not in emails:
            raise ValueError('reviewer needs a configured email')
        verified = merge.read(host.author_login, repo['name'], emails[login], root=root)
        if verified['login'] != login:
            raise ValueError('configured reviewer login differs from code host')
    return selected


def select_reviewers(root, ref):
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    ref = pull_request(ref)
    settings = _settings(config, ref)
    host = registry.load('code_host', config)
    pr = merge.checked_pr(host, ref, root)
    files = merge.read(host.files, ref, root=root)
    if len(files) != pr['changed_files']:
        raise ValueError('incomplete changed files')
    paths = [row['path'] for row in files if _source(row['path'], config)]
    if not paths:
        raise merge.Refused('no changed source paths for reviewer selection')
    return _rank(root, config, settings,
                 config['brief']['remote'] + '/' + pr['base'], paths, pr['author'])


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
            raise ValueError('mergeability unmeasured')
        checks = merge.checks_at(host, ref, pr['head'], root)
        ignored = config['shepherd']['review_gate_check']
        checks = [row for row in checks if row['name'] != ignored]
        protection_result = host.protection(ref.split('#')[0], pr['base'], root=root)
        missing = protection_result.exit == 2 and 'branch protection absent' in protection_result.reason
        if protection_result.exit and not missing:
            raise ValueError(protection_result.reason or 'branch protection unmeasured')
        if not missing and (not isinstance(protection_result.data, dict) or
                            'message' in protection_result.data or 'errors' in protection_result.data):
            raise ValueError('branch protection error body')
        if ((missing or not protection_result.data.get('required_checks'))
                and pr['base'] != settings['default_branch']):
            protection_result = host.protection(ref.split('#')[0], settings['default_branch'], root=root)
        fallback = settings['review_required_checks']
        missing = protection_result.exit == 2 and 'branch protection absent' in protection_result.reason
        if protection_result.exit and not missing:
            raise ValueError(protection_result.reason or 'branch protection unmeasured')
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
        raise ValueError('reviewer needs a configured chat mention')
    return ' '.join('<@' + by_login[login] + '>' for login in reviewers)


def post_review_request(root, ref):
    """Request and post the same reviewer set only while the fresh gate clears."""
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        ref = pull_request(ref)
        if ref not in state.read_state(root)['raised_prs'] + state.read_state(root)['claimed_prs']:
            raise ValueError('PR is not owned today')
        gate = ping_gate(root, ref)
        if gate.exit:
            print(gate.reason)
            return gate.exit
        reviewers = state.read_state(root).get('pr_reviewers', {}).get(ref)
        if reviewers is None:
            reviewers = select_reviewers(root, ref)
        if (not isinstance(reviewers, list) or len(reviewers) < config['shepherd']['min_reviewers']
                or len(set(reviewers)) != len(reviewers)):
            raise ValueError('invalid selected reviewer record')
        host = registry.load('code_host', config)
        requested = merge.read(host.request_reviewers, ref, reviewers, root=root)
        if set(requested['requested']) != set(reviewers):
            raise ValueError('requested reviewer set differs from selected set')
        state._write_state(lambda data: data.setdefault('pr_reviewers', {}).update({ref: reviewers}),
                           root, reserved=False, kind='pr.reviewers_selected',
                           payload={'pr': ref, 'reviewers': reviewers})
        gate = ping_gate(root, ref)
        if gate.exit:
            print(gate.reason)
            return gate.exit
        channel = config['shepherd']['review_channel']
        if not re.fullmatch(r'[A-Z0-9]+', channel):
            raise ValueError('shepherd.review_channel is required')
        pr = gate.data['pr']
        text = f'PR #{pr["number"]} ready for review: <{pr["url"]}|#{pr["number"]}> {_mentions(config, reviewers)}'
        chat = registry.load('chat', config)
        posted = chat.post(channel, text, None, root=root)
        if posted.exit:
            print(posted.reason or 'review post was not sent')
            return posted.exit
        if posted.data['channel'] != channel or not re.fullmatch(r'[0-9]+\.[0-9]+', posted.data['ts']):
            raise ValueError('invalid chat post confirmation')
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
            raise ValueError('raise needs base, title, body and item')
        data = state.read_state(root)
        merge.require(item in data['items'] and item in data['approved_items'],
                      'PR item must be in the approved plan')
        merge.require(data['items'][item].get('pr') is None, 'item already links another PR')
        if config['adapters']['code_host'] == 'none':
            raise ValueError('code_host adapter is none; configure github')
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
        if code:
            print(reason)
            return code
        from wuwei import dispatch, outward
        row = data['items'][item]
        if row['gates']:
            body += f'\n\nReview tier: {row["gates"]["tier"]} ({", ".join(dispatch.gate_set(row))})'
        code, reason = outward.lint(title + '\n' + body, 'code_host', config, root=root)
        if code:
            print(reason)
            return code
        identity = merge.read(vcs.identity, str(repo_path), root=root)
        expected = settings['identity']
        if expected['email'] and identity['email'] != expected['email']:
            raise merge.Refused('repository identity does not match configured owner')
        if expected['name'] and identity['name'] != expected['name']:
            raise merge.Refused('repository identity does not match configured owner')
        if any(identity[key] != {'name': identity['name'], 'email': identity['email']}
               for key in ('author', 'committer')):
            raise merge.Refused('author and committer identity differ from configured repository identity')
        branch = config['brief']['remote'] + '/' + base
        base_sha = merge.read(vcs.merge_base, str(repo_path), branch, root=root)['sha']
        merge.sha(base_sha)
        changes = merge.read(vcs.diff_stat, str(repo_path), base_sha, head, root=root)
        paths = [row['path'] for row in changes if _source(row['path'], config)]
        merge.require(paths, 'no changed source paths for reviewer selection')
        author = obligations._owner_login(config)
        reviewers = _rank(root, config, settings, branch, paths, author, repo_path)
        host = registry.load('code_host', config)
        head_branch = merge.read(vcs.branch, str(repo_path), root=root)['name']
        created = merge.read(host.create_pr, {'repo': repo_name, 'base': base,
            'head': head_branch, 'title': title, 'body': body}, root=root)
        ref = pull_request(f'{repo_name}#{created["number"]}')
        pr = merge.checked_pr(host, ref, root)
        if pr['head'] != head or pr['url'] != created['url']:
            raise ValueError('created PR does not match checked head and URL')
        state.record_pr(root, item, ref, raised=True, head=head, reviewers=reviewers)
        dispatch.tracker_call(item, 'in_review', root)
        if reviewers:
            requested = merge.read(host.request_reviewers, ref, reviewers, root=root)
            if set(requested['requested']) != set(reviewers):
                raise ValueError('reviewer request could not be verified')
        print(ref)
        return 0
    except (merge.Refused, state.StateError) as exc:
        print(exc)
        return 1
    except ERRORS as exc:
        print(f'PR raise unmeasured: {exc}; check adapters.vcs and adapters.code_host, then retry wuwei pr raise')
        return 2


def claim_pr(root, ref, item):
    """Claim a fresh, externally verified PR for an approved item."""
    try:
        root = workspace.find_workspace(root)
        config = workspace.load_config(root)
        ref = pull_request(ref)
        _settings(config, ref)
        host = registry.load('code_host', config)
        pr = merge.checked_pr(host, ref, root)
        merge.require(pr['state'] == 'open' and not pr['merged'], 'PR is not open')
        state.record_pr(root, item, ref, raised=False, head=pr['head'])
        print(ref)
        return 0
    except (merge.Refused, state.StateError) as exc:
        print(exc)
        return 1
    except ERRORS as exc:
        print(f'PR claim unmeasured: {exc}')
        return 2
