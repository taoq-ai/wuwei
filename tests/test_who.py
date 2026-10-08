"""#552: bin/wuwei who walks the register: a node, its edges and the tier a routine message gets."""

import json

import pytest

from wuwei import graph, workspace
from wuwei.__main__ import main


CONFIG = '''[owner]
name = "Pat Example"
pronouns = "they/them"

[outward.servers]
acme = "slack"
[outward.modes]
acme = "draft"

[outbound]
default_tier = "ask"
work_channels = ["C01"]
company_domains = ["example.test"]
[outbound.people]
"slack:U01" = {email = "ada@example.test", class = "team"}
"slack:U02" = {email = "bo@example.test", class = "team"}

[shepherd.authors]
"dev@example.test" = {login = "dev", mention = "U02"}
'''
MEMBERS = [{'from': f'person:slack:{person}', 'type': 'member_of', 'to': 'channel:C01', 'card': 'D-1'}
           for person in ('U01', 'U02')]
NAMES = {'channel:C01': 'eng', 'person:slack:U01': 'Ada', 'person:slack:U02': 'Bo'}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-08T12:00:00+00:00')
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(CONFIG)
    graph.sync(tmp_path, workspace.load_config(tmp_path), MEMBERS, NAMES)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def who(capsys, *args):
    code = main(['who', *args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_who_channel(ws, capsys):
    before = sorted(path.name for path in (ws / '.wuwei').rglob('*'))
    register = (ws / '.wuwei/graph.json').read_text()
    code, out, _ = who(capsys, 'C01')
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == 'channel:C01 (eng)'
    assert 'class team (outbound.work_channels)' in lines
    assert 'people: person:slack:U01 (Ada, team), person:slack:U02 (Bo, team)' in lines
    assert 'a routine message here: send' in lines
    assert 'edge: person:slack:U01 member_of channel:C01 (card D-1)' in lines
    assert sorted(path.name for path in (ws / '.wuwei').rglob('*')) == before
    assert (ws / '.wuwei/graph.json').read_text() == register


def test_who_channel_json(ws, capsys):
    code, out, _ = who(capsys, '#eng', '--json')
    assert code == 0
    [found] = json.loads(out)
    assert set(found) == {'node', 'name', 'edges', 'tier', 'rule'}
    assert found['node'] == 'channel:C01' and found['name'] == 'eng' and found['tier'] == 'send'
    assert {'from': 'channel:C01', 'type': 'class', 'to': 'team', 'view': 'outbound.work_channels'} in found['edges']
    assert all(edge in found['edges'] for edge in MEMBERS)


def test_who_person(ws, capsys):
    code, out, _ = who(capsys, 'U01')
    lines = out.splitlines()
    assert code == 0 and lines[0] == 'person:slack:U01 (Ada)'
    assert 'class team (outbound.people)' in lines
    assert 'edge: person:slack:U01 maps_to address:ada@example.test (outbound.people)' in lines
    assert 'edge: person:slack:U01 member_of channel:C01 (card D-1)' in lines
    assert any(line.startswith('a routine direct message: ask (') for line in lines), lines


@pytest.mark.parametrize('name', ['connector:acme', 'mcp__acme__send_message'])
def test_who_connector(ws, capsys, name):
    code, out, _ = who(capsys, name)
    lines = out.splitlines()
    assert code == 0 and lines[0] == 'connector:acme'
    assert 'edge: connector:acme sends_through slack (outward.servers)' in lines
    assert 'edge: connector:acme mode draft (outward.modes)' in lines
    assert any(line.startswith('a routine write through it: ask (') and 'outward.modes' in line
               for line in lines), lines


def test_who_login(ws, capsys):
    code, out, _ = who(capsys, 'login:dev')
    lines = out.splitlines()
    assert code == 0 and lines[0] == 'login:dev'
    assert 'edge: address:dev@example.test maps_to login:dev (shepherd.authors)' in lines
    assert 'edge: address:dev@example.test maps_to person:slack:U02 (shepherd.authors)' in lines
    assert any(line.startswith('a routine direct message to person:slack:U02: ') for line in lines), lines


def test_who_misses(ws, capsys):
    code, _, err = who(capsys, 'nobody')
    assert code == 1 and 'bin/wuwei outbound learn' in err
    (ws / '.wuwei/graph.json').write_text('not json')
    code, _, err = who(capsys, 'C01')
    assert code == 2 and 'init --upgrade' in err
    (ws / '.wuwei/graph.json').unlink()
    code, _, err = who(capsys, 'C01')
    assert code == 1 and 'bin/wuwei init --upgrade' in err
