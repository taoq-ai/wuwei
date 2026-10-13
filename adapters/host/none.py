"""Unavailable host measurements fail closed."""

from wuwei.registry import record_none


def free_memory(root=None):
    return record_none('host', 'free_memory', root)


def free_percent(root=None):
    return record_none('host', 'free_percent', root)


def hand_over(target, argv, env, root=None):
    return record_none('host', 'hand_over', root, measurement=False)


def processes(orphans=False, pid=None, root=None):
    return record_none('host', 'processes', root)


def terminate_process(record, grace, root=None):
    return record_none('host', 'terminate_process', root, measurement=False)
