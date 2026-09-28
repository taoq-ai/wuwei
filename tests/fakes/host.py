"""In-process host memory fake with the same result and call recording contract."""

from fakes.replay import Recorder
from wuwei.registry import Result


class Fake(Recorder):
    def __init__(self, results=None):
        super().__init__({'free_memory': Result(0, 8 * 1024**3)} if results is None else results)

    def free_memory(self, root=None):
        return self._call('free_memory', (), root)
