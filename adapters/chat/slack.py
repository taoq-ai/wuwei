"""Slack Web API chat adapter."""

import os
import json
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request

from .._http import Failure, credential, operation, request, status
from wuwei.registry import outward_operation


URL = 'https://slack.com/api/'


def _url(method):
    """SLACK_API_BASE points at a fake or a proxy; the token never goes out in clear."""
    base = os.environ.get('SLACK_API_BASE') or URL
    parts = urlsplit(base)
    if parts.scheme != 'https' and not (
            parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise Failure('SLACK_API_BASE must be https, or http to a loopback host')
    return base.rstrip('/') + '/' + method


def _send(payload, identity='connector'):
    if identity not in ('connector', 'custom_app'):
        raise Failure('invalid chat identity')
    token = (credential('SLACK_BOT_TOKEN') if identity == 'custom_app' else
             os.environ.get('SLACK_USER_TOKEN') or credential('SLACK_BOT_TOKEN'))
    value = request(_url('chat.postMessage'), token, payload)
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


def history(channel, **params):
    """Bounded conversations.history rows, newest first; each caller validates its rows."""
    token = os.environ.get('SLACK_USER_TOKEN') or credential('SLACK_BOT_TOKEN')
    rows, cursor = [], ''
    for _ in range(10):
        url = _url('conversations.history') + '?' + urlencode(
            {'channel': channel, 'limit': 100, 'cursor': cursor, **params})
        try:
            with urllib.request.urlopen(Request(url, headers={'Authorization': f'Bearer {token}'}),
                                        timeout=30) as response:
                body = response.read(4_000_001)
        except HTTPError as exc:
            if exc.code != 429:
                raise Failure(status(exc.code)) from None
            # ponytail: no backoff state; the caller's next poll is the retry.
            # Persist a not-before time if 429s repeat.
            wait = (exc.headers or {}).get('Retry-After', '')
            raise Failure(f'rate limited; retry after {wait if wait.isdigit() else "unknown"} s') from None
        if len(body) > 4_000_000:
            raise Failure('history response too large')
        value = json.loads(body)
        if not isinstance(value, dict) or value.get('ok') is not True or not isinstance(value.get('messages'), list):
            raise Failure('invalid history response')
        rows.extend(value['messages'])
        cursor = value.get('response_metadata', {}).get('next_cursor', '')
        if not isinstance(cursor, str):
            raise Failure('invalid history cursor')
        if not cursor:
            return rows
    # ponytail: ten pages of 100 per channel; more than that between two polls (outage)
    # fails every poll until fixed. Return the oldest pages and let the cursor advance.
    raise Failure('history exceeds ten pages')


@operation('slack.sent')
def sent(channel, owner, *, root=None):
    """Read a bounded channel history; the CLI filters owner messages again."""
    if not isinstance(channel, str) or not channel or not isinstance(owner, list):
        raise Failure('invalid sent-message query')
    messages = []
    for row in history(channel):
        if not isinstance(row, dict) or not isinstance(row.get('user'), str) or not isinstance(row.get('text'), str):
            raise Failure('invalid history message')
        if row['user'] in owner and not row.get('bot_id') and not row.get('subtype'):
            messages.append({'sender': row['user'], 'text': row['text']})
    return messages
