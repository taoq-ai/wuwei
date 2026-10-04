"""Jira Cloud REST tracker adapter (Basic auth: JIRA_EMAIL and JIRA_API_TOKEN at JIRA_SITE)."""

from base64 import b64encode
import re

from .._http import Failure, credential, operation, request, settings
from wuwei.registry import outward_operation


def _site():
    site = credential('JIRA_SITE').rstrip('/')
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::[0-9]+)?', site):
        raise Failure('JIRA_SITE must be an https:// origin')
    return site


def _call(path, payload=None, method='POST'):
    site = _site()
    token = b64encode(f"{credential('JIRA_EMAIL')}:{credential('JIRA_API_TOKEN')}".encode()).decode()
    return request(f'{site}/rest/api/3/{path}', token, payload, method=method,
                   authorization='Basic', extra_headers={'Accept': 'application/json'})


def _key(item):
    if not isinstance(item, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]*-[1-9][0-9]*', item):
        raise Failure('invalid Jira issue key')
    return item


def _document(text):
    """Atlassian document format: one paragraph per line."""
    return {'type': 'doc', 'version': 1, 'content': [
        {'type': 'paragraph', 'content': [{'type': 'text', 'text': line}] if line else []}
        for line in text.splitlines() or ['']]}


def _project(root):
    project = settings(root)['tracker']['project']
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', project):
        raise Failure('tracker.project must name the Jira project key')
    return project


@operation('jira.backlog')
def backlog(filter, *, root=None):
    if not isinstance(filter, str):
        raise Failure('invalid backlog filter')
    jql = f'project = "{_project(root)}" AND statusCategory != Done' + (f' AND ({filter})' if filter else '')
    value = _call('search/jql', {'jql': jql, 'fields': ['summary', 'updated', 'status'],
                                 'maxResults': 100})
    if value.get('nextPageToken') or not isinstance(value.get('issues'), list):
        raise Failure('incomplete Jira backlog')
    site = _site()
    return [{'id': row['key'], 'title': row['fields']['summary'],
             'url': f"{site}/browse/{row['key']}", 'updated': row['fields']['updated'],
             'state': row['fields']['status']['name']} for row in value['issues']]


@operation('jira.claim')
def claim(item, *, root=None):
    account = _call('myself', method='GET')['accountId']
    return _call(f'issue/{_key(item)}/assignee', {'accountId': account}, 'PUT')


@operation('jira.transition')
def transition(item, state, *, root=None):
    rows = _call(f'issue/{_key(item)}/transitions', method='GET')['transitions']
    matches = [row['id'] for row in rows if row['to']['name'] == state]
    if len(matches) != 1:
        raise Failure('Jira transition to that state not found or ambiguous')
    return _call(f'issue/{item}/transitions', {'transition': {'id': matches[0]}})


@outward_operation('tracker')
@operation('jira.create')
def create(draft, *, root=None):
    if (not isinstance(draft, dict) or not isinstance(draft.get('title'), str)
            or draft.keys() - {'title', 'description', 'item', 'category', 'parent'}):
        raise Failure('invalid issue draft')
    parent = _key(draft['parent']) if draft.get('parent') else None
    created = _call('issue', {'fields': {
        'project': {'key': _project(root)}, 'summary': draft['title'],
        'description': _document(draft.get('description', '')),
        'issuetype': {'name': 'Bug' if draft.get('category') == 'bugs' else 'Task'}}})
    key = _key(created['key'])
    if parent:
        try:  # The issue exists now; a failed link must not invite a duplicate create.
            _call('issueLink', {'type': {'name': 'Relates'}, 'inwardIssue': {'key': key},
                                'outwardIssue': {'key': parent}})
        except Failure:
            pass
    return {'id': key, 'url': f'{_site()}/browse/{key}'}


@outward_operation('tracker')
@operation('jira.comment')
def comment(item, text, category, *, root=None):
    return {'id': _call(f'issue/{_key(item)}/comment', {'body': _document(text)})['id']}


@operation('jira.history')
def history(item, *, root=None):
    value = _call(f'issue/{_key(item)}/changelog?maxResults=100', method='GET')
    if value.get('isLast') is not True or not isinstance(value.get('values'), list):
        raise Failure('incomplete Jira history')
    return [{'createdAt': row['created'], 'toState': {'name': change['toString']}}
            for row in value['values'] for change in row['items'] if change['field'] == 'status']


@operation('jira.created')
def created(item, *, root=None):
    value = _call(f'issue/{_key(item)}?fields=created', method='GET')['fields']['created']
    if not isinstance(value, str):
        raise Failure('missing issue creation time')
    return value
