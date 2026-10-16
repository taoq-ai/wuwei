import json
from pathlib import Path

from wuwei import agents, setup, ws

PLUGIN = Path(__file__).resolve().parents[1]


def test_init_creates_the_workspace_and_merges_harness_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: 'acme/app')
    settings = tmp_path / '.claude' / 'settings.json'
    settings.parent.mkdir()
    settings.write_text(json.dumps({'permissions': {'allow': ['mcp__slack'], 'deny': ['Bash(rm -rf /:*)']}, 'model': 'x'}))
    setup.init(tmp_path)
    data = json.loads(settings.read_text())
    assert data['model'] == 'x' and data['permissions']['allow'][0] == 'mcp__slack'
    assert 'Bash(git:*)' in data['permissions']['allow']
    assert 'Bash(rm -rf /:*)' in data['permissions']['deny']
    assert 'Bash(git push --force:*)' in data['permissions']['deny']
    assert 'Bash(terraform apply:*)' in data['permissions']['ask']
    assert ws.config(tmp_path)['repos'] == ['acme/app']
    assert (tmp_path / ws.DIR / 'canary').read_text().startswith('wuwei-canary-')
    setup.init(tmp_path)
    again = json.loads(settings.read_text())
    assert again['permissions']['deny'].count('Bash(git push --force:*)') == 1


def test_the_generated_agents_match_the_charters():
    assert agents.stale(PLUGIN) == []


def test_every_agent_has_its_reviewed_tool_grant():
    allow = json.loads((PLUGIN / 'agents' / 'allowlist.json').read_text())
    for role, tools in allow.items():
        text = (PLUGIN / 'agents' / f'{role}.md').read_text()
        assert f'tools: {", ".join(tools)}\n' in text


def test_no_runtime_module_imports_outside_the_standard_library():
    import ast
    import sys
    for path in (PLUGIN / 'cli' / 'wuwei').glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            for name in names:
                top = name.split('.')[0]
                assert top == 'wuwei' or top in sys.stdlib_module_names, (path.name, name)


def test_the_runtime_holds_its_size_budget():
    lines = sum(len(path.read_text().splitlines()) for path in (PLUGIN / 'cli' / 'wuwei').glob('*.py'))
    assert lines <= 3000, f'{lines} runtime lines: the constitution budget is 3000'


def test_hooks_json_routes_every_event_to_the_cli():
    hooks = json.loads((PLUGIN / 'hooks' / 'hooks.json').read_text())['hooks']
    assert set(hooks) == {'SessionStart', 'PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop'}
    for event, entries in hooks.items():
        assert entries[0]['hooks'][0]['command'] == f'"${{CLAUDE_PLUGIN_ROOT}}"/bin/wuwei hook {event}'


def test_agent_front_matter_has_no_bare_colon_in_a_value():
    for path in (PLUGIN / 'agents').glob('*.md'):
        front = path.read_text().split('---\n')[1]
        for line in front.splitlines():
            key, _, value = line.partition(': ')
            assert ': ' not in value, f'{path.name}: "{line}" is not valid YAML front matter'


def test_the_ziran_baseline_records_the_reviewed_grants():
    baseline = json.loads((PLUGIN / 'agents' / 'ziran-baseline.json').read_text())
    allow = json.loads((PLUGIN / 'agents' / 'allowlist.json').read_text())
    assert {name: sorted(agent['tools']) for name, agent in baseline['agents'].items()} == {
        name: sorted(tools) for name, tools in allow.items()}


def test_the_hero_matches_its_generator():
    import importlib.util
    spec = importlib.util.spec_from_file_location('hero', PLUGIN / 'scripts' / 'build-hero.py')
    hero = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hero)
    for name, palette in hero.PAL.items():
        assert (PLUGIN / 'docs' / 'site' / 'assets' / f'hero-{name}.svg').read_text() == hero.svg(palette), name


def test_version_is_the_plugin_version(capsys):
    from wuwei import __main__ as cli
    assert cli.main(['--version']) == 0
    assert capsys.readouterr().out.strip() == json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text())['version']


def test_init_cloud_vendors_the_plugin_into_the_repository(tmp_path, monkeypatch):
    import os
    import subprocess
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    setup.init(tmp_path, cloud=True)
    setup.init(tmp_path, cloud=True)
    claude = tmp_path / '.claude'
    cli = claude / 'wuwei' / 'bin' / 'wuwei'
    assert os.access(cli, os.X_OK) and (claude / 'wuwei' / 'charters' / '_common.md').is_file()
    assert (claude / 'skills' / 'wuwei-plan' / 'SKILL.md').is_file() and (claude / 'agents' / 'builder.md').is_file()
    assert not list((claude / 'wuwei').rglob('__pycache__'))
    assert (claude / 'wuwei' / '.gitignore').read_text() == '__pycache__/\n'  # running the copy leaves none to commit
    hooks = json.loads((claude / 'settings.json').read_text())['hooks']
    for event in ('SessionStart', 'PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop'):
        assert [h['hooks'][0]['command'] for h in hooks[event]] == [f'"$CLAUDE_PROJECT_DIR"/.claude/wuwei/bin/wuwei hook {event}']
    assert (tmp_path / ws.DIR / '.gitignore').read_text().splitlines()[-1] == '*'
    version = json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text())['version']
    assert subprocess.run([str(cli), '--version'], capture_output=True, text=True).stdout.strip() == version
    payload = json.dumps({'cwd': str(tmp_path)})
    env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_CODE_REMOTE'}
    run = lambda env: subprocess.run([str(cli), 'hook', 'SessionStart'], input=payload, capture_output=True,
                                     text=True, env=env, cwd=tmp_path).stdout
    assert run(env) == ''  # on a machine, the installed plugin serves; the vendored copy stays quiet
    assert 'WUWEI' in run({**env, 'CLAUDE_CODE_REMOTE': 'true'})


def test_release_please_is_not_pinned_to_a_version_already_released():
    config = json.loads((PLUGIN / 'release-please-config.json').read_text())
    released = json.loads((PLUGIN / '.release-please-manifest.json').read_text())
    for path, package in config['packages'].items():
        assert package.get('release-as') != released.get(path), (
            f'release-as {package["release-as"]} is already released: remove it, or every release stays there')


def _files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def vendored_drift(repository):
    """The paths under repository/.claude/ that differ from what setup.vendor() writes from the tree."""
    import tempfile
    with tempfile.TemporaryDirectory() as fresh:
        want, have = _files(setup.vendor(fresh)), _files(repository / '.claude')
    owned = ('wuwei/',) + tuple(f'skills/{skill.name}/' for skill in (PLUGIN / 'skills').iterdir())
    extra = {path for path in have if path.startswith(owned) and path not in want}
    return sorted({path for path in want if have.get(path) != want[path]} | extra)


def test_the_vendored_plugin_matches_the_tree_it_was_copied_from():
    drift = vendored_drift(PLUGIN)
    assert drift == [], f'.claude/ lags the tree in {drift}: run setup.vendor() (wuwei init --cloud) and commit .claude/'


def test_the_drift_check_names_a_changed_vendored_file(tmp_path):
    setup.vendor(tmp_path)
    assert vendored_drift(tmp_path) == []
    (tmp_path / '.claude' / 'wuwei' / 'cli' / 'wuwei' / 'gh.py').write_text('# stale\n')
    (tmp_path / '.claude' / 'wuwei' / 'cli' / 'wuwei' / 'gone.py').write_text('# removed upstream\n')
    (tmp_path / '.claude' / 'agents' / 'builder.md').unlink()
    (tmp_path / '.claude' / 'agents' / 'mine.md').write_text('a project agent stays\n')
    (tmp_path / '.claude' / 'skills' / 'mine').mkdir()
    (tmp_path / '.claude' / 'skills' / 'mine' / 'SKILL.md').write_text('a project skill stays\n')
    (tmp_path / '.claude' / 'wuwei' / 'cli' / 'wuwei' / '__pycache__').mkdir()
    (tmp_path / '.claude' / 'wuwei' / 'cli' / 'wuwei' / '__pycache__' / 'gh.cpython-311.pyc').write_bytes(b'x')
    assert vendored_drift(tmp_path) == ['agents/builder.md', 'wuwei/cli/wuwei/gh.py', 'wuwei/cli/wuwei/gone.py']


def test_release_please_bumps_the_vendored_plugin_version_with_the_root():
    files = json.loads((PLUGIN / 'release-please-config.json').read_text())['packages']['.']['extra-files']
    bumped = {entry['path'] for entry in files if entry.get('type') == 'json' and entry.get('jsonpath') == '$.version'}
    assert {'.claude-plugin/plugin.json', '.claude/wuwei/.claude-plugin/plugin.json'} <= bumped
    version = lambda path: json.loads((PLUGIN / path).read_text())['version']  # noqa: E731
    assert version('.claude/wuwei/.claude-plugin/plugin.json') == version('.claude-plugin/plugin.json')


def test_doctor_reads_the_code_host_as_wuwei_does_and_says_when_no_hook_fired(tmp_path, monkeypatch):
    from wuwei import gh, hook
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: 'acme/app')

    def cloud_gh(args, timeout=30):  # a cloud session: the proxy token fails auth status, REST works
        if args[:2] == ['auth', 'status']:
            raise gh.GhError('The token in GH_TOKEN is invalid.')
        return [] if '/rules/' in args[1] else 'main'
    monkeypatch.setattr(setup.gh, 'run', cloud_gh)
    setup.init(tmp_path)
    ws.set_config(tmp_path, 'repos', 'acme/app')
    rows = {name: (status, detail) for name, status, detail in setup.doctor(tmp_path)}
    assert rows['gh'] == ('ok', 'reads acme/app')
    assert rows['hooks'][0] == 'warn' and 'no hook has fired' in rows['hooks'][1]
    hook.session_start(tmp_path, {})
    assert {name: status for name, status, _ in setup.doctor(tmp_path)}['hooks'] == 'ok'


def test_doctor_counts_a_hook_row_in_this_clones_ledger_since_the_latest_init(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: '')
    hooks = lambda: {name: status for name, status, _ in setup.doctor(tmp_path)}['hooks']  # noqa: E731
    setup.init(tmp_path)
    mine = (tmp_path / ws.DIR / 'cache' / 'clone').read_text()
    (tmp_path / ws.DIR / 'cache' / 'clone').write_text('0ther000\n')
    ws.record(tmp_path, 'refused', {'tool': 'Bash'})  # another machine's hook, synced on wuwei/state
    (tmp_path / ws.DIR / 'cache' / 'clone').write_text(mine)
    for kind in ('attest', 'sent'):  # the CLI writes these too
        ws.record(tmp_path, kind, {})
    assert hooks() == 'warn'
    ws.record(tmp_path, 'refused', {'tool': 'Bash'})
    assert hooks() == 'ok'
    setup.init(tmp_path)  # a hook row older than the latest init says nothing about the hooks now
    assert hooks() == 'warn'
    ws.record(tmp_path, 'prompt', {'questions': []})
    assert hooks() == 'ok'


def test_doctor_hooks_skips_rows_that_are_not_objects_and_counts_a_clone_file_without_init(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: '')
    setup.init(tmp_path)
    (tmp_path / ws.DIR / 'cache' / 'clone').write_text('fresh000\n')  # the clone id reset after init
    ws.record(tmp_path, 'refused', {'tool': 'Bash'})
    with open(tmp_path / ws.DIR / 'ledger' / 'fresh000.jsonl', 'a', encoding='utf-8') as handle:
        handle.write('[1]\nnull\n5\n"x"\n')
    rows = {name: status for name, status, _ in setup.doctor(tmp_path)}
    assert rows['hooks'] == 'ok' and rows['ledger'] == 'fail'


def test_doctor_finishes_on_ledger_rows_with_malformed_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: '')
    setup.init(tmp_path)
    with open(tmp_path / ws.DIR / 'ledger' / f'{ws.clone(tmp_path)}.jsonl', 'a', encoding='utf-8') as handle:
        handle.write('{"kind": [1]}\n{"ts": 5, "kind": "refused"}\n{"kind": "refused", "data": [1]}\n')
    rows = {name: status for name, status, _ in setup.doctor(tmp_path)}
    assert rows['hooks'] == 'warn' and rows['ledger'] == 'fail'


def test_init_cloud_twice_keeps_other_hooks_and_writes_the_same_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    settings = tmp_path / '.claude' / 'settings.json'
    settings.parent.mkdir()
    other = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'echo other'}]}
    settings.write_text(json.dumps({'hooks': {'PreToolUse': [other]}}))
    setup.init(tmp_path, cloud=True)
    first = settings.read_text()
    setup.init(tmp_path, cloud=True)
    assert settings.read_text() == first and json.loads(first)['hooks']['PreToolUse'][0] == other
