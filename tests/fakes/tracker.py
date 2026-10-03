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

    def create(self, draft, root=None):
        return self._call('create', (draft,), root)

    def comment(self, item, text, category, root=None):
        return self._call('comment', (item, text, category), root)

    def created(self, item, root=None):
        return self._call('created', (item,), root)


def ported(fake):
    """The fake's text-bearing calls behind the real outward wrapper, as the linear module."""
    from types import SimpleNamespace
    from wuwei.registry import outward_operation

    def create(draft, *, root=None):
        return fake.create(draft, root)

    def comment(item, text, category, *, root=None):
        return fake.comment(item, text, category, root)
    for function in (create, comment):
        function.__module__ = 'adapters.tracker.linear'
    return SimpleNamespace(create=outward_operation('tracker')(create),
                           comment=outward_operation('tracker')(comment),
                           claim=fake.claim, transition=fake.transition,
                           backlog=fake.backlog, created=fake.created)
