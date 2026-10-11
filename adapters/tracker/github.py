"""GitHub Issues and Projects tracker adapter (GraphQL, GITHUB_TRACKER_TOKEN or the gh login).

Ticket ids are owner/repo#N. With tracker.board (owner/number) a transition sets the board's
Status field; without one, in review is a label and done closes the issue. With
tracker.auth = "gh" and no GITHUB_TRACKER_TOKEN, the same GraphQL runs through gh api graphql.
"""

import json
import os
import re
import subprocess

from .._http import Failure, credential, gh_limit, operation, request, retry, settings, status
from wuwei import redact
from wuwei.registry import outward_operation


URL = 'https://api.github.com/graphql'
ISSUE = 'repository(owner:$owner,name:$name){issue(number:$number){id}}'
VARIABLES = '$owner:String!,$name:String!,$number:Int!'


def _query(query, variables, root):
    payload = {'query': query, 'variables': variables}
    if os.environ.get('GITHUB_TRACKER_TOKEN'):
        value = retry(lambda: request(URL, credential('GITHUB_TRACKER_TOKEN'), payload), root)
    elif settings(root)['tracker']['auth'] == 'gh':
        value = retry(lambda: _gh(payload), root)
    else:
        raise Failure('GITHUB_TRACKER_TOKEN is missing; set it in .wuwei/env, or set '
                      'tracker.auth = "gh" to use your gh login')
    if value.get('errors') or not isinstance(value.get('data'), dict):
        raise _error(value, variables)
    return value['data']


def _error(value, variables):
    """#617: name the ticket and GitHub's first error message (one line, redacted, capped);
    the error body is read for that message only, never as data."""
    ticket = ('{owner}/{name}#{number}'.format(**variables)
              if {'owner', 'name', 'number'} <= variables.keys() else '')
    errors = value.get('errors')
    first = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
    message = first.get('message')
    text = redact.redact(' '.join(message.split()))[:160] if isinstance(message, str) else ''
    return Failure('GitHub error response' + (f' for {ticket}' if ticket else '')
                   + (f': {text}' if text else ''))


def _gh(payload):
    """The owner's gh login (#602); only the exit, an HTTP status and a hint leave, never gh's text."""
    try:
        result = subprocess.run(['gh', 'api', 'graphql', '--hostname', 'github.com', '--input', '-'],
                                input=json.dumps(payload), capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        raise Failure('gh is not on PATH; install the GitHub CLI and run gh auth login') from None
    except subprocess.TimeoutExpired:
        raise Failure('gh api graphql timed out after 30 s') from None
    if result.returncode:
        if limit := gh_limit(result.stderr):
            raise limit
        code = re.search(r'\(HTTP ([1-5][0-9][0-9])\)', result.stderr)
        if code:
            hint = status(int(code[1]))
        elif re.search(r'scope', result.stderr, re.I):
            hint = 'run gh auth refresh -s project'
        elif result.stdout.lstrip().startswith('{'):  # a GraphQL error body: its message only (#617)
            try:
                body = json.loads(result.stdout)
            except ValueError:
                body = {}
            hint = str(_error(body if isinstance(body, dict) else {}, payload['variables']))
        else:
            hint = 'run gh auth status'
        raise Failure(f'gh api graphql exited {result.returncode}: {hint}')
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise Failure('invalid JSON object')
    return value


def _ref(item):
    match = re.fullmatch(r'([\w.-]+)/([\w.-]+)#([1-9][0-9]*)', item if isinstance(item, str) else '')
    if not match:
        raise Failure('invalid GitHub issue id; expected owner/repo#N')
    return {'owner': match[1], 'name': match[2], 'number': int(match[3])}


def _repo(root):
    config = settings(root)
    repo = config['tracker']['project'] or next((row['name'] for row in config['repos']), '')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise Failure('tracker.project must name the GitHub owner/repo')
    return repo


def _repos(root):
    """tracker.project and every configured repository, once each (#601)."""
    config = settings(root)
    names = list(dict.fromkeys(name for name in (config['tracker']['project'],
                                                 *(row['name'] for row in config['repos'])) if name))
    if not names:
        _repo(root)  # its message names the missing project
    for name in names:
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', name):
            raise Failure(f'{name} is not a GitHub owner/repo; fix tracker.project or repos.name')
    return names


def _issue(item, root):
    return _query(f'query({VARIABLES}){{{ISSUE}}}', _ref(item), root)['repository']['issue']['id']


@operation('github.backlog')
def backlog(filter, *, root=None):
    if not isinstance(filter, str):
        raise Failure('invalid backlog filter')
    labels = ',labels:[$label]' if filter else ''
    found = []
    for repo in _repos(root):
        owner, name = repo.split('/')
        rows = _query('query($owner:String!,$name:String!' + (',$label:String!' if filter else '') +
                      '){repository(owner:$owner,name:$name){issues(first:100,states:OPEN' + labels +
                      '){nodes{number title url updatedAt} pageInfo{hasNextPage}}}}',
                      {'owner': owner, 'name': name, **({'label': filter} if filter else {})}, root
                      )['repository']['issues']
        if rows['pageInfo']['hasNextPage'] is not False:
            raise Failure(f'incomplete GitHub backlog for {repo}')
        found += [{'id': f"{repo}#{row['number']}", 'title': row['title'], 'url': row['url'],
                   'updated': row['updatedAt'], 'state': 'Open'} for row in rows['nodes']]
    return found


@operation('github.claim')
def claim(item, *, root=None):
    value = _query(f'query({VARIABLES}){{viewer{{id}} {ISSUE}}}', _ref(item), root)
    return _query('mutation($id:ID!,$user:ID!){addAssigneesToAssignable(input:{assignableId:$id,'
                  'assigneeIds:[$user]}){assignable{... on Issue{id}}}}',
                  {'id': value['repository']['issue']['id'], 'user': value['viewer']['id']}, root)


@operation('github.transition')
def transition(item, state, *, root=None):
    tracker = settings(root)['tracker']
    if tracker['board']:
        match = re.fullmatch(r'([\w.-]+)/([1-9][0-9]*)', tracker['board'])
        if not match:
            raise Failure('tracker.board must be owner/number')
        value = _query(
            f'query({VARIABLES},$login:String!,$board:Int!){{repositoryOwner(login:$login){{'
            '... on ProjectV2Owner{projectV2(number:$board){id field(name:"Status"){'
            '... on ProjectV2SingleSelectField{id options{id name}}}}}} '
            'repository(owner:$owner,name:$name){issue(number:$number){'
            'projectItems(first:100){nodes{id project{id}}}}}}',
            {**_ref(item), 'login': match[1], 'board': int(match[2])}, root)
        project = value['repositoryOwner']['projectV2']
        option = [row['id'] for row in project['field']['options'] if row['name'] == state]
        node = [row['id'] for row in value['repository']['issue']['projectItems']['nodes']
                if row['project']['id'] == project['id']]
        if len(option) != 1 or len(node) != 1:
            raise Failure('GitHub board status or issue item not found')
        return _query('mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){'
                      'updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,'
                      'fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}',
                      {'project': project['id'], 'item': node[0],
                       'field': project['field']['id'], 'option': option[0]}, root)
    if state == tracker['states']['done']:
        return _query('mutation($id:ID!){closeIssue(input:{issueId:$id}){issue{id}}}',
                      {'id': _issue(item, root)}, root)
    value = _query(f'query({VARIABLES},$label:String!){{repository(owner:$owner,name:$name){{'
                   'issue(number:$number){id} label(name:$label){id}}}', {**_ref(item), 'label': state}, root)
    if not value['repository']['label']:
        raise Failure('GitHub label for that state not found')
    return _query('mutation($id:ID!,$label:ID!){addLabelsToLabelable(input:{labelableId:$id,'
                  'labelIds:[$label]}){labelable{... on Issue{id}}}}',
                  {'id': value['repository']['issue']['id'], 'label': value['repository']['label']['id']}, root)


@outward_operation('tracker')
@operation('github.create')
def create(draft, *, root=None):
    if (not isinstance(draft, dict) or not isinstance(draft.get('title'), str)
            or draft.keys() - {'title', 'description', 'item', 'category', 'parent'}):
        raise Failure('invalid issue draft')
    repo = _repo(root)
    owner, name = repo.split('/')
    value = _query('query($owner:String!,$name:String!){repository(owner:$owner,name:$name){'
                   'id label(name:"bug"){id}}}', {'owner': owner, 'name': name}, root)['repository']
    body = draft.get('description', '') + (f"\n\nRelated: {draft['parent']}" if draft.get('parent') else '')
    labels = [value['label']['id']] if draft.get('category') == 'bugs' and value['label'] else []
    issue = _query('mutation($repositoryId:ID!,$title:String!,$body:String!,$labelIds:[ID!]){'
                   'createIssue(input:{repositoryId:$repositoryId,title:$title,body:$body,'
                   'labelIds:$labelIds}){issue{number url}}}',
                   {'repositoryId': value['id'], 'title': draft['title'], 'body': body,
                    'labelIds': labels}, root)['createIssue']['issue']
    return {'id': f"{repo}#{issue['number']}", 'url': issue['url']}


@outward_operation('tracker')
@operation('github.comment')
def comment(item, text, category, *, root=None):
    value = _query('mutation($id:ID!,$body:String!){addComment(input:{subjectId:$id,body:$body}){'
                   'commentEdge{node{id}}}}', {'id': _issue(item, root), 'body': text}, root)
    return {'id': value['addComment']['commentEdge']['node']['id']}


@operation('github.history')
def history(item, *, root=None):
    """The first assignment stands for In Progress; Projects v2 keeps no readable history."""
    nodes = _query(f'query({VARIABLES}){{repository(owner:$owner,name:$name){{issue(number:$number){{'
                   'timelineItems(itemTypes:[ASSIGNED_EVENT],first:1){nodes{... on AssignedEvent{'
                   'createdAt}}}}}}', _ref(item), root)['repository']['issue']['timelineItems']['nodes']
    return [{'createdAt': nodes[0]['createdAt'], 'toState': {'name': 'In Progress'}}] if nodes else []


@operation('github.created')
def created(item, *, root=None):
    value = _query(f'query({VARIABLES}){{repository(owner:$owner,name:$name){{issue(number:$number){{'
                   'createdAt}}}', _ref(item), root)['repository']['issue']['createdAt']
    if not isinstance(value, str):
        raise Failure('missing issue creation time')
    return value
