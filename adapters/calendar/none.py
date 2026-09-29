"""No calendar feed configured."""

from wuwei.registry import Result


def events(since, until, root=None):
    return Result(0, [])
