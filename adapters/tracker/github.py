"""GitHub Issues and Projects tracker adapter (GraphQL, GITHUB_TRACKER_TOKEN).

Ticket ids are owner/repo#N. With tracker.board (owner/number) a transition sets the board's
Status field; without one, in review is a label and done closes the issue.
"""

import re

from .._http import Failure, credential, operation, request, settings
from wuwei.registry import outward_operation


URL = 'https://api.github.com/graphql'
ISSUE = 'repository(owner:$owner,name:$name){issue(number:$number){id}}'
VARIABLES = '$owner:String!,$name:String!,$number:Int!'


def _query(query, variables):
    value = request(URL, credential('GITHUB_TRACKER_TOKEN'), {'query': query, 'variables': variables})
    if value.get('errors') or not isinstance(value.get('data'), dict):
        raise Failure('GitHub error response')
    return value['data']


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


def _issue(item):
    return _query(f'query({VARIABLES}){{{ISSUE}}}', _ref(item))['repository']['issue']['id']


@operation('github.backlog')
def backlog(filter, *, root=None):
    if not isinstance(filter, str):
        raise Failure('invalid backlog filter')
    repo = _repo(root)
    owner, name = repo.split('/')
    labels = ',labels:[$label]' if filter else ''
    rows = _query('query($owner:String!,$name:String!' + (',$label:String!' if filter else '') +
                  '){repository(owner:$owner,name:$name){issues(first:100,states:OPEN' + labels +
                  '){nodes{number title url updatedAt} pageInfo{hasNextPage}}}}',
                  {'owner': owner, 'name': name, **({'label': filter} if filter else {})}
                  )['repository']['issues']
    if rows['pageInfo']['hasNextPage'] is not False:
        raise Failure('incomplete GitHub backlog')
    return [{'id': f"{repo}#{row['number']}", 'title': row['title'], 'url': row['url'],
             'updated': row['updatedAt'], 'state': 'Open'} for row in rows['nodes']]


@operation('github.claim')
def claim(item, *, root=None):
    value = _query(f'query({VARIABLES}){{viewer{{id}} {ISSUE}}}', _ref(item))
    return _query('mutation($id:ID!,$user:ID!){addAssigneesToAssignable(input:{assignableId:$id,'
                  'assigneeIds:[$user]}){assignable{... on Issue{id}}}}',
                  {'id': value['repository']['issue']['id'], 'user': value['viewer']['id']})


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
            {**_ref(item), 'login': match[1], 'board': int(match[2])})
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
                       'field': project['field']['id'], 'option': option[0]})
    if state == tracker['states']['done']:
        return _query('mutation($id:ID!){closeIssue(input:{issueId:$id}){issue{id}}}',
                      {'id': _issue(item)})
    value = _query(f'query({VARIABLES},$label:String!){{repository(owner:$owner,name:$name){{'
                   'issue(number:$number){id} label(name:$label){id}}}', {**_ref(item), 'label': state})
    if not value['repository']['label']:
        raise Failure('GitHub label for that state not found')
    return _query('mutation($id:ID!,$label:ID!){addLabelsToLabelable(input:{labelableId:$id,'
                  'labelIds:[$label]}){labelable{... on Issue{id}}}}',
                  {'id': value['repository']['issue']['id'], 'label': value['repository']['label']['id']})


@outward_operation('tracker')
@operation('github.create')
def create(draft, *, root=None):
    if (not isinstance(draft, dict) or not isinstance(draft.get('title'), str)
            or draft.keys() - {'title', 'description', 'item', 'category', 'parent'}):
        raise Failure('invalid issue draft')
    repo = _repo(root)
    owner, name = repo.split('/')
    value = _query('query($owner:String!,$name:String!){repository(owner:$owner,name:$name){'
                   'id label(name:"bug"){id}}}', {'owner': owner, 'name': name})['repository']
    body = draft.get('description', '') + (f"\n\nRelated: {draft['parent']}" if draft.get('parent') else '')
    labels = [value['label']['id']] if draft.get('category') == 'bugs' and value['label'] else []
    issue = _query('mutation($repositoryId:ID!,$title:String!,$body:String!,$labelIds:[ID!]){'
                   'createIssue(input:{repositoryId:$repositoryId,title:$title,body:$body,'
                   'labelIds:$labelIds}){issue{number url}}}',
                   {'repositoryId': value['id'], 'title': draft['title'], 'body': body,
                    'labelIds': labels})['createIssue']['issue']
    return {'id': f"{repo}#{issue['number']}", 'url': issue['url']}


@outward_operation('tracker')
@operation('github.comment')
def comment(item, text, category, *, root=None):
    value = _query('mutation($id:ID!,$body:String!){addComment(input:{subjectId:$id,body:$body}){'
                   'commentEdge{node{id}}}}', {'id': _issue(item), 'body': text})
    return {'id': value['addComment']['commentEdge']['node']['id']}


@operation('github.history')
def history(item, *, root=None):
    """The first assignment stands for In Progress; Projects v2 keeps no readable history."""
    nodes = _query(f'query({VARIABLES}){{repository(owner:$owner,name:$name){{issue(number:$number){{'
                   'timelineItems(itemTypes:[ASSIGNED_EVENT],first:1){nodes{... on AssignedEvent{'
                   'createdAt}}}}}}', _ref(item))['repository']['issue']['timelineItems']['nodes']
    return [{'createdAt': nodes[0]['createdAt'], 'toState': {'name': 'In Progress'}}] if nodes else []


@operation('github.created')
def created(item, *, root=None):
    value = _query(f'query({VARIABLES}){{repository(owner:$owner,name:$name){{issue(number:$number){{'
                   'createdAt}}}}', _ref(item))['repository']['issue']['createdAt']
    if not isinstance(value, str):
        raise Failure('missing issue creation time')
    return value
