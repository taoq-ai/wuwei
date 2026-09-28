"""Unavailable review_bot operations, recorded without sensitive arguments."""

from wuwei import registry


def score(pr, *, root=None):
    return registry.record_none('review_bot', 'score', root)


def open_findings(pr, *, root=None):
    return registry.record_none('review_bot', 'open_findings', root)
