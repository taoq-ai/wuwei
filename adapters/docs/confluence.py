"""Confluence Cloud pages through the v2 REST API."""

import base64
import html
import re

from .._http import Failure, credential, operation, request
from ._lines import parse
from wuwei.registry import outward_operation


def _page(ref, root):
    """(base, id) from a page link, or a bare id under docs.space's site."""
    found = re.fullmatch(r'(https://[\w-]+\.atlassian\.net/wiki)/.*?/pages/(\d+)(?:[/?#].*)?', str(ref))
    if found:
        return found[1], found[2]
    if re.fullmatch(r'\d+', str(ref)) and root is not None:
        from wuwei import workspace
        space = workspace.load_config(workspace.find_workspace(root))['docs']['space']
        found = re.fullmatch(r'(https://[\w-]+\.atlassian\.net/wiki)/.*', space)
        if found:
            return found[1], str(ref)
    raise Failure('invalid Confluence page')


def _call(url, payload=None, method='GET'):
    token = base64.b64encode(f"{credential('CONFLUENCE_EMAIL')}:"
                             f"{credential('CONFLUENCE_API_TOKEN')}".encode()).decode()
    value = request(url, token, payload, authorization='Basic', method=method)
    if not isinstance(value.get('id'), str) or not value['id']:
        raise Failure('invalid Confluence response')
    return value


def _storage(body):
    out, items = [], []
    for kind, text in parse(body) + [('end', '')]:
        if kind != 'li' and items:
            out.append('<ul>' + ''.join(items) + '</ul>')
            items = []
        text = html.escape(text, quote=False)
        if kind == 'li':
            items.append(f'<li>{text}</li>')
        elif kind != 'end':
            out.append(f'<{kind}>{text}</{kind}>')
    return ''.join(out)


def _link(base, value):
    webui = value['_links']['webui']
    if not isinstance(webui, str) or not webui.startswith('/'):
        raise Failure('invalid Confluence link')
    return base + webui


@operation('confluence.read')
def read(ref, *, root=None):
    base, page = _page(ref, root)
    value = _call(f'{base}/api/v2/pages/{page}')
    return {'id': value['id'], 'title': value['title'], 'link': _link(base, value),
            'updated': value['version']['createdAt']}


@outward_operation('docs')
@operation('confluence.write')
def write(draft, *, root=None):
    storage = _storage(draft['body'])
    if draft['ref']:
        base, page = _page(draft['ref'], root)
        current = _call(f'{base}/api/v2/pages/{page}?body-format=storage')
        value = _call(f'{base}/api/v2/pages/{page}', {
            'id': page, 'status': 'current', 'title': current['title'],
            'body': {'representation': 'storage',
                     'value': current['body']['storage']['value'] + storage},
            'version': {'number': current['version']['number'] + 1}}, 'PUT')
    else:
        base, parent = _page(draft['parent'], root)
        space = _call(f'{base}/api/v2/pages/{parent}')['spaceId']
        value = _call(f'{base}/api/v2/pages', {
            'spaceId': space, 'status': 'current', 'title': draft['title'], 'parentId': parent,
            'body': {'representation': 'storage', 'value': storage}}, 'POST')
    return {'id': value['id'], 'link': _link(base, value)}
