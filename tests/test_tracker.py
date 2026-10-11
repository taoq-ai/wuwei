"""Tracker hygiene (5.11): creation, the duties and the comment writer, offline."""

import json

import pytest

from fakes.tracker import Fake, ported
from wuwei import registry, state, tracker, workspace
from wuwei.__main__ import main


def test_open_duties():
    """#842: a due duty is open until a later done or skipped for the same pair, in due order."""
    def row(kind, item, duty):
        payload = {'item': item, 'duty': duty, 'ticket': 'ENG-1'}
        if kind == 'duty.due':
            payload['command'] = f'wuwei tracker move {item} {duty[8:]}'
        return {'kind': kind, 'payload': payload}
    rows = [row('duty.due', 'B', 'tracker.done'), row('duty.due', 'A', 'tracker.claim'),
            row('duty.done', 'A', 'tracker.claim'), row('duty.due', 'A', 'tracker.in_review'),
            row('duty.due', 'C', 'tracker.claim'), row('duty.skipped', 'C', 'tracker.claim'),
            row('duty.due', 'A', 'tracker.in_review'), {'kind': 'tracker.call', 'payload': {}}]
    assert tracker.open_duties(rows) == [
        ('B', 'tracker.done', 'wuwei tracker move B done'),
        ('A', 'tracker.in_review', 'wuwei tracker move A in_review')]
    assert tracker.skipped_duties(rows) == [{'item': 'C', 'duty': 'tracker.claim', 'ticket': 'ENG-1'}]
    rows.append(row('duty.done', 'B', 'tracker.done'))
    assert [entry[0] for entry in tracker.open_duties(rows)] == ['A']


def test_ticket():
    assert tracker.ticket({}, 'item-1') is None
    assert tracker.ticket({'tickets': {'item-1': {'id': 'ENG-1', 'source': 'set'}}},
                          'item-1') == 'ENG-1'


CREATED = registry.Result(0, {'id': 'ENG-9', 'url': 'https://example.test/ENG-9'})


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(tmp_path)
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
        {item: {'id': ticket, 'source': 'set'}}), root)


def day_events(root, kind=None):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [row for row in rows if kind is None or row['kind'] == kind]


BUG = ['tracker', 'create', '--bug', 'item-1', 'Export fails on empty rows',
       '--evidence', 'cli/x.py:12']


@pytest.mark.parametrize('flag,seat,category', [('--bug', 'builder', 'bugs'),
                                                ('--triage', 'sentinel-quality', 'triage')])
def test_bug_from_a_seat_creates_under_send(ws, capsys, flag, seat, category):
    """#644: the finder files in the owner's own tracker."""
    root, fake = ws
    seed_ticket(root)
    command = ['tracker', 'create', flag, *BUG[3:], '--seat', seat]
    assert main(command) == 0
    assert 'ENG-9' in capsys.readouterr().out
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


def test_bug_in_auto_creates_once(ws, capsys):
    root, fake = ws
    seed_ticket(root)
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
    assert main(['tracker', 'create', 'item-1']) == 0
    (_, (draft,), _), = fake.calls
    assert draft == {'title': 'Add the export button', 'item': 'item-1', 'category': 'items',
                     'description': 'Evidence: issue 12\nGoal: G-1\nTrack: SLICE'}
    assert state.read_state(root)['tickets'] == {'item-1': {'id': 'ENG-9', 'source': 'create'}}
    assert main(['tracker', 'create', 'item-1']) == 0
    assert len(fake.calls) == 1


def test_item_ticket_from_a_seat_finding(ws):
    """#646: a finding item's ticket opens from the finding and the day item's goal."""
    root, fake = ws
    state._write_state(lambda data: data.update(
        items={'fix-pin-ruff-in-ci': {'phase': 'merged', 'goal': 'G-1', 'track': 'SLICE'}},
        seat_findings={'fix-pin-ruff-in-ci': {'scope': 'Pin ruff in CI', 'evidence': 'seat finding',
                                              'track': 'SLICE', 'at': '2026-09-29T12:00:00Z'}}),
        root)
    assert main(['tracker', 'create', 'fix-pin-ruff-in-ci']) == 0
    (_, (draft,), _), = fake.calls
    assert draft['title'] == 'Pin ruff in CI'
    assert draft['description'] == 'Evidence: seat finding\nGoal: G-1\nTrack: SLICE'

def test_create_without_adapter_cannot_run(ws, monkeypatch, capsys):
    root, _ = ws
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setattr(registry, 'load', lambda kind, config: pytest.fail('no port call'))
    assert main(['tracker', 'create', 'item-1']) == 2
    assert 'tracker adapter is none' in capsys.readouterr().err


def approved(root, item='item-1', phase='implement'):
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=[item],
        items={item: {'phase': phase, 'status': 'queued'}}), root)


def comments(fake):
    return [call[1] for call in fake.calls if call[0] == 'comment']


def story(root):
    """A phase change and a gate verdict, as their producers write them."""
    state.transition('item-1', 'gate', root)
    state._write_state(lambda data: data['gate_verdicts'].update({'item-1:quality:initial': {
        'verdict': 'FIX', 'findings': ['- P1 | cli/x.py:1 | empty | blocks: yes',
                                       '- P3 | cli/x.py:2 | naming | blocks: no']}}),
        root, kind='gate.received',
        payload={'item': 'item-1', 'role': 'quality', 'round': 'initial', 'verdict': 'FIX'})


def test_log_writes_the_story_once(ws):
    root, fake = ws
    approved(root)
    seed_ticket(root)
    story(root)
    assert main(['tracker', 'log']) == 0
    # #838: every kind the tracker logs goes out through the port; nothing is held.
    assert sorted(comments(fake)) == [
        ('ENG-1', '[2026-09-29 item-1] Phase: gate.', 'progress'),
        ('ENG-1', '[2026-09-29 item-1] Review quality (initial): FIX, 1 blocking findings.', 'verdicts')]
    log = state.read_state(root)['tracker_log']
    assert [entry['outcome'] for entry in log.values()] == ['written'] * 2
    before = (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert main(['tracker', 'log']) == 0
    assert len(fake.calls) == 2
    assert (workspace.day_dir(root) / 'events.jsonl').read_text() == before


def test_log_leaves_the_pr_link_and_merge_to_the_duties(ws):
    root, fake = ws
    approved(root, phase='gate')
    seed_ticket(root)
    state.record_pr(root, 'item-1', 'acme/app#1', raised=True)
    state.transition('item-1', 'merged', root)
    assert main(['tracker', 'log']) == 0
    texts = [text for _, text, _ in comments(fake)]
    assert texts == ['[2026-09-29 item-1] Phase: raised.']


def test_log_carry_is_a_close_entry(ws):
    from wuwei import plan
    root, fake = ws
    approved(root)
    seed_ticket(root)
    plan.dispose('item-1', 'carried', root=root)
    assert main(['tracker', 'log']) == 0
    assert comments(fake) == [('ENG-1', '[2026-09-29 item-1] Carried to 2026-09-30.', 'close')]


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


def github(root, orgs=('acme',), adapter='github'):
    """The loaded config with a GitHub tracker on acme/app, by dict override."""
    base = workspace.load_config(root)
    return {**base, 'adapters': {**base['adapters'], 'tracker': adapter},
            'tracker': {**base['tracker'], 'project': 'acme/app'},
            'outbound': {**base['outbound'], 'code_host_orgs': list(orgs)}}


@pytest.mark.parametrize('orgs', [('acme',), ()])
def test_creates_labels_by_owner(ws, orgs):
    """#670: WUWEI creates a label on its own only on the owner's tracker."""
    root, _ = ws
    assert tracker.creates_labels(github(root, orgs)) is bool(orgs)
    assert tracker.creates_labels(github(root, orgs, 'linear')) is True


NONE_MISSING = {'created': [], 'missing': []}


def test_labels_none_and_malformed(ws, monkeypatch):
    root, fake = ws
    monkeypatch.setattr(registry, 'load', lambda *a: pytest.fail('loaded an adapter'))
    assert tracker.labels(root, github(root, adapter='none'), True) == registry.Result(0, NONE_MISSING)
    for data in ({'created': []}, None, {'created': 'x', 'missing': []}):
        result = tracker.labels(root, github(root), True, Fake({'labels': registry.Result(0, data)}))
        assert result.exit == 2 and result.reason.startswith('tracker labels: an adapter')

    def broken(create, root=None):
        raise ValueError('bad')
    result = tracker.labels(root, github(root), False, type('Port', (), {'labels': staticmethod(broken)}))
    assert result.exit == 2 and 'tracker labels unmeasured' in result.reason
    fine = Fake({'labels': registry.Result(0, {'created': [], 'missing': ['In Review']})})
    assert tracker.labels(root, github(root), False, fine).data['missing'] == ['In Review']
    assert fine.calls == [('labels', (False,), root)]


def test_ensure_labels_lines(ws):
    root, fake = ws
    fake.results['labels'] = registry.Result(0, {'created': ['In Review'], 'missing': []})
    assert tracker.ensure_labels(root, 'Upgraded', True) == ['Upgraded tracker label "In Review"']
    assert fake.calls[-1] == ('labels', (True,), root)
    fake.results['labels'] = registry.Result(0, NONE_MISSING)
    assert tracker.ensure_labels(root, 'Created', True) == []
    fake.results['labels'] = registry.Result(2, reason='github.labels: could not run: no token')
    assert tracker.ensure_labels(root, 'Created', True) == [
        'tracker labels not created: github.labels: could not run: no token; run bin/wuwei doctor']


def test_tracker_move_runs_the_shared_move(ws, monkeypatch, capsys):
    """#670: tracker move re-runs a lifecycle move through dispatch.tracker_call."""
    from wuwei import dispatch
    root, _ = ws
    calls, answer = [], [registry.Result(0)]
    monkeypatch.setattr(dispatch, 'tracker_call',
                        lambda *args: calls.append(args) or answer[0])
    assert main(['tracker', 'move', 'A', 'in_review']) == 0
    assert calls == [('A', 'in_review', root)] and capsys.readouterr().out == 'A: ticket in_review\n'
    assert main(['tracker', 'move', 'A', 'done']) == 0
    assert calls[-1] == ('A', 'done', root) and capsys.readouterr().out == 'A: ticket done\n'
    assert main(['tracker', 'move', 'A', 'claim']) == 0
    assert calls[-1] == ('A', 'claim', root) and capsys.readouterr().out == 'A: ticket claim\n'
    answer[0] = registry.Result(1, reason='A not moved to In Review: missing')
    assert main(['tracker', 'move', 'A', 'in_review']) == 1
    assert capsys.readouterr().err == 'wuwei tracker: A not moved to In Review: missing\n'
    with pytest.raises(SystemExit) as raised:
        main(['tracker', 'move', 'A', 'merged'])
    assert raised.value.code == 2


def test_log_never_sends_an_absolute_path(ws):
    root, fake = ws
    approved(root)
    seed_ticket(root)
    from wuwei import plan
    settings(root, 'log = ["close"]')
    plan.dispose('item-1', 'parked', 'waits on /srv/x/notes.txt', root=root)
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
    state._write_state(lambda data: data.setdefault('tickets', {}).update(tickets), directory=directory)


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
