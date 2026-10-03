"""Unavailable tracker operations, recorded without sensitive arguments."""

from wuwei import registry
from wuwei.registry import outward_operation


def backlog(filter, *, root=None):
    return registry.record_none('tracker', 'backlog', root)


def claim(item, *, root=None):
    return registry.record_none('tracker', 'claim', root, measurement=False)


def transition(item, state, *, root=None):
    return registry.record_none('tracker', 'transition', root, measurement=False)


@outward_operation('tracker')
def create(draft, *, root=None):
    return registry.record_none('tracker', 'create', root, measurement=False)


def history(item, *, root=None):
    return registry.record_none('tracker', 'history', root)


def created(item, *, root=None):
    return registry.record_none('tracker', 'created', root)


@outward_operation('tracker')
def comment(item, text, category, *, root=None):
    return registry.record_none('tracker', 'comment', root, measurement=False)
