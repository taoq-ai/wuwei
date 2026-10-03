"""Enforce outbound approval tiers and outward lint before writes."""

import json
import os
from pathlib import Path
import re

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.guards import Guard
from wuwei import outward


NATIVE_TOOLS = {'Bash', 'Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep', 'Agent',
                'Skill', 'ToolSearch', 'AskUserQuestion', 'LS', 'Task', 'TodoWrite',
                'TaskOutput', 'TaskStop', 'EnterPlanMode', 'ExitPlanMode',
                'WebFetch', 'WebSearch', 'NotebookEdit'}


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
                raise ValueError('invalid WUWEI_WORKSPACE override')
            policy_root = workspace.worktree_workspace(cwd)
        config = workspace.load_config(policy_root) if policy_root else None
        patterns = (config['outward']['tool_patterns'] if config else
                    workspace.SCHEMA['outward']['tool_patterns'][1])
        channels = {rule['channel'] for rule in patterns
                    if isinstance(tool, str) and re.fullmatch(rule['pattern'], tool, re.IGNORECASE)}
        if not channels:
            if isinstance(tool, str) and tool.startswith('mcp__'):
                server, _, name = tool[5:].lower().rpartition('__')
                words = name.split('_')
                reads = ('get', 'list', 'search', 'read', 'find', 'fetch',
                         'query', 'describe', 'view', 'lookup')
                if (words[0] in reads or
                        (len(words) > 1 and words[0] and words[0] in server
                         and words[1] in reads)):
                    return CLEAN, ''
            elif isinstance(tool, str) and tool.strip():
                return CLEAN, ''
        root = workspace.guard_scope(payload)
        if root is None:
            return CLEAN, ''
        if not isinstance(tool, str) or not tool.strip():
            return UNRUN, 'outward: tool name required'
        if root != policy_root:
            config = workspace.load_config(root)
            channels = {rule['channel'] for rule in config['outward']['tool_patterns']
                        if re.fullmatch(rule['pattern'], tool, re.IGNORECASE)}
        if not channels:
            return UNRUN, 'outward: configure outward.tool_patterns for this write tool'
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration'
        inputs = payload['tool_input']
        if re.search(r'(?:^|_)(?:dm|direct_message)(?:_|$)', tool, re.IGNORECASE):
            inputs = {**inputs, 'is_dm': True}
        return policy(inputs, root, config, channels)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload'


GUARDS = [Guard('PreToolUse', None, check_tier),
          Guard('PreToolUse', None, check_lint, profile_relaxable=True)]
