"""Unavailable docs operations, recorded without page text."""

from wuwei import registry
from wuwei.registry import outward_operation


def read(ref, *, root=None):
    return registry.record_none('docs', 'read', root)


@outward_operation('docs')
def write(draft, *, root=None):
    return registry.record_none('docs', 'write', root, measurement=False)
