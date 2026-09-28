"""Linear GraphQL tracker adapter."""

from .._http import Failure, credential, operation, request
from wuwei.registry import outward_operation


URL = 'https://api.linear.app/graphql'


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


@operation('linear.claim')
def claim(item, *, root=None):
    viewer = _query('query{viewer{id}}', {})['viewer']
    return _updated(item, {'assigneeId': viewer['id']})


@operation('linear.transition')
def transition(item, state, *, root=None):
    return _updated(item, {'stateId': state})


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
