"""Guard modules expose a plain GUARDS list; private modules are helpers."""

from importlib import import_module
import pkgutil
import re
from typing import Callable, NamedTuple


EVENTS = ('PreToolUse', 'PostToolUse', 'SubagentStop', 'SessionStart', 'PreCompact', 'Stop')


class Guard(NamedTuple):
    event: str
    matcher: str | None
    check: Callable[[dict], tuple[int, str]]


def discover():
    guards = []
    for module in pkgutil.iter_modules(__path__, __name__ + '.'):
        if not module.name.rsplit('.', 1)[-1].startswith('_'):
            records = import_module(module.name).GUARDS
            if not isinstance(records, list):
                raise ValueError(f'{module.name}: GUARDS must be a list')
            for guard in records:
                if not isinstance(guard, Guard) or not callable(guard.check):
                    raise ValueError(f'{module.name}: invalid guard record')
                if guard.matcher is not None and not isinstance(guard.matcher, str):
                    raise ValueError(f'{module.name}: invalid guard matcher')
                if guard.event not in EVENTS:
                    raise ValueError('unknown guard event')
                if guard.matcher is not None:
                    re.compile(guard.matcher)
            guards.extend(records)
    return guards
