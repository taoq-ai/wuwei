"""Notion pages through the public REST API."""

import re

from .._http import Failure, credential, operation, request
from ._lines import parse
from wuwei.registry import outward_operation


URL = 'https://api.notion.com/v1'
KINDS = {'h1': 'heading_1', 'h2': 'heading_2', 'h3': 'heading_3', 'li': 'bulleted_list_item',
         'p': 'paragraph'}


def _id(ref):
    found = re.search(r'([0-9a-f]{32})$', str(ref).replace('-', '').split('?')[0].split('#')[0])
    if not found:
        raise Failure('invalid Notion page')
    return found[1]


def _call(path, payload=None, method='GET'):
    value = request(URL + path, credential('NOTION_TOKEN'), payload, method=method,
                    extra_headers={'Notion-Version': '2022-06-28'})
    if value.get('object') == 'error':
        raise Failure('Notion error response')
    return value


def _blocks(body):
    # ponytail: Notion takes at most 100 blocks and 2000 characters per text; longer pages
    # refuse until they are split into several appends.
    rows = parse(body)
    if len(rows) > 100 or any(len(text) > 2000 for _, text in rows):
        raise Failure('page too long for one Notion request')
    return [{'object': 'block', 'type': KINDS[kind],
             KINDS[kind]: {'rich_text': [{'type': 'text', 'text': {'content': text}}]}}
            for kind, text in rows]


def _text(value, key):
    if not isinstance(value.get(key), str) or not value[key]:
        raise Failure('invalid Notion response')
    return value[key]


@operation('notion.read')
def read(ref, *, root=None):
    value = _call(f'/pages/{_id(ref)}')
    title = next((''.join(part['plain_text'] for part in field['title'])
                  for field in value['properties'].values() if field.get('type') == 'title'), '')
    return {'id': _text(value, 'id'), 'title': title, 'link': _text(value, 'url'),
            'updated': _text(value, 'last_edited_time')}


@outward_operation('docs')
@operation('notion.write')
def write(draft, *, root=None):
    if draft['ref']:
        page = _id(draft['ref'])
        _call(f'/blocks/{page}/children', {'children': _blocks(draft['body'])}, 'PATCH')
        return {'id': page, 'link': f'https://www.notion.so/{page}'}
    value = _call('/pages', {'parent': {'page_id': _id(draft['parent'])},
                             'properties': {'title': {'title': [{'text': {'content': draft['title']}}]}},
                             'children': _blocks(draft['body'])}, 'POST')
    return {'id': _text(value, 'id'), 'link': _text(value, 'url')}
