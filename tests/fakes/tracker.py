"""Recording tracker fake for offline discovery and lifecycle tests."""

from fakes.replay import Recorder


class Fake(Recorder):
    port = 'tracker'

    def __init__(self, results=None):
        super().__init__({} if results is None else results)

    def backlog(self, filter, root=None):
        return self._call('backlog', (filter,), root)

    def claim(self, item, root=None):
        return self._call('claim', (item,), root)

    def transition(self, item, state, root=None):
        return self._call('transition', (item, state), root)
