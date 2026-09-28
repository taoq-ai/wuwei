"""Unavailable chat operations, recorded without sensitive arguments."""

from wuwei import registry
from wuwei.registry import outward_operation


@outward_operation('chat')
def post(channel, text, thread, *, root=None):
    return registry.record_none('chat', 'post', root, measurement=False)


@outward_operation('chat')
def dm(text, *, root=None):
    return registry.record_none('chat', 'dm', root, measurement=False)


def sent(channel, owner, *, root=None):
    return registry.record_none('chat', 'sent', root)
