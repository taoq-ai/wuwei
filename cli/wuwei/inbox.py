"""The workspace inbox: normalised inbound events, redacted before they are stored."""

from wuwei import registry, state
from wuwei.registry import Result

FIELDS = ('id', 'source', 'channel', 'thread', 'sender', 'text', 'ts')
REQUIRED = ('id', 'source', 'channel', 'sender', 'ts')


def _redacted(result):
    data = result.data
    return (result.exit in (0, 1) and isinstance(data, dict) and isinstance(data.get('text'), str)
            and isinstance(data.get('findings'), list)
            and all(isinstance(item, dict) and isinstance(item.get('kind'), str)
                    for item in data['findings']))


def store(root, config, events):
    """The only writer of .wuwei/inbox/inbox.jsonl; nothing is stored unless all events redact."""
    if not isinstance(events, list) or not all(
            isinstance(event, dict) and tuple(sorted(event)) == tuple(sorted(FIELDS))
            and all(isinstance(value, str) for value in event.values())
            and all(event[key] for key in REQUIRED) for event in events):
        return Result(2, None, 'inbox: malformed event')
    redactor = registry.load('redactor', config)
    batch = []
    for event in events:
        result = redactor.redact(event['text'], root=root)
        if not _redacted(result):
            return Result(2, None, result.reason or 'inbox: redactor returned malformed data')
        batch.append((event, result.data))
    try:
        for event, data in batch:
            state.append_jsonl(root / '.wuwei' / 'inbox' / 'inbox.jsonl', {**event, 'text': data['text']})
            if data['findings']:
                state.append_event('inbox.redacted', {
                    'id': event['id'], 'source': event['source'],
                    'findings': [item['kind'] for item in data['findings']]}, root)
    except (OSError, ValueError) as exc:
        return Result(2, None, f'inbox: could not store: {exc}')
    return Result(1 if any(data['findings'] for _, data in batch) else 0, len(events))
