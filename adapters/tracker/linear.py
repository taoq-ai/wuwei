"""Linear GraphQL tracker adapter."""

from .._http import Failure, credential, operation, request
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


@outward_operation('tracker')
@operation('linear.create')
def create(draft, *, root=None):
    if not isinstance(draft, dict) or not isinstance(draft.get('teamId'), str) or not isinstance(draft.get('title'), str):
        raise Failure('invalid issue draft')
    allowed = {'teamId', 'title', 'description', 'stateId', 'assigneeId', 'projectId'}
    if draft.keys() - allowed:
        raise Failure('unsupported issue field')
    value = _query('mutation($input:IssueCreateInput!){issueCreate(input:$input){success issue{id}}}',
                   {'input': draft})['issueCreate']
    if value['success'] is not True or not isinstance(value['issue'], dict):
        raise Failure('Linear create failed')
    return value['issue']


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
