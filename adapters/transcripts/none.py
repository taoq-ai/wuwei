"""Meeting transcripts are not configured."""

from wuwei.registry import Result


def recent(since, root=None):
    return Result(0, [])
