import json
import os
import shutil
import subprocess
from pathlib import Path

from conftest import write_plan
from wuwei import gh, ws


def test_a_hook_subprocess_reads_the_board_through_the_stub_gh_and_never_reaches_the_real_one(root, tmp_path):
    """A counting gh sits after the stub on PATH: the stub answers first, so the counter logs nothing."""
    log, shim = tmp_path / 'calls.log', tmp_path / 'shim'
    shim.mkdir()
    (shim / 'gh').write_text(f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')
    (shim / 'gh').chmod(0o755)
    env = {**os.environ, 'PATH': os.pathsep.join([os.environ['PATH'], str(shim)])}
    first = Path(shutil.which('gh', path=env['PATH']))
    assert b'wuwei-test-stub' in first.read_bytes() and first.parent != shim
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
                       'status': 'open', 'score': 3}])
    done = subprocess.run([str(ws.PLUGIN / 'bin' / 'wuwei'), 'hook', 'Stop'], text=True, capture_output=True, env=env, cwd=root,
                          input=json.dumps({'session_id': 's1', 'cwd': str(root), 'stop_hook_active': False}))
    assert done.returncode == 0, done.stderr
    assert not log.exists()
    try:
        gh.run(['api', 'rate_limit'])
    except gh.GhError:
        pass
    assert not log.exists()
