"""Unavailable manifest verification is never clean."""

from wuwei.registry import record_none


def sign(manifest, key, root=None):
    return record_none('integrity', 'sign', root, measurement=False)


def verify(manifest, signature, key, root=None):
    return record_none('integrity', 'verify', root)
