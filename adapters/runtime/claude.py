"""Claude host dispatch instructions for plugin agent types."""

from pathlib import Path
import re

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
