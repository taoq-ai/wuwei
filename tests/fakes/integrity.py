"""Explicit measured integrity evidence for tests of other policies."""

import json

from wuwei.registry import Result


def seed(root):
    directory = root / '.wuwei/integrity'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'verdict.json').write_text(json.dumps(
        {'exit': 0, 'fingerprint': 'a' * 64, 'reason': ''}))


def measured(monkeypatch):
    from wuwei import integrity
    monkeypatch.setattr(integrity, 'check', lambda root: Result(0, 'a' * 64))
