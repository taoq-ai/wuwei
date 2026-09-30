"""Slack inbound: the owner DM channel and mentions of the owner, from conversations.history."""

import re

from .._http import Failure, credential, operation
from ..chat.slack import history

# ponytail: one cursor for every channel. Re-reading 300 s behind it covers a message
# that lands in a channel already read while later ones are read, and bounds the first
# poll; inbox.store dedups the overlap. Per-channel cursors if a gap is ever observed.
LOOKBACK = 300
TS = re.compile(r'\d+\.\d{6}')


@operation('slack.poll')
def poll(since, *, root=None):
    from wuwei import workspace
    if not isinstance(since, str) or since and not re.fullmatch(r'\d+(?:\.\d+)?', since):
        raise Failure('invalid cursor')
    config = workspace.load_config(workspace.find_workspace(root))
    owners = [handle for handle in config['owner']['handles'] if re.fullmatch(r'[UW][A-Z0-9]+', handle)]
    channels = config['outbound']['work_channels'] + config['outbound']['external_channels']
    if channels and not owners:
        raise Failure('owner.handles has no Slack user id for mentions')
    dm = credential('SLACK_OWNER_DM_CHANNEL')
    seconds = int(since.split('.')[0]) if since else int(workspace.now().timestamp())
    events = []
    for channel in (dm, *channels):
        for row in history(channel, oldest=str(seconds - LOOKBACK)):
            if not isinstance(row, dict):
                raise Failure('invalid history message')
            if row.get('bot_id') or row.get('app_id') or row.get('subtype'):
                continue
            user, text, ts, thread = row.get('user'), row.get('text'), row.get('ts'), row.get('thread_ts', '')
            team = row.get('team', '')
            if not (all(isinstance(value, str) for value in (user, text, ts, thread, team))
                    and user and TS.fullmatch(ts)):
                raise Failure('invalid history message')
            if channel != dm and (user in owners or not any(
                    f'<@{owner}>' in text or f'<@{owner}|' in text for owner in owners)):
                continue
            events.append({'id': f'{channel}/{ts}', 'source': 'slack', 'channel': channel,
                           'thread': thread, 'sender': f'{team}/{user}', 'text': text, 'ts': ts})
    return sorted(events, key=lambda event: tuple(map(int, event['ts'].split('.'))))
