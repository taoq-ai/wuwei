"""Unavailable runtime operations, recorded without sensitive arguments."""

from wuwei import registry


def dispatch(role, brief_path, worktree, write, *, root=None):
    return registry.record_none('runtime', 'dispatch', root, measurement=False)


def status(job, *, root=None):
    return registry.record_none('runtime', 'status', root)


def result(job, *, root=None):
    return registry.record_none('runtime', 'result', root)


def continue_job(job, feedback, *, root=None):
    return registry.record_none('runtime', 'continue_job', root, measurement=False)
