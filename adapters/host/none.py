"""Unavailable host measurements fail closed."""

from wuwei.registry import record_none


def free_memory(root=None):
    return record_none('host', 'free_memory', root)


def hand_over(target, argv, env, root=None):
    return record_none('host', 'hand_over', root, measurement=False)
