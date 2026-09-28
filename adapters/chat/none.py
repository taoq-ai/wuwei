"""Unavailable chat operations, recorded without sensitive arguments."""

from wuwei import registry


def post(channel, text, thread, *, root=None):
    return registry.record_none('chat', 'post', root, measurement=False)


def dm(text, *, root=None):
    return registry.record_none('chat', 'dm', root, measurement=False)
