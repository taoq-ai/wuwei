"""Enforce outbound approval tiers and outward lint before writes."""

import os
from pathlib import Path
import re

from wuwei.exits import CLEAN, UNRUN
from wuwei.guards import Guard
from wuwei import outward


NATIVE_TOOLS = {'Bash', 'Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep', 'Agent',
                'Skill', 'ToolSearch', 'AskUserQuestion', 'LS', 'Task', 'TodoWrite',
                'TaskOutput', 'TaskStop', 'EnterPlanMode', 'ExitPlanMode',
                'WebFetch', 'WebSearch', 'NotebookEdit'}


def check_tier(payload):
    return _check(payload, outward.check_tier)


def check_lint(payload):
    return _check(payload, outward.check_lint)


def _check(payload, policy):
    try:
        from wuwei import workspace
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
