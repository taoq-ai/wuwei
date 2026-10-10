"""#476: the plugin reference, generated from the CLI's own tables."""

import argparse
from argparse import Namespace
import hashlib
from importlib import import_module
import pkgutil
import re

import pytest

from wuwei import commands, integrity, shell, workspace
from wuwei.commands import next as next_command
from wuwei.guards import protect_state


def _parser():
    parser = argparse.ArgumentParser(prog='wuwei')
    subparsers = parser.add_subparsers(dest='command')
    for module in pkgutil.iter_modules(commands.__path__, commands.__name__ + '.'):
        if not module.name.rsplit('.', 1)[-1].startswith('_'):
            import_module(module.name).register(subparsers)
    return parser, subparsers


def _widget_paths():
    found = set()

    def walk(parser, path):
        if any('--widget' in action.option_strings for action in parser._actions):
            found.add(' '.join(path))
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    walk(child, (*path, name))

    walk(_parser()[0], ())
    return found


def test_text_comes_from_the_tables():
    from wuwei import guide
    from wuwei.__main__ import GROUPS
    text = guide.text()
    lines = text.splitlines()
    helps = {action.dest: action.help for action in _parser()[1]._choices_actions}
    for heading, names in GROUPS:
        if heading.startswith(('Daily', 'Recovery')):
            for name in names.split():
                assert f'- {name}: {helps[name]}' in lines
    owner = next(line for line in lines if line.startswith('## Owner only'))
    assert 'ask the owner' in owner
    owner_line = lines[lines.index(owner) + 1]
    for pair in protect_state._OWNER_ACTIONS:
        assert ' '.join(pair).strip() in owner_line
    read_line = next(line for line in lines if line.startswith('Read-only, never refused:'))
    for path in commands.READ_ONLY:
        assert (f'{path} {commands._NEEDS[path]}' if path in commands._NEEDS else path) in read_line
    for phrase in (shell.UNPARSED.removeprefix('unparsed: '),
                   shell.WORKSPACE_ROOT.removeprefix('workspace guard: ')[1:],
                   protect_state._STATE_HINT, next_command.EXECUTABLE):
        assert phrase in text
    for area in workspace.AREAS:
        cells = [workspace.POSTURES[posture][area] for posture in workspace.POSTURES]
        assert f'| {area} | ' + ' | '.join(cells) + ' |' in lines
    for entry in guide.WIDGETS:
        assert f'wuwei {entry}' in text
    assert not re.search(r'(^|[\s(`])/(Users|home|tmp|private|var)/', text)
    assert '\N{EM DASH}' not in text and not re.search('[\U0001F300-\U0001FAFF\u2600-\u27BF]', text)
    assert len(lines) < 97


def test_widget_printers_match_the_parsers(monkeypatch):
    from wuwei import guide
    from test_cli_known_command import _registered
    registered = _registered()
    for path in _widget_paths():
        assert any(entry.startswith(path + ' ') for entry in guide.WIDGETS), path
    for entry in guide.WIDGETS:
        words = entry.split()
        assert any(words[:len(p.split())] == p.split() for p in registered), entry
    before = guide.text()
    monkeypatch.setitem(workspace.POSTURES, 'guarded', {**workspace.POSTURES['guarded'], 'mcp': 'block'})
    assert guide.text() != before
    monkeypatch.undo()
    monkeypatch.setattr(commands, 'READ_ONLY', commands.READ_ONLY | {'fixture path'})
    assert guide.text() != before


def test_guide_command_prints_the_text(capsys):
    from wuwei import guide
    from wuwei.__main__ import GROUPS, main
    capsys.readouterr()
    assert main(['guide']) == 0
    assert capsys.readouterr().out == guide.text()
    assert commands.read_only(['guide'])
    daily = next(names for heading, names in GROUPS if heading.startswith('Daily')).split()
    assert daily[daily.index('next') + 1] == 'guide'


def initialised(tmp_path, monkeypatch, export_to=None):
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    project = tmp_path / 'project'
    project.mkdir()
    if export_to:
        (project / export_to).write_text('# Owner notes\n')
    assert init.run(Namespace(path=str(project))) == 0
    if export_to:
        config = project / '.wuwei/config.toml'
        config.write_text(config.read_text().replace('export_to = "CLAUDE.md"', f'export_to = "{export_to}"'))
    return project


def block(path):
    from wuwei import guide
    text = path.read_text()
    assert text.count(guide.START) == 1 and text.count(guide.END) == 1
    return text.split(guide.START, 1)[1].split(guide.END, 1)[0].strip('\n').split('\n')


def upgrade(project, dry_run=False):
    from wuwei.commands import init
    return init.upgrade(Namespace(path=str(project), dry_run=dry_run))


def test_init_writes_the_stamped_block_and_upgrade_keeps_it(tmp_path, monkeypatch, capsys):
    from wuwei import guide
    project = initialised(tmp_path, monkeypatch)
    path = project / 'CLAUDE.md'
    stamp, *body = block(path)
    digest = hashlib.sha256(guide.text().encode()).hexdigest()[:12]
    assert f'plugin {integrity.version()}' in stamp and f'tables {digest}' in stamp
    assert '\n'.join(body) + '\n' == guide.text() and len(body) + 3 < 100
    assert 'Guide: CLAUDE.md block written' in capsys.readouterr().out
    path.write_text('# Owner paragraph\n\n' + path.read_text())
    before = path.read_bytes()
    assert upgrade(project) == 0
    out = capsys.readouterr().out
    assert path.read_bytes() == before and 'guide block' not in out
    assert 'No workspace changes needed' in out


def test_block_goes_to_the_configured_file(tmp_path, monkeypatch, capsys):
    from wuwei import guide
    project = initialised(tmp_path, monkeypatch, export_to='NOTES.md')
    (project / 'CLAUDE.md').unlink()
    assert upgrade(project) == 0
    assert 'Upgraded NOTES.md: guide block' in capsys.readouterr().out
    assert (project / 'NOTES.md').read_text().startswith('# Owner notes\n\n' + guide.START)
    assert not (project / 'CLAUDE.md').exists()


@pytest.mark.parametrize('drift', ['table', 'deleted'])
def test_doctor_sees_and_fixes_a_stale_block(tmp_path, monkeypatch, capsys, drift):
    from wuwei import guide
    from wuwei.commands import doctor
    project = initialised(tmp_path, monkeypatch)
    path = project / 'CLAUDE.md'
    if drift == 'table':
        monkeypatch.setitem(workspace.POSTURES, 'guarded', {**workspace.POSTURES['guarded'], 'mcp': 'block'})
    else:
        path.write_text('# Owner paragraph\n')
    before = path.read_bytes()
    capsys.readouterr()
    assert upgrade(project, dry_run=True) == 0
    assert 'Would upgrade CLAUDE.md: guide block' in capsys.readouterr().out
    assert path.read_bytes() == before
    found = next(row for row in doctor._workspace(project, workspace.load_config(project), None, [])
                 if row['name'] == 'template')
    assert found['status'] == 'warn' and found['apply'] == 'init-upgrade'
    assert 'Would upgrade CLAUDE.md: guide block' in found['detail']
    _, preview, apply = doctor.FIXES['init-upgrade']
    _, token = preview(project)
    assert apply(project, token) == 0
    assert '\n'.join(block(path)[1:]) + '\n' == guide.text()


def test_unwritable_block_warns_and_init_and_upgrade_finish(tmp_path, monkeypatch, capsys):
    from wuwei.commands import init
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'AGENTS.md').write_text('# Agents\n')
    (project / 'CLAUDE.md').symlink_to('AGENTS.md')
    assert init.run(Namespace(path=str(project))) == 0
    captured = capsys.readouterr()
    assert 'wuwei init: warning: guide block not written:' in captured.err
    assert 'plugin integrity' in captured.out and 'block written' not in captured.out
    assert (project / 'AGENTS.md').read_text() == '# Agents\n'
    for dry_run in (True, False):
        assert upgrade(project, dry_run=dry_run) == 0
        assert 'guide block not written' in capsys.readouterr().err
    from wuwei.commands import doctor
    rows = {row['name']: row for row in doctor._workspace(project, workspace.load_config(project), None, [])}
    assert rows['template']['status'] == 'ok'
    assert rows['guide']['status'] == 'warn' and 'symlink' in rows['guide']['value']


def test_guide_names_the_pr_read_commands():
    # #530: reading review comments and the reviewer list is pr state and pr ping-check.
    from wuwei import guide
    [line] = [line for line in guide.text().splitlines() if 'wuwei pr state' in line]
    assert 'wuwei pr ping-check' in line and 'reviewer list' in line


RERUN = ('wuwei decision show D-n --widget', '`wuwei decide D-n "<label>" --card <hash>`',
         'without asking the card again. Below strict, never show the owner a host-terminal command for a card they answered')


def test_a_failed_card_confirmation_reruns_with_card():
    # #599: the next step after a confirmation failure is the widget's --card command, never a host terminal.
    from wuwei import guide
    assert all(part in guide.text() for part in RERUN)
