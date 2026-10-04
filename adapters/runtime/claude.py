"""Claude host dispatch instructions for plugin agent types, and one headless turn."""

import json
from pathlib import Path
import re
import subprocess

from wuwei import env, workspace
from wuwei.registry import Result
from wuwei.brief import launch_prompt


def dispatch(role, brief_path, worktree, write, *, root=None):
    from wuwei import mcp
    measured = mcp.launch(root, worktree)
    if measured.exit:
        return measured
    try:
        if not isinstance(role, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', role):
            return Result(1, reason='invalid role')
        from wuwei.security import agent_path
        charter = agent_path(root, role)
        brief = Path(brief_path).resolve(strict=True)
        tree = Path(worktree).resolve(strict=True)
        if not charter.is_file() or not brief.is_file() or not tree.is_dir():
            return Result(1, reason='unknown role, brief or worktree')
        return Result(0, {'prompt': launch_prompt(brief, charter, root=root),
                          'agent_type': 'wuwei:' + role, 'brief_path': str(brief),
                          'worktree': str(tree), 'write': write})
    except (OSError, ValueError, TypeError) as exc:
        return Result(2, reason=f'Claude dispatch could not run: {exc}')


def status(job, *, root=None):
    return Result(2, reason='Claude host must report seat status')


def result(job, *, root=None):
    return Result(2, reason='Claude host must report seat result')


def continue_job(job, feedback, *, root=None):
    from wuwei import mcp
    measured = mcp.launch(root, job.get('worktree') if isinstance(job, dict) else None)
    if measured.exit:
        return measured
    if not isinstance(job, dict) or not isinstance(feedback, str) or not feedback:
        return Result(2, reason='invalid Claude continuation')
    try:
        agent_type = job['agent_type']
        if not isinstance(agent_type, str) or not agent_type.startswith('wuwei:'):
            raise ValueError('invalid Claude agent type')
        result = dispatch(agent_type.removeprefix('wuwei:'), job['brief_path'],
                          job['worktree'], job['write'], root=root)
        if result.exit:
            return result
        result.data['feedback'] = feedback
        result.data['prompt'] += '\n\n' + feedback
        return result
    except (KeyError, TypeError, ValueError) as exc:
        return Result(2, reason=f'Claude continuation could not run: {exc}')


SESSION = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TIMEOUT = 1800


# ponytail: not a runtime port operation; only Claude Code has headless sessions. Add it to
# registry.PARAMETERS when a second runtime does.
def headless(prompt, session, tools, *, root=None, variables=None):
    """One headless turn: start a session, or resume one by id; the prompt goes on stdin.

    variables adds WUWEI_ markers (the seat role) to the child environment, nothing else.
    """
    if (not isinstance(prompt, str) or not prompt.strip()
            or not (variables is None or isinstance(variables, dict) and all(
                isinstance(key, str) and re.fullmatch(r'WUWEI_[A-Z_]+', key) and isinstance(value, str)
                for key, value in variables.items()))
            or not (session is None or isinstance(session, str) and SESSION.fullmatch(session))
            or not isinstance(tools, list) or not tools
            or not all(isinstance(tool, str) and re.fullmatch(r'[A-Za-z]+', tool) for tool in tools)):
        return Result(2, reason='invalid headless call')
    # Flags checked against the Claude Code CLI reference on 2026-09-30. The prompt goes on
    # stdin so the variadic --allowedTools cannot swallow it (scripts/headless_adapter.py).
    # --tools removes every other built-in tool, so a permissions.allow rule in user or
    # project settings cannot widen the role. MCP tools are not built-ins:
    # --strict-mcp-config without --mcp-config loads no MCP server.
    argv = ['claude', '-p', '--output-format', 'json', '--permission-mode', 'dontAsk',
            '--tools', ','.join(tools), '--allowedTools', ','.join(tools), '--strict-mcp-config',
            *(['--resume', session] if session else [])]
    try:
        process = subprocess.run(argv, input=prompt, cwd=str(workspace.find_workspace(root)),
                                 capture_output=True, text=True, env={**env.child_environment(), **(variables or {})},
                                 timeout=TIMEOUT)
        data = json.loads(process.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # No stdout or stderr text in the reason: it may carry prompt content.
        return Result(2, reason=f'Claude headless could not run: {type(exc).__name__}')
    if not isinstance(data, dict):
        data = {}
    sid, denials = data.get('session_id'), data.get('permission_denials')
    if not (isinstance(sid, str) and SESSION.fullmatch(sid) and session in (None, sid)
            and isinstance(data.get('result'), str) and isinstance(data.get('is_error'), bool)
            and isinstance(denials, list)
            and all(isinstance(row, dict) and isinstance(row.get('tool_name'), str) for row in denials)):
        return Result(2, reason='Claude headless: invalid result')
    return Result(0 if process.returncode == 0 and not data['is_error'] else 1,
                  {'session_id': sid, 'result': data['result'],
                   'denials': [row['tool_name'] for row in denials]})
