"""#492: bin/wuwei outbound learn proposes an unknown connector on one card; the answer writes it."""

import json
from types import SimpleNamespace

import pytest

from wuwei import state, watch, workspace


UUID = '00000000-0000-4000-8000-000000000001'
TOOL = f'mcp__{UUID}__send_message'
CONFIG = '''[owner]
name = "Pat Example"
pronouns = "they/them"

[outbound]
default_tier = "ask"
work_channels = ["C1"]
external_channels = ["C09"]
company_domains = ["example.com"]
code_host_orgs = ["acme"]

[shepherd.authors]
"ada@example.com" = {login = "ada", mention = "U01"}
'''
CHANNELS = [{'id': 'C01', 'name': 'team-review', 'members': 4, 'shared': False},
            {'id': 'C02', 'name': 'partners', 'members': 9, 'shared': True},
            {'id': 'D01', 'name': 'direct', 'members': 2, 'shared': False},
            {'id': 'C09', 'name': 'vendor', 'members': 3, 'shared': False},
            {'id': 'C1', 'name': 'work', 'members': 5, 'shared': False}]
PEOPLE = [{'id': 'U01', 'name': 'Ada', 'email': 'ada@example.com'},
          {'id': 'U02', 'name': 'Bo', 'email': 'bo@other.org'}]


@pytest.fixture
def root(tmp_path, monkeypatch):
    from fakes.integrity import seed
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(CONFIG)
    seed(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-04T09:00:00Z')
    day = workspace.day_dir(tmp_path)
    day.mkdir(parents=True)
    (day / 'channels.json').write_text(json.dumps(CHANNELS))
    (day / 'people.json').write_text(json.dumps(PEOPLE))
    state._write_state(lambda data: data.update(pr_reviewers={'acme/app#7': ['ada', 'bo']},
                                                author_logins={'bo@other.org': 'bo'}),
                       tmp_path, reserved=False)
    return tmp_path


def configure(root, text):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('[outbound]\ndefault_tier = "ask"\n', f'[outbound]\ndefault_tier = "ask"\n{text}\n'))


def posture(root, name):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'\n[security]\nposture = "{name}"\n')


def learn(root, *extra, tool=TOOL, listings=True):
    from wuwei.__main__ import main
    day = workspace.day_dir(root)
    files = ['--channels', str(day / 'channels.json'), '--people', str(day / 'people.json')]
    return main(['outbound', 'learn', '--tool', tool, *(files if listings else []), *extra])


def events(root, kind):
    return [row['payload'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == kind]


def decisions(root):
    return sorted(path.name for path in (workspace.day_dir(root) / 'decisions').glob('D-*.md'))


def test_reserved(root, capsys):
    from wuwei.__main__ import main
    for kind in ('outbound.learned', 'outbound.proposed'):
        assert main(['event', kind, '{}']) == 1
        assert 'wuwei outbound learn' in capsys.readouterr().err
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state('outbound_learn', {}, root)


@pytest.mark.parametrize('case,code,text', [
    ('off', 1, 'outbound.learn is off'),
    ('bad tool', 1, 'mcp__<server>__<tool>'),
    ('no channel', 1, '--as'),
    ('no listings', 1, f'bin/wuwei outbound learn --tool {TOOL} --channels <file> --people <file>'),
    ('mail listings', 1, 'listings apply to a slack connector'),
    ('missing file', 2, 'cannot read a listing'),
    ('bad id', 1, 'channels.json'), ('pipe', 1, 'channels.json'), ('newline', 1, 'channels.json'),
    ('extra key', 1, 'people.json'), ('duplicate', 1, 'people.json'),
])
def test_learn_guards(root, capsys, case, code, text):
    day = workspace.day_dir(root)
    before = (root / '.wuwei/config.toml').read_text()
    rows = {'bad id': [{**CHANNELS[0], 'id': 'c01'}], 'pipe': [{**CHANNELS[0], 'name': 'a|b'}],
            'newline': [{**CHANNELS[0], 'name': 'a\nb'}]}
    if case in rows:
        (day / 'channels.json').write_text(json.dumps(rows[case]))
    if case == 'extra key':
        (day / 'people.json').write_text(json.dumps([{**PEOPLE[0], 'role': 'x'}]))
    if case == 'duplicate':
        (day / 'people.json').write_text(json.dumps([PEOPLE[0], PEOPLE[0]]))
    if case == 'missing file':
        (day / 'people.json').unlink()
    if case == 'off':
        configure(root, 'learn = "off"')
        before = (root / '.wuwei/config.toml').read_text()
    extra = [] if case in ('no channel', 'off') else ['--as', 'mail' if case == 'mail listings' else 'slack']
    assert learn(root, *extra, tool='mcp__bad' if case == 'bad tool' else TOOL,
                 listings=case not in ('no listings', 'no channel')) == code
    assert text in capsys.readouterr().err
    assert (root / '.wuwei/config.toml').read_text() == before
    assert not (day / 'decisions').exists() and 'outbound_learn' not in state.read_state(root)


def test_proposal_filters(root, capsys):
    from wuwei.commands.outbound import propose
    day = workspace.day_dir(root)
    (day / 'plan.md').write_text('Pairing with U04 today.\n')
    people = [*PEOPLE, {'id': 'U03', 'name': 'Cy', 'email': 'cy@example.com'},
              {'id': 'U04', 'name': 'Di', 'email': 'di@example.com'},
              {'id': 'U05', 'name': 'Ed', 'email': 'ed@other.org'}]
    (day / 'decisions').mkdir()
    (day / 'decisions/D-1.md').write_text('Context: ask U05\n')
    config, data = workspace.load_config(root), state.read_state(root)
    found = propose(root, config, data, UUID, 'slack', TOOL, CHANNELS, people, card=True)
    assert found['alias'] is True
    assert [(row['id'], row['class']) for row in found['channels']] == [('C01', 'team'), ('C02', 'client')]
    assert [(row['id'], row['entry'], row['why']) for row in found['people']] == [
        ('U01', {'email': 'ada@example.com', 'class': 'team'}, 'reviewer'),
        ('U02', {'org': 'acme', 'class': 'team'}, 'reviewer'),
        ('U04', {'email': 'di@example.com', 'class': 'team'}, "named in today's records")]
    assert 'not proposed: 1 people' in capsys.readouterr().out  # U05: named, not internal
    found = propose(root, config, data, UUID, 'slack', TOOL, CHANNELS, people, card=False)
    assert [row['id'] for row in found['people']] == ['U01', 'U02']
    (root / '.wuwei/config.toml').write_text(
        CONFIG.replace('["C1"]', '["C1", "C01"]').replace('["C09"]', '["C09", "C02"]')
        + '\n[outbound.people]\n"slack:U01" = {email = "ada@example.com"}\n"slack:U02" = {org = "acme"}\n'
        + f'\n[outward.servers]\n"{UUID}" = "slack"\n')
    assert propose(root, workspace.load_config(root), data, UUID, 'slack', TOOL, CHANNELS,
                   PEOPLE, card=False) is None


def card(root, capsys):
    assert learn(root, '--as', 'slack') == 0
    return json.loads(capsys.readouterr().out)


def test_card(root, capsys):
    from wuwei.__main__ import main
    widget = card(root, capsys)
    assert decisions(root) == ['D-1.md']
    assert main(['decision', 'lint', str(workspace.day_dir(root) / 'decisions/D-1.md')]) == 0
    data = state.read_state(root)
    assert 'D-1' in data['decision_routes'] and data['outbound_learn']['D-1']['answered'] is None
    [question] = widget
    assert question['question'].startswith(
        f'D-1: Connector {UUID} is Slack, mode draft; add 1 work channel, 1 client channel and 2 people? ')
    assert [row['label'] for row in question['options']] == [
        'Approve (Recommended)', 'Approve channels only', 'Defer: keep as drafts',
        'Approve, mode send']
    assert question['record'] == 'wuwei decide D-1 "<label>"'
    capsys.readouterr()
    assert card(root, capsys) == widget and decisions(root) == ['D-1.md']


def answer(root, monkeypatch, option):
    from wuwei.commands import decision
    monkeypatch.setattr(decision, 'owner_confirm', lambda *args: 'at the host terminal')
    return decision.owner_outcome(SimpleNamespace(id='D-1', option=option), root=root)


def send(root, guard):
    call = {'cwd': str(root), 'tool_name': TOOL, 'hook_event_name': 'PreToolUse',
            'session_id': 'test', 'tool_use_id': 'call',
            'tool_input': {'text': 'thanks <@U01> <@U02>', 'channel': 'C01'}}
    return guard(call)


@pytest.mark.parametrize('option', ['approve', 'channels', 'keep'])
def test_answers(root, capsys, monkeypatch, option):
    from wuwei.guards.outward import check_lint, check_tier
    card(root, capsys)
    before = (root / '.wuwei/config.toml').read_text()
    assert answer(root, monkeypatch, option) == (0, option)
    config = workspace.load_config(root)
    assert state.read_state(root)['outbound_learn']['D-1']['answered'] == option
    learned = events(root, 'outbound.learned')
    if option == 'keep':
        assert (root / '.wuwei/config.toml').read_text() == before and learned == []
        assert 'a draft for the owner to send' in send(root, check_tier)[1]
        assert learn(root, '--as', 'slack') == 1
        assert 'kept as drafts today (D-1)' in capsys.readouterr().err
        return
    assert config['outward']['servers'] == {UUID: 'slack'}
    assert config['outbound']['work_channels'] == ['C1', 'C01']
    assert config['outbound']['external_channels'] == ['C09', 'C02']
    assert learned == [{'decision': 'D-1', 'option': option, 'mode': 'card', 'server': UUID,
                        'channel': 'slack', 'alias': True, 'connector_mode': None, 'channels': ['C01', 'C02'],
                        'people': ['U01', 'U02'] if option == 'approve' else [], 'owner': False}]
    if option == 'approve':
        assert set(config['outbound']['people']) == {'slack:U01', 'slack:U02'}
        assert send(root, check_tier) == send(root, check_lint) == (0, '')
    else:
        assert config['outbound']['people'] == {} and send(root, check_tier)[0] == 1
    text = (root / '.wuwei/config.toml').read_text()
    assert answer(root, monkeypatch, option)[0] == 1
    assert (root / '.wuwei/config.toml').read_text() == text


def test_other_card(root, capsys, monkeypatch):
    # #492 scope addition: an other connector shows its class and mode; the card changes the mode.
    from wuwei.__main__ import main
    tool = f'mcp__{UUID}__create_project'
    assert learn(root, '--as', 'other', tool=tool, listings=False) == 0
    [question] = json.loads(capsys.readouterr().out)
    assert question['question'].startswith(f'D-1: Connector {UUID} is other, mode send? ')
    assert 'Approve, mode refuse' in [row['label'] for row in question['options']]
    assert main(['decision', 'lint', str(workspace.day_dir(root) / 'decisions/D-1.md')]) == 0
    assert answer(root, monkeypatch, 'refuse') == (0, 'refuse')
    config = workspace.load_config(root)
    assert config['outward']['servers'] == {UUID: 'other'}
    assert config['outward']['modes'] == {UUID: 'refuse'}
    assert events(root, 'outbound.learned')[0]['connector_mode'] == 'refuse'


def test_template_tables_are_sections():
    # An inline people or servers table cannot take learned entries; the template shows sections.
    from pathlib import Path
    text = (Path(__file__).parents[1] / 'templates/workspace/config.toml').read_text()
    for name in ('outward.servers', 'outward.modes', 'outbound.people'):
        assert f'# [{name}]\n' in text
    assert '# people = {' not in text and '# servers = {' not in text


@pytest.mark.parametrize('name', ['observe', 'guarded', 'strict'])
def test_auto(root, capsys, name):
    configure(root, 'learn = "auto"')
    posture(root, name)
    (workspace.day_dir(root) / 'plan.md').write_text('Pairing with U03 today.\n')
    (workspace.day_dir(root) / 'people.json').write_text(json.dumps(
        [*PEOPLE, {'id': 'U03', 'name': 'Cy', 'email': 'cy@example.com'}]))
    assert learn(root, '--as', 'slack') == 0
    out = capsys.readouterr().out
    if name == 'strict':
        assert decisions(root) == ['D-1.md'] and '"record"' in out
        assert events(root, 'outbound.learned') == []
        return
    assert '"record"' not in out and not (workspace.day_dir(root) / 'decisions').exists()
    config = workspace.load_config(root)
    assert set(config['outbound']['people']) == {'slack:U01', 'slack:U02'}
    assert [row['mode'] for row in events(root, 'outbound.learned')] == ['auto']


def test_auto_never_learns_other_without_the_card(root, capsys):
    # Verify #492: `other` is mode send with no audience rules, so auto still asks.
    configure(root, 'learn = "auto"')
    posture(root, 'guarded')
    assert learn(root, '--as', 'other', tool=f'mcp__{UUID}__create_project', listings=False) == 0
    assert '"record"' in capsys.readouterr().out and decisions(root) == ['D-1.md']
    assert events(root, 'outbound.learned') == []
    assert 'servers' not in workspace.load_config(root)['outward'] or \
        UUID not in workspace.load_config(root)['outward']['servers']


def test_as_cannot_override_a_resolving_channel(root, capsys):
    # Verify #492: a mail connector that drafted cannot be relabelled other to pass.
    configure(root, 'learn = "auto"')
    posture(root, 'guarded')
    assert learn(root, '--as', 'other', tool=f'mcp__{UUID}__send_email', listings=False) == 1
    assert 'already resolves to mail' in capsys.readouterr().err
    assert events(root, 'outbound.learned') == []


# #495: the owner's own Slack identity is learned on the same card.
SLACK = f'mcp__{UUID}__slack_send_message'


def owner_file(root, identity):
    path = workspace.day_dir(root) / 'owner.json'
    path.write_text(json.dumps(identity))
    return str(path)


def dm(root, guard, channel='D09', text='Your build is green'):
    return guard({'cwd': str(root), 'tool_name': SLACK, 'hook_event_name': 'PreToolUse',
                  'session_id': 'test', 'tool_use_id': 'call',
                  'tool_input': {'text': text, 'channel': channel}})


def draft_card(root, capsys, reason):
    import re
    from wuwei.__main__ import main
    capsys.readouterr()
    assert main(['drafts', 'show', re.search(r'draft-[0-9a-f]{32}', reason)[0], '--widget']) == 0
    return json.loads(capsys.readouterr().out)[0]['options'][0]['description']


def test_dm_without_identity_names_the_rule_and_the_card(root, capsys, monkeypatch):
    from wuwei.guards.outward import check_tier
    monkeypatch.chdir(root)
    code, reason = dm(root, check_tier)
    assert code == 1 and 'unknown DM recipient D09' in reason
    assert 'bin/wuwei drafts show draft-' in reason
    assert f'bin/wuwei outbound learn --tool {SLACK} --owner <file>' in draft_card(root, capsys, reason)
    configure(root, 'owner = {slack = {user = "U09", dm = "D09"}}')
    code, reason = dm(root, check_tier, 'U02', 'Thanks')
    assert code == 1 and 'unknown DM recipient U02' in reason
    assert 'outbound learn' not in reason + draft_card(root, capsys, reason)


def test_listing_step_names_the_identity_tool(root, capsys):
    assert learn(root, tool=SLACK, listings=False) == 1
    err = capsys.readouterr().err
    assert 'auth_test' in err and 'whoami' in err and '--owner <file>' in err
    configure(root, 'owner = {slack = {user = "U09", dm = "D09"}}')
    assert learn(root, tool=SLACK, listings=False) == 1
    assert '--owner' not in capsys.readouterr().err


@pytest.mark.parametrize('identity', [{'user': 'x', 'dm': ''}, {'user': 'U09'},
                                      {'user': 'U09', 'dm': 'C1'}, {'user': 'U09', 'dm': 'D08'},
                                      {'user': 'U09', 'dm': 'D09', 'name': 'Pat'}, ['U09']])
def test_owner_file_shape(root, capsys, monkeypatch, identity):
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D08')
    before = (root / '.wuwei/config.toml').read_text()
    assert learn(root, '--owner', owner_file(root, identity), tool=SLACK, listings=False) == 1
    assert '"user", "dm"' in capsys.readouterr().err
    assert (root / '.wuwei/config.toml').read_text() == before
    assert not (workspace.day_dir(root) / 'decisions').exists()


def test_owner_file_unreadable(root, capsys):
    missing = str(workspace.day_dir(root) / 'missing.json')
    assert learn(root, '--owner', missing, tool=SLACK, listings=False) == 2
    assert 'cannot read' in capsys.readouterr().err


@pytest.mark.parametrize('mode,name', [('card', 'guarded'), ('auto', 'observe')])
def test_owner_card_and_answers(root, capsys, monkeypatch, mode, name):
    from wuwei.guards.outward import check_lint, check_tier
    configure(root, f'learn = "{mode}"')
    posture(root, name)
    path = owner_file(root, {'user': 'U09', 'dm': 'D09'})
    assert learn(root, '--owner', path, tool=SLACK, listings=False) == 0
    [question] = json.loads(capsys.readouterr().out)
    assert 'your identity U09, DM D09' in question['question']
    text = (workspace.day_dir(root) / 'decisions/D-1.md').read_text()
    assert "- owner U09, DM D09 from the connector's identity call" in text
    assert decisions(root) == ['D-1.md']
    assert answer(root, monkeypatch, 'approve') == (0, 'approve')
    config = workspace.load_config(root)
    assert config['outbound']['owner']['slack'] == {'user': 'U09', 'dm': 'D09'}
    assert events(root, 'outbound.learned')[0]['owner'] is True
    assert dm(root, check_tier) == dm(root, check_lint) == (0, '')
    assert len(events(root, 'outward.to_owner')) == 1


def test_owner_keep_writes_nothing(root, capsys, monkeypatch):
    from wuwei.guards.outward import check_tier
    assert learn(root, '--owner', owner_file(root, {'user': 'U09', 'dm': 'D09'}),
                 tool=SLACK, listings=False) == 0
    before = (root / '.wuwei/config.toml').read_text()
    assert answer(root, monkeypatch, 'keep') == (0, 'keep')
    assert (root / '.wuwei/config.toml').read_text() == before
    assert dm(root, check_tier)[0] == 1


def test_owner_proposes_only_empty_fields(root, capsys):
    from wuwei.commands.outbound import propose
    configure(root, 'owner = {slack = {user = "U09"}}')
    config, data = workspace.load_config(root), state.read_state(root)
    found = propose(root, config, data, UUID, 'slack', SLACK, [], [], card=True,
                    owner={'user': 'U09', 'dm': 'D09'})
    assert found['owner'] == {'dm': 'D09'}
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('user = "U09"', 'user = "U09", dm = "D09"')
                    + f'\n[outward.servers]\n"{UUID}" = "slack"\n')
    assert learn(root, '--owner', owner_file(root, {'user': 'U09', 'dm': 'D09'}),
                 tool=SLACK, listings=False) == 1
    assert 'nothing new to learn' in capsys.readouterr().err


def test_learn_classes(root, capsys, monkeypatch):
    # #496: a shared channel is proposed as client, the rest team; people are team.
    from wuwei.guards.outward import check_tier
    card(root, capsys)
    text = (workspace.day_dir(root) / 'decisions/D-1.md').read_text()
    assert '- channel #partners (C02, 9 members): client, shared with an external org\n' in text
    assert '- channel #team-review (C01, 4 members): team\n' in text
    assert '- person Ada (U01, reviewer): team\n' in text
    assert answer(root, monkeypatch, 'approve') == (0, 'approve')
    config = workspace.load_config(root)
    assert {key: row['class'] for key, row in config['outbound']['people'].items()} == {
        'slack:U01': 'team', 'slack:U02': 'team'}
    call = {'cwd': str(root), 'tool_name': TOOL, 'hook_event_name': 'PreToolUse', 'session_id': 'test',
            'tool_use_id': 'call', 'tool_input': {'text': 'I will ship it tomorrow', 'channel': 'C02'}}
    code, reason = check_tier(call)
    # The learned client class holds the commitment on a card (no default row blocks).
    assert code == 1 and reason.startswith('outward: draft draft-')
    assert 'ask by rule 3 (audience=client topic=commitment) for C02' in reason


@pytest.mark.parametrize('option,channels,clients,people', [
    ('C01-client', ['C1'], ['C09', 'C01', 'C02'], {'slack:U01': 'team', 'slack:U02': 'team'}),
    ('C02-team', ['C1', 'C01', 'C02'], ['C09'], {'slack:U01': 'team', 'slack:U02': 'team'}),
    ('U02-company', ['C1', 'C01'], ['C09', 'C02'], {'slack:U01': 'team', 'slack:U02': 'company'})])
def test_learn_card_sets_a_class(root, capsys, monkeypatch, option, channels, clients, people):
    # #496 review F2: the learn card asks the class of each entry; one option per entry changes it.
    from wuwei.__main__ import main
    card(root, capsys)
    path = workspace.day_dir(root) / 'decisions/D-1.md'
    assert main(['decision', 'lint', str(path)]) == 0
    assert '| C01-client | Approve, #team-review (C01) as client |' in path.read_text()
    assert answer(root, monkeypatch, option) == (0, option)
    config = workspace.load_config(root)
    assert config['outbound']['work_channels'] == channels
    assert config['outbound']['external_channels'] == clients
    assert {key: row['class'] for key, row in config['outbound']['people'].items()} == people
