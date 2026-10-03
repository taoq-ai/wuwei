"""The workspace inbox: normalised inbound events, redacted before they are stored."""

import json
from pathlib import Path

from wuwei import registry, state
from wuwei.registry import Result
from wuwei.exits import ADAPTER_DATA

FIELDS = ('id', 'source', 'channel', 'thread', 'sender', 'text', 'ts')
REQUIRED = ('id', 'source', 'channel', 'sender', 'ts')


def _redacted(result):
    data = result.data
    return (result.exit in (0, 1) and isinstance(data, dict) and isinstance(data.get('text'), str)
            and isinstance(data.get('findings'), list)
            and all(isinstance(item, dict) and isinstance(item.get('kind'), str)
                    for item in data['findings']))


def read(root):
    """Stored events, oldest first; a missing inbox is empty, a corrupt line fails."""
    try:
        text = (Path(root) / '.wuwei' / 'inbox' / 'inbox.jsonl').read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in text.splitlines()]


def store(root, config, events):
    """The only writer of .wuwei/inbox/inbox.jsonl; nothing is stored unless all events redact."""
    if not isinstance(events, list) or not all(
            isinstance(event, dict) and tuple(sorted(event)) == tuple(sorted(FIELDS))
            and all(isinstance(value, str) for value in event.values())
            and all(event[key] for key in REQUIRED) for event in events):
        return Result(2, None, f'inbox: malformed event; {ADAPTER_DATA}')
    # ponytail: reads the whole inbox per store; index ids when the inbox grows large.
    try:
        seen = {(row['source'], row['id']) for row in read(root)}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return Result(2, None, f'inbox: unreadable: {exc}; run bin/wuwei doctor')
    fresh = []
    for event in events:
        if (event['source'], event['id']) not in seen:
            seen.add((event['source'], event['id']))
            fresh.append(event)
    events = fresh
    if not events:
        return Result(0, 0)
    redactor = registry.load('redactor', config)
    batch = []
    for event in events:
        result = redactor.redact(event['text'], root=root)
        if not _redacted(result):
            return Result(2, None, result.reason or f'inbox: redactor returned malformed data; {ADAPTER_DATA}')
        batch.append((event, result.data))
    try:
        for event, data in batch:
            state.append_jsonl(root / '.wuwei' / 'inbox' / 'inbox.jsonl', {**event, 'text': data['text']})
            if data['findings']:
                state.append_event('inbox.redacted', {
                    'id': event['id'], 'source': event['source'],
                    'findings': [item['kind'] for item in data['findings']]}, root)
    except (OSError, ValueError) as exc:
        return Result(2, None, f'inbox: could not store: {exc}; run bin/wuwei doctor')
    return Result(1 if any(data['findings'] for _, data in batch) else 0, len(events))
