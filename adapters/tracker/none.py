"""Unavailable tracker operations, recorded without sensitive arguments."""

from wuwei import registry


def claim(item, *, root=None):
    return registry.record_none('tracker', 'claim', root, measurement=False)


def transition(item, state, *, root=None):
    return registry.record_none('tracker', 'transition', root, measurement=False)


def create(draft, *, root=None):
    return registry.record_none('tracker', 'create', root, measurement=False)


def history(item, *, root=None):
    return registry.record_none('tracker', 'history', root)
