"""Recorded role grants and the optional real ZIRAN audit boundary."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'agents/ziran-baseline.json'


def test_ziran_baseline_matches_allowlist():
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    allowlist = json.loads((ROOT / 'agents/allowlist.json').read_text(encoding='utf-8'))
    assert baseline['version'] == 1
    assert {name: agent['tools'] for name, agent in baseline['agents'].items()} == allowlist


@pytest.mark.parametrize('widened', [False, True], ids=['reviewed', 'builder-webfetch'])
def test_real_ziran_audit(tmp_path, widened):
    ziran = shutil.which('ziran')
    if ziran is None:
        pytest.skip('ziran is not on PATH; install ziran==0.40.0 to run the real role audit')
    agents = shutil.copytree(ROOT / 'agents', tmp_path / 'agents')  # ziran discovers agents only under a directory named agents
    if widened:
        builder = agents / 'builder.md'
        text = builder.read_text(encoding='utf-8')
        builder.write_text(text.replace('\ntools: ', '\ntools: WebFetch, ', 1), encoding='utf-8')
    result = subprocess.run(
        [ziran, 'audit', str(agents), '--baseline', str(BASELINE), '--format', 'json'],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == (1 if widened else 0), result.stdout + result.stderr
    report = json.loads(result.stdout)
    if widened:
        assert any(
            row['rule'] == 'BL003' and row['agent'] == 'builder'
            and 'WebFetch' in row['tools']
            for row in report['findings']
        ), report
