"""Unavailable scanner operations, recorded without sensitive arguments."""

from wuwei import registry


def audit(path, *, root=None):
    return registry.record_none('scanner', 'audit', root)


def gate(result, threshold, *, root=None):
    return registry.record_none('scanner', 'gate', root)


def traces(file, *, root=None):
    return registry.record_none('scanner', 'traces', root)


def mcp(servers, *, root=None):
    return registry.record_none('scanner', 'mcp', root)
