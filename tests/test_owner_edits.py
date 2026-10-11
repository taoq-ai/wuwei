"""Owner memory edit history and seat boundary."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from wuwei import integrity, registry
from wuwei.guards.protect_state import check_file

ROOT = Path(__file__).resolve().parents[1]
GOALS = '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n'


def workspace(tmp_path):
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'config.toml').write_text('')
    (base / 'memory/goals.md').write_text(GOALS)
    vcs = registry.load('vcs', {'adapters': {'vcs': 'git'}})
    assert vcs.workspace_init(base).exit == 0
    return base


def cli(root, *args):
    return subprocess.run([sys.executable, '-P', '-m', 'wuwei', *args],
                          env={**os.environ, 'PYTHONPATH': str(ROOT / 'cli'),
                               'WUWEI_WORKSPACE': str(root)},
                          capture_output=True, text=True)


def history(base):
    return subprocess.run(['git', '-C', str(base), 'log', '-1', '--format=%B'],
                          check=True, capture_output=True, text=True).stdout


def gated(tmp_path, monkeypatch, enforce='true'):
    """A planner session that proposed provisional goals."""
    from test_plan import TEMPLATE, lead
    from wuwei import plan, workspace as ws

    base = workspace(tmp_path)
    (base / 'config.toml').write_text(f'[guards]\nenforce = {enforce}\n')
    (base / 'memory/goals.md').write_text(TEMPLATE.read_text(encoding='utf-8'))
    (base / 'executable').write_text(str(tmp_path / 'bin/wuwei') + '\n')  # the planner's CLI
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    plan.propose(lead(), tmp_path)
    plan.session('planner-1', tmp_path)
    draft = ws.day_dir(tmp_path).relative_to(tmp_path) / 'goals.md'
    return base, draft.as_posix()


@pytest.mark.parametrize('posture', ['false', 'true'])
def test_approve_records_the_gate_goals(tmp_path, monkeypatch, posture):
    """#833: plan approve writes the provisional goals the gate showed, as an owner commit."""
    from wuwei import plan
    base, draft = gated(tmp_path, monkeypatch, posture)
    plan.approve(['A'], tmp_path, goals_confirmed=True)
    assert (base / 'memory/goals.md').read_text() == (tmp_path / draft).read_text()
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0


def test_approve_records_goals_edited_in_the_session(tmp_path, monkeypatch):
    """#833: goals the planner changed on the owner's word are recorded by the gate approval."""
    from wuwei import plan
    base, draft = gated(tmp_path, monkeypatch)
    defined = (tmp_path / draft).read_text()
    (base / 'memory/goals.md').write_text(defined)
    assert integrity.workspace_check(tmp_path).exit == 1
    plan.approve(['A'], tmp_path, goals_confirmed=True)
    assert (base / 'memory/goals.md').read_text() == defined
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0


def test_approve_leaves_committed_goals_alone(tmp_path, monkeypatch):
    from wuwei import plan
    base, draft = gated(tmp_path, monkeypatch)
    plan.approve(['A'], tmp_path, goals_confirmed=True)
    before = history(base)
    from wuwei import promotion
    assert promotion.save_goals(tmp_path, (base / 'memory/goals.md').read_text()) is False
    assert history(base) == before



