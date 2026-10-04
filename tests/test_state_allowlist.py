"""Generic commands deny new evidence by default, including reader inventories."""

import ast
import json
from pathlib import Path

import pytest

from wuwei import state, workspace
from wuwei.__main__ import main


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data['items'].update(A={}), reserved=False)
    return tmp_path


def stored(root):
    directory = workspace.day_dir(root)
    return [(directory / name).read_bytes() for name in ('state.json', 'events.jsonl')]


@pytest.mark.parametrize('path,producer', [
    ('future_evidence', 'dedicated command'),
    ('items.A.future_evidence', 'dedicated command'),
    ('items.A', 'wuwei plan approve'),
    ('items', 'wuwei plan approve'),
    ('items.A.phase', 'wuwei state transition'),
    ('items.A.flags.trust_surface', 'wuwei plan approve'),
    ('items.A.pr', 'wuwei pr raise or wuwei pr claim'),
    ('seats.builder.status', 'wuwei hook PreToolUse'),
    ('fast_checks', 'wuwei fast-checks'),
    ('reply_acks', 'wuwei reply'),
    ('claimed_prs', 'dedicated command'),
    ('raised_prs', 'dedicated command'),
    ('gate_verdicts', 'wuwei dispatch receive'),
    ('goal_seats', 'wuwei plan approve'),
    ('items.A.gates', 'wuwei dispatch next'),
    ('items.A.tier', 'wuwei plan approve'),
    ('decision_outcomes', 'wuwei decision route or wuwei build'),
    ('decision_routes', 'wuwei decision route'),
    ('steward_notes', 'wuwei steward run'),
    ('steward_acks', 'wuwei steward ack'),
    ('gate_approved', 'wuwei plan approve'),
    ('envelope', 'wuwei plan approve'),
    ('watch', 'wuwei watch'),
    ('pr_action_done', 'wuwei pr act'),
    ('pr_reply_drafts', 'wuwei pr act'),
    ('pr_action_decisions', 'wuwei pr act'),
    ('sessions', 'wuwei hook SessionStart'),
    ('sessions.A.role', 'wuwei hook SessionStart'),
    ('claims', 'wuwei brief builder'),
    ('negotiation_loops', 'wuwei steward run'),
    ('items.A.assumption', 'wuwei decision route --external'),
    ('author_logins', 'wuwei pr raise, ping or reviewers'),
    ('grants', 'wuwei hook PreToolUse (deploy guard)'),
])
def test_nonallowlisted_state_paths_refuse_without_write(root, capsys, path, producer):
    before = stored(root)
    assert main(['state', 'set', path, '{}']) == 1
    message = capsys.readouterr().err
    assert path in message and producer in message
    assert stored(root) == before


@pytest.mark.parametrize('update', [
    lambda data: data.update(future_evidence={}),
    lambda data: data['items']['A'].update(future_evidence={}),
    lambda data: data['items'].update(B={'note': 'new item'}),
    lambda data: data.pop('raised_prs'),
])
def test_callback_cannot_change_unlisted_fields(root, update):
    before = stored(root)
    with pytest.raises(state.StateError, match='dedicated command|wuwei'):
        state.write_state(update)
    assert stored(root) == before


def test_only_owner_tuning_and_existing_notes_are_allowed(root):
    for path, value in [('cap', 3), ('seat_policy.builder.model', 'model'),
                        ('items.A.note', 'Working on this')]:
        assert main(['state', 'set', path, json.dumps(value)]) == 0
    data = state.read_state()
    assert data['cap'] == 3
    assert data['seat_policy'] == {'builder': {'model': 'model'}}
    assert data['items']['A']['note'] == 'Working on this'
    before = stored(root)
    assert main(['state', 'set', 'items.B.note', '"cannot create"']) == 1
    assert stored(root) == before
    state.transition('A', 'implement')
    assert state.read_state()['items']['A']['phase'] == 'implement'
    for name in ('state.json', 'events.jsonl'):
        assert (workspace.day_dir(root) / name).stat().st_mode & 0o777 == 0o444


@pytest.mark.parametrize('field,value', [('cap', 2), ('seat_policy.builder', {'model': 'x'})])
def test_approved_settings_stay_frozen_under_writer_lock(root, field, value):
    state._write_state(lambda data: data.update(gate_approved=True), reserved=False)
    before = stored(root)
    assert main(['state', 'set', field, json.dumps(value)]) == 1
    with pytest.raises(state.StateError):
        state.write_state(lambda data: data.update({field.split('.')[0]: value}))
    assert stored(root) == before
    assert main(['state', 'set', 'items.A.note', '"still editable"']) == 0


@pytest.mark.parametrize('kind,producer', [
    ('future.evidence', 'dedicated command'),
    ('seat launched', 'wuwei hook PreToolUse'),
    ('seat stopped', 'wuwei hook SubagentStop'),
    ('brief written', 'wuwei brief'),
    ('session.seen', 'wuwei hook SessionStart'),
    ('item.claimed', 'wuwei worktree add'),
    ('state.transition', 'wuwei state transition'),
    ('fast_checks.record', 'wuwei fast-checks'),
    ('plan.approved', 'wuwei plan approve'),
    ('pr.claimed', 'wuwei pr claim'),
    ('reply: acknowledged', 'wuwei reply'),
    ('decision.decided', 'wuwei decision outcome'),
    ('decision.routed', 'wuwei decision route'),
    ('steward.notes', 'wuwei steward run'),
    ('steward.run', 'wuwei steward run'),
    ('steward.due', 'wuwei hook PostToolUse'),
    ('steward.acknowledged', 'wuwei steward ack'),
    ('day.close_requested', 'wuwei close'),
    ('remote.acknowledged', 'wuwei remote ack'),
    ('gate.tiered', 'wuwei dispatch next'),
    ('session.rotated', 'wuwei hook Stop'),
    ('negotiation.loop', 'wuwei steward run'),
    ('negotiation.notified', 'wuwei listen'),
    ('decision.waited', 'wuwei sweep'),
    ('reviewer.unresolved', 'wuwei pr raise, ping or reviewers'),
    ('grant.asked', 'wuwei hook PreToolUse'),
    ('grant.used', 'wuwei hook PreToolUse'),
    ('grant.revoked', 'wuwei grants revoke'),
])
def test_nonfree_events_refuse_without_append(root, capsys, kind, producer):
    before = stored(root)
    assert main(['event', '--', kind, '{}']) == 1
    message = capsys.readouterr().err
    assert kind in message and producer in message
    assert stored(root) == before


def test_free_note_and_internal_events(root):
    assert main(['event', 'note', '{"text":"progress"}']) == 0
    state.append_event('future.producer', {'measured': True})
    events = [json.loads(line) for line in stored(root)[1].splitlines()]
    assert events[-2]['kind'] == 'note'
    assert events[-2]['ts'] == workspace.now().isoformat()
    assert events[-1]['kind'] == 'future.producer'


def reader_inventory():
    """Conservative source inventory: dictionary reads plus kind tests and prefixes.

    Scan all CLI modules so helpers used by guards, sweeps and policies are included.
    Include helper arguments and container literals for dynamic reads such as due(key)
    and loops over field names. Non-state keys are included to avoid alias guessing.
    """
    keys, kinds = set(), set()
    source = Path(__file__).resolve().parents[1] / 'cli/wuwei'
    for path in source.rglob('*.py'):
        if path in (source / 'state.py', source / 'commands/state.py', source / 'commands/event.py'):
            continue
        tree = ast.parse(path.read_text())
        constants = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value
        for node in ast.walk(tree):
            candidates = (node.elts if isinstance(node, (ast.Tuple, ast.List, ast.Set))
                          else node.keys if isinstance(node, ast.Dict)
                          else node.args if isinstance(node, ast.Call)
                          and isinstance(node.func, ast.Name) else ())
            keys.update(part.value for part in candidates
                        if isinstance(part, ast.Constant) and isinstance(part.value, str)
                        and part.value.isidentifier())
            key = None
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                key = node.slice
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == 'get' and node.args):
                key = node.args[0]
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
            if not isinstance(node, (ast.Compare, ast.Call)):
                continue
            if not any((isinstance(part, ast.Name) and part.id == 'kind') or
                       (isinstance(part, ast.Constant) and part.value == 'kind')
                       for part in ast.walk(node)):
                continue
            candidates = list(ast.walk(node))
            for part in list(candidates):
                if isinstance(part, ast.Name) and part.id in constants:
                    candidates.extend(ast.walk(constants[part.id]))
            kinds.update(part.value for part in candidates
                         if isinstance(part, ast.Constant) and isinstance(part.value, str))
    return keys, kinds


def test_reader_inventory_cannot_be_written_generically(root, capsys):
    keys, kinds = reader_inventory()
    assert {'raised_prs', 'claimed_prs', 'fast_checks', 'reply_acks', 'channel_posts',
            'gate_approved', 'approved_items', 'decision_outcomes', 'gate_verdicts',
            'seats', 'watch', 'merges', 'flags', 'phase', 'report_at', 'trust_surface',
            'clock_at', 'poll_at', 'sweep_at', 'activity_at', 'drafts'} <= keys
    assert {'brief written', 'seat launched', 'plan.approved', 'state.',
            'watch: clock', 'watch: sweep', 'reply: acknowledged'} <= kinds
    before = stored(root)
    data = state.read_state(root)
    for key in sorted(keys):
        if not key:
            continue
        # These two settings are owner-tunable inputs, frozen on approval above.
        if key not in {'cap', 'seat_policy'}:
            # Check permission separately so invalid values cannot mask an open path.
            assert not state._generic_allowed(key.split('.'), data), key
            value = json.dumps(data.get(key, {}))
            assert main(['state', 'set', '--', key, value]) == 1, key
        path = f'items.A.{key}'
        assert not state._generic_allowed(path.split('.'), data), path
        value = json.dumps(data['items']['A'].get(key, {}))
        assert main(['state', 'set', path, value]) == 1, path
    for kind in sorted(kinds):
        if kind.strip():
            assert main(['event', '--', kind, '{}']) == 1, kind
            # A prefix reader must not become forgeable via a new suffix.
            assert main(['event', '--', kind + 'future', '{}']) == 1, kind
    assert stored(root) == before
    capsys.readouterr()


def test_callback_cannot_change_equal_but_different_json_types(root):
    state._write_state(lambda data: data.update(evidence={'count': 1}), reserved=False)
    before = stored(root)
    with pytest.raises(state.StateError):
        state.write_state(lambda data: data['evidence'].update(count=True))
    assert stored(root) == before


@pytest.mark.parametrize('surface', ['state', 'typed_state', 'event'])
def test_reader_inventory_detects_widened_allowlist(root, capsys, monkeypatch, surface):
    from wuwei.commands import event
    if surface in ('state', 'typed_state'):
        expected = 'report_at' if surface == 'state' else 'gate_approved'
        monkeypatch.setattr(state, 'OWNER_FIELDS', state.OWNER_FIELDS | {expected})
    else:
        monkeypatch.setattr(event, 'FREE_KINDS', event.FREE_KINDS | {'seat launched'})
        expected = 'seat launched'
    with pytest.raises(AssertionError, match=expected):
        test_reader_inventory_cannot_be_written_generically(root, capsys)
