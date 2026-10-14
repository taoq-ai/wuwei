"""Outward sends: the MCP resolution guards/edges.check_send shares, and the lint (#838)."""

import json
import os
from pathlib import Path
import re

from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED, PAYLOAD
from wuwei.guards import Guard
from wuwei import outward


NATIVE_TOOLS = {'Bash', 'Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep', 'Agent',
                'Skill', 'ToolSearch', 'AskUserQuestion', 'LS', 'Task', 'TodoWrite',
                'TaskOutput', 'TaskStop', 'EnterPlanMode', 'ExitPlanMode',
                'WebFetch', 'WebSearch', 'NotebookEdit'}

# #469: name words of an unmatched MCP tool; tests pin both lists.
WRITES = frozenset((
    'send', 'post', 'reply', 'add', 'create', 'update', 'delete', 'remove', 'set', 'put',
    'patch', 'write', 'upload', 'schedule', 'publish', 'invite', 'kick', 'archive', 'join',
    'leave', 'react', 'pin', 'star', 'edit', 'move', 'assign', 'merge', 'close', 'open',
    'submit', 'approve', 'comment', 'message', 'dm',
    'save', 'notify', 'draft', 'respond', 'push', 'fork', 'request', 'dismiss', 'mark',
    'manage', 'run', 'mute', 'trigger', 'share'))
LEADING = ('get', 'list', 'search', 'read', 'find', 'fetch', 'query', 'describe', 'view', 'lookup')
READS = frozenset(LEADING + (
    'history', 'replies', 'info', 'members', 'users', 'channels', 'conversations', 'threads',
    'permalink', 'profile', 'count', 'status', 'exists'))


def _words(name):
    return [word.lower() for word in re.split(r'[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])', name) if word]


def tool_kind(tool):
    """'read', 'write' or 'unknown' for an MCP tool by the words of its name (#469)."""
    server, _, name = tool[5:].rpartition('__')
    words = _words(name)
    if words and (words[0] in LEADING
                  or len(words) > 1 and words[0] in server.lower() and words[1] in LEADING):
        return 'read'  # The leading-read test first: get_message stays a read.
    if WRITES.intersection(words):
        return 'write'
    return 'read' if READS.intersection(words) else 'unknown'


# #492: tool vocabulary on the name words joined by '_'; used only when one channel matches.
# Monitoring writes (Sentry-style resolve_issue, mute_alert, update_alert_rule) are other, not
# tracker. 'resolve' stays out of WRITES: resolve-library-id style reads would turn writes.
OTHER = (r'(?:.*_)?(?:resolve|unresolve|mute|unmute|trigger)_(?:.*_)?(?:issues?|alerts?|incidents?)(?:_.*)?'
         r'|(?:.*_)?alert_rules?(?:_.*)?')
VOCABULARY = (
    ('slack', r'(?:conversations|channels)_.*|chat_post.*|(?:.*_)?add_(?:message|reaction)s?(?:_.*)?'),
    ('tracker', rf'(?!(?:{OTHER})$)(?:.*_)?issues?(?:_.*)?'),
    ('code_host', r'(?:.*_)?pull_requests?_(?:.*_)?comments?(?:_.*)?'),
    ('mail', r'(?:.*_)?(?:drafts?|labels?|threads?|spam|trash|forward|inbox|e?mails?)(?:_.*)?'),
    ('docs', r'(?:.*_)?(?:pages?|blocks?|databases?)(?:_.*)?'),
    ('other', OTHER))
# #727: servers that act only on the owner's machine; the command guards judge what runs.
LOCAL_SERVERS = ('terminal', 'Claude_Preview', 'Claude_Code_iOS_Simulator', 'computer-use')
LOCAL = (rf"mcp__(?:{'|'.join(map(re.escape, LOCAL_SERVERS))})__.*"
         r'|mcp__Claude_Browser__preview_.*')
DM_TOOL = r'(?:^|_)(?:dm|direct_message)(?:_|$)'


def resolve(tool, config):
    """#492: the channels of a tool: the owner alias, then the rules, then the vocabulary;
    reads skip the alias and vocabulary. config None is the schema defaults."""
    if not isinstance(tool, str):
        return set()
    if config:
        rules, servers = config['outward']['tool_patterns'], config['outward']['servers']
    else:
        from wuwei import workspace
        rules, servers = workspace.SCHEMA['outward']['tool_patterns'][1], {}
    channels = {rule['channel'] for rule in rules if re.fullmatch(rule['pattern'], tool, re.IGNORECASE)}
    if not tool.startswith('mcp__') or tool_kind(tool) == 'read':
        return channels
    server, _, name = tool[5:].rpartition('__')
    alias = next((channel for key, channel in servers.items() if key.casefold() == server.casefold()), None)
    if alias:
        return {alias}
    if channels:
        return channels
    if re.fullmatch(LOCAL, tool):
        return {'local'}
    joined = '_'.join(_words(name))
    found = {channel for channel, pattern in VOCABULARY if re.fullmatch(pattern, joined)}
    return found if len(found) == 1 else set()


# #838: the one refusal; config set asks its own Owner step card (#831).
NOT_ALLOWED = ("outward: {tool} may send to other people and is not on outward.allow; {surface}the "
               "owner adds it: bin/wuwei config set outward.allow '[\"{tool}\"]' --add (it asks its "
               "Owner step card), then run the call again")
# #838 review: the narrow fix first, only for a canvas or page id; a channel, DM, user or
# address is never offered as the owner's.
PAGES = "outbound.owner.pages '[\"{id}\"]' --add"
MAIL = "outbound.owner.mail '\"<your address>\"'"
# Unknown by name and no channel: it runs; the lint guard logs this (B5 lead call, no new walls).
UNKNOWN = ("outward: {tool} is neither a read nor a write by name, so it ran; if it sends to other "
           "people, the owner adds it: bin/wuwei config set outward.allow '[\"{tool}\"]' --add (it "
           "asks its Owner step card)")


def _page(value):
    """The first canvas_id or page_id (a Notion parent's included) in a payload, else None."""
    if isinstance(value, list):
        return next(filter(None, map(_page, value)), None)
    if not isinstance(value, dict):
        return None
    for key, item in value.items():
        if outward._snake(key) in ('canvas_id', 'page_id') and isinstance(item, str):
            return item
    return next(filter(None, map(_page, value.values())), None)


def refusal(tool, channel, inputs, config):
    """NOT_ALLOWED; a canvas or page id (or a Slack F... destination) is offered first as the
    owner's page, plain ids only; mail asks for the owner's address only while it is unset."""
    found = _page(inputs)
    if found is None and channel in ('slack', 'chat'):
        found = next((target for target in outward._text(inputs)[1]
                      if re.fullmatch(r'F[A-Z0-9]+', target)), None)
    line = (PAGES.format(id=found if re.fullmatch(r'[A-Za-z0-9._-]+', found) else '<id>')
            if found is not None else
            MAIL if channel == 'mail' and not config['outbound']['owner']['mail'] else None)
    surface = ('if it is your own surface, the owner adds it: bin/wuwei config set '
               f'{line} (it asks its Owner step card); else ') if line else ''
    return NOT_ALLOWED.format(tool=tool, surface=surface)


def check_lint(payload):
    return _check(payload, send=False)


def allow_key(tool):
    """UUID connector accounts share an exact tool name; named servers remain exact."""
    from uuid import UUID
    if tool.startswith('mcp__'):
        server, separator, name = tool[5:].partition('__')
        try:
            UUID(server)
        except ValueError:
            pass
        else:
            if separator and name:
                return ('uuid', name)
    return ('exact', tool)


def _check(payload, send):
    """#838: an MCP write is local (a #727 local tool, or every destination the owner's own
    surface), allowed by outward.allow or refused; the canary floor stays on every send."""
    try:
        from wuwei import security, workspace
        raw = json.dumps(payload.get('tool_input', {}))
        if send and any(marker in raw for marker in outward.MARKERS):
            scope = workspace.guard_scope(payload)
            if scope is not None:
                from wuwei import shell
                commands = []
                if payload.get('tool_name') == 'Bash':
                    try:
                        commands = shell.normalize(payload['tool_input']['command'])
                    except shell.ParseError:
                        pass
                # Only scripts entirely parsed as gh are covered by the edges gh body scan.
                if not commands or not all(command.argv and Path(command.argv[0]).name == 'gh'
                                           for command in commands):
                    code, reason = security.outbound(payload.get('tool_input'), scope)
                    return (code, reason) if code else (FINDINGS, outward.OWNER_MARKERS)
        if payload.get('tool_name') == 'Bash' and send:
            cwd = Path(payload.get('cwd') or Path.cwd()).resolve()
            try:
                root = workspace.find_workspace(cwd)
            except FileNotFoundError:
                if 'WUWEI_WORKSPACE' in os.environ:
                    raise
                root = workspace.worktree_workspace(cwd)
            if root is None or not security.matches(payload.get('tool_input'), security.load(root)):
                return CLEAN, ''
            if workspace.guard_scope(payload) is None:
                return CLEAN, ''
            return security.outbound(payload.get('tool_input'), root)
        tool = payload.get('tool_name')
        if tool in NATIVE_TOOLS:
            if 'WUWEI_WORKSPACE' in os.environ:
                workspace.find_workspace(payload.get('cwd'))
            return CLEAN, ''
        if isinstance(tool, str) and (tool.strip() and not tool.startswith('mcp__')
                                      or tool.startswith('mcp__') and tool_kind(tool) == 'read'):
            return CLEAN, ''
        cwd = Path(payload.get('cwd') or Path.cwd()).resolve()
        try:
            workspace.find_workspace(cwd)
        except FileNotFoundError:
            if 'WUWEI_WORKSPACE' in os.environ:
                raise ValueError(f'invalid WUWEI_WORKSPACE override; {DAMAGED}')
        root = workspace.guard_scope(payload)
        if root is None:
            return CLEAN, ''
        if not isinstance(tool, str) or not tool.strip():
            return UNRUN, f'outward: tool name required; {PAYLOAD}'
        if not re.fullmatch(r'mcp__[A-Za-z0-9_.-]+', tool):
            return UNRUN, f'outward: invalid MCP tool name; {PAYLOAD}'
        config = workspace.load_config(root)
        channels = resolve(tool, config)
        inputs = payload.get('tool_input')
        if channels == {'local'}:  # #727: the command guards judge what runs.
            return security.outbound(inputs, root) if send else (CLEAN, '')
        if send:  # the canary floor first, on every MCP write
            code, reason = security.outbound(inputs, root)
            if code:
                return code, reason
        if not isinstance(inputs, dict):
            return UNRUN, (f'outward: tool_input is not an object; got {type(inputs).__name__}; '
                           'pass the tool arguments as a JSON object')
        outward._text(inputs)  # Validate shape after the security floor.
        if re.search(DM_TOOL, tool, re.IGNORECASE):
            inputs = {**inputs, 'is_dm': True}
        channel = next(iter(channels)) if len(channels) == 1 else 'other'
        owner = outward.owner_only(inputs, config, channel)
        if not owner and allow_key(tool) not in map(allow_key, config['outward']['allow']):
            if not channels and tool_kind(tool) == 'unknown':
                return (CLEAN, '') if send else (FINDINGS, UNKNOWN.format(tool=tool))
            return (FINDINGS, refusal(tool, channel, inputs, config)) if send else (CLEAN, '')
        if send:
            if owner:
                outward.to_owner(inputs, root, config, channel)
            return CLEAN, ''
        result = outward.check_lint(inputs, root, config, {channel}, to_owner=owner)
        return result if result[0] else outward.humanize_lint(inputs, root, config, {channel})
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, re.error):
        return UNRUN, outward.UNREADABLE


GUARDS = [Guard('PreToolUse', None, check_lint, profile_relaxable=True)]
