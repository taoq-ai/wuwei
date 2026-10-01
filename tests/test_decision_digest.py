"""Batched two-way seat decision digest from the sweep."""

from datetime import timedelta

from wuwei import registry, state, watch, workspace
from wuwei.registry import Result


def test_two_pending_decisions_make_one_digest_within_hour(tmp_path, monkeypatch):
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    sent = []

    class Chat:
        def dm(self, text, *, root=None):
            sent.append(text)
            return Result(1, text, 'outward: deliver as a draft for the owner to send')

    monkeypatch.setattr(registry, 'load', lambda kind, config: Chat() if kind == 'chat' else None)
    from test_decision import VALID
    from wuwei.__main__ import main
    monkeypatch.chdir(root)
    decision_dir = workspace.day_dir(root) / 'decisions'
    decision_dir.mkdir(parents=True)
    (decision_dir / 'D-1.md').write_text(VALID)
    (decision_dir / 'D-2.md').write_text(VALID)
    (decision_dir / 'D-3.md').write_text(VALID)
    assert main(['decision', 'route', 'D-1']) == 0
    assert main(['decision', 'route', 'D-2']) == 0
    assert watch.digest(root, workspace.load_config(root)) == 0
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(hours=1)).isoformat())
    assert main(['decision', 'route', 'D-3']) == 0
    assert watch.digest(root, workspace.load_config(root)) == 0
    assert len(sent) == 1
    assert 'D-1' in sent[0] and 'D-2' in sent[0]
    drafts = list((workspace.day_dir(root) / 'decisions').glob('two-way-digest-*.md'))
    assert len(drafts) == 1 and drafts[0].read_text() == sent[0]
    assert watch.saved(root)['digest_ids'] == ['D-1', 'D-2']
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(hours=1)).isoformat())
    assert watch.digest(root, workspace.load_config(root)) == 0
    assert len(sent) == 2 and 'D-3' in sent[1]


def test_digest_port_failure_is_unmeasured_and_keeps_decisions_pending(tmp_path, monkeypatch):
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    state._write_state(lambda data: data.update(decision_outcomes={
        'D-1': {'option': 'A', 'outcome': 'A', 'decided_by': 'seat', 'reversibility': 'two-way'},
    }), root, reserved=False)

    class Chat:
        def dm(self, text, *, root=None):
            return Result(2, reason='chat unavailable')

    monkeypatch.setattr(registry, 'load', lambda kind, config: Chat())
    assert watch.digest(root, workspace.load_config(root)) == 2
    assert 'digest_at' not in watch.saved(root)


def test_digest_with_default_chat_adapter_saves_draft(tmp_path, monkeypatch):
    from wuwei import outward
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    monkeypatch.setattr(outward, 'check_call', lambda *args: (0, ''))
    state._write_state(lambda data: data.update(decision_outcomes={
        'D-1': {'option': 'A', 'decided_by': 'seat', 'reversibility': 'two-way'},
    }), root, reserved=False)
    assert watch.digest(root, workspace.load_config(root)) == 0
    drafts = list((workspace.day_dir(root) / 'decisions').glob('two-way-digest-*.md'))
    assert len(drafts) == 1 and 'D-1: A' in drafts[0].read_text()
    assert watch.saved(root)['digest_ids'] == ['D-1']


def test_digest_cooldown_crosses_midnight(tmp_path, monkeypatch):
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T23:30:00+00:00')
    calls = []

    class Chat:
        def dm(self, text, *, root=None):
            calls.append(text)
            return Result(1, text, 'outward: deliver as a draft for the owner to send')

    monkeypatch.setattr(registry, 'load', lambda kind, config: Chat())
    state._write_state(lambda data: data.update(decision_outcomes={
        'D-1': {'option': 'A', 'decided_by': 'seat', 'reversibility': 'two-way'},
    }), root, reserved=False)
    assert watch.digest(root, workspace.load_config(root)) == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T00:15:00+00:00')
    state._write_state(lambda data: data.update(decision_outcomes={
        'D-1': {'option': 'B', 'decided_by': 'seat', 'reversibility': 'two-way'},
    }), root, reserved=False)
    assert watch.digest(root, workspace.load_config(root)) == 0
    assert len(calls) == 1
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T01:31:00+00:00')
    assert watch.digest(root, workspace.load_config(root)) == 0
    assert len(calls) == 2



def test_digest_lines_follow_the_digest_verbosity(tmp_path, monkeypatch):
    root = tmp_path
    (root / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00+00:00')
    sent = []

    class Chat:
        def dm(self, text, *, root=None):
            sent.append(text)
            return Result(0, {})

    monkeypatch.setattr(registry, 'load', lambda kind, config: Chat())
    for level in ('', '[owner.verbosity]\ndigest = "full"\n'):
        (root / '.wuwei/config.toml').write_text(level)
        state._write_state(lambda data: data.update(watch={}, decision_outcomes={
            'D-1': {'option': 'A', 'decided_by': 'seat', 'reversibility': 'two-way'},
            'D-2': {'option': 'B', 'decided_by': 'seat', 'reversibility': 'two-way'}}), root, reserved=False)
        assert watch.digest(root, workspace.load_config(root)) == 0
    assert sent == ['Two-way decisions taken:\n- D-1: A\n- D-2: B\n',
                    'Two-way decisions taken:\n- D-1: A (decisions/D-1.md)\n- D-2: B (decisions/D-2.md)\n']
