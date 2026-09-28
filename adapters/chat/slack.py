"""Slack Web API chat adapter."""

import os
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


@operation('slack.sent')
def sent(channel, owner, *, root=None):
    """Read a bounded channel history; the CLI filters owner messages again."""
    if not isinstance(channel, str) or not channel or not isinstance(owner, list):
        raise Failure('invalid sent-message query')
    token = os.environ.get('SLACK_USER_TOKEN') or credential('SLACK_BOT_TOKEN')
    messages, cursor = [], ''
    for _ in range(10):
        url = URL + 'conversations.history?' + urlencode({'channel': channel, 'limit': 100, 'cursor': cursor})
        with urlopen(Request(url, headers={'Authorization': f'Bearer {token}'}), timeout=30) as response:
            body = response.read(4_000_001)
        if len(body) > 4_000_000:
            raise Failure('history response too large')
        value = json.loads(body)
        if not isinstance(value, dict) or value.get('ok') is not True or not isinstance(value.get('messages'), list):
            raise Failure('invalid history response')
        for row in value['messages']:
            if not isinstance(row, dict) or not isinstance(row.get('user'), str) or not isinstance(row.get('text'), str):
                raise Failure('invalid history message')
            if row['user'] in owner and not row.get('bot_id') and not row.get('subtype'):
                messages.append({'sender': row['user'], 'text': row['text']})
        cursor = value.get('response_metadata', {}).get('next_cursor', '')
        if not isinstance(cursor, str):
            raise Failure('invalid history cursor')
        if not cursor:
            return messages
    raise Failure('history exceeds ten pages')
