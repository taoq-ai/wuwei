"""The code host, read through the gh CLI. Every call returns parsed JSON or raises GhError."""

import json
import subprocess


class GhError(Exception):
    pass


def run(args, timeout=30):
    """gh <args>; parsed JSON when the output is JSON, else the text. Tests replace this function."""
    try:
        done = subprocess.run(['gh', *args], capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise GhError(f'gh could not run: {exc}') from exc
    if done.returncode:
        lines = (done.stderr or done.stdout).strip().splitlines()
        raise GhError((lines[-1] if lines else f'gh exited {done.returncode}')[:200])
    text = done.stdout.strip()
    try:
        return json.loads(text) if text[:1] in '[{' else text
    except ValueError:
        return text


THREADS = '''query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){
pullRequest(number:$number){reviewThreads(first:100){nodes{isResolved comments(last:1){nodes{author{login}}}}}}}}'''


# REST only: GraphQL is refused in Claude Code cloud sessions.
def pages(path, limit=30):
    """Every item of a list endpoint, 100 per page (GitHub lists at most 3,000 PR files)."""
    found, sep = [], '&' if '?' in path else '?'
    for number in range(1, limit + 1):
        batch = run(['api', f'{path}{sep}per_page=100&page={number}'])
        found += batch
        if len(batch) < 100:
            break
    return found

def _summary(pr):
    return {'number': pr['number'], 'title': pr.get('title') or '', 'body': pr.get('body') or '',
            'state': 'MERGED' if pr.get('merged_at') else (pr.get('state') or '').upper(), 'isDraft': bool(pr.get('draft')),
            'headRefName': pr['head']['ref'], 'headRefOid': pr['head']['sha'], 'baseRefName': pr['base']['ref'],
            'author': {'login': (pr.get('user') or {}).get('login', '')}, 'url': pr.get('html_url', ''),
            'mergedAt': pr.get('merged_at'), 'createdAt': pr.get('created_at'), 'updatedAt': pr.get('updated_at')}


def pr(repo, number):
    """One PR in the shape evidence reads: files, checks, review requests and reviews included."""
    base = f'repos/{repo}/pulls/{number}'
    data = run(['api', base])
    head = data['head']['sha']
    checks = run(['api', f'repos/{repo}/commits/{head}/check-runs?per_page=100']).get('check_runs', [])
    statuses = run(['api', f'repos/{repo}/commits/{head}/status']).get('statuses', [])
    return {**_summary(data),
            'files': [{'path': f['filename'], 'additions': f.get('additions', 0), 'deletions': f.get('deletions', 0),
                       'patch': f.get('patch'), 'renamed': f.get('previous_filename') or ''} for f in pages(f'{base}/files')],
            'statusCheckRollup': [{'name': c['name'], 'status': (c.get('status') or '').upper(),
                                   'conclusion': (c.get('conclusion') or '').upper()} for c in checks]
            + [{'context': s['context'], 'state': (s.get('state') or '').upper(), 'url': s.get('target_url')} for s in statuses],
            'reviewRequests': [{'login': u['login']} for u in data.get('requested_reviewers') or ()]
            + [{'login': t['slug']} for t in data.get('requested_teams') or ()],
            'reviews': [{'author': {'login': (r.get('user') or {}).get('login', '')}, 'state': r.get('state'),
                         'commit': r.get('commit_id')}
                        for r in run(['api', f'{base}/reviews?per_page=100'])]}


def workflow_paths(repo, query='?event=pull_request_review&per_page=100'):
    """The workflow paths of one run ('/<id>'), or of the last 100 the repository ran on pull_request_review."""
    found = run(['api', f'repos/{repo}/actions/runs{query}'])
    return sorted({r['path'] for r in found.get('workflow_runs', [found])})


def open_prs(repo):
    return [_summary(p) for p in run(['api', f'repos/{repo}/pulls?state=open&per_page=100'])]


def merged_prs(repo, since):
    found = run(['api', f'repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100'])
    return [_summary(p) for p in found if p.get('merged_at') and p['merged_at'] >= since]


def _author(comment):
    return ((comment or {}).get('user') or (comment or {}).get('author') or {}).get('login')


def unanswered_threads(repo, number, author):
    """Unresolved review threads whose last comment is not the PR author's: GraphQL locally, the
    CCR route in a cloud session, else review comments grouped by reply (no resolved flag there)."""
    owner, name = repo.split('/', 1)
    try:
        data = run(['api', 'graphql', '-f', f'query={THREADS}', '-F', f'owner={owner}', '-F', f'name={name}',
                    '-F', f'number={number}'])
        nodes = data['data']['repository']['pullRequest']['reviewThreads']['nodes']
        return sum(1 for node in nodes if not node['isResolved']
                   and (node['comments']['nodes'] or [{}])[-1].get('author', {}).get('login') != author)
    except GhError:
        pass
    try:
        data = run(['api', f'repos/{repo}/pulls/{number}/ccr/review_threads'])
        threads = data.get('threads', data.get('review_threads', [])) if isinstance(data, dict) else data
        count = 0
        for thread in threads:
            resolved = thread.get('is_resolved', thread.get('isResolved', thread.get('resolved', False)))
            comments = thread.get('comments') or []
            comments = comments.get('nodes', []) if isinstance(comments, dict) else comments
            count += bool(not resolved and comments and _author(comments[-1]) != author)
        return count
    except GhError:
        pass
    last = {c.get('in_reply_to_id') or c['id']: _author(c) for c in run(['api', f'repos/{repo}/pulls/{number}/comments?per_page=100'])}
    return sum(1 for login in last.values() if login != author)


def compare(repo, older, newer):
    """Status, commits and files (in the shape pr() gives) from older to newer, each a sha or a branch."""
    data = run(['api', f'repos/{repo}/compare/{older}...{newer}'])
    return {**data, 'files': [{'path': f['filename'], 'additions': f.get('additions', 0), 'deletions': f.get('deletions', 0)}
                              for f in data.get('files') or ()]}


def has_path(repo, path):
    try:
        run(['api', f'repos/{repo}/contents/{path}'])
        return True
    except GhError:
        return False


def default_branch(repo):
    return run(['api', f'repos/{repo}', '--jq', '.default_branch'])


def login():
    return run(['api', 'user', '--jq', '.login'])


def deployments(repo):
    return run(['api', f'repos/{repo}/deployments?per_page=100'])


def releases(repo):
    return run(['api', f'repos/{repo}/releases?per_page=100'])


def rules(repo, branch):
    return run(['api', f'repos/{repo}/rules/branches/{branch}'])


def file(repo, path, ref=None):
    """A file's text on the default branch (or at ref), or GhError."""
    import base64
    data = run(['api', f'repos/{repo}/contents/{path}' + (f'?ref={ref}' if ref else '')])
    if not isinstance(data, dict) or data.get('encoding') != 'base64':
        raise GhError(f'{path} is not a file')
    return base64.b64decode(data['content']).decode('utf-8', 'replace')


def listing(repo, path, ref):
    """The entries of a directory at ref, or [] when it does not exist."""
    try:
        data = run(['api', f'repos/{repo}/contents/{path}?ref={ref}'])
    except GhError:
        return []
    return data if isinstance(data, list) else []
