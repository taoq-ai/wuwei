"""No inbound source configured."""

from wuwei import registry


def poll(since, *, root=None):
    return registry.record_none('inbound', 'poll', root)
