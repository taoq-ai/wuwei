"""External boundary for the opt-in headless test, not a production runtime port."""

import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


def run(argv, *, cwd, env=None, input=None, timeout=30, own_group=True):
    """Bound each process tree, including Claude's subagents and hook children."""
    executable = str(argv[0])
    try:
        with subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, text=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, start_new_session=own_group) as process:
            try:
                out, err = process.communicate(input, timeout=timeout)
            except subprocess.TimeoutExpired:
                if own_group:
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.communicate()
                raise RuntimeError(f'unmeasured: {Path(executable).name} timeout after {timeout}s')
            return subprocess.CompletedProcess(argv, process.returncode, out, err)
    except OSError as exc:
        raise RuntimeError(f'unmeasured: {Path(executable).name} could not run: {exc.strerror}') from exc


def claude_command(plugin, *, turns=48, budget=3, resume=None):
    return ['claude', '-p', '--plugin-dir', str(plugin), '--model', 'sonnet',
            '--max-turns', str(turns), '--max-budget-usd', str(budget), '--output-format', 'json',
            '--setting-sources', 'project', '--strict-mcp-config', '--mcp-config',
            '{"mcpServers":{}}', '--tools', 'Bash,Read,Write,Edit,Glob,Grep,Agent,Skill',
            '--allowedTools', 'Bash,Read,Write,Edit,Glob,Grep,Agent,Skill',
            *(['--resume', resume] if resume else [])]


def observe(python, log, argv):
    """Transparent python3 shim: observe bin/wuwei without changing the signed plugin."""
    is_wuwei = len(argv) >= 6 and argv[:3] == ['-I', '-P', '-c'] and 'run_module("wuwei"' in argv[3]
    if not is_wuwei:
        os.execv(python, [python, *argv])
    # bin/wuwei passes its two import paths before the actual CLI arguments.
    args = argv[6:]
    raw = sys.stdin.read()
    result = run([python, *argv], cwd=Path.cwd(), input=raw, own_group=False)
    row = {'event': 'cli', 'args': args, 'exit': result.returncode}
    if args[:2] == ['build', 'next'] and result.returncode == 0:
        try:
            row['result'] = json.loads(result.stdout)
        except ValueError:
            row['result'] = None
    if len(args) == 2 and args[0] == 'hook':
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            payload = {}
        row.update(event=args[1], tool=payload.get('tool_name', ''),
                   input=payload.get('tool_input', {}), session=payload.get('session_id'),
                   agent_type=payload.get('agent_type'))
    with Path(log).open('a', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(row) + '\n')
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(observe(sys.argv[1], sys.argv[2], sys.argv[3:]))
