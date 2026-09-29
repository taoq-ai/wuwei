"""Parse and validate workspace note frontmatter."""

from datetime import date
import json
import re

OWNER_NOTES = {'baseline'}

TYPES = {'hub', 'reference', 'decision', 'person', 'question'}
STATUSES = {'active', 'archived'}
FIELDS = {'type', 'summary', 'aliases', 'status', 'created'}
SLUG_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def parse_note(text):
    """Return (fields, body), or raise ValueError for an invalid note."""
    lines = [line.rstrip('\r') for line in text.split('\n')]
    if lines[0] != '---':
        raise ValueError('missing frontmatter')
    fields = {}
    for index, line in enumerate(lines[1:], 1):
        if line == '---':
            body = '\n'.join(lines[index + 1:])
            break
        if line[:1].isspace():
            raise ValueError('invalid frontmatter line')
        match = re.fullmatch(r'([a-z]+):[ \t]*(.*?)[ \t]*', line)
        if not match:
            raise ValueError('invalid frontmatter line')
        key, value = match.groups()
        if key not in FIELDS or key in fields:
            raise ValueError(f'unknown or duplicate field: {key}')
        if key == 'aliases':
            if value.splitlines() != [value] or not (value.startswith('[') and value.endswith(']')):
                raise ValueError('aliases must be a list')
            items = value[1:-1].strip()
            values = [] if not items else [part.strip() for part in items.split(',')]
            if any(not item or '[' in item or ']' in item for item in values):
                raise ValueError('invalid aliases')
            try:
                fields[key] = [json.loads(item) if item.startswith('"') else item for item in values]
            except json.JSONDecodeError as exc:
                raise ValueError('invalid aliases') from exc
        else:
            fields[key] = json.loads(value) if value.startswith('"') else value
            if key == 'summary' and (not fields[key].strip() or fields[key].splitlines() != [fields[key]]):
                raise ValueError('summary must be one nonempty line')
    else:
        raise ValueError('missing frontmatter closing delimiter')
    for key in ('type', 'summary', 'aliases', 'status'):
        if key not in fields:
            raise ValueError(f'missing {key}')
    if fields['type'] not in TYPES:
        raise ValueError('invalid type')
    if any(not item.strip() or item.splitlines() != [item] for item in fields['aliases']):
        raise ValueError('invalid aliases')
    if fields['status'] not in STATUSES:
        raise ValueError('invalid status')
    if 'created' in fields:
        try:
            date.fromisoformat(fields['created'])
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid created date') from exc
    if fields['type'] == 'decision' and not any(re.match(r'^Why:\s*\S', line) for line in body.splitlines()):
        raise ValueError('decision note requires a Why: line')
    return fields, body
