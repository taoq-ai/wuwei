"""Claude host dispatch instructions for plugin agent types."""

from pathlib import Path
import re

from wuwei.registry import Result


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
        return Result(0, {'prompt': f'Read instructions {charter} and brief {brief}.',
                          'agent_type': 'wuwei:' + role, 'brief_path': str(brief),
                          'worktree': str(tree), 'write': write})
    except (OSError, ValueError) as exc:
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
    return Result(0, {'agent_type': job['agent_type'], 'worktree': job['worktree'],
                      'feedback': feedback, 'write': job['write']})
