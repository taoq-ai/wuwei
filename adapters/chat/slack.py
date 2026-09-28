"""Slack Web API chat adapter."""

import os

from .._http import Failure, credential, operation, request
from wuwei.registry import outward_operation


URL = 'https://slack.com/api/'


def _send(payload, identity='connector'):
    if identity not in ('connector', 'custom_app'):
        raise Failure('invalid chat identity')
    token = (credential('SLACK_BOT_TOKEN') if identity == 'custom_app' else
             os.environ.get('SLACK_USER_TOKEN') or credential('SLACK_BOT_TOKEN'))
    value = request(URL + 'chat.postMessage', token, payload)
    if value.get('ok') is not True or not isinstance(value.get('ts'), str):
        raise Failure('Slack error response')
    return {'channel': value['channel'], 'ts': value['ts']}


@outward_operation('chat')
@operation('slack.post')
def post(channel, text, thread, *, root=None):
    from wuwei import workspace
    identity = workspace.load_config(workspace.find_workspace(root))['chat']['identity']
    payload = {'channel': channel, 'text': text}
    if thread:
        payload['thread_ts'] = thread
    return _send(payload, identity)


@outward_operation('chat')
@operation('slack.dm')
def dm(text, *, root=None):
    # A DM recipient is not in this port's signature. A configured owner channel
    # is supplied by the environment, where no workspace config can leak it.
    return _send({'channel': credential('SLACK_OWNER_DM_CHANNEL'), 'text': text})
