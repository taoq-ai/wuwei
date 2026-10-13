"""In-process host memory fake with the same result and call recording contract."""

import os

from fakes.replay import Recorder
from wuwei.registry import Result


def process_table():
    return {os.getpid(): {'pid': os.getpid(), 'ppid': 42, 'command': 'test worker',
                          'identity': 'test start', 'etime': '00:00', 'cwd': None}}


class Fake(Recorder):
    def __init__(self, results=None):
        super().__init__({'free_memory': Result(0, 8 * 1024**3), 'free_percent': Result(0, 62), 'processes': Result(0, process_table())}
                         if results is None else results)

    def free_memory(self, root=None):
        return self._call('free_memory', (), root)

    def free_percent(self, root=None):
        return self._call('free_percent', (), root)

    def processes(self, orphans=False, pid=None, root=None):
        return self._call('processes', (orphans, pid), root)

    def terminate_process(self, record, grace, root=None):
        return self._call('terminate_process', (record, grace), root)
