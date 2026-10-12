"""Issue #327: config set and config add-repo with one confirmation."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei.workspace import load_config


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'templates/workspace/config.toml').read_text()
REPO = '\n[[repos]]\nname = "acme/widget"\npath = "widget"\ndefault_branch = "main"\n'


def config_module():
    from wuwei.commands import config
    return config


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    from fakes.integrity import seed

    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text(TEMPLATE)
    seed(root)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T09:00:00')
    return root


class Confirm:
    def __init__(self, answer=True):
        self.digests, self.answer = [], answer

    def __call__(self, digest, **kwargs):
        self.digests.append(digest)
        return self.answer


def config_set(key, value, confirm, replace=False, add=False):
    return config_module().set_value(SimpleNamespace(key=key, value=value, replace=replace, add=add), confirm=confirm)


def test_one_value_lands_after_its_digest(workspace, capsys):
    confirm = Confirm()
    assert config_set('owner.verbosity.default', '"standard"', confirm) == 0
    out = capsys.readouterr().out
    assert '+default = "standard"' in out
    _, after = out.split('Applied the change')
    command = "bin/wuwei config set owner.verbosity.default '\"standard\"'"  # #856: the token hashes the command
    assert confirm.digests == [hashlib.sha256(command.encode()).hexdigest()[:12]]
    assert 'replaced: owner.verbosity.default = "standard" (was "brief")' in after
    assert load_config(workspace)['owner']['verbosity']['default'] == 'standard'
    assert config_set('owner.verbosity.default', '"standard"', confirm) == 0
    out = capsys.readouterr().out
    assert 'No config.toml changes' in out and 'replaced' not in out


def test_declined_value_writes_nothing(workspace, capsys):
    assert config_set('owner.verbosity.default', '"standard"', Confirm(False)) == 1
    assert 'declined; nothing written' in capsys.readouterr().err
    assert (workspace / '.wuwei/config.toml').read_text() == TEMPLATE


@pytest.mark.parametrize('key,value,reason', [
    ('owner.verbosity', '"brief"', 'owner.verbosity.default'),
    ('owner.verbosity.default', '"loud"', 'verbosity'),
    ('cap', 'many', ''),
    ('cap', '2\nprofile = "standard"', 'one TOML value'),
    ('nonsense', '1', 'nonsense'),
    ('bad key!', '1', 'dotted key'),
])
def test_invalid_value_is_refused_before_the_digest(workspace, capsys, key, value, reason):
    confirm = Confirm()
    assert config_set(key, value, confirm) == 1
    assert confirm.digests == []
    assert reason in capsys.readouterr().err
    assert (workspace / '.wuwei/config.toml').read_text() == TEMPLATE


@pytest.mark.parametrize('key', ['owner', 'repos'])
def test_top_level_key_in_an_empty_config_is_refused(workspace, capsys, key):
    (workspace / '.wuwei/config.toml').write_text('')
    assert config_set(key, '1', Confirm()) == 1
    assert 'list index' not in capsys.readouterr().err
    assert (workspace / '.wuwei/config.toml').read_text() == ''


def test_unchanged_value_asks_nothing(workspace, capsys):
    confirm = Confirm()
    assert config_set('owner.verbosity.default', '"brief"', confirm) == 0
    assert 'No config.toml changes' in capsys.readouterr().out and confirm.digests == []


def test_unanswerable_confirmation_is_unrun(workspace, capsys):
    def refuse(digest, **kwargs):
        raise OSError('no answer')

    assert config_set('owner.verbosity.default', '"standard"', refuse) == 2
    assert 'no answer' in capsys.readouterr().err
    assert (workspace / '.wuwei/config.toml').read_text() == TEMPLATE


def test_repository_value_lands_in_its_table(workspace):
    (workspace / '.wuwei/config.toml').write_text(TEMPLATE + REPO)
    assert config_set('repos.0.merge_deploys', 'false', Confirm()) == 0
    assert load_config(workspace)['repos'][0]['merge_deploys'] is False


def test_owner_tool_patterns_on_template(workspace):
    (workspace / '.wuwei/config.toml').write_text(TEMPLATE + REPO)
    confirm = Confirm()
    assert config_set('outward.tool_patterns', '[{pattern = "x", channel = "slack"}]', confirm, replace=True) == 0
    assert load_config(workspace)['outward']['tool_patterns'] == [{'pattern': 'x', 'channel': 'slack'}]
    assert len(confirm.digests) == 1


def test_same_value_twice_is_byte_identical(workspace, capsys):
    value = '[{pattern = "x", channel = "slack"}]'
    assert config_set('outward.tool_patterns', value, Confirm()) == 0
    once, confirm = (workspace / '.wuwei/config.toml').read_bytes(), Confirm()
    capsys.readouterr()
    assert config_set('outward.tool_patterns', value, confirm) == 0
    assert 'No config.toml changes' in capsys.readouterr().out and confirm.digests == []
    assert (workspace / '.wuwei/config.toml').read_bytes() == once


@pytest.mark.parametrize('key,value,kind,example', [
    ('outward.tool_patterns', '[{pattern: "x"}]', 'a list of tables', '[{pattern = "text", channel = "text"}]'),
    ('cap', 'many', 'an integer', '0'),
    ('owner.verbosity.default', 'standard', 'a string', '"brief"'),
])
def test_not_toml_names_the_type(workspace, capsys, key, value, kind, example):
    confirm = Confirm()
    assert config_set(key, value, confirm) == 1
    err = capsys.readouterr().err
    assert confirm.digests == [] and key in err and kind in err and example in err
    assert (workspace / '.wuwei/config.toml').read_text() == TEMPLATE


@pytest.mark.parametrize('argv,words', [
    (['config', 'set', '--help'], ('key', 'value')),
])
def test_commands_are_wired(capsys, argv, words):
    from wuwei.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert all(word in out for word in words), out


@pytest.mark.parametrize('command', ['setup', 'calibrate'])
def test_setup_and_calibrate_are_gone(capsys, command):
    # #832: init, config set, config add-repo and config promote configure a workspace.
    from wuwei.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main([command])
    assert exc.value.code == 2 and 'invalid choice' in capsys.readouterr().err


def add_repo(confirm, name='acme/widget', path='widget', branch='main', identity=None):
    return config_module().add_repo(SimpleNamespace(name=name, path=path, branch=branch, identity=identity),
                            confirm=confirm)


def test_repository_table_lands_after_its_digest(workspace, capsys):
    confirm = Confirm()
    assert add_repo(confirm, identity='Pat Example <pat@example.test>') == 0
    assert '+[[repos]]' in capsys.readouterr().out and len(confirm.digests) == 1
    [repo] = load_config(workspace)['repos']
    assert (repo['name'], repo['path'], repo['default_branch']) == ('acme/widget', 'widget', 'main')
    assert repo['identity'] == {'name': 'Pat Example', 'email': 'pat@example.test'}


def test_added_repository_is_indexed(workspace, capsys):
    (workspace.parent / 'widget').mkdir()
    assert add_repo(Confirm(), path='../widget') == 0
    index = json.loads((Path.home() / '.config/wuwei/workspaces.json').read_text())
    assert index == {str(workspace.resolve()): [str((workspace.parent / 'widget').resolve())]}


def test_unwritable_index_still_writes_the_config(workspace, capsys):
    (Path.home() / '.config').write_text('')
    assert add_repo(Confirm(), path='../widget') == 0
    assert load_config(workspace)['repos'][0]['path'] == '../widget'
    err = capsys.readouterr().err
    assert 'workspace index not written' in err and 'rerun bin/wuwei init --upgrade' in err


@pytest.mark.parametrize('kwargs', [{}, {'name': 'acme/other'}])
def test_duplicate_repository_is_refused_before_the_digest(workspace, capsys, kwargs):
    (workspace / '.wuwei/config.toml').write_text(TEMPLATE + REPO)
    confirm = Confirm()
    assert add_repo(confirm, **kwargs) == 1
    assert 'duplicate' in capsys.readouterr().err and confirm.digests == []


@pytest.mark.parametrize('kwargs', [{'identity': 'no email'}, {'name': 'widget'}])
def test_malformed_repository_is_refused_before_the_digest(workspace, kwargs):
    confirm = Confirm()
    assert add_repo(confirm, **kwargs) == 1
    assert confirm.digests == [] and (workspace / '.wuwei/config.toml').read_text() == TEMPLATE


def test_repository_text_is_escaped():
    import tomllib

    name = 'Pat "Quote" \\ Example'
    text = config_module().repo_tables('cap = 1', [{'name': 'acme/widget', 'path': 'a"b\\c', 'default_branch': 'main',
                                                     'identity': {'name': name, 'email': 'pat@example.test'}}])
    repo = tomllib.loads(text)['repos'][0]
    assert repo['path'] == 'a"b\\c' and repo['identity']['name'] == name


# #673: a list key is replaced by default; --add keeps its effective items.
@pytest.mark.parametrize('replace', [False, True])
def test_list_set_replaces(workspace, capsys, replace):
    (workspace / '.wuwei/config.toml').write_text(TEMPLATE + REPO + 'fast_checks = ["make lint", "make test"]\n')
    assert config_set('repos.0.fast_checks', '["x"]', Confirm(), replace=replace) == 0
    assert load_config(workspace)['repos'][0]['fast_checks'] == ['x']
    after = capsys.readouterr().out.split('Applied the change')[1]
    assert 'replaced: repos.0.fast_checks = ["x"] (was ["make lint", "make test"])' in after


def test_deploy_list_line_says_added(workspace, capsys):
    text = TEMPLATE.replace('deny = [] #', 'deny = ["make deploy*"] #')
    (workspace / '.wuwei/config.toml').write_text(text)
    assert config_set('deploy.deny', '["npm publish*"]', Confirm()) == 0
    assert load_config(workspace)['deploy']['deny'] == ['make deploy*', 'npm publish*']
    assert ('added: deploy.deny = ["make deploy*", "npm publish*"] (was ["make deploy*"])'
            in capsys.readouterr().out)


def test_list_set_add_once(workspace, capsys):
    before = load_config(workspace)['outbound']['code_host_orgs']
    assert config_set('outbound.code_host_orgs', '["C1"]', Confirm(), add=True) == 0
    line = [row for row in capsys.readouterr().out.splitlines() if row.startswith('added: ')]
    assert len(line) == 1 and line[0].startswith('added: outbound.code_host_orgs = ')
    assert line[0].endswith(f'(was {json.dumps(before)})')
    assert config_set('outbound.code_host_orgs', '["C1"]', Confirm(), add=True) == 0
    assert 'No config.toml changes' in capsys.readouterr().out
    assert config_set('outbound.code_host_orgs', '[]', Confirm(), add=True) == 0
    assert 'No config.toml changes' in capsys.readouterr().out
    assert load_config(workspace)['outbound']['code_host_orgs'] == [*before, 'C1']


def test_add_and_replace_exclude_each_other(workspace):
    from wuwei.__main__ import main
    with pytest.raises(SystemExit) as exc:
        main(['config', 'set', 'outbound.code_host_orgs', '["C1"]', '--add', '--replace'])
    assert exc.value.code == 2


# #492: with --add a list key keeps its effective items, a named-entry table keeps its entries.
def test_list_set_appends(workspace):
    from wuwei.workspace import SCHEMA
    before = load_config(workspace)['outbound']['code_host_orgs']
    assert config_set('outbound.code_host_orgs', '["C1"]', Confirm(), add=True) == 0
    assert load_config(workspace)['outbound']['code_host_orgs'] == [*before, 'C1']
    rule = '[{pattern = "mcp__acme__send", channel = "slack"}]'
    assert config_set('outward.tool_patterns', rule, Confirm(), add=True) == 0
    assert load_config(workspace)['outward']['tool_patterns'] == [
        *SCHEMA['outward']['tool_patterns'][1], {'pattern': 'mcp__acme__send', 'channel': 'slack'}]


def test_empty_list_set_writes_empty(workspace, capsys):
    # #604: '[]' empties a list instead of adding nothing to the effective (default) list.
    assert config_set('spec.skip_tiers', '[]', Confirm()) == 0
    assert '+skip_tiers = []' in capsys.readouterr().out
    assert load_config(workspace)['spec']['skip_tiers'] == []


def test_list_set_replace(workspace):
    assert config_set('shepherd.source_exclude', '["C1"]', Confirm(), replace=True) == 0
    assert load_config(workspace)['shepherd']['source_exclude'] == ['C1']


def test_table_set_adds_entries(workspace):
    assert config_set('outward.servers', '{acme = "slack"}', Confirm(), add=True) == 0
    assert config_set('outward.servers', '{other = "local"}', Confirm(), add=True) == 0
    assert load_config(workspace)['outward']['servers'] == {'acme': 'slack', 'other': 'local'}
    assert 'other = "local"' in (workspace / '.wuwei/config.toml').read_text()


def test_add_refused_on_scalar(workspace, capsys):
    confirm = Confirm()
    assert config_set('owner.verbosity.default', '"standard"', confirm, add=True) == 1
    assert '--add' in capsys.readouterr().err and confirm.digests == []
    assert (workspace / '.wuwei/config.toml').read_text() == TEMPLATE
    assert config_set('owner.verbosity.default', '"standard"', confirm, replace=True) == 0
    assert load_config(workspace)['owner']['verbosity']['default'] == 'standard'


def test_config_show_tags(workspace, capsys):
    from wuwei.__main__ import main
    rule = '[{pattern = "mcp__acme__send", channel = "slack"}]'
    assert config_set('outward.tool_patterns', rule, Confirm(), add=True) == 0
    capsys.readouterr()
    assert main(['config', 'show', 'outward.tool_patterns']) == 0
    rows = capsys.readouterr().out.splitlines()
    assert len(rows) == 6 and [row.rsplit(' ', 1)[1] for row in rows] == ['default'] * 5 + ['owner']
    assert main(['config', 'show', 'outbound.owner_channel']) == 0
    assert capsys.readouterr().out.splitlines() == ['"session"  default']
    assert main(['config', 'show', 'outbound.nonsense']) == 1
    assert 'unknown key outbound.nonsense' in capsys.readouterr().err


def test_card_command_names_add(workspace, monkeypatch):
    # #838: the outward refusal names the --add line; its card shows that exact command.
    from wuwei import sessions
    seen = []
    monkeypatch.setattr(sessions, 'needs_owner', lambda root, command, *rest: seen.append(command) or 'Owner step')
    config_set('outward.allow', '["mcp__slack__send"]', None, add=True)
    assert seen == ["bin/wuwei config set outward.allow '[\"mcp__slack__send\"]' --add"]
