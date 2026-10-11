"""Seed a day's records as a test needs them (#844): the event log is the truth, so a fixture
writes one patch event, never state.json, and skips the writer's lifecycle checks."""


def write(root=None, data=None, *, directory=None):
    """Set each top-level value of data in today's records (or directory's)."""
    from wuwei import state, workspace
    directory = workspace.day_dir(root) if directory is None else directory
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'state.lock').open('a') as lock:
        state.lock_ex(lock, 'state.lock')
        state._append_event('state.write', {}, directory, patch={'set': data})
