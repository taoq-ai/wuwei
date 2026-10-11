"""Issue 353: keys from a newer template warn, and the owner is told to restart Claude Code."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei import workspace

ROOT = Path(__file__).resolve().parents[1]
# No security material in these fixtures, so the outward guard has nothing to read.
TEMPLATE = (ROOT / 'templates/workspace/config.toml').read_text().replace('required = true', 'required = false')
TYPO = TEMPLATE.replace('[scanner]\n', '[scanner]\nseverity_treshold = "high"\n')
OFF = TYPO.replace('enforce = true', 'enforce = false')


def typo_line(text):
    return text.splitlines().index('severity_treshold = "high"') + 1


WARNING = 'unknown key scanner.severity_treshold at line {}; did you mean scanner.severity_threshold?'


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from fakes.integrity import seed
    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text(TYPO)
    seed(root)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    return root


def write(root, text):
    (root / '.wuwei/config.toml').write_text(text)


def replay(monkeypatch, capsys, root, session='test'):
    from wuwei.commands import hook
    payload = {'session_id': session, 'transcript_path': str(root / 'transcript.jsonl'),
               'cwd': str(root), 'hook_event_name': 'PreToolUse',
               'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    code = hook.run(SimpleNamespace(event='PreToolUse'))
    return code, capsys.readouterr().out


def test_unknown_key_warns_with_the_nearest_key(ws):
    found = []
    assert workspace.load_config(ws, warnings=found)['scanner']['severity_threshold'] == 'high'
    assert found == ['config.toml: ' + WARNING.format(typo_line(TYPO))]
    again = []
    workspace.load_config(ws, warnings=again)  # the memo keeps the warnings
    assert again == found


def test_enforce_off_warns_about_the_unknown_key(ws):
    write(ws, OFF)
    found = []
    workspace.load_config(ws, warnings=found)
    assert found == ['config.toml: ' + WARNING.format(typo_line(OFF))]


def test_unknown_key_without_a_near_key_says_remove_it(ws):
    write(ws, 'nonsense = 1\n[guards]\nenforce = true\n')
    found = []
    workspace.load_config(ws, warnings=found)
    assert 'unknown key nonsense at line 1; remove it or use a documented key' in found[0]


@pytest.mark.parametrize('text', [TYPO, OFF], ids=['enforce', 'log-only'])
def test_tool_calls_pass_either_way(ws, monkeypatch, capsys, text):
    write(ws, text)
    code, out = replay(monkeypatch, capsys, ws)
    assert code == 0 and "deny" not in out, out


def test_template_states_the_unknown_key_rule():
    assert TEMPLATE.splitlines()[0] == ('# Defaults apply when settings are omitted. Unknown keys warn; '
                                        'bin/wuwei init --upgrade removes the ones no longer read.')


def test_template_version_is_a_documented_key(ws):
    write(ws, TEMPLATE.replace('template_version = ""', 'template_version = "0.1.0"'))
    found = []
    assert workspace.load_config(ws, warnings=found)['template_version'] == '0.1.0'
    assert found == []


def test_config_check_prints_the_warning(ws, monkeypatch, capsys):
    from fakes.code_host import Fake as CodeHost
    from wuwei import registry
    from wuwei.commands import config
    from wuwei.registry import Result
    code_host = CodeHost()
    code_host.auth_status = lambda root=None: Result(0)
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: code_host if kind == 'code_host' else real(kind, cfg))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    config.run(SimpleNamespace())
    err = capsys.readouterr().err
    assert ('wuwei config check: warning: config.toml: ' + WARNING.format(typo_line(TYPO))) in err


def test_config_check_reports_two_tables(ws, monkeypatch, capsys):
    from fakes.code_host import Fake as CodeHost
    from wuwei import registry
    from wuwei.commands import config
    from wuwei.registry import Result
    code_host = CodeHost()
    code_host.auth_status = lambda root=None: Result(0)
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: code_host if kind == 'code_host' else real(kind, cfg))
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    text = TEMPLATE.replace('[outward]\n', '[outward]\ncode_host_orgs = ["acme"]\n')
    write(ws, text)
    lines = text.splitlines()
    good, bad = lines.index('code_host_orgs = []') + 1, lines.index('code_host_orgs = ["acme"]') + 1
    assert config.run(SimpleNamespace()) == 1
    err = capsys.readouterr().err
    assert (f'wuwei config check: code_host_orgs is set in [outbound] (line {good}) and [outward] '
            f'(line {bad})') in err


def plugin(tmp_path, version, marker=False):
    directory = tmp_path / 'cache' / version
    (directory / '.claude-plugin').mkdir(parents=True)
    (directory / '.claude-plugin/plugin.json').write_text(json.dumps({'name': 'wuwei', 'version': version}))
    if marker:
        (directory / '.in_use').mkdir()
        (directory / '.in_use' / str(os.getpid())).write_text('')
    return directory


@pytest.fixture
def installed(tmp_path, monkeypatch):
    from wuwei import integrity
    directory = plugin(tmp_path, '0.12.0')
    monkeypatch.setattr(integrity, 'PLUGIN', directory)
    return directory


def test_version_and_release(installed):
    from wuwei import integrity
    assert integrity.version() == '0.12.0'
    assert integrity.release('0.13.0') == (0, 13, 0)
    assert integrity.release('') is None and integrity.release('1.x') is None
    (installed / '.claude-plugin/plugin.json').unlink()
    assert integrity.version() == ''


def test_newer_template(installed):
    from wuwei import integrity
    assert integrity.newer_template({'template_version': '0.13.0'}) == ('0.12.0', '0.13.0')
    for template in ('0.12.0', '0.11.0', '', 'dev'):
        assert integrity.newer_template({'template_version': template}) is None


def test_other_versions(tmp_path, monkeypatch):
    from wuwei import integrity
    plugin(tmp_path, '0.12.0', marker=True)
    monkeypatch.setattr(integrity, 'PLUGIN', plugin(tmp_path, '0.13.0', marker=True))
    assert integrity.other_versions() == ['0.12.0']
    for item in (tmp_path / 'cache/0.12.0/.in_use').iterdir():
        item.unlink()
    assert integrity.other_versions() == []
    (tmp_path / 'cache/0.12.0/.in_use').rmdir()
    assert integrity.other_versions() == []


def test_restart_text(tmp_path, installed):
    from wuwei import integrity
    assert integrity.restart({'template_version': '0.12.0'}) == ''
    assert integrity.restart(None) == ''
    assert integrity.restart({'template_version': '0.13.0'}) == (
        'restart Claude Code: hooks 0.12.0 still running (plugin 0.13.0 installed)')
    plugin(tmp_path, '0.11.0', marker=True)
    assert integrity.restart({'template_version': '0.12.0'}) == (
        'restart Claude Code: hooks 0.11.0 still running (plugin 0.12.0 installed)')
    assert integrity.restart(None) == (
        'restart Claude Code: hooks 0.11.0 still running (plugin 0.12.0 installed)')
    plugin(tmp_path, '0.10.0', marker=True)
    assert integrity.restart({'template_version': '0.13.0'}) == (
        'restart Claude Code: hooks 0.10.0, 0.11.0 and 0.12.0 still running (plugin 0.13.0 installed)')


NEWER = TYPO.replace('template_version = ""', 'template_version = "0.13.0"')


def newer_events(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [row['payload'] for row in rows if row['kind'] == 'config.newer_template']


def test_old_hook_passes_and_records_once_per_session(ws, installed, monkeypatch, capsys):
    write(ws, NEWER)
    for session in ('one', 'one', 'two', 'wuwei-probe'):
        code, out = replay(monkeypatch, capsys, ws, session)
        assert code == 0 and 'deny' not in out, out
    assert newer_events(ws) == [{'plugin': '0.12.0', 'template': '0.13.0', 'session': 'one'},
                                {'plugin': '0.12.0', 'template': '0.13.0', 'session': 'two'}]


def test_same_version_template_records_no_event(ws, installed, monkeypatch, capsys):
    write(ws, NEWER.replace('"0.13.0"', '"0.12.0"'))
    code, out = replay(monkeypatch, capsys, ws)
    assert code == 0 and 'deny' not in out, out
    assert newer_events(ws) == []


@pytest.fixture
def newest(tmp_path, monkeypatch):
    from wuwei import integrity
    monkeypatch.setattr(integrity, 'PLUGIN', plugin(tmp_path, '0.13.0'))


@pytest.mark.parametrize('before', ['""', '"0.12.0"', '"dev"'])
def test_stamp_raises_the_version(newest, before):
    import tomllib
    from wuwei.commands.init import _stamp
    text = f'cap = 1\ntemplate_version = {before} # kept comment\n[owner]\nname = "x"\n'
    stamped = _stamp(text)
    assert stamped == text.replace(before, '"0.13.0"')


def test_stamp_adds_a_missing_key_at_the_top_level(newest):
    import tomllib
    from wuwei.commands.init import _stamp
    stamped = _stamp('[owner]\nname = "x"\n')
    assert tomllib.loads(stamped) == {'template_version': '0.13.0', 'owner': {'name': 'x'}}


def test_stamp_never_lowers_or_guesses(newest):
    from wuwei import integrity
    from wuwei.commands.init import _stamp
    newer = 'template_version = "0.14.0"\n'
    assert _stamp(newer) == newer
    (integrity.PLUGIN / '.claude-plugin/plugin.json').unlink()
    assert _stamp('cap = 1\n') == 'cap = 1\n'


def upgrade_output(tmp_path, monkeypatch, capsys, dry_run, others):
    from wuwei import integrity
    from wuwei.commands import init
    monkeypatch.setattr(integrity, 'other_versions', lambda: others)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    capsys.readouterr()
    init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=dry_run))
    return capsys.readouterr().out.splitlines()


def test_upgrade_ends_with_the_restart_line(tmp_path, monkeypatch, capsys):
    from wuwei import integrity
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert upgrade_output(tmp_path, monkeypatch, capsys, False, ['0.11.0'])[-1] == integrity.RESTART


@pytest.mark.parametrize('dry_run,others', [(True, ['0.11.0']), (False, [])])
def test_upgrade_restart_line_only_when_needed(tmp_path, monkeypatch, capsys, dry_run, others):
    from wuwei import integrity
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert integrity.RESTART not in upgrade_output(tmp_path, monkeypatch, capsys, dry_run, others)


def test_release_notes_carry_the_restart_line():
    from wuwei import integrity
    workflow = (ROOT / '.github/workflows/release.yml').read_text()
    assert 'append_body: true' in workflow and integrity.RESTART in workflow


def unread(tmp_path, raw):
    from wuwei.commands.init import _unread_keys
    found = []
    workspace.load_config(tmp_path, raw=raw, warnings=found)
    return _unread_keys(raw, found)


REPO = 'name = "{0}"\npath = "/{0}"\ndefault_branch = "main"\n'


@pytest.mark.parametrize('raw,expected,removed', [
    ('cap = 1\nzzzz = [\n  1,\n  2,\n]\n[owner]\nname = "a"\n',
     {'cap': 1, 'owner': {'name': 'a'}}, ['zzzz']),
    ('cap = 1\nfoo.bar = 1\n', {'cap': 1}, ['foo']),
    ('[qqq]\na = 1\n[qqq.sub]\nb = 2\n[owner]\nname = "a"\n', {'owner': {'name': 'a'}}, ['qqq']),
    ('[[repos]]\n' + REPO.format('a') + '[[repos]]\n' + REPO.format('b') + 'zzz = 1\n',
     {'repos': [{'name': 'a', 'path': '/a', 'default_branch': 'main'},
                {'name': 'b', 'path': '/b', 'default_branch': 'main'}]}, ['repos.1.zzz']),
    ('[[repos]]\n' + REPO.format('a') + '[repos.merge]\nauto = true\nzzzz = 1\n',
     {'repos': [{'name': 'a', 'path': '/a', 'default_branch': 'main', 'merge': {'auto': True}}]},
     ['repos.0.merge.zzzz']),
    ('cap = 1\n', {'cap': 1}, []),
], ids=['multi-line', 'dotted', 'table', 'second-repo', 'repo-subtable', 'none'])
def test_unread_keys_are_removed(tmp_path, raw, expected, removed):
    import tomllib
    text, gone, kept = unread(tmp_path, raw)
    assert tomllib.loads(text) == expected and gone == removed and kept == []


def test_a_likely_typo_is_kept(tmp_path):
    raw = '[host]\nseatz = 2\n'
    assert unread(tmp_path, raw) == (raw, [], [('host.seatz', 'host.seats')])


def test_a_retired_key_is_removed_despite_a_near_match(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, 'RETIRED', ('host.seatz',))
    assert unread(tmp_path, '[host]\nseatz = 2\n') == ('[host]\n', ['host.seatz'], [])


def test_a_comment_above_the_next_kept_header_survives(tmp_path):
    text, removed, kept = unread(tmp_path, '[qqq]\na = 1\n\n# Who owns this workspace.\n[owner]\nname = "a"\n')
    assert text == '\n# Who owns this workspace.\n[owner]\nname = "a"\n' and removed == ['qqq']


def test_a_removal_that_breaks_the_toml_refuses(tmp_path):
    with pytest.raises(ValueError, match=r'zzzz.*by hand'):
        unread(tmp_path, 'zzzz = """\n[owner]\n"""\n[owner]\nname = "a"\n')


def test_unread_key_in_an_inline_table_refuses(tmp_path):
    with pytest.raises(ValueError, match=r'owner\.mystery.*by hand'):
        unread(tmp_path, 'owner = { name = "a", mystery = 1 }\n')


def test_upgrade_keeps_keys_from_a_newer_template(tmp_path, monkeypatch, capsys):
    import re
    from wuwei import integrity
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    monkeypatch.setattr(integrity, 'version', lambda: '0.13.0')
    path = tmp_path / '.wuwei/config.toml'
    text = path.read_text()
    for template, removes in (('0.13.0', True), ('0.14.0', False)):
        path.write_text(re.sub(r'^template_version = .*$', f'template_version = "{template}"\nzzzz = 1',
                               text, count=1, flags=re.M))
        capsys.readouterr()
        init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=True))
        out = capsys.readouterr().out
        assert ('Would upgrade config.toml: remove zzzz (no longer read)' in out) is removes, out


def test_upgrade_removes_and_reports_retired_keys(tmp_path, monkeypatch, capsys):
    # #789 batch 2: every key workspace.RETIRED names leaves config.toml on init --upgrade.
    import tomllib
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    path = tmp_path / '.wuwei/config.toml'
    clean = path.read_text()
    repo = '[[repos]]\nname = "{0}"\npath = "/{0}"\ndefault_branch = "main"\n'
    repos = repo.format('a') + repo.format('b')
    path.write_text(clean.replace('[brief]\n', '[brief]\nlead_minutes = 30\nstyle.length = "concise"\n', 1)
                    .replace('[adapters]\n', '[adapters]\ninbound = "slack"\n', 1)
                    .replace('[shepherd]\n', '[shepherd]\nautostart = false\n', 1)
                    .replace('[tracker]\n', '[tracker]\nrequired = true\nskip_tiers = ["light"]\n'
                             'strict_close = true\nauto = ["progress"]\n', 1)
                    .replace('[owner.verbosity]\n', '[owner.verbosity]\ndm = "full"\n', 1)
                    .replace('[scanner.mcp]\n', '[scanner.mcp]\nproject_file = ".mcp.json"\n'
                             'user_file = "~/.claude.json"\ntimeout_seconds = 60\nblock = ["critical"]\n', 1)
                    + '[pace]\ndefault = "fast"\n[listen]\npoll_seconds = 60\n[responder]\nenabled = true\n'
                    + '[control_plane]\nowner = "T1/U1"\n'
                    + '[grants]\nstanding = []\n' + '[discovery]\nmin_queue = 2\nautostart = "goal"\n' + repos
                    + 'tests = "pytest"\n')  # repos.1.tests has a near key (repos.1.gates)
    clean += repos
    capsys.readouterr()
    init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False))
    out = capsys.readouterr().out
    for key in ('brief.lead_minutes', 'brief.style', 'pace', 'repos.1.tests', 'listen', 'responder',
                'control_plane', 'adapters.inbound', 'shepherd.autostart', 'owner.verbosity.dm',
                'grants', 'scanner.mcp.project_file', 'scanner.mcp.user_file',
                'scanner.mcp.timeout_seconds', 'scanner.mcp.block', 'tracker.required',
                'tracker.skip_tiers', 'tracker.strict_close', 'tracker.auto', 'discovery'):
        assert f'Upgraded config.toml: remove {key} (no longer read)' in out, out
    assert tomllib.loads(path.read_text()) == tomllib.loads(clean)


def test_upgrade_retires_the_memory_machines(tmp_path, monkeypatch, capsys):
    # #833: consolidation, voice, the note and digest memory keys and memory/forget.json go.
    import tomllib
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    path = tmp_path / '.wuwei/config.toml'
    clean = path.read_text()
    path.write_text(clean.replace('[memory]\n', '[memory]\nmax_notes = 60\nnote_line_cap = 80\n'
                                  'probation_days = 10\nstate_entry_cap = 3\ndigest = "week"\n', 1)
                    + '[consolidation]\narchive_after_days = 30\n[voice]\nreview_prs = []\n'
                    '[voice.sources]\ninternal = ["C1"]\n')
    forget = tmp_path / '.wuwei/memory/forget.json'
    forget.write_text('{}')
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    out = capsys.readouterr().out
    for key in ('memory.max_notes', 'memory.note_line_cap', 'memory.probation_days',
                'memory.state_entry_cap', 'memory.digest', 'consolidation', 'voice'):
        assert f'Upgraded config.toml: remove {key} (no longer read)' in out, out
    assert tomllib.loads(path.read_text()) == tomllib.loads(clean)
    assert not forget.exists()


@pytest.mark.parametrize('tier,posture', [('today', 'guarded'), ('ask', 'guarded'), ('today', 'strict')])
def test_upgrade_maps_the_today_merge_tier_to_merge_auto(tmp_path, monkeypatch, capsys, tier, posture):
    # #816: grants and merge.default_tier are retired; "today" merged on every repository, so a
    # repository without its own merge.auto keeps merging through the merge policy.
    import tomllib
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    path = tmp_path / '.wuwei/config.toml'
    repo = '[[repos]]\nname = "{0}"\npath = "/{0}"\ndefault_branch = "main"\n'
    path.write_text(path.read_text().replace('[security]\n', f'[security]\nposture = "{posture}"\n', 1)
                    + f'[merge]\ndefault_tier = "{tier}"\nowner_paths = []\n'
                    '[grants]\nstanding = []\n' + repo.format('a') + repo.format('b') + '[repos.merge]\nauto = false\n')
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    out = capsys.readouterr().out
    config = tomllib.loads(path.read_text())
    assert config['merge'] == {'owner_paths': []} and 'grants' not in config
    for key in ('merge.default_tier', 'grants'):
        assert f'Upgraded config.toml: remove {key} (no longer read)' in out, out
    today = tier == 'today' and posture != 'strict'  # "today" never merged under strict
    assert tomllib.loads(path.read_text())['security'] == {'required': True}  # #837: retired
    assert [repo.get('merge', {}).get('auto') for repo in config['repos']] == [True if today else None, False]
    assert ('Upgraded config.toml: repos.0.merge.auto = true (was merge.default_tier = "today")' in out) is today
    assert 'repos.1.merge.auto' not in out


@pytest.mark.parametrize('dry_run', [False, True])
@pytest.mark.parametrize('name', ['listen', 'watch', 'shepherd'])
def test_upgrade_removes_an_installed_retired_unit(tmp_path, monkeypatch, capsys, dry_run, name):
    # #810, #847: the listener, watch and shepherd user services are no longer shipped.
    from wuwei import registry
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    calls = []
    monkeypatch.setattr(registry, 'watch_service', lambda: SimpleNamespace(call=calls.append))
    unit = workspace.watch_unit(tmp_path, name=name)[1]
    unit.parent.mkdir(parents=True)
    unit.write_text(f'old {name}\n')
    out = upgrade_output(tmp_path, monkeypatch, capsys, dry_run, [])
    if dry_run:
        assert f'Would remove the {name} service (no longer shipped)' in out
        assert unit.exists() and calls == []
    else:
        assert f'Removed the {name} service (no longer shipped)' in out
        assert not unit.exists() and calls


def git(path, *args):
    return subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True)


def hooked_trees(tmp_path, monkeypatch):
    """A workspace with one configured repository and four linked worktrees: the managed shims,
    the chain, the owner's own hooks under worktrees/, and an adopted worktree on the shims
    outside worktrees/ (#847 F2)."""
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    root = tmp_path.resolve()
    assert init.run(SimpleNamespace(path=str(root), upgrade=False, dry_run=False)) == 0
    repo = root / 'repo'
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
    assert git(repo, '-c', 'user.name=A', '-c', 'user.email=a@example.test', 'commit', '-q', '--allow-empty',
               '-m', 'start').returncode == 0
    git(repo, 'config', '--local', 'extensions.worktreeConfig', 'true')
    shims = root / '.wuwei/git-hooks'
    shims.mkdir()
    (shims / 'pre-push').write_text('#!/bin/sh\n')
    trees = {}
    for name in ('worktrees/shim', 'worktrees/chain', 'worktrees/own', 'house/adopted'):
        tree = root / name
        assert git(repo, 'worktree', 'add', '-q', '-b', name.split('/')[1], str(tree)).returncode == 0
        git_dir = Path(git(tree, 'rev-parse', '--absolute-git-dir').stdout.strip())
        (git_dir / 'wuwei-workspace').write_text(str(root) + '\n')
        value = {'worktrees/chain': git_dir / 'wuwei-hooks', 'worktrees/own': root / 'own-hooks'}.get(name, shims)
        if name == 'worktrees/chain':
            value.mkdir()
            (value / 'pre-commit').write_text('#!/bin/sh\n')
        git(tree, 'config', '--worktree', 'core.hooksPath', str(value))
        trees[name] = (tree, git_dir, value)
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + '\n[watch]\nsweep_seconds = 900\n[sessions]\nstale_seconds = 600\n'
                    '[worktree]\ngit_hooks = "chain"\n'
                    '[[repos]]\nname = "acme/repo"\npath = "repo"\ndefault_branch = "main"\n')
    for name in ('watch.lock', 'watch.stdout.log', 'watch.stderr.log', 'shepherd.lock', 'shepherd.stderr.log'):
        (root / '.wuwei' / name).write_text('')
    return root, shims, trees, path


@pytest.mark.parametrize('dry_run', [False, True])
def test_upgrade_unhooks_worktrees_and_retires_the_watch(tmp_path, monkeypatch, capsys, dry_run):
    # #847: init --upgrade unsets WUWEI's core.hooksPath (the shims and the chain) in every
    # linked worktree of a configured repository, keeps the owner's own value and the anchor,
    # removes the managed hooks, the watch and shepherd files and the [watch], [sessions] and
    # [worktree] settings.
    import tomllib
    from wuwei.commands import init
    root, shims, trees, path = hooked_trees(tmp_path, monkeypatch)
    before = path.read_text()
    capsys.readouterr()
    init.run(SimpleNamespace(path=str(root), upgrade=True, dry_run=dry_run))
    out = capsys.readouterr().out.splitlines()
    prefix = 'Would upgrade' if dry_run else 'Upgraded'
    for name in ('worktrees/shim', 'worktrees/chain', 'house/adopted'):
        assert f'{prefix} worktree {name}: unset core.hooksPath' in out, out
    assert not any('worktree worktrees/own' in line for line in out)
    hooks = {name: git(tree, 'config', '--worktree', '--get', 'core.hooksPath').stdout.strip()
             for name, (tree, _, _) in trees.items()}
    if dry_run:
        assert hooks == {name: str(value) for name, (_, _, value) in trees.items()}
        assert shims.is_dir() and trees['worktrees/chain'][2].is_dir() and path.read_text() == before
        assert (root / '.wuwei/watch.lock').exists()
        return
    assert hooks == {'worktrees/shim': '', 'worktrees/chain': '', 'worktrees/own': str(root / 'own-hooks'),
                     'house/adopted': ''}
    assert not shims.exists() and not trees['worktrees/chain'][2].exists()
    assert all((git_dir / 'wuwei-workspace').read_text().strip() == str(root) for _, git_dir, _ in trees.values())
    config = tomllib.loads(path.read_text())
    assert not {'watch', 'sessions', 'worktree'} & set(config)
    for key in ('watch', 'sessions', 'worktree'):
        assert f'Upgraded config.toml: remove {key} (no longer read)' in out, out
    assert not [name for name in ('watch.lock', 'watch.stdout.log', 'watch.stderr.log', 'shepherd.lock',
                                  'shepherd.stderr.log') if (root / '.wuwei' / name).exists()]


def test_upgrade_keeps_the_shims_a_worktree_still_points_at(tmp_path, monkeypatch, capsys):
    # #847 F2: a worktree whose hooks path could not be unset keeps .wuwei/git-hooks, named.
    from wuwei import registry
    from wuwei.commands import init
    from wuwei.registry import Result
    root, shims, trees, _ = hooked_trees(tmp_path, monkeypatch)
    failing, real_load = str(trees['house/adopted'][0]), registry.load

    def load(kind, config):
        module = real_load(kind, config)
        if kind == 'vcs':
            real = module.unhook
            module.unhook = lambda repo, write, root=None: (
                Result(2, None, 'git.unhook: could not run: locked') if repo == failing
                else real(repo, write, root=root))
        return module
    monkeypatch.setattr(registry, 'load', load)
    capsys.readouterr()
    init.run(SimpleNamespace(path=str(root), upgrade=True, dry_run=False))
    out = capsys.readouterr().out
    assert shims.is_dir()
    assert 'left .wuwei/git-hooks: worktree house/adopted may still point at it' in out, out
    assert git(trees['worktrees/shim'][0], 'config', '--worktree', '--get', 'core.hooksPath').stdout == ''


def test_upgrade_retires_the_decision_and_steward_settings(tmp_path, monkeypatch, capsys):
    # Part 14: autonomy, decisions, steward and the digest verbosity leave config.toml.
    import tomllib
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    path = tmp_path / '.wuwei/config.toml'
    clean = path.read_text()
    for name in ('[autonomy]', '[decisions]', '[steward]', 'digest ='):
        assert name not in clean
    path.write_text(clean.replace('[owner.verbosity]\n', '[owner.verbosity]\ndigest = "full"\n', 1)
                    + '[steward]\nevery_tool_calls = 250\nloop_window_hours = 4\nloop_threshold = 9\n'
                    '[autonomy]\nmode = "supervised"\n'
                    '[decisions]\nwait_hours = 24\n[decisions.lenses]\ncompany-rule = "Q?"\n')
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    out = capsys.readouterr().out
    for key in ('owner.verbosity.digest', 'steward', 'autonomy', 'decisions'):
        assert f'Upgraded config.toml: remove {key} (no longer read)' in out, out
    assert tomllib.loads(path.read_text()) == tomllib.loads(clean)


def test_upgrade_retires_the_docs_system(tmp_path, monkeypatch, capsys):
    # Part 19 (#841): the [docs] table and adapters.docs leave config.toml; the config loads clean.
    import tomllib
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    path = tmp_path / '.wuwei/config.toml'
    clean = path.read_text()
    assert '\n[docs]' not in clean
    path.write_text(clean.replace('[adapters]\n', '[adapters]\ndocs = "notion"\n', 1)
                    + '[docs]\nsystem = "notion"\nspace = "https://example.com/page"\npublish = ["report"]\n')
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    out = capsys.readouterr().out
    for key in ('adapters.docs', 'docs'):
        assert f'Upgraded config.toml: remove {key} (no longer read)' in out, out
    assert tomllib.loads(path.read_text()) == tomllib.loads(clean)
    warnings = []
    workspace.load_config(tmp_path, warnings=warnings)
    assert warnings == []


@pytest.mark.parametrize('dry_run', [True, False])
def test_upgrade_maps_observe_to_enforce_false(tmp_path, monkeypatch, capsys, dry_run):
    # #837: an observe workspace stays log-only after the upgrade, and says so.
    import re
    import tomllib
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    path = tmp_path / '.wuwei/config.toml'
    text = re.sub(r'(?m)^enforce = .*\n', '', path.read_text(), count=1)
    path.write_text(text.replace('[security]\n', '[security]\nposture = "observe"\n', 1))
    before = path.read_text()
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=dry_run)) == 0
    out = capsys.readouterr().out.splitlines()
    prefix = 'Would upgrade' if dry_run else 'Upgraded'
    assert f'{prefix} config.toml: guards.enforce = false (was security.posture = "observe")' in out
    assert f'{prefix} config.toml: remove security.posture (no longer read)' in out
    if dry_run:
        assert path.read_text() == before
    else:
        assert workspace.load_config(tmp_path)['guards'] == {'enforce': False}
        assert 'posture' not in tomllib.loads(path.read_text())['security']


GRAPH_COMMENT = ('# A view of .wuwei/graph.json: bin/wuwei config set and the cards write both; '
                 'bin/wuwei who walks it.')


@pytest.mark.parametrize('dry_run', [True, False])
def test_upgrade_retires_the_outward_tiers_and_the_register(tmp_path, monkeypatch, capsys, dry_run):
    # #838: the tier, class, learn and register keys, the graph comments and graph.json go.
    import tomllib
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    path = tmp_path / '.wuwei/config.toml'
    clean = path.read_text()
    assert GRAPH_COMMENT not in clean and not (tmp_path / '.wuwei/graph.json').exists()
    old = (clean.replace('[outbound]\n', f'{GRAPH_COMMENT}\n[outbound]\ndefault_tier = "ask"\nlearn = "off"\n'
                         'work_channels = ["C1"]\ncompany_domains = ["example.test"]\n'
                         'tiers = [{ audience = "team", tier = "send" }]\n', 1)
           .replace('allow = []\n', 'allow = []\npatterns = []\ndraft_ttl = 60\n', 1)
           + '[outbound.people]\n"slack:U1" = {class = "team"}\n[outward.modes]\nacme = "draft"\n'
           '[outward.classes]\nacme = "team"\n')
    path.write_text(old)
    graph = tmp_path / '.wuwei/graph.json'
    graph.write_text('{}')
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=dry_run)) == 0
    out = capsys.readouterr().out.splitlines()
    prefix = 'Would upgrade' if dry_run else 'Upgraded'
    for key in ('outbound.default_tier', 'outbound.learn', 'outbound.work_channels',
                'outbound.company_domains', 'outbound.tiers', 'outbound.people', 'outward.patterns',
                'outward.draft_ttl', 'outward.modes', 'outward.classes'):
        assert f'{prefix} config.toml: remove {key} (no longer read)' in out, out
    assert f'{prefix} config.toml: remove the graph comments' in out
    assert f'{prefix} .wuwei/graph.json: remove (no longer read)' in out
    if dry_run:
        assert path.read_text() == old and graph.exists()
    else:
        assert tomllib.loads(path.read_text()) == tomllib.loads(clean)
        assert GRAPH_COMMENT not in path.read_text() and not graph.exists()


def test_upgrade_keeps_a_symlinked_graph_json(tmp_path, monkeypatch, capsys):
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    target = tmp_path / 'elsewhere.json'
    target.write_text('{}')
    (tmp_path / '.wuwei/graph.json').symlink_to(target)
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    out = capsys.readouterr().out
    assert 'left .wuwei/graph.json: a symlink' in out.splitlines() and target.exists()  # #848: named, kept
    assert 'graph.json: remove' not in out


# #848: what a 0.27.0 workspace left under .wuwei/ that nothing reads any more.
OLD_FILES = ('memory/rehearsals.json', 'memory/rehearsals.lock', 'memory/targets.json',
             'memory/targets.lock', 'memory/cruise.json', 'memory/forget.json', 'memory/voice.md',
             'memory/digests/2026-W40.md', 'inbox/inbox.jsonl', 'inbox/sent.json', 'inbox/cursor.json',
             'ziran/github/' + 'a' * 64 + '.json', 'generated/skills/wuwei-consolidate/SKILL.md',
             *(f'{name}.{suffix}' for name in ('watch', 'shepherd', 'listen')
               for suffix in ('lock', 'stdout.log', 'stderr.log')))


@pytest.mark.parametrize('dry_run', [True, False])
def test_upgrade_leaves_nothing_retired_from_a_0_27_0_workspace(tmp_path, monkeypatch, capsys, dry_run):
    import tomllib
    from wuwei import workspace
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=False, dry_run=False)) == 0
    base = tmp_path / '.wuwei'
    old = ((ROOT / 'tests/fixtures/workspace-0.27.0/config.toml').read_text()
           .replace('[owner.verbosity]\n', '[owner.verbosity]\ndecisions = "full"\n', 1)
           .replace('[adapters]\n', '[adapters]\nredactor = "builtin"\n', 1))
    (base / 'config.toml').write_text(old)
    for name in OLD_FILES:
        (base / name).parent.mkdir(parents=True, exist_ok=True)
        (base / name).write_text('{}')
    outside = tmp_path / 'elsewhere.json'
    outside.write_text('{}')
    (base / 'graph.json').symlink_to(outside)
    history = base / 'days/2026-10-01/state.snapshot.json'
    history.parent.mkdir(parents=True)
    history.write_text('{}')
    capsys.readouterr()
    assert init.run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=dry_run)) == 0
    out = capsys.readouterr().out.splitlines()
    prefix = 'Would upgrade' if dry_run else 'Upgraded'
    removed = sorted({name.split('/')[0] if name.split('/')[0] in ('inbox', 'ziran') else
                      'memory/digests' if name.startswith('memory/digests/') else name for name in OLD_FILES})
    for name in removed:
        assert out.count(f'{prefix} .wuwei/{name}: remove (no longer read)') == 1, (name, out)
    assert 'left .wuwei/graph.json: a symlink' in out
    for key in ('owner.verbosity.decisions', 'adapters.redactor', 'retro.repo'):
        assert f'{prefix} config.toml: remove {key} (no longer read)' in out, out
    assert outside.exists() and history.exists() and (base / 'graph.json').is_symlink()
    if dry_run:
        assert (base / 'config.toml').read_text() == old
        assert all((base / name).exists() for name in OLD_FILES)
        return
    assert not [name for name in OLD_FILES if (base / name).exists()]
    assert not [name for name in ('inbox', 'ziran', 'memory/digests') if (base / name).exists()]
    config = tomllib.loads((base / 'config.toml').read_text())
    for key in workspace.RETIRED:
        table = config
        for part in key.split('.')[:-1]:
            table = table.get(part, {})
        assert key.split('.')[-1] not in table, key
    assert (base / 'memory/index.md').is_file()
