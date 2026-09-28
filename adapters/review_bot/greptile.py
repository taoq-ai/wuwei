"""Read Greptile review evidence through its HTTP MCP tools."""

import json
import re

from .._http import Failure, credential, operation, request


URL = 'https://api.greptile.com/mcp'


def _arguments(pr, root):
    match = re.fullmatch(r'([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)', pr)
    if not match:
        raise Failure('invalid PR reference')
    branch = 'main'
    if root is not None:
        from wuwei.workspace import load_config
        for repo in load_config(root)['repos']:
            if repo['name'] == match[1]:
                branch = repo['default_branch']
                break
    return {'name': match[1], 'remote': 'github', 'defaultBranch': branch,
            'prNumber': int(match[2])}


def _tool(name, pr, root):
    value = request(URL, credential('GREPTILE_API_KEY'),
                    {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                     'params': {'name': name, 'arguments': _arguments(pr, root)}},
                    extra_headers={'Accept': 'application/json, text/event-stream',
                                   'Mcp-Method': 'tools/call', 'Mcp-Name': name})
    if value.get('error') or value.get('result', {}).get('isError'):
        raise Failure('Greptile error response')
    content = value['result']['content']
    if not isinstance(content, list) or len(content) != 1 or content[0]['type'] != 'text':
        raise Failure('invalid Greptile response')
    return json.loads(content[0]['text'])


def _review(pr, root):
    merge = _tool('get_merge_request', pr, root)['mergeRequest']
    if merge['reviewAnalysis']['hasNewCommitsSinceReview'] is not False:
        raise Failure('review is stale')
    if not any(review.get('status') == 'COMPLETED' for review in merge['codeReviews']):
        raise Failure('completed review unavailable')
    return merge


@operation('greptile.score')
def score(pr, *, root=None):
    merge = _review(pr, root)
    comments = merge['comments']['greptile']
    if not isinstance(comments, list):
        raise Failure('invalid Greptile comments')
    for comment in comments:
        match = re.search(r'Confidence Score:\s*([0-5])/5', comment['body'], re.I)
        if match:
            return int(match[1])
    raise Failure('Greptile score unavailable')


@operation('greptile.open_findings')
def open_findings(pr, *, root=None):
    _review(pr, root)
    response = _tool('list_merge_request_comments', pr, root)
    comments = response['comments']
    if not isinstance(comments, list) or response.get('total', len(comments)) != len(comments):
        raise Failure('invalid Greptile comments')
    return [comment for comment in comments
            if comment['isGreptileComment'] is True and comment['addressed'] is False]
