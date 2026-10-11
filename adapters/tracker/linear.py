"""Linear GraphQL tracker adapter."""

from .._http import Failure, credential, operation, request, settings
from wuwei.registry import outward_operation


URL = 'https://api.linear.app/graphql'
_state_ids = {}


def _query(query, variables):
    value = request(URL, credential('LINEAR_API_KEY'),
                    {'query': query, 'variables': variables}, authorization='')
    if value.get('errors') or not isinstance(value.get('data'), dict):
        raise Failure('Linear error response')
    return value['data']


def _updated(item, changes):
    value = _query('mutation($id:String!,$input:IssueUpdateInput!){issueUpdate(id:$id,input:$input){success issue{id}}}',
                   {'id': item, 'input': changes})['issueUpdate']
    if value['success'] is not True or not isinstance(value['issue'], dict):
        raise Failure('Linear update failed')
    return value['issue']


@operation('linear.backlog')
def backlog(filter, *, root=None):
    if not isinstance(filter, str):
        raise Failure('invalid backlog filter')
    where = ',filter:{' + ('team:{id:{eq:$team}},' if filter else '') + 'state:{type:{nin:["completed","canceled"]}}}'
    declaration = '($team:String!)' if filter else ''
    rows = _query('query' + declaration + '{issues(first:100' + where +
                  '){nodes{identifier title url updatedAt state{name}} pageInfo{hasNextPage}}}',
                  {'team': filter} if filter else {})['issues']
    if not isinstance(rows.get('nodes'), list) or rows['pageInfo']['hasNextPage'] is not False:
        raise Failure('incomplete Linear backlog')
    result = []
    for row in rows['nodes']:
        values = (row['identifier'], row['title'], row['url'],
                  row['updatedAt'], row['state']['name'])
        if any(not isinstance(value, str) or not value for value in values):
            raise Failure('invalid Linear backlog issue')
        result.append(dict(zip(('id', 'title', 'url', 'updated', 'state'), values)))
    return result


@operation('linear.claim')
def claim(item, *, root=None):
    viewer = _query('query{viewer{id}}', {})['viewer']
    return _updated(item, {'assigneeId': viewer['id']})


@operation('linear.transition')
def transition(item, state, *, root=None):
    if not isinstance(state, str) or not state:
        raise Failure('invalid Linear state')
    issue = _query('query($id:String!){issue(id:$id){team{id}}}', {'id': item})['issue']
    team = issue['team']['id']
    if not isinstance(team, str) or not team:
        raise Failure('Linear issue has no team')
    if team not in _state_ids:
        rows = _query('query($team:String!){workflowStates(first:100,filter:{team:{id:{eq:$team}}}){nodes{id name} pageInfo{hasNextPage}}}',
                      {'team': team})['workflowStates']
        if rows['pageInfo']['hasNextPage'] is not False or not isinstance(rows['nodes'], list):
            raise Failure('incomplete Linear workflow states')
        names = {}
        for row in rows['nodes']:
            if not isinstance(row['id'], str) or not isinstance(row['name'], str):
                raise Failure('invalid Linear workflow state')
            if row['name'] in names:
                raise Failure('duplicate Linear workflow state name')
            names[row['name']] = row['id']
        _state_ids[team] = names
    state_id = _state_ids[team].get(state)
    if not state_id:
        raise Failure('Linear workflow state not found')
    return _updated(item, {'stateId': state_id})


def _uuid(item):
    issue = _query('query($id:String!){issue(id:$id){id}}', {'id': item})['issue']
    if not isinstance(issue, dict) or not isinstance(issue.get('id'), str):
        raise Failure('Linear issue not found')
    return issue['id']


@outward_operation('tracker')
@operation('linear.create')
def create(draft, *, root=None):
    """The neutral 5.11 draft, or Linear's own fields for existing callers."""
    if not isinstance(draft, dict) or not isinstance(draft.get('title'), str):
        raise Failure('invalid issue draft')
    if 'teamId' in draft:
        if draft.keys() - {'teamId', 'title', 'description', 'stateId', 'assigneeId', 'projectId'}:
            raise Failure('unsupported issue field')
        issue = dict(draft)
    else:
        if draft.keys() - {'title', 'description', 'item', 'category', 'parent'}:
            raise Failure('unsupported issue field')
        tracker = settings(root)['tracker']
        team = tracker['project'] or tracker['backlog_filter']
        if not team:
            raise Failure('tracker.project or backlog_filter must name a Linear team')
        issue = {'teamId': team, 'title': draft['title'], 'description': draft.get('description', '')}
        if draft.get('parent'):
            issue['parentId'] = _uuid(draft['parent'])
    value = _query('mutation($input:IssueCreateInput!){issueCreate(input:$input){success issue{id identifier url}}}',
                   {'input': issue})['issueCreate']
    if value['success'] is not True or not isinstance(value['issue'], dict):
        raise Failure('Linear create failed')
    return {'id': value['issue']['identifier'], 'url': value['issue']['url']}


@outward_operation('tracker')
@operation('linear.comment')
def comment(item, text, category, *, root=None):
    value = _query('mutation($input:CommentCreateInput!){commentCreate(input:$input){success comment{id}}}',
                   {'input': {'issueId': _uuid(item), 'body': text}})['commentCreate']
    if value['success'] is not True or not isinstance(value['comment'], dict):
        raise Failure('Linear comment failed')
    return {'id': value['comment']['id']}


@operation('linear.history')
def history(item, *, root=None):
    value = _query('query($id:String!){issue(id:$id){history(first:100){nodes{id createdAt fromState{name} toState{name}} pageInfo{hasNextPage}}}}',
                   {'id': item})['issue']['history']
    if value['pageInfo']['hasNextPage'] or not isinstance(value['nodes'], list):
        raise Failure('incomplete Linear history')
    return value['nodes']


@operation('linear.created')
def created(item, *, root=None):
    value = _query('query($id:String!){issue(id:$id){createdAt}}', {'id': item})['issue']
    if not isinstance(value, dict) or not isinstance(value.get('createdAt'), str):
        raise Failure('missing issue creation time')
    return value['createdAt']


@operation('linear.labels')
def labels(create, *, root=None):
    """#670: Linear moves workflow states, not labels, so it needs none."""
    return {'created': [], 'missing': []}
