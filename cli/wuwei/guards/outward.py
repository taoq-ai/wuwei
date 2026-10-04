"""Enforce outbound approval tiers and outward lint before writes."""

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
    'manage', 'run', 'mute', 'trigger'))
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
# The mode a connector without an owner mode follows; None is the class's own tier rule.
CLASS_MODES = {'other': 'send'}


def mode(tool, config, channel):
    """#492: the owner's mode for the tool's server, else the class default."""
    server = tool[5:].rpartition('__')[0].casefold()
    owned = next((value for key, value in config['outward']['modes'].items()
                  if key.casefold() == server), None)
    return owned or CLASS_MODES.get(channel)


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
    joined = '_'.join(_words(name))
    found = {channel for channel, pattern in VOCABULARY if re.fullmatch(pattern, joined)}
    return found if len(found) == 1 else set()


def check_tier(payload):
    return _check(payload, outward.check_tier)


def check_lint(payload):
    return _check(payload, _lint)


def _lint(inputs, root, config, channels):
    # ponytail: runs even when check_tier refuses the same call, so a retried write records its
    # tells twice; pass the tier result between guards if the metric needs exact counts.
    result = outward.check_lint(inputs, root, config, channels)
    return result if result[0] else outward.humanize_lint(inputs, root, config, channels)


def _check(payload, policy):
    try:
        from wuwei import workspace
        raw = json.dumps(payload.get('tool_input', {}))
        if (policy is outward.check_tier
                and any(marker in raw for marker in ('WUWEI parked ', 'WUWEI carried '))):
            scope = workspace.guard_scope(payload)
            if scope is not None:
                from wuwei import security, shell
                commands = []
                if payload.get('tool_name') == 'Bash':
                    try:
                        commands = shell.normalize(payload['tool_input']['command'])
                    except shell.ParseError:
                        pass
                # Only scripts entirely parsed as gh are covered by the PR guard.
                if not commands or not all(command.argv and Path(command.argv[0]).name == 'gh'
                                           for command in commands):
                    code, reason = security.outbound(payload.get('tool_input'), scope)
                    return (code, reason) if code else (FINDINGS, 'owner disposition markers must be posted by the owner')
        if payload.get('tool_name') == 'Bash' and policy is outward.check_tier:
            from wuwei import security
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
        if payload.get('tool_name') in NATIVE_TOOLS:
            if 'WUWEI_WORKSPACE' in os.environ:
                workspace.find_workspace(payload.get('cwd'))
            return CLEAN, ''
        tool = payload.get('tool_name')
        cwd = Path(payload.get('cwd') or Path.cwd()).resolve()
        try:
            policy_root = workspace.find_workspace(cwd)
        except FileNotFoundError:
            if 'WUWEI_WORKSPACE' in os.environ:
                raise ValueError(f'invalid WUWEI_WORKSPACE override; {DAMAGED}')
            policy_root = workspace.worktree_workspace(cwd)
        config = workspace.load_config(policy_root) if policy_root else None
        channels = resolve(tool, config)
        if not channels:
            if isinstance(tool, str) and tool.startswith('mcp__'):
                if tool_kind(tool) == 'read':
                    return CLEAN, ''
            elif isinstance(tool, str) and tool.strip():
                return CLEAN, ''
        root = workspace.guard_scope(payload)
        if root is None:
            return CLEAN, ''
        if not isinstance(tool, str) or not tool.strip():
            return UNRUN, f'outward: tool name required; {PAYLOAD}'
        if root != policy_root:
            config = workspace.load_config(root)
            channels = resolve(tool, config)
        if not channels:
            return _unmatched(tool, root, config, policy)
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration; pass one channel per call'
        inputs = payload['tool_input']
        if re.search(r'(?:^|_)(?:dm|direct_message)(?:_|$)', tool, re.IGNORECASE):
            inputs = {**inputs, 'is_dm': True}
        channel = next(iter(channels))
        found = mode(tool, config, channel) if tool.startswith('mcp__') and tool_kind(tool) != 'read' else None
        if found == 'refuse':
            return UNRUN, (f'outward: connector {tool[5:].rpartition("__")[0]} refuses writes by the '
                           "owner's mode; write it as a draft for the owner to send")
        if found == 'draft' and policy is outward.check_tier:
            result = (FINDINGS, f'{outward.APPROVAL_REQUIRED}: connector mode draft for {channel}: outward.modes')
        elif found == 'send' and policy is outward.check_tier:
            result = outward.check_send(inputs, root, config, channels)
        elif found == 'send' and not outward._text(inputs)[0]:
            result = (CLEAN, '')  # Nothing to lint in a write without text.
        else:
            result = policy(inputs, root, config, channels)
        if result[0] == FINDINGS and result[1].startswith(outward.APPROVAL_REQUIRED):
            from wuwei import drafts  # Only a held call pays for the queue (#346).
            if drafts.spend(root, tool, channel, inputs):
                return CLEAN, ''  # The owner approved this call once (#493).
            return FINDINGS, drafts.hold(root, config, channel, 'tool', 'mcp', inputs, result[1], tool=tool)
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload; run bin/wuwei config check; if the config is clean, save this as a draft for the owner to send'


def _unmatched(tool, root, config, policy):
    """#469: a tool nothing resolves, inside a workspace: reads pass, writes refuse, unknown
    names follow the outward area level in check_lint only. #492: the way out is the draft
    and the planner's learn command, never a config line."""
    found = tool_kind(tool)
    if found == 'read':  # Reached only when the scope's config differs from the cwd's.
        return CLEAN, ''
    if not re.fullmatch(r'mcp__[A-Za-z0-9_-]+', tool):
        return UNRUN, f'outward: invalid MCP tool name; {PAYLOAD}'
    server = tool[5:].rpartition('__')[0]
    learn = (f', and the planner runs bin/wuwei outbound learn --tool {tool}'
             if config['outbound']['learn'] != 'off' else '')
    if found == 'write':
        return UNRUN, (f'outward: connector {server} is not known for write tool {tool}; '
                       f'write it as a draft for the owner to send{learn}')
    if policy is outward.check_tier:
        return CLEAN, ''
    from wuwei import workspace
    name, levels = workspace.posture(config)
    unknown = f'outward: unknown MCP tool {tool} of connector {server}'
    if levels['outward'] == 'block':
        return UNRUN, f'{unknown}, not a read or a write by its name; write it as a draft for the owner to send{learn}'
    if levels['outward'] == 'warn':
        from wuwei import state, watch  # Only now: watch stays off every other hook path.
        # ponytail: reads the day's events per call of an unknown tool; two racing first
        # calls may both record. Keep a per-day set in state if that shows in latency.
        if not any(row['kind'] == 'outward.unknown_tool' and row['payload'].get('tool') == tool
                   for row in watch.records(workspace.day_dir(root) / 'events.jsonl')):
            state.append_event('outward.unknown_tool', {
                'tool': tool, 'posture': name,
                'reason': f'{unknown} passed under {name}; if it writes, write it as a draft for the owner to send{learn}'}, root)
    return CLEAN, ''


GUARDS = [Guard('PreToolUse', None, check_tier),
          Guard('PreToolUse', None, check_lint, profile_relaxable=True)]
