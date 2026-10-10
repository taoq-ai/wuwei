"""Unavailable fast checks never count as clean."""

from wuwei import registry


def run(path, command, timeout=300, root=None):
    return registry.record_none('checks', 'run', root)
