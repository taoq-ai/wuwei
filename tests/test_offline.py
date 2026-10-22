import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import write_plan
from wuwei import gh, ws


def test_a_hook_subprocess_reads_the_board_through_the_stub_gh_and_never_reaches_the_real_one(root, tmp_path, monkeypatch):
    """A counting gh sits directly after the stub on PATH, before any real gh: a call that skips the stub lands in its log."""
    log, shim = tmp_path / 'calls.log', tmp_path / 'shim'
    shim.mkdir()
    (shim / 'gh').write_text(f'#!/bin/sh\necho "$@" >> {log}\nexit 1\n')
    (shim / 'gh').chmod(0o755)
    stub, *rest = os.environ['PATH'].split(os.pathsep)
    monkeypatch.setenv('PATH', os.pathsep.join([stub, str(shim), *rest]))
    assert b'wuwei-test-stub' in Path(shutil.which('gh')).read_bytes()
    assert not {'GH_TOKEN', 'GITHUB_TOKEN'} & set(os.environ) and not any(Path(os.environ['GH_CONFIG_DIR']).iterdir())
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
                       'status': 'open', 'score': 3}])
    done = subprocess.run(['sh', str(ws.PLUGIN / 'bin' / 'wuwei'), 'hook', 'Stop'], text=True, capture_output=True, cwd=root,
                          input=json.dumps({'session_id': 's1', 'cwd': str(root), 'stop_hook_active': False}))
    assert done.returncode == 0, done.stderr
    with pytest.raises(gh.GhError, match='offline|could not run'):  # Windows runs no stub: it finds no gh.exe
        gh.run(['api', 'rate_limit'])
    assert not log.exists()
