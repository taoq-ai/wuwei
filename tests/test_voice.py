"""Owner voice learning, promotion, protection, and audience lint."""

import json
from types import SimpleNamespace

from wuwei import registry, workspace
from wuwei.guards.protect_state import check_file, check_bash


def setup(root):
    base = root / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'days/2026-09-28/proposals').mkdir(parents=True)
    (base / 'config.toml').write_text(
        '[owner]\nname = "Pat Example"\npronouns = "they/them"\n'
        'handles = ["UOWNER", "pat-dev"]\n'
        '[adapters]\nchat = "slack"\n'
        '[voice.sources]\ninternal = ["C1"]\n'
        '[voice]\nreview_prs = ["org/repo#7"]\n')
    return base


def test_voice_is_protected_like_config(tmp_path):
    base = setup(tmp_path)
    (base / 'memory/voice.md').write_text('## internal\n')
    payload = {'cwd': str(tmp_path), 'tool_name': 'Write',
               'tool_input': {'file_path': '.wuwei/memory/voice.md'}}
    assert check_file(payload)[0] == 1
    payload['tool_name'] = 'Bash'
    payload['tool_input'] = {'command': 'echo x > .wuwei/memory/voice.md'}
    assert check_bash(payload)[0] == 1


def test_learn_filters_owner_and_redacts_before_proposal(tmp_path, monkeypatch):
    from wuwei.voice import learn
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    messages = [
        {'sender': 'UOWNER', 'text': 'Send the update to jane@example.com at +1 415 555 1212.'},
        {'sender': 'UOTHER', 'text': 'private peer message'},
    ]
    comments = {'comments': [
        {'author': 'pat-dev', 'body': 'I reviewed the change.'},
        {'author': 'other', 'body': 'private PR comment'},
    ], 'threads': []}
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(sent=lambda channel, owner, root=None: registry.Result(0, messages))
        if kind == 'chat' else
        SimpleNamespace(threads=lambda ref, root=None: registry.Result(0, comments))))
    assert learn(tmp_path) == 0
    files = sorted((base / 'days/2026-09-28/proposals').glob('*.json'))
    assert len(files) == 2
    raw = ''.join(path.read_text() for path in files)
    assert 'private peer message' not in raw and 'private PR comment' not in raw
    assert 'jane@example.com' not in raw and '415 555 1212' not in raw
    assert '[REDACTED]' in raw
    assert all(json.loads(path.read_text())['target'] == '.wuwei/memory/voice.md' for path in files)
    assert not (base / 'memory/voice.md').exists()


def test_learn_chat_none_fails_closed_without_writes(tmp_path):
    from wuwei.voice import learn
    base = setup(tmp_path)
    (base / 'config.toml').write_text((base / 'config.toml').read_text().replace('chat = "slack"', 'chat = "none"'))
    assert learn(tmp_path) == 2
    assert not list((base / 'days/2026-09-28/proposals').iterdir())


def test_learn_failed_later_source_leaves_no_partial_proposals(tmp_path, monkeypatch):
    from wuwei.voice import learn
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(sent=lambda channel, owner, root=None: registry.Result(0, [
            {'sender': 'UOWNER', 'text': 'A clean example.'}])) if kind == 'chat' else
        SimpleNamespace(threads=lambda ref, root=None: registry.Result(2, None))))
    assert learn(tmp_path) == 2
    assert not list((base / 'days/2026-09-28/proposals').iterdir())


def test_relearning_keeps_prior_promotion_evidence(tmp_path, monkeypatch):
    from wuwei.voice import learn
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    current = {'text': 'First wording.'}
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(sent=lambda channel, owner, root=None: registry.Result(0, [
            {'sender': 'UOWNER', 'text': current['text']}])) if kind == 'chat' else
        SimpleNamespace(threads=lambda ref, root=None: registry.Result(0, {'comments': [], 'threads': []}))))
    assert learn(tmp_path) == 0
    proposal = next((base / 'days/2026-09-28/proposals').glob('*.json'))
    evidence = tmp_path / json.loads(proposal.read_text())['evidence']
    original = evidence.read_text()
    proposal.rename(proposal.with_suffix('.landed'))
    current['text'] = 'Second wording.'
    assert learn(tmp_path) == 0
    assert evidence.read_text() == original


def test_voice_command_reports_unavailable_chat(tmp_path, monkeypatch):
    from wuwei.__main__ import main
    base = setup(tmp_path)
    (base / 'config.toml').write_text((base / 'config.toml').read_text().replace('chat = "slack"', 'chat = "none"'))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    assert main(['voice', 'learn']) == 2


def test_promote_can_land_voice_proposal(tmp_path, monkeypatch):
    from wuwei.promotion import promote
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    (base / 'days/2026-09-28/evidence.md').write_text('redacted evidence')
    (base / 'days/2026-09-28/proposals/voice.json').write_text(json.dumps({
        'target': '.wuwei/memory/voice.md', 'action': 'add',
        'text': '## internal\n- max_length: 80\n', 'reason': 'owner examples',
        'evidence': '.wuwei/days/2026-09-28/evidence.md'}))
    assert promote(tmp_path)[0]['status'] == 'landed'
    assert (base / 'memory/voice.md').is_file()


def test_promote_cannot_archive_voice_profile(tmp_path, monkeypatch):
    from wuwei.promotion import promote
    base = setup(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    (base / 'memory/voice.md').write_text('## internal\n- max_length: 80\n')
    (base / 'days/2026-09-28/evidence.md').write_text('redacted evidence')
    (base / 'days/2026-09-28/proposals/voice.json').write_text(json.dumps({
        'target': '.wuwei/memory/voice.md', 'action': 'archive',
        'reason': 'bad action', 'evidence': '.wuwei/days/2026-09-28/evidence.md'}))
    assert promote(tmp_path)[0]['status'] == 'rejected'
    assert (base / 'memory/voice.md').is_file()


def test_audience_voice_lint(tmp_path):
    from wuwei.outward import lint
    base = setup(tmp_path)
    (base / 'memory/voice.md').write_text(
        '## shared\n- never: please be advised\n'
        '## internal\n- max_length: 12\n- required_prefix: Hi\n- never: kindly\n'
        '## review\n- max_length: 100\n')
    config = workspace.load_config(tmp_path)
    assert lint('Hi team', 'C1', config, root=tmp_path)[0] == 0
    assert lint('Ready', 'C1', config, root=tmp_path)[0] == 1
    assert lint('Hi kindly', 'C1', config, root=tmp_path)[0] == 1
    assert lint('Hi please be advised', 'C1', config, root=tmp_path)[0] == 1
    assert lint('Ready', 'code_host', config, root=tmp_path)[0] == 0


def test_bad_voice_rules_fail_closed(tmp_path):
    from wuwei.outward import lint
    base = setup(tmp_path)
    (base / 'memory/voice.md').write_text('## internal\n- max_length: infinity\n')
    assert lint('Hi team', 'C1', workspace.load_config(tmp_path), root=tmp_path)[0] == 2


def test_dangling_voice_symlink_fails_closed(tmp_path):
    from wuwei.outward import lint
    base = setup(tmp_path)
    (base / 'memory/voice.md').symlink_to(base / 'missing.md')
    assert lint('Hi team', 'C1', workspace.load_config(tmp_path), root=tmp_path)[0] == 2


def test_workspace_shared_never_rules_reject_machine_openers(tmp_path):
    from pathlib import Path
    from wuwei.outward import lint
    base = setup(tmp_path)
    template = Path(__file__).resolve().parents[1] / 'templates/workspace/memory/voice.md'
    (base / 'memory/voice.md').write_text(template.read_text())
    assert lint('Great question. The change is ready.', 'C1',
                workspace.load_config(tmp_path), root=tmp_path)[0] == 1
