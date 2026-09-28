"""Enforce outward lint and draft-only substantive messages before writes."""

import os
import re

from wuwei.exits import CLEAN, UNRUN
from wuwei.guards import Guard


NATIVE_TOOLS = {'Bash', 'Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep', 'Agent',
                'Skill', 'ToolSearch', 'AskUserQuestion', 'LS', 'Task', 'TodoWrite',
                'TaskOutput', 'TaskStop', 'EnterPlanMode', 'ExitPlanMode',
                'WebFetch', 'WebSearch', 'NotebookEdit'}


def check(payload):
    try:
        from wuwei import workspace
        try:
            root = workspace.find_workspace(payload.get('cwd'))
        except FileNotFoundError:
            if 'WUWEI_WORKSPACE' in os.environ:
                return UNRUN, 'outward: invalid WUWEI_WORKSPACE override'
            return CLEAN, ''
        tool = payload['tool_name']
        if not isinstance(tool, str) or not tool.strip():
            return UNRUN, 'outward: tool name required'
        if tool in NATIVE_TOOLS:
            return CLEAN, ''
        from wuwei import outward

        config = workspace.load_config(root)
        channels = {rule['channel'] for rule in config['outward']['tool_patterns']
                    if re.fullmatch(rule['pattern'], tool, re.IGNORECASE)}
        if not channels:
            if tool.startswith('mcp__'):
                server, _, name = tool[5:].lower().rpartition('__')
                words = name.split('_')
                reads = ('get', 'list', 'search', 'read', 'find', 'fetch',
                         'query', 'describe', 'view', 'lookup')
                if not (words[0] in reads or
                        (len(words) > 1 and words[0] and words[0] in server
                         and words[1] in reads)):
                    return UNRUN, 'outward: configure outward.tool_patterns for this write tool'
            return CLEAN, ''
        if len(channels) != 1:
            return UNRUN, 'outward: ambiguous tool channel configuration'
        return outward.check_call(payload['tool_input'], root, config, channels)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, re.error):
        return UNRUN, 'outward: cannot read or validate policy or payload'


GUARDS = [Guard('PreToolUse', None, check)]
