"""Recording code_host fake for core tests."""

from fakes.replay import Recorder


class Fake(Recorder):
    port = 'code_host'

    def pr(self, ref, root=None):
        return self._call('pr', (ref,), root)

    def checks(self, ref, sha, root=None):
        return self._call('checks', (ref, sha), root)

    def reviews(self, ref, root=None):
        return self._call('reviews', (ref,), root)

    def threads(self, ref, root=None):
        return self._call('threads', (ref,), root)

    def protection(self, repo, branch, root=None):
        return self._call('protection', (repo, branch), root)

    def create_pr(self, draft, root=None):
        return self._call('create_pr', (draft,), root)

    def request_reviewers(self, ref, logins, root=None):
        return self._call('request_reviewers', (ref, logins), root)

    def comment(self, ref, text, thread, root=None):
        return self._call('comment', (ref, text, thread), root)

    def merge(self, ref, sha, root=None):
        return self._call('merge', (ref, sha), root)

    def revert_pr(self, ref, root=None):
        return self._call('revert_pr', (ref,), root)

    def files(self, ref, root=None):
        return self._call('files', (ref,), root)

    def history(self, repo, start, branch, patches=True, root=None):
        return self._call('history', (repo, start, branch, patches), root)

    def author_login(self, repo, email, root=None):
        return self._call('author_login', (repo, email), root)
