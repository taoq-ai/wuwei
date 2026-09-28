"""Codex companion subprocess and workspace-root verification."""

import json
from pathlib import Path
import re
import subprocess
import time

from wuwei import registry, workspace


def _call(action, tree, *args, root=None):
    try:
        config = workspace.load_config(root)
        command = config['codex']['command']
        if not command:
            return registry.Result(2, reason='codex.command is not configured')
        process = subprocess.run([*command, action, *args, '--json'], cwd=str(tree),
                                 capture_output=True, text=True,
                                 timeout=config['codex']['timeout_seconds'])
        if process.returncode:
            return registry.Result(2, reason=f'Codex {action} failed: {process.stderr.strip() or process.returncode}')
        data = json.loads(process.stdout)
        if not isinstance(data, dict):
            raise ValueError('expected JSON object')
        if data.get('error'):
            return registry.Result(2, reason=f'Codex {action}: {data["error"]}')
        return registry.Result(0, data)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return registry.Result(2, reason=f'Codex {action} could not run: {exc}')


def dispatch(role, brief_path, worktree, write, *, root=None):
    try:
        if not isinstance(role, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', role):
            return registry.Result(1, reason='invalid role')
        charter = Path(__file__).resolve().parents[2] / 'charters' / (role + '.md')
        tree = Path(worktree).resolve(strict=True)
        brief = Path(brief_path).resolve(strict=True)
        if not charter.is_file() or not brief.is_file() or not tree.is_dir():
            return registry.Result(1, reason='unknown role, brief or worktree')
        prompt = f'Read charter {charter} and brief {brief}. Work in {tree}. '
        prompt += 'Do not ask questions or reach external services. Report decisions and finish available work.'
        options = ['--fresh', '--background']
        if write:
            options.append('--write')
        started_at = time.time()
        return _started(_call('task', tree, *options, prompt, root=root), tree, role, started_at, root)
    except (OSError, ValueError) as exc:
        return registry.Result(2, reason=f'Codex dispatch could not run: {exc}')


def _job(job):
    if not isinstance(job, dict) or not isinstance(job.get('id'), str) or not job['id']:
        raise ValueError('invalid Codex job')
    tree = Path(job['worktree']).resolve(strict=True)
    if not tree.is_dir():
        raise ValueError('Codex worktree is not a directory')
    return job['id'], tree


def _started(started, tree, role, started_at, root):
    if started.exit:
        return started
    job_id = started.data.get('jobId')
    if not isinstance(job_id, str) or not job_id:
        return registry.Result(2, reason='Codex task omitted job id')
    snapshot = _call('status', tree, job_id, root=root)
    if snapshot.exit:
        return snapshot
    status_job = snapshot.data.get('job')
    roots = [snapshot.data.get('workspaceRoot')]
    if isinstance(status_job, dict):
        roots.append(status_job.get('workspaceRoot'))
    roots = [value for value in roots if value is not None]
    if not roots or not all(isinstance(value, str) for value in roots):
        return registry.Result(2, reason='Codex status omitted workspace root')
    if any(Path(value).resolve() != tree for value in roots):
        cancelled = _call('cancel', tree, job_id, root=root)
        if cancelled.exit:
            return registry.Result(2, reason=f'Codex workspace mismatch; cancellation failed: {cancelled.reason}')
        return registry.Result(1, reason='Codex workspace root differs from worktree; job cancelled')
    return registry.Result(0, {'id': job_id, 'worktree': str(tree), 'role': role,
                               'started_at': started_at})


def status(job, *, root=None):
    try:
        job_id, tree = _job(job)
        response = _call('status', tree, job_id, root=root)
        if response.exit:
            return response
        job_data = response.data.get('job')
        status_value = job_data.get('status') if isinstance(job_data, dict) else None
        if status_value not in ('queued', 'running', 'completed', 'failed', 'cancelled'):
            return registry.Result(2, reason='Codex status is missing or unknown')
        return registry.Result(0, {'status': status_value, 'model': job_data.get('model')})
    except (OSError, ValueError, KeyError) as exc:
        return registry.Result(2, reason=f'Codex status could not run: {exc}')


def result(job, *, root=None):
    try:
        job_id, tree = _job(job)
        response = _call('result', tree, job_id, root=root)
        if response.exit:
            return response
        data = response.data
        stored = data.get('storedJob')
        if not isinstance(stored, dict):
            return registry.Result(2, reason='Codex result omitted stored job')
        result_data = stored.get('result') if isinstance(stored.get('result'), dict) else {}
        codex_data = result_data.get('codex') if isinstance(result_data.get('codex'), dict) else {}
        text = result_data.get('rawOutput') or codex_data.get('stdout') or stored.get('rendered')
        if not isinstance(text, str) or not text:
            return registry.Result(2, reason='Codex result omitted text')
        output = {'text': text}
        role = job.get('role', 'builder')
        from wuwei.guards.verdict import check_retro
        retro_code, retro_reason = check_retro({'cwd': str(tree), 'agent_id': job_id,
                                                'agent_type': role, 'last_assistant_message': text}, root=root)
        from wuwei.verdict import lint_file
        decisions = workspace.day_dir(root) / 'decisions'
        verdicts = [lint_file(verdict, role=role, root=root)
                    for verdict in decisions.glob('gate-*.md')
                    if verdict.stat().st_mtime >= job.get('started_at', float('inf'))]
        for code, reason in verdicts:
            if code:
                return registry.Result(code, output, reason)
        if retro_code:
            return registry.Result(retro_code, output, retro_reason)
        return registry.Result(0, output)
    except (OSError, ValueError, KeyError) as exc:
        return registry.Result(2, reason=f'Codex result could not run: {exc}')


def continue_job(job, feedback, *, root=None):
    try:
        _, tree = _job(job)
        if not isinstance(feedback, str) or not feedback:
            raise ValueError('empty Codex feedback')
        started_at = time.time()
        started = _call('task', tree, '--resume-last', '--background', '--write', feedback, root=root)
        return _started(started, tree, job.get('role', 'builder'), started_at, root)
    except (OSError, ValueError, KeyError) as exc:
        return registry.Result(2, reason=f'Codex continuation could not run: {exc}')
