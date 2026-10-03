"""The docs port contract: every adapter, recorded HTTP, no network (#419)."""

import base64
import importlib
import json
import os
from pathlib import Path

import pytest

from test_reference_adapters import Reply

ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = json.loads((ROOT / 'tests/fixtures/docs/recordings.json').read_text())
NOTION = RECORDINGS['notion']
CONFLUENCE = RECORDINGS['confluence']
NOTION_PAGE = 'https://www.notion.so/Example-docs-11111111222233334444555555555555'
NOTION_PARENT = 'https://www.notion.so/Docs-home-00000000111122223333444444444444'
WIKI = 'https://example.atlassian.net/wiki'
CONFLUENCE_PAGE = WIKI + '/spaces/DOCS/pages/101/Example+docs'
CONFLUENCE_PARENT = WIKI + '/spaces/DOCS/pages/100/Docs+home'
BODY = '### What changed\nAdds a <flag>.\n- Pull request: https://example.com/pr/1\nPlain line.'


def replay(monkeypatch, *answers):
    calls = []
    answers = iter(answers)

    def urlopen(request, timeout=None):
        assert timeout == 30
        calls.append((request.get_method(), request.full_url, dict(request.header_items()),
                      json.loads(request.data) if request.data else None))
        answer = next(answers)
        return answer if isinstance(answer, Reply) else Reply(answer)

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    return calls


def draft(parent, ref=''):
    return {'kind': 'page', 'item': 'X', 'title': 'X: Add a flag', 'body': BODY,
            'parent': parent, 'ref': ref}


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv('NOTION_TOKEN', 'private-notion-token')
    monkeypatch.setenv('CONFLUENCE_EMAIL', 'docs@example.com')
    monkeypatch.setenv('CONFLUENCE_API_TOKEN', 'private-confluence-token')


def test_known_adapters():
    from wuwei import registry
    assert registry.known('docs') == ['confluence', 'markdown', 'none', 'notion']


def test_notion_contract(monkeypatch, credentials):
    notion = importlib.import_module('adapters.docs.notion')
    calls = replay(monkeypatch, NOTION['read'], NOTION['create'], NOTION['append'])
    result = notion.read(NOTION_PAGE)
    assert result.exit == 0 and result.data == {
        'id': NOTION['read']['id'], 'title': 'Example docs', 'link': NOTION['read']['url'],
        'updated': '2026-10-01T10:00:00.000Z'}
    write = notion.write.__wrapped__
    created = write(draft(NOTION_PARENT))
    assert created.exit == 0 and created.data == {'id': NOTION['create']['id'],
                                                  'link': NOTION['create']['url']}
    appended = write(draft(NOTION_PARENT, NOTION_PAGE))
    assert appended.exit == 0 and appended.data == {
        'id': '11111111222233334444555555555555',
        'link': 'https://www.notion.so/11111111222233334444555555555555'}
    base = 'https://api.notion.com/v1'
    assert [call[:2] for call in calls] == [
        ('GET', base + '/pages/11111111222233334444555555555555'),
        ('POST', base + '/pages'),
        ('PATCH', base + '/blocks/11111111222233334444555555555555/children')]
    assert calls[0][3] is None
    assert all(call[2]['Authorization'] == 'Bearer private-notion-token' for call in calls)
    blocks = [{'object': 'block', 'type': kind,
               kind: {'rich_text': [{'type': 'text', 'text': {'content': text}}]}}
              for kind, text in (('heading_3', 'What changed'), ('paragraph', 'Adds a <flag>.'),
                                 ('bulleted_list_item', 'Pull request: https://example.com/pr/1'),
                                 ('paragraph', 'Plain line.'))]
    assert calls[1][3] == {'parent': {'page_id': '00000000111122223333444444444444'},
                           'properties': {'title': {'title': [{'text': {'content': 'X: Add a flag'}}]}},
                           'children': blocks}
    assert calls[2][3] == {'children': blocks}


def test_confluence_contract(monkeypatch, credentials):
    confluence = importlib.import_module('adapters.docs.confluence')
    calls = replay(monkeypatch, CONFLUENCE['read'], CONFLUENCE['parent'], CONFLUENCE['create'],
                   CONFLUENCE['current'], CONFLUENCE['update'])
    result = confluence.read(CONFLUENCE_PAGE)
    assert result.exit == 0 and result.data == {
        'id': '101', 'title': 'Example docs', 'link': CONFLUENCE_PAGE,
        'updated': '2026-10-01T10:00:00.000Z'}
    write = confluence.write.__wrapped__
    created = write(draft(CONFLUENCE_PARENT))
    assert created.exit == 0 and created.data == {'id': '102', 'link': WIKI + '/spaces/DOCS/pages/102/X'}
    appended = write(draft(CONFLUENCE_PARENT, CONFLUENCE_PAGE))
    assert appended.exit == 0 and appended.data == {'id': '101', 'link': CONFLUENCE_PAGE}
    pages = WIKI + '/api/v2/pages'
    assert [call[:2] for call in calls] == [
        ('GET', pages + '/101'), ('GET', pages + '/100'), ('POST', pages),
        ('GET', pages + '/101?body-format=storage'), ('PUT', pages + '/101')]
    token = base64.b64encode(b'docs@example.com:private-confluence-token').decode()
    assert all(call[2]['Authorization'] == 'Basic ' + token for call in calls)
    storage = ('<h3>What changed</h3><p>Adds a &lt;flag&gt;.</p>'
               '<ul><li>Pull request: https://example.com/pr/1</li></ul><p>Plain line.</p>')
    assert calls[2][3] == {'spaceId': '55', 'status': 'current', 'title': 'X: Add a flag',
                           'parentId': '100', 'body': {'representation': 'storage', 'value': storage}}
    assert calls[4][3] == {'id': '101', 'status': 'current', 'title': 'Example docs',
                           'body': {'representation': 'storage',
                                    'value': '<p>Earlier text</p>' + storage},
                           'version': {'number': 4}}


@pytest.mark.parametrize('name,ref,answer', [
    ('notion', NOTION_PAGE, NOTION['error']),
    ('confluence', CONFLUENCE_PAGE, Reply(CONFLUENCE['error'], status=500)),
])
def test_error_body_is_unrun_without_provider_text(monkeypatch, credentials, name, ref, answer):
    adapter = importlib.import_module(f'adapters.docs.{name}')
    replay(monkeypatch, answer)
    result = adapter.read(ref)
    assert result.exit == 2 and result.data is None
    assert 'provider detail' not in result.reason


@pytest.mark.parametrize('name,variable,ref', [
    ('notion', 'NOTION_TOKEN', NOTION_PAGE),
    ('confluence', 'CONFLUENCE_EMAIL', CONFLUENCE_PAGE),
    ('confluence', 'CONFLUENCE_API_TOKEN', CONFLUENCE_PAGE),
])
def test_missing_credential_never_calls_network(monkeypatch, credentials, name, variable, ref):
    monkeypatch.delenv(variable)
    calls = replay(monkeypatch)
    adapter = importlib.import_module(f'adapters.docs.{name}')
    for result in (adapter.read(ref), adapter.write.__wrapped__(draft(ref))):
        assert result.exit == 2 and variable in result.reason
    assert calls == []


def test_markdown_contract(tmp_path, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    markdown = importlib.import_module('adapters.docs.markdown')
    parent = tmp_path / 'worktree/docs'
    created = markdown.write(draft(str(parent)))
    target = parent / 'X.md'
    assert created.exit == 0 and created.data == {'id': str(target), 'link': str(target)}
    assert target.read_text() == '# X: Add a flag\n\n' + BODY
    read = markdown.read(str(target))
    assert read.exit == 0 and read.data['id'] == read.data['link'] == str(target)
    assert read.data['title'] == 'X: Add a flag' and read.data['updated']
    appended = markdown.write(draft(str(parent), str(target)) | {'body': '## 2026-10-03\nMore.'})
    assert appended.exit == 0
    assert target.read_text() == '# X: Add a flag\n\n' + BODY + '\n## 2026-10-03\nMore.'
    assert markdown.read(str(parent / 'missing.md')).exit == 1
    link = parent / 'link.md'
    link.symlink_to(target)
    assert markdown.read(str(link)).exit == 1
    assert markdown.write(draft(str(parent), str(link))).exit == 2
    assert markdown.write(draft(str(parent), str(tmp_path / 'outside.md'))).exit == 2
    assert not (tmp_path / 'outside.md').exists()
    assert sorted(os.listdir(parent)) == ['X.md', 'link.md']
