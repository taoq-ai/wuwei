"""Unavailable code host, using the shared event and result contract."""

from wuwei.registry import record_none, outward_operation


def pr(ref, root=None):
    return record_none("code_host", "pr", root, measurement=True)


def commits(ref, root=None):
    return record_none('code_host', 'commits', root, measurement=True)


def checks(ref, sha, root=None):
    return record_none("code_host", "checks", root, measurement=True)


def reviews(ref, root=None):
    return record_none("code_host", "reviews", root, measurement=True)


def threads(ref, root=None):
    return record_none("code_host", "threads", root, measurement=True)


def default_branch(repo, root=None):
    return record_none('code_host', 'default_branch', root, measurement=True)


def protection(repo, branch, root=None):
    return record_none("code_host", "protection", root, measurement=True)


def create_pr(draft, root=None):
    return record_none("code_host", "create_pr", root, measurement=False)


def request_reviewers(ref, logins, root=None):
    return record_none("code_host", "request_reviewers", root, measurement=False)


@outward_operation('code_host')
def comment(ref, text, thread, root=None):
    return record_none("code_host", "comment", root, measurement=False)


def merge(ref, sha, root=None):
    return record_none("code_host", "merge", root, measurement=False)


def revert_pr(ref, root=None):
    return record_none("code_host", "revert_pr", root, measurement=False)


def files(ref, root=None):
    return record_none('code_host', 'files', root, measurement=True)


def history(repo, start, branch, patches=True, root=None):
    return record_none('code_host', 'history', root, measurement=True)


def author_login(repo, email, root=None):
    return record_none('code_host', 'author_login', root, measurement=True)


def token_scopes(variable, root=None):
    return record_none('code_host', 'token_scopes', root, measurement=True)


def auth_status(root=None):
    return record_none('code_host', 'auth_status', root, measurement=True)


def viewer_login(root=None):
    return record_none('code_host', 'viewer_login', root, measurement=True)


def merged_prs(repo, root=None):
    return record_none('code_host', 'merged_prs', root, measurement=True)


def open_prs(repo, root=None):
    return record_none('code_host', 'open_prs', root, measurement=True)


def probe(ref, tags, root=None):
    return record_none('code_host', 'probe', root, measurement=True)


def deployments(repo, since, root=None):
    return record_none('code_host', 'deployments', root, measurement=True)


def issue(repo, title, body, root=None):
    return record_none('code_host', 'issue', root, measurement=False)
