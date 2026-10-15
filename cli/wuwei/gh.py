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


PR_FIELDS = ('number,title,body,state,isDraft,headRefName,headRefOid,baseRefName,author,url,'
             'mergedAt,createdAt,files,statusCheckRollup,reviewRequests,reviews')

THREADS = '''query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){
pullRequest(number:$number){reviewThreads(first:100){nodes{isResolved comments(last:1){nodes{author{login}}}}}}}}'''


def pr(repo, number):
    return run(['pr', 'view', str(number), '--repo', repo, '--json', PR_FIELDS])


def open_prs(repo):
    return run(['pr', 'list', '--repo', repo, '--state', 'open', '--limit', '100', '--json',
                'number,title,body,headRefName,author,url,isDraft'])


def merged_prs(repo, since):
    return run(['pr', 'list', '--repo', repo, '--state', 'merged', '--limit', '200', '--search',
                f'merged:>={since}', '--json', 'number,title,createdAt,mergedAt,headRefName,body'])


def unanswered_threads(repo, number, author):
    """Unresolved review threads whose last comment is not the PR author's."""
    owner, name = repo.split('/', 1)
    data = run(['api', 'graphql', '-f', f'query={THREADS}', '-F', f'owner={owner}', '-F', f'name={name}',
                '-F', f'number={number}'])
    nodes = data['data']['repository']['pullRequest']['reviewThreads']['nodes']
    return sum(1 for node in nodes if not node['isResolved']
               and (node['comments']['nodes'] or [{}])[-1].get('author', {}).get('login') != author)


def ancestor(repo, older, newer):
    """True when commit older is newer or an ancestor of it."""
    if older == newer:
        return True
    data = run(['api', f'repos/{repo}/compare/{older}...{newer}'])
    return data.get('status') in ('ahead', 'identical')


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


def file(repo, path):
    """A file's text on the default branch, or GhError."""
    import base64
    data = run(['api', f'repos/{repo}/contents/{path}'])
    if not isinstance(data, dict) or data.get('encoding') != 'base64':
        raise GhError(f'{path} is not a file')
    return base64.b64decode(data['content']).decode('utf-8', 'replace')
