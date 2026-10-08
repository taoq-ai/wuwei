"""#552: the register of people, channels and tools; the config sections are views over it."""

import json

import pytest

from wuwei import graph, outward, workspace


CONFIG = '''[owner]
name = "Pat Example"
pronouns = "they/them"
handles = ["U0OWNER", "pat-dev"]

[[repos]]
name = "fixture-org/app"
path = "."
default_branch = "main"
[repos.shepherd]
reviewers = ["rev-one", "rev-two"]

[[repos]]
name = "fixture-org/lib"
path = "lib"
default_branch = "main"

[voice.sources]
internal = ["C01", "C02"]
client = ["C03"]

[outward.servers]
acme = "slack"
Mailer = "mail"
[outward.modes]
acme = "draft"
[outward.classes]
Mailer = "client"

[outbound]
default_tier = "ask"
work_channels = ["C01", "C03", "c01", "C01"]
external_channels = ["C03"]
company_domains = ["example.test"]
code_host_orgs = ["fixture-org"]
[outbound.people]
"slack:U01" = {email = "ada@example.test", class = "team"}
"slack:U9" = {}
"github:dev" = {org = "fixture-org"}
"email:Client@Outside.test" = {class = "client"}
[outbound.channel_classes]
C03 = "public"
C04 = "company"
[outbound.owner]
mail = "pat@example.test"
code_host = "pat-dev"
[outbound.owner.slack]
user = "U0OWNER"
dm = "D0OWNER"

[shepherd.authors]
"dev@example.test" = {login = "dev", mention = "U02"}
"other@example.test" = {login = "other"}
'''


def load(text=CONFIG):
    return workspace.load_config('.', raw=text)


@pytest.fixture
def config():
    return load()


def test_views_of_build_are_the_sections(config):
    # The register-or-view invariant on the keys: every modeled key reads back unchanged.
    register = graph.build(config)
    assert graph.views(register) == graph.sections(config)
    assert set(graph.sections(config)) == set(graph.VIEWS)
    assert graph.sections(config)['outbound.work_channels'] == ['C01', 'C03', 'c01', 'C01']
    assert graph.sections(config)['repos.shepherd.reviewers'] == {'fixture-org/app': ['rev-one', 'rev-two']}
    nodes = register['nodes']
    for node in ('person:slack:U01', 'person:slack:U9', 'person:github:dev', 'person:email:Client@Outside.test',
                 'channel:C01', 'channel:c01', 'channel:C04', 'connector:acme', 'connector:Mailer',
                 'address:dev@example.test', 'login:dev', 'person:slack:U02', 'person:owner',
                 'login:pat-dev', 'channel:D0OWNER', 'voice:internal', 'repo:fixture-org/app', 'login:rev-one'):
        assert node in nodes, node
    assert all(edge['from'] in nodes and (':' not in edge['to'] or edge['to'] in nodes)
               for edge in register['edges'])
    assert {'from': 'channel:C03', 'type': 'class', 'to': 'client',
            'view': 'outbound.external_channels'} in register['edges']
    assert graph.views(graph.build(load(''))) == graph.sections(load(''))


def test_drift_names_the_changed_key(config):
    register = graph.build(config)
    assert graph.drift(register, config) == []
    changed = load(CONFIG.replace('work_channels = ["C01", "C03", "c01", "C01"]', 'work_channels = ["C09"]'))
    assert graph.drift(register, changed) == ['outbound.work_channels']


def test_register_only_edges_and_names_survive_a_rebuild(config):
    member = {'from': 'person:slack:U07', 'type': 'member_of', 'to': 'channel:C01', 'card': 'D-3'}
    first = graph.build(config, add=[member], names={'channel:C01': 'eng'})
    again = graph.build(config, first)
    assert member in again['edges'] and again['nodes']['channel:C01']['name'] == 'eng'
    assert 'person:slack:U07' in again['nodes']
    assert graph.views(again) == graph.sections(config)
    assert graph.build(config, again, add=[member])['edges'].count(member) == 1


def test_load_save_sync(tmp_path, config):
    (tmp_path / '.wuwei').mkdir()
    assert graph.load(tmp_path) is None
    assert graph.sync(tmp_path, config) is True
    assert graph.load(tmp_path) == graph.build(config)
    assert graph.sync(tmp_path, config) is False
    path = tmp_path / '.wuwei/graph.json'
    assert json.loads(path.read_text()) == graph.build(config)


@pytest.mark.parametrize('text', [
    'not json', '[]', '{"version": 1, "nodes": {}}', '{"version": 2, "nodes": {}, "edges": []}',
    '{"version": 1, "nodes": {}, "edges": [], "x": 1}', '{"version": 1, "nodes": {"C01": {}}, "edges": []}',
    '{"version": 1, "nodes": {"channel:C01": {"colour": "red"}}, "edges": []}',
    '{"version": 1, "nodes": {}, "edges": [{"from": "channel:C01", "type": "likes", "to": "team"}]}',
    '{"version": 1, "nodes": {}, "edges": [{"from": "channel:C01", "type": "class", "to": "team", "view": "x.y"}]}',
    '{"version": 1, "nodes": {}, "edges": [{"from": "channel:C01", "type": "class"}]}',
])
def test_a_damaged_register_raises_and_is_never_overwritten(tmp_path, config, text):
    (tmp_path / '.wuwei').mkdir()
    path = tmp_path / '.wuwei/graph.json'
    path.write_text(text)
    with pytest.raises(ValueError, match='init --upgrade'):
        graph.load(tmp_path)
    with pytest.raises(ValueError):
        graph.sync(tmp_path, config)
    assert path.read_text() == text


def test_a_symlinked_register_is_damaged(tmp_path):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / 'elsewhere.json').write_text('{"version": 1, "nodes": {}, "edges": []}')
    (tmp_path / '.wuwei/graph.json').symlink_to(tmp_path / 'elsewhere.json')
    with pytest.raises(ValueError, match='symlink'):
        graph.load(tmp_path)


def test_warn_prints_one_line(capsys):
    graph.warn('config set', ValueError('graph.json is damaged (JSONDecodeError)'))
    err = capsys.readouterr().err
    assert err.count('\n') == 1
    assert err.startswith('wuwei config set: warning: .wuwei/graph.json not updated: ')
    assert 'bin/wuwei init --upgrade' in err


def test_find(config):
    register = graph.build(config, names={'channel:C01': 'eng', 'person:slack:U01': 'Ada'})
    assert graph.find(register, 'channel:C01') == ['channel:C01']
    assert graph.find(register, 'C04') == ['channel:C04']
    assert graph.find(register, 'slack:U01') == ['person:slack:U01']
    assert graph.find(register, 'U01') == ['person:slack:U01']
    assert graph.find(register, '#eng') == ['channel:C01']
    assert graph.find(register, '@ada') == ['person:slack:U01']
    assert graph.find(register, 'mcp__acme__send_message') == ['connector:acme']
    assert graph.find(register, 'mcp__mailer__send') == ['connector:Mailer']
    assert graph.find(register, 'tool:acme/send_message') == ['connector:acme']
    assert graph.find(register, 'dev') == ['person:github:dev', 'login:dev']
    assert graph.find(register, 'nobody') == []


def test_related_and_line(config):
    register = graph.build(config, add=[{'from': 'person:slack:U01', 'type': 'member_of',
                                         'to': 'channel:C04', 'card': 'D-2'},
                                        {'from': 'person:slack:U02', 'type': 'member_of', 'to': 'channel:C04'}])
    lines = [graph.line(edge) for edge in graph.related(register, 'channel:C04')]
    assert lines == ['channel:C04 class company (outbound.channel_classes)',
                     'person:slack:U01 member_of channel:C04 (card D-2)',
                     'person:slack:U02 member_of channel:C04 (learned)']


def test_cite_names_only_the_edge_that_decided(config):
    register = graph.build(config)
    reason = (f'{outward.APPROVAL_REQUIRED}: approval tier ask by rule 4 (audience=client) for C03: '
              'C03 in outbound.channel_classes as public')
    assert [graph.line(e) for e in graph.cite(register, reason)] == [
        'channel:C03 class public (outbound.channel_classes)']
    reason = 'ask by rule 4 (audience=client) for C03: C03 in outbound.external_channels as client'
    assert [graph.line(e) for e in graph.cite(register, reason)] == [
        'channel:C03 class client (outbound.external_channels)']
    reason = 'ask by rule 1 (tool=mcp__acme__.*) for C01: C01 in outbound.work_channels as team, outward.modes'
    assert [graph.line(e) for e in graph.cite(register, reason, 'mcp__acme__send_message')] == [
        'channel:C01 class team (outbound.work_channels)', 'connector:acme mode draft (outward.modes)']
    assert graph.cite(register, 'unknown destination C77, not in outbound.work_channels, '
                                'connector default class company', 'mcp__acme__send') == []


def test_annotate_is_idempotent_and_the_template_is_annotated():
    raw = '[owner]\nname = ""\n\n[outbound]\nwork_channels = []\n[outbound.people]\n[deploy]\n'
    once = graph.annotate(raw)
    assert once.count(graph.COMMENT) == 3
    assert once.index(graph.COMMENT) == 0
    assert graph.annotate(once) == once
    assert '[deploy]' in once and f'{graph.COMMENT}\n[deploy]' not in once
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / 'templates/workspace/config.toml').read_text()
    assert graph.annotate(template) == template


def _replaced(config, views):
    """config with every modeled key taken from views."""
    import copy
    config = copy.deepcopy(config)
    for key, value in views.items():
        if key == 'repos.shepherd.reviewers':
            for repo in config['repos']:
                repo['shepherd']['reviewers'] = value.get(repo['name'], [])
            continue
        *path, last = key.split('.')
        target = config
        for part in path:
            target = target[part]
        target[last] = value
    return config


CALLS = [
    ('Thanks', {'channel': 'C01'}, 'slack', None),
    ('Thanks', {'channel': 'C03'}, 'slack', None),
    ('Thanks', {'channel': 'C04'}, 'slack', None),
    ('Thanks', {'channel': 'C77'}, 'slack', None),
    ('Thanks', {'channel': 'D0OWNER'}, 'slack', None),
    ('Thanks', {'channel': 'U01'}, 'slack', None),
    ('Thanks <@U01> and <@U02>', {'channel': 'C01'}, 'slack', None),
    ('Thanks', {'channel': 'C01', 'thread_ts': '1.2'}, 'slack', None),
    ('tests passed', {'channel': 'C01'}, 'slack', 'mcp__acme__send_message'),
    ('tests passed', {}, 'mail', 'mcp__Mailer__send'),
    ('tests passed', {'to': ['ada@example.test']}, 'mail', 'mcp__other__send'),
    ('We will ship by Friday', {'channel': 'C01'}, 'slack', None),
]


@pytest.mark.parametrize('text,context,kind,tool', CALLS)
def test_a_guard_decides_the_same_from_the_register_or_the_view(tmp_path, monkeypatch, text, context, kind, tool):
    # Invariant (design 9.2, #552): a guard decision is the same whether read from the register or the view.
    from wuwei.guards import outward as guard
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    (tmp_path / '.wuwei').mkdir()
    config = load()
    other = _replaced(config, graph.views(graph.build(config)))
    for name in (tool or '', 'mcp__acme__send_message', 'mcp__mailer__send'):
        assert guard.resolve(name, config) == guard.resolve(name, other)
    results = []
    for source in (config, other):
        why = []
        results.append((outward.classify(text, tmp_path, source, dict(context), kind=kind, why=why, tool=tool), why))
    assert results[0] == results[1]
