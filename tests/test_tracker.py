"""Tracker hygiene (5.11): the ticket rule, creation and the comment writer, offline."""

import json

import pytest

from fakes.tracker import Fake, ported
from wuwei import integrity, registry, state, tracker, workspace
from wuwei.__main__ import main


def config(adapter='linear', required=True, skip=(), posture='guarded'):
    return {'adapters': {'tracker': adapter},
            'tracker': {'required': required, 'skip_tiers': list(skip)},
            'guards': {'mode': 'enforce'},
            'security': {'posture': posture, 'areas': dict.fromkeys(workspace.AREAS)}}


MISSING = ("item-1 has no ticket: the planner proposes one on the item's card (an existing "
           "ticket or a new one from its record) and records the owner's answer")
STRICT = ("item-1 has no ticket: the owner runs bin/wuwei tracker create item-1 (opens one from "
          "the item's record) or bin/wuwei plan set item-1 ticket=<id> in a host terminal")


@pytest.mark.parametrize('posture,expected', [('observe', MISSING), ('guarded', MISSING),
                                              ('strict', STRICT)])
def test_missing_reason_by_posture(posture, expected):
    """#636: below strict the reason names the card, never a terminal command."""
    assert tracker.check({}, config(posture=posture), 'item-1') == ('missing', expected)
    assert ('bin/wuwei' in expected) is (posture == 'strict')


def test_owners_none_is_skipped():
    data = {'tickets': {'item-1': {'id': None, 'source': 'none'}}}
    assert tracker.check(data, config(), 'item-1') == ('skipped', '')


@pytest.mark.parametrize('settings,data,row,expected', [
    (config('none'), {}, {}, ('off', '')),
    (config(required=False), {}, {}, ('off', '')),
    (config(), {'tickets': {'item-1': {'id': 'ENG-1', 'source': 'set'}}}, {}, ('ticket', '')),
    (config(skip=['light']), {}, {'tier': 'light'}, ('skipped', '')),
    (config(skip=['light']), {}, {'gates': {'tier': 'light'}}, ('skipped', '')),
    (config(skip=['light']), {}, {}, ('missing', MISSING)),
    (config(skip=['light']), {}, None, ('missing', MISSING)),
    (config(skip=['light']), {}, {'tier': 'light', 'gates': {'tier': 'standard'}},
     ('missing', MISSING)),
])
def test_check(settings, data, row, expected):
    assert tracker.check(data, settings, 'item-1', row) == expected


def test_ticket():
    assert tracker.ticket({}, 'item-1') is None
    assert tracker.ticket({'tickets': {'item-1': {'id': 'ENG-1', 'source': 'set'}}},
                          'item-1') == 'ENG-1'


def test_pending_items_draft_names_approval():
    row = {'id': 'draft-1', 'status': 'pending', 'channel': 'tracker', 'operation': 'create',
           'inputs': {'draft': {'title': 'x', 'item': 'item-1', 'category': 'items'}}}
    other = {**row, 'id': 'draft-2', 'inputs': {'draft': {'title': 'x', 'item': 'item-1',
                                                          'category': 'bugs'}}}
    data = {'drafts': {'draft-2': other, 'draft-1': row}}
    assert tracker.pending(data, 'item-1') == 'draft-1'
    assert tracker.check(data, config(), 'item-1') == (
        'missing', 'item-1 has no ticket: draft draft-1 opens it once the owner answers Send '
                   'on its card (bin/wuwei drafts show draft-1 --widget)')
    assert tracker.check(data, config(posture='strict'), 'item-1') == (
        'missing', 'item-1 has no ticket: the owner runs bin/wuwei drafts approve draft-1 '
                   'in a host terminal')
    row['status'] = 'sent'
    assert tracker.pending(data, 'item-1') is None


CREATED = registry.Result(0, {'id': 'ENG-9', 'url': 'https://example.test/ENG-9'})


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(integrity, '_host_confirm', lambda *a, **k: True)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[owner]\nname = "Pat Example"\npronouns = "they/them"\n'
        '[adapters]\ntracker = "linear"\n')
    day = workspace.day_dir(tmp_path)
    day.mkdir(parents=True)
    (day / 'proposal.json').write_text(json.dumps({'candidates': [
        {'id': 'item-1', 'scope': 'Add the export\n  button', 'evidence': 'issue 12',
         'goal': 'G-1', 'track': 'SLICE'}]}))
    fake = Fake({'create': CREATED, 'comment': registry.Result(0, {'id': 'c-1'}),
                 'transition': registry.Result(0, {})})
    port = ported(fake)
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: port if kind == 'tracker'
                        else load(kind, config))
    return tmp_path, fake


def settings(root, text):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[tracker]\n' + text + '\n')


def seed_ticket(root, item='item-1', ticket='ENG-1'):
    state._write_state(lambda data: data.setdefault('tickets', {}).update(
        {item: {'id': ticket, 'source': 'set'}}), root, reserved=False)


def day_events(root, kind=None):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [row for row in rows if kind is None or row['kind'] == kind]


BUG = ['tracker', 'create', '--bug', 'item-1', 'Export fails on empty rows',
       '--evidence', 'cli/x.py:12']


@pytest.mark.parametrize('flag,seat,category', [('--bug', 'builder', 'bugs'),
                                                ('--triage', 'sentinel-quality', 'triage')])
def test_bug_from_a_seat_creates_under_send(ws, capsys, flag, seat, category):
    """#644: the finder files in the owner's own tracker; no draft under the send umbrella."""
    root, fake = ws
    seed_ticket(root)
    command = ['tracker', 'create', flag, *BUG[3:], '--seat', seat]
    assert main(command) == 0
    assert 'ENG-9' in capsys.readouterr().out
    assert state.read_state(root).get('drafts', {}) == {}
    created, = [row['payload'] for row in day_events(root, 'tracker.created')]
    assert (created['class'], created['subject'], created['seat']) == (category, 'item-1', seat)
    assert main(command) == 0
    assert 'ENG-9' in capsys.readouterr().out
    assert len(fake.calls) == 1 and len(day_events(root, 'tracker.created')) == 1


def test_seat_is_a_closed_list(ws):
    with pytest.raises(SystemExit) as exc:
        main(BUG + ['--seat', 'lead'])
    assert exc.value.code == 2


def outbound(root, text):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(text + '\n')


def test_bug_held_under_ask_names_the_card(ws, capsys):
    root, fake = ws
    seed_ticket(root)
    outbound(root, '[outbound]\ndefault_tier = "ask"')
    assert main(BUG) == 1
    out = capsys.readouterr().out
    row, = state.read_state(root)['drafts'].values()
    assert f'bin/wuwei drafts show {row["id"]} --widget' in out and 'category not in tracker.auto' in out
    assert 'drafts approve' not in out
    assert row['inputs']['draft'] == {'title': 'Export fails on empty rows', 'description': 'Evidence: cli/x.py:12',
                                      'item': 'item-1', 'category': 'bugs', 'parent': 'ENG-1'}
    before = (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert main(BUG) == 1
    assert capsys.readouterr().out == out
    assert (workspace.day_dir(root) / 'events.jsonl').read_text() == before
    assert fake.calls == []


def test_bug_owner_row_holds(ws, capsys):
    root, fake = ws
    seed_ticket(root)
    outbound(root, '[outbound]\ntiers = [{ tool = "tracker", audience = "owner", tier = "ask" }]')
    assert main(BUG) == 1
    out = capsys.readouterr().out
    assert 'rule 1' in out and 'tool=tracker audience=owner' in out
    assert day_events(root, 'draft.created') and fake.calls == []


def test_bug_held_under_strict_names_the_terminal(ws, capsys):
    root, fake = ws
    seed_ticket(root)
    outbound(root, '[outbound]\ndefault_tier = "ask"\n[security]\nposture = "strict"')
    assert main(BUG) == 1
    out = capsys.readouterr().out
    assert 'bin/wuwei drafts approve draft-' in out and 'host terminal' in out


def test_bug_blocked_under_block(ws, capsys):
    root, fake = ws
    seed_ticket(root)
    outbound(root, '[outbound]\ndefault_tier = "block"')
    assert main(BUG) == 1
    assert 'outbound.default_tier' in capsys.readouterr().err
    assert not state.read_state(root).get('drafts') and fake.calls == []


def test_bug_in_client_tracker_keeps_outward_rules(ws, capsys):
    root, fake = ws
    seed_ticket(root)
    text = (root / '.wuwei/config.toml').read_text().replace('tracker = "linear"', 'tracker = "github"')
    (root / '.wuwei/config.toml').write_text(text + '[tracker]\nproject = "outside-org/repo"\n')
    assert main(BUG) == 1
    assert 'audience=client' in capsys.readouterr().out
    assert fake.calls == []


def test_bug_in_auto_creates_once(ws, capsys):
    root, fake = ws
    seed_ticket(root)
    settings(root, 'auto = ["bugs"]')
    assert main(BUG) == 0
    assert 'ENG-9' in capsys.readouterr().out
    created, = [row['payload'] for row in day_events(root, 'tracker.created')]
    assert {key: created[key] for key in ('class', 'subject', 'ticket', 'parent')} == {
        'class': 'bugs', 'subject': 'item-1', 'ticket': 'ENG-9', 'parent': 'ENG-1'}
    assert state.read_state(root)['tickets'] == {'item-1': {'id': 'ENG-1', 'source': 'set'}}
    assert main(BUG) == 0
    assert 'ENG-9' in capsys.readouterr().out
    assert len(fake.calls) == 1 and len(day_events(root, 'tracker.created')) == 1


def test_creation_refusals(ws, capsys):
    root, fake = ws
    assert main(['tracker', 'create', '--bug', 'item-1', 'Broken', '--evidence',
                 '/srv/x/file.py:3']) == 1
    assert 'absolute path' in capsys.readouterr().err
    settings(root, 'create = ["bugs"]')
    assert main(['tracker', 'create', '--follow-up', 'item-1', 'Later', '--evidence', 'x']) == 1
    assert 'tracker.create' in capsys.readouterr().err
    assert main(['tracker', 'create', 'nothing']) == 2
    assert fake.calls == [] and not day_events(root)


def test_item_ticket_from_the_proposal(ws, capsys):
    root, fake = ws
    settings(root, 'auto = ["items"]')
    assert main(['tracker', 'create', 'item-1']) == 0
    (_, (draft,), _), = fake.calls
    assert draft == {'title': 'Add the export button', 'item': 'item-1', 'category': 'items',
                     'description': 'Evidence: issue 12\nGoal: G-1\nTrack: SLICE'}
    assert state.read_state(root)['tickets'] == {'item-1': {'id': 'ENG-9', 'source': 'create'}}
    assert main(['tracker', 'create', 'item-1']) == 0
    assert len(fake.calls) == 1


def test_create_without_adapter_cannot_run(ws, monkeypatch, capsys):
    root, _ = ws
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setattr(registry, 'load', lambda kind, config: pytest.fail('no port call'))
    assert main(['tracker', 'create', 'item-1']) == 2
    assert 'tracker adapter is none' in capsys.readouterr().err


def approved(root, item='item-1', phase='implement'):
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=[item],
        items={item: {'phase': phase, 'status': 'queued'}}), root, reserved=False)


def comments(fake):
    return [call[1] for call in fake.calls if call[0] == 'comment']


def story(root):
    """A decision outcome, a phase change and a gate verdict, as their producers write them."""
    decisions = workspace.day_dir(root) / 'decisions'
    decisions.mkdir()
    (decisions / 'D-1.md').write_text('Question: Ship item-1 now?\nOutcome: yes\n')
    state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update(
        {'D-1': {'option': 'yes', 'decided_by': 'owner'}}), root, reserved=False,
        kind='decision.decided', payload={'id': 'D-1', 'option': 'yes', 'decided_by': 'owner'})
    state.transition('item-1', 'gate', root)
    state._write_state(lambda data: data['gate_verdicts'].update({'item-1:quality:initial': {
        'verdict': 'FIX', 'findings': ['- P1 | cli/x.py:1 | empty | blocks: yes',
                                       '- P3 | cli/x.py:2 | naming | blocks: no']}}),
        root, reserved=False, kind='gate.received',
        payload={'item': 'item-1', 'role': 'quality', 'round': 'initial', 'verdict': 'FIX'})


def test_log_writes_the_story_once(ws):
    root, fake = ws
    approved(root)
    seed_ticket(root)
    story(root)
    assert main(['tracker', 'log']) == 0
    assert comments(fake) == [('ENG-1', '[2026-09-29 item-1] Phase: gate.', 'progress')]
    drafted = sorted(row['text'] for row in state.read_state(root)['drafts'].values())
    assert drafted == ['[2026-09-29 item-1] Decision D-1: Ship item-1 now? Outcome: yes.',
                       '[2026-09-29 item-1] Review quality (initial): FIX, 1 blocking findings.']
    log = state.read_state(root)['tracker_log']
    assert sorted(entry['outcome'] for entry in log.values()) == ['drafted', 'drafted', 'written']
    before = (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert main(['tracker', 'log']) == 0
    assert len(fake.calls) == 1
    assert (workspace.day_dir(root) / 'events.jsonl').read_text() == before


def test_log_pr_merge_and_carry(ws):
    root, fake = ws
    approved(root, phase='gate')
    seed_ticket(root)
    state.record_pr(root, 'item-1', 'acme/app#1', raised=True)
    state.transition('item-1', 'merged', root)
    assert main(['tracker', 'log']) == 0
    texts = [text for _, text, _ in comments(fake)]
    assert texts == ['[2026-09-29 item-1] Phase: raised.', '[2026-09-29 item-1] Pull request: acme/app#1.',
                     '[2026-09-29 item-1] Merged in acme/app#1.']


def test_log_carry_is_a_close_entry(ws):
    from wuwei import plan
    root, fake = ws
    approved(root)
    seed_ticket(root)
    plan.dispose('item-1', 'carried', root=root)
    assert main(['tracker', 'log']) == 0
    assert comments(fake) == [('ENG-1', '[2026-09-29 item-1] Carried to 2026-09-30 (D-1).', 'close')]


def test_log_filters(ws, monkeypatch):
    root, fake = ws
    approved(root)
    settings(root, 'log = ["verdicts"]')
    story(root)
    assert main(['tracker', 'log']) == 0  # no ticket: nowhere to log
    assert fake.calls == []
    seed_ticket(root)
    assert main(['tracker', 'log']) == 0
    assert [entry['kind'] for entry in state.read_state(root)['tracker_log'].values()] == ['verdicts']
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setattr(registry, 'load', lambda kind, config: pytest.fail('no port call'))
    assert main(['tracker', 'log']) == 0


def phases(root, count):
    for _ in range(count):
        state.transition('item-1', 'parked', root)
        state.transition('item-1', 'implement', root)


def test_log_caps_and_folds_per_ticket(ws):
    root, fake = ws
    approved(root)
    seed_ticket(root)
    settings(root, 'max_per_item_per_day = 3')
    phases(root, 2)
    state.transition('item-1', 'parked', root)  # five phase changes
    assert main(['tracker', 'log']) == 0
    texts = [text for _, text, _ in comments(fake)]
    assert texts == ['[2026-09-29 item-1] Phase: parked.', '[2026-09-29 item-1] Phase: implement.',
                     '[2026-09-29 item-1] Folded 3 updates: progress 3.']
    folded, = [row['payload'] for row in day_events(root, 'tracker.folded')]
    assert (folded['item'], folded['ticket'], folded['counts']) == ('item-1', 'ENG-1', {'progress': 3})
    state.transition('item-1', 'implement', root)
    assert main(['tracker', 'log']) == 0
    assert len(fake.calls) == 3 and len(day_events(root, 'tracker.folded')) == 1
    log = state.read_state(root)['tracker_log']
    assert sum(entry['outcome'] == 'folded' for entry in log.values()) == 4


def test_log_refusal_unrun_and_fold_category(ws):
    root, fake = ws
    approved(root)
    seed_ticket(root)
    state.transition('item-1', 'gate', root)
    fake.results['comment'] = registry.Result(1, reason='outward: lint refused')
    assert main(['tracker', 'log']) == 1
    entry, = state.read_state(root)['tracker_log'].values()
    assert entry['outcome'] == 'refused' and 'lint refused' in entry['reason']
    assert main(['tracker', 'log']) == 0 and len(fake.calls) == 1
    state.transition('item-1', 'parked', root)
    fake.results['comment'] = registry.Result(2, reason='LINEAR_API_KEY is missing')
    assert main(['tracker', 'log']) == 2
    assert len(state.read_state(root)['tracker_log']) == 1
    fake.results['comment'] = registry.Result(0, {'id': 'c-2'})
    assert main(['tracker', 'log']) == 0
    assert comments(fake)[-1][1] == '[2026-09-29 item-1] Phase: parked.'


def test_fold_holding_a_decision_drafts(ws):
    root, fake = ws
    approved(root)
    seed_ticket(root)
    settings(root, 'max_per_item_per_day = 1')
    story(root)
    assert main(['tracker', 'log']) == 0
    row, = state.read_state(root)['drafts'].values()
    assert row['inputs']['category'] == 'decisions'
    assert row['text'].endswith('Folded 3 updates: decisions 1, progress 1, verdicts 1.')


def test_log_never_sends_an_absolute_path(ws):
    root, fake = ws
    approved(root)
    seed_ticket(root)
    settings(root, 'auto = ["decisions"]')
    decisions = workspace.day_dir(root) / 'decisions'
    decisions.mkdir()
    (decisions / 'D-1.md').write_text('Question: Keep /srv/x/notes.txt for item-1?\n')
    state.append_event('decision.decided', {'id': 'D-1', 'option': 'yes'}, root)
    assert main(['tracker', 'log']) == 1
    assert fake.calls == []
    entry, = state.read_state(root)['tracker_log'].values()
    assert entry['outcome'] == 'refused' and 'absolute path' in entry['reason']


def repos(*names):
    return ''.join(f'[[repos]]\nname = "{name}"\npath = "{name.split("/")[1]}"\n'
                   f'default_branch = "main"\n' for name in names)


def loaded(tmp_path, adapter='github', project=None, names=('acme/app',)):
    text = (f'[owner]\nname = "Pat Example"\npronouns = "they/them"\n'
            f'[adapters]\ntracker = "{adapter}"\n'
            + (f'[tracker]\nproject = "{project}"\n' if project else '') + repos(*names))
    return workspace.load_config(tmp_path, raw=text)


@pytest.mark.parametrize('settings,ticket,expected', [
    ({}, '24', 'acme/app#24'),
    ({'project': 'acme/tracker', 'names': ('acme/app', 'acme/lib')}, '24', 'acme/tracker#24'),
    ({'names': ('acme/app', 'acme/lib')}, '24', 'acme/app#24'),
    ({}, 'acme/other#24', 'acme/other#24'),
    ({}, '0', '0'),
    ({}, '024', '024'),
    ({}, 'ENG-24', 'ENG-24'),
    ({'adapter': 'linear'}, '24', '24'),
    ({'adapter': 'none'}, '24', '24'),
])
def test_full_id(tmp_path, settings, ticket, expected):
    """#741: a bare GitHub number gains the tracker repository; every other id is kept."""
    assert tracker.full_id(loaded(tmp_path, **settings), ticket) == expected


@pytest.mark.parametrize('settings', [{'names': ()}, {'project': 'TEAM'}])
def test_full_id_refuses_without_a_repository(tmp_path, settings):
    with pytest.raises(ValueError) as refused:
        tracker.full_id(loaded(tmp_path, **settings), '24')
    assert 'owner/repo#24' in str(refused.value) and 'tracker.project' in str(refused.value)


def stored(directory, tickets):
    directory.parent.mkdir(parents=True, exist_ok=True)
    state._write_state(lambda data: data.setdefault('tickets', {}).update(tickets),
                       reserved=False, directory=directory)


def test_upgrade_normalises_the_latest_days_bare_tickets(tmp_path, monkeypatch):
    """#741: init --upgrade turns a stored 24 into acme/app#24 once and records it."""
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    days = tmp_path / '.wuwei/days'
    assert tracker.upgrade(tmp_path, loaded(tmp_path)) == []
    today = days / '2026-09-29'
    stored(today, {'X': {'id': '24', 'source': 'candidate'}, 'Y': {'id': 'acme/app#2', 'source': 'set'},
                   'Z': {'id': None, 'source': 'none'}})
    before = (today / 'state.json').read_bytes()
    line = '2026-09-29/state.json: ticket X 24 to acme/app#24'
    assert tracker.upgrade(tmp_path, loaded(tmp_path), write=False) == [line]
    assert (today / 'state.json').read_bytes() == before
    unnamed, = tracker.upgrade(tmp_path, loaded(tmp_path, names=()))
    assert 'ticket X 24 unchanged' in unnamed and 'owner/repo#24' in unnamed
    assert tracker.upgrade(tmp_path, loaded(tmp_path, adapter='linear')) == []
    assert (today / 'state.json').read_bytes() == before
    assert tracker.upgrade(tmp_path, loaded(tmp_path)) == [line]
    tickets = state.read_state(directory=today)['tickets']
    assert [tickets[key]['id'] for key in 'XYZ'] == ['acme/app#24', 'acme/app#2', None]
    rows = [json.loads(text) for text in (today / 'events.jsonl').read_text().splitlines()]
    assert [row['payload'] for row in rows if row['kind'] == 'plan.set'] == [
        {'item': 'X', 'ticket': 'acme/app#24', 'was': '24', 'prs_seen': False}]
    assert tracker.upgrade(tmp_path, loaded(tmp_path)) == []


def test_upgrade_reads_the_last_day_with_a_state(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    days = tmp_path / '.wuwei/days'
    stored(days / '2026-09-28', {'X': {'id': '24', 'source': 'candidate'}})
    (days / '2026-09-29').mkdir()
    assert tracker.upgrade(tmp_path, loaded(tmp_path)) == [
        '2026-09-28/state.json: ticket X 24 to acme/app#24']
    (days / '2026-09-29/state.json').write_text('{')
    unread, = tracker.upgrade(tmp_path, loaded(tmp_path))
    assert unread.startswith('2026-09-29/state.json: tickets unread: ')
