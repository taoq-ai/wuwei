"""Recording vcs fake for core tests."""

from fakes.replay import Recorder


class Fake(Recorder):
    port = 'vcs'

    def authorship(self, repo, branch, paths, days, root=None):
        return self._call('authorship', (repo, branch, paths, days), root)

    def branch(self, repo, root=None):
        return self._call('branch', (repo,), root)

    def resolve(self, repo, sha, root=None):
        return self._call('resolve', (repo, sha), root)

    def rebase(self, repo, ref, root=None):
        return self._call('rebase', (repo, ref), root)

    def fetch(self, repo, remote, branch, expected, root=None):
        return self._call('fetch', (repo, remote, branch, expected), root)

    def push(self, repo, remote, branch, expected, root=None):
        return self._call('push', (repo, remote, branch, expected), root)

    def branches(self, repo, pattern, root=None):
        return self._call('branches', (repo, pattern), root)

    def pushed_branches(self, repo, root=None):
        return self._call('pushed_branches', (repo,), root)

    def identity(self, repo, root=None):
        return self._call('identity', (repo,), root)

    def remote_url(self, repo, root=None):
        return self._call('remote_url', (repo,), root)

    def head(self, repo, root=None):
        return self._call('head', (repo,), root)

    def merge_base(self, repo, ref, root=None):
        return self._call('merge_base', (repo, ref), root)

    def status(self, repo, root=None):
        return self._call('status', (repo,), root)

    def diff_stat(self, repo, base, head, root=None):
        return self._call('diff_stat', (repo, base, head), root)

    def log_since(self, repo, sha, root=None):
        return self._call('log_since', (repo, sha), root)

    def worktree_add(self, repo, branch, path, root=None):
        return self._call('worktree_add', (repo, branch, path), root)

    def repo_context(self, repo, root=None):
        return self._call('repo_context', (repo,), root)

    def commit_context(self, repo, settings, env, root=None):
        return self._call('commit_context', (repo, settings, env), root)

    def push_context(self, repo, remote, refspecs, root=None):
        return self._call('push_context', (repo, remote, refspecs), root)

    def hooks_path(self, repo, path, mode, root=None):
        return self._call('hooks_path', (repo, path, mode), root)

    def hooks_target(self, repo, root=None):
        return self._call('hooks_target', (repo,), root)

    def worktree_identity(self, repo, name, email, root=None):
        return self._call('worktree_identity', (repo, name, email), root)

    def push_commits(self, repo, remote, destination, local_sha, remote_sha, default_branch, root=None):
        return self._call('push_commits', (repo, remote, destination, local_sha, remote_sha, default_branch), root)

    def changes_on(self, repo, day, root=None):
        return self._call('changes_on', (repo, day), root)

    def read_tree(self, repo, ref, paths, root=None):
        return self._call('read_tree', (repo, ref, paths), root)

    def workspace_changes(self, repo, root=None):
        return self._call('workspace_changes', (repo,), root)

    def recent_commits(self, repo, root=None):
        return self._call('recent_commits', (repo,), root)

    def worktrees(self, repo, root=None):
        return self._call('worktrees', (repo,), root)

    def worktree_checkout(self, repo, branch, path, root=None):
        return self._call('worktree_checkout', (repo, branch, path), root)
