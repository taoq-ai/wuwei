"""Owner memory edit history and seat boundary."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from wuwei import integrity, registry, state
from wuwei.guards.protect_state import check_file

ROOT = Path(__file__).resolve().parents[1]
GOALS = '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\ntarget: 1\ndate: 2026-10-30\npriority: 1\n'


def workspace(tmp_path):
    base = tmp_path / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'config.toml').write_text('')
    (base / 'memory/goals.md').write_text(GOALS)
    (base / 'memory/voice.md').write_text('## internal\n- max_length: 80\n')
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


def test_goals_edit_commits_owner_history_and_clears_integrity(tmp_path):
    base = workspace(tmp_path)
    source = tmp_path / 'new-goals.md'
    source.write_text(GOALS.replace('target: 1', 'target: 2'))
    result = cli(tmp_path, 'goals', 'edit', '--file', str(source))
    assert result.returncode == 0, result.stderr
    assert (base / 'memory/goals.md').read_text() == source.read_text()
    assert 'Promoted-by: wuwei' in history(base)
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0


def test_goals_edit_commits_existing_hand_edit(tmp_path):
    base = workspace(tmp_path)
    target = base / 'memory/goals.md'
    target.write_text(GOALS.replace('target: 1', 'target: 2'))
    assert integrity.workspace_check(tmp_path).exit == 1
    result = cli(tmp_path, 'goals', 'edit', '--file', str(target))
    assert result.returncode == 0, result.stderr
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0


def test_invalid_goals_leave_history_and_target_unchanged(tmp_path):
    base = workspace(tmp_path)
    source = tmp_path / 'bad.md'
    source.write_text('## G-1\noutcome:\n')
    before = history(base)
    result = cli(tmp_path, 'goals', 'edit', '--file', str(source))
    assert result.returncode == 1 and 'goals' in result.stderr
    assert result.stdout == ''
    assert (base / 'memory/goals.md').read_text() == GOALS
    assert history(base) == before


def test_goals_and_voice_edit_say_what_they_saved(tmp_path, monkeypatch, capsys):
    from wuwei.__main__ import main
    workspace(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    source = tmp_path / 'new-goals.md'
    source.write_text(GOALS.replace('target: 1', 'target: 2'))
    for said in ('saved', 'unchanged'):
        assert main(['goals', 'edit', '--file', str(source)]) == 0
        assert capsys.readouterr().out == f'goals: 1 goal {said} (G-1)\n'
    voice = tmp_path / 'voice.md'
    voice.write_text('## internal\n- max_length: 90\n')
    assert main(['voice', 'edit', '--file', str(voice)]) == 0
    assert capsys.readouterr().out == 'voice: saved\n'


def test_editor_flow_uses_selected_editor(tmp_path, monkeypatch):
    base = workspace(tmp_path)
    editor = tmp_path / 'editor'
    editor.write_text('#!/bin/sh\nsed "s/target: 1/target: 2/" "$1" > "$1.next"\nmv "$1.next" "$1"\n')
    editor.chmod(0o755)
    monkeypatch.setenv('EDITOR', str(editor))
    assert cli(tmp_path, 'goals', 'edit').returncode == 0
    assert 'target: 2' in (base / 'memory/goals.md').read_text()
    assert integrity.workspace_check(tmp_path).exit == 0


def test_voice_edit_commits_owner_history_and_clears_integrity(tmp_path):
    base = workspace(tmp_path)
    source = tmp_path / 'voice.md'
    source.write_text('## internal\n- max_length: 100\n')
    result = cli(tmp_path, 'voice', 'edit', '--file', str(source))
    assert result.returncode == 0, result.stderr
    assert (base / 'memory/voice.md').read_text() == source.read_text()
    assert 'Promoted-by: wuwei' in history(base)
    assert 'Edited-by: owner' in history(base)
    assert integrity.workspace_check(tmp_path).exit == 0


def gated(tmp_path, monkeypatch, posture='guarded', topics=('goals',)):
    """A planner session that proposed provisional goals and asked the gate question."""
    from test_decision import gate
    from test_plan import TEMPLATE, lead
    from wuwei import plan, workspace as ws
    from wuwei.guards.decision import record_gate

    base = workspace(tmp_path)
    (base / 'config.toml').write_text(f'[security]\nposture = "{posture}"\n[outbound]\ndefault_tier = "ask"\n')  # #527: these tests hold a draft
    (base / 'memory/goals.md').write_text(TEMPLATE.read_text(encoding='utf-8'))
    (base / 'executable').write_text(str(tmp_path / 'bin/wuwei') + '\n')  # the planner's CLI
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T09:00:00+02:00')
    plan.propose(lead(), tmp_path)
    plan.session('planner-1', tmp_path)
    for topic in topics:
        assert record_gate(gate(tmp_path, header=topic.title())) == (0, '')
    draft = ws.day_dir(tmp_path).relative_to(tmp_path) / 'goals.md'
    return base, draft.as_posix()


@pytest.mark.parametrize('posture', ['observe', 'guarded'])
def test_planner_records_gate_approved_goals(tmp_path, monkeypatch, posture):
    from wuwei import plan
    base, draft = gated(tmp_path, monkeypatch, posture)
    result = cli(tmp_path, 'goals', 'edit', '--file', str(tmp_path / draft))
    assert result.returncode == 0, result.stderr
    assert (base / 'memory/goals.md').read_text() == (tmp_path / draft).read_text()
    plan.approve(['A'], tmp_path, goals_confirmed=True)


def asked_draft(tmp_path, monkeypatch, posture='guarded', answer='Send now (Recommended)'):
    """The planner asked the owner a Draft card for a held tool call (#493)."""
    from test_decision import draft_question
    from test_drafts import held
    from wuwei.guards.decision import record_gate
    gated(tmp_path, monkeypatch, posture, topics=())
    _, _, row = held(tmp_path)
    assert record_gate(draft_question(tmp_path, row['id'], answer=answer)) == (0, '')
    return row['id']


def test_edited_approve_sends_only_the_owner_typed_text(tmp_path, monkeypatch):
    """--file outside strict skips the host prompt only for the text the owner typed into a
    Draft card citing the id (#493)."""
    from test_decision import draft_question
    from wuwei import drafts
    from wuwei.guards.decision import record_gate

    def no_terminal(*args, **kwargs):
        raise OSError('this is an owner action: run it in a host terminal')
    monkeypatch.setattr(integrity, '_host_confirm', no_terminal)
    draft_id = asked_draft(tmp_path, monkeypatch, answer='Send with an edit')
    config = tmp_path / '.wuwei/config.toml'
    config.write_text('[owner]\nname = "Pat Example"\n' + config.read_text())
    reply = tmp_path / 'reply.txt'
    reply.write_text('Happy to help on Friday')
    result = drafts.approve(tmp_path, draft_id, source=reply, answered=True)
    assert result.exit == 2 and 'owner action' in result.reason
    assert state.read_state(tmp_path)['drafts'][draft_id]['status'] == 'pending'
    assert record_gate(draft_question(tmp_path, draft_id, answer='Thanks, see you then')) == (0, '')
    reply.write_text('Thanks, see you then\n')
    assert drafts.approve(tmp_path, draft_id, source=reply, answered=True).exit == 0
    stored = state.read_state(tmp_path)['drafts'][draft_id]
    assert stored['status'] == 'approved' and stored['final_text'] == 'Thanks, see you then'


def test_strict_asked_draft_stays_held(tmp_path, monkeypatch):
    from test_drafts import held
    draft_id = asked_draft(tmp_path, monkeypatch, 'strict')
    code, reason, row = held(tmp_path)
    assert code == 1 and row['id'] == draft_id
