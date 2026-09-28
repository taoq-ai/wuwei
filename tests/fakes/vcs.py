"""Recording vcs fake for core tests."""

from fakes.replay import Recorder


class Fake(Recorder):
    port = 'vcs'

    def resolve(self, repo, sha, root=None):
        return self._call('resolve', (repo, sha), root)

    def branches(self, repo, pattern, root=None):
        return self._call('branches', (repo, pattern), root)

    def identity(self, repo, root=None):
        return self._call('identity', (repo,), root)

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
