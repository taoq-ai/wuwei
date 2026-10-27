import json
import re
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize('role', ['sentinel-arch', 'sentinel-goal', 'sentinel-quality', 'sentinel-security'])
def test_every_gate_carries_the_worktree_write_mutant_and_stub_rules(role):
    text = ' '.join((PLUGIN / 'agents' / f'{role}.md').read_text().split())
    for rule in ('check out, reset or build in the main worktree', 'with the Write tool, never a shell heredoc',
                 'Re-run every mutant you list as surviving', 'with a stub program on PATH',
                 '<owner/repo> alone before its draft PR exists'):
        assert rule in text, (role, rule)


def _flat(path):
    return ' '.join((PLUGIN / path).read_text().split())


GUARD_RULES = ('generated combinatorial probe', 'under real bash', 'with a stub program on PATH',
               'how many commands were generated', 'how many really ran the door program', 'the holes',
               're-runs it and adds a class for each hole it finds',
               "When a change to guard parsing makes more commands unreadable or rewrites the guard's parser",
               'the checks that do not rely on door words (the program names and paths a guard matches',
               'written by code (json.dumps or a Python literal), never typed into a shell')


def test_the_guard_probe_rules_are_this_repository_lessons_in_agents_md():
    text = _flat('AGENTS.md')
    for rule in GUARD_RULES:
        assert rule in text, rule


@pytest.mark.parametrize('role', ['builder', 'sentinel-arch', 'sentinel-goal', 'sentinel-quality', 'sentinel-security'])
def test_a_generic_charter_names_the_repository_process_for_parser_probes_not_this_repository(role):
    text = _flat(f'agents/{role}.md')
    assert "the repository's own process names" in text, role
    for lesson in ('routes.json', 'guards.py', 'hook.py', 'generated combinatorial probe'):
        assert lesson not in text, (role, lesson)


def test_equivalence_needs_a_differential_probe_with_0_differences():
    text = _flat('agents/sentinel-quality.md')
    assert ('equivalent or deletable only after a generated differential probe between the head and '
            'the change shows 0 differences') in text
    assert 'a surviving mutant alone is reported as untested, `[low] blocks: no`' in text
    assert 'A mutant that is equivalent' not in text


@pytest.mark.parametrize('gate', ['arch', 'goal', 'quality', 'security'])
def test_a_standards_line_adds_checks_and_the_gate_rules_alone_decide_what_blocks(gate):
    """#1213: a standards line saying an untested guard is a blocking finding met rule 3, and gates split."""
    assert 'Standards lines add checks; rules 3 and 5 alone decide what blocks.' in _flat(f'agents/sentinel-{gate}.md')
    assert 'Without one it is a note; a trust-boundary security finding still blocks.' in _flat(f'agents/sentinel-{gate}.md')
    assert 'A standards line names what to check, never when a finding blocks' in _flat('agents/steward.md')


def test_the_planner_forwards_the_verdicts_for_one_head_together():
    text = _flat('charters/planner.md')
    assert ('every gate verdict for a head goes to the builder together, once the last gate for that '
            'head returns') in text
    assert 'the builder starts fixing only then' in text


def test_the_steward_files_a_repository_lesson_in_its_standards_and_a_seat_lesson_as_a_proposal():
    text = _flat('charters/steward.md')
    assert "a lesson about one repository's code goes in `.wuwei/standards.md` as a line that names that repository" in text
    assert 'A lesson that fits both is a charter proposal' in text
    assert 'a lesson about how seats work in any repository is a charter proposal for the retro' in text


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
    assert lines <= 4000, f'{lines} runtime lines: the constitution budget is 4000'


def test_the_runtime_reads_numbers_in_ascii_digits_only():
    found = []
    for path in sorted((PLUGIN / 'cli' / 'wuwei').glob('*.py')):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if '\\d' in line or re.search(r'(?<!\.isascii\(\) and )\b\w+\.isdigit\(', line):
                found.append(f'{path.name}:{number}')
    assert found == []


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
        assert (PLUGIN / 'docs' / 'site' / 'assets' / f'hero-{name}.svg').read_text(encoding='utf-8') == hero.svg(palette), name


def test_one_module_holds_the_plugin_path_and_its_version_and_dead_definitions_are_gone():
    texts = {path.name: path.read_text() for path in (PLUGIN / 'cli' / 'wuwei').glob('*.py')}
    assert [name for name, text in texts.items() if 'Path(__file__).resolve().parents[2]' in text] == ['ws.py']
    assert sum(text.count("'plugin.json'") for text in texts.values()) == 1
    assert not [name for name, text in texts.items() if re.search(r'^CONFIDENCE =|def _confidence\(', text, re.M)]
    assert ws.version() == json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text())['version']


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
    assert (claude / 'skills' / 'wuwei-run' / 'SKILL.md').is_file() and (claude / 'agents' / 'builder.md').is_file()
    assert not list((claude / 'wuwei').rglob('__pycache__'))
    assert (claude / 'wuwei' / '.gitignore').read_text() == '__pycache__/\n'  # running the copy leaves none to commit
    hooks = json.loads((claude / 'settings.json').read_text())['hooks']
    for event in ('SessionStart', 'PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop'):
        assert [h['hooks'][0]['command'] for h in hooks[event]] == [f'"$CLAUDE_PROJECT_DIR"/.claude/wuwei/bin/wuwei hook {event}']
    assert (tmp_path / ws.DIR / '.gitignore').read_text().splitlines()[-1] == '*'
    version = json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text())['version']
    assert subprocess.run(['sh', str(cli), '--version'], capture_output=True, text=True).stdout.strip() == version
    payload = json.dumps({'cwd': str(tmp_path)})
    env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_CODE_REMOTE'}
    run = lambda env: subprocess.run(['sh', str(cli), 'hook', 'SessionStart'], input=payload, capture_output=True,
                                     text=True, env=env, cwd=tmp_path).stdout
    assert run(env) == ''  # on a machine, the installed plugin serves; the vendored copy stays quiet
    assert 'WUWEI' in run({**env, 'CLAUDE_CODE_REMOTE': 'true'})


COMMIT_TYPES = ('feat', 'fix', 'perf', 'revert', 'docs', 'refactor', 'test', 'build', 'ci', 'chore', 'style')


def test_every_commit_type_on_main_has_a_visible_changelog_section():
    """release-please hides docs, refactor, chore, test, ci, build and style by default, so a release
    PR silently drops those commits from its notes. The owner wants every commit on main listed."""
    config = json.loads((PLUGIN / 'release-please-config.json').read_text())
    sections = {s['type']: s for s in config['packages']['.'].get('changelog-sections', [])}
    for kind in COMMIT_TYPES:
        assert kind in sections, f'{kind} has no changelog section: its commits vanish from the release notes'
        assert not sections[kind].get('hidden'), f'{kind} is hidden from the release notes'
        assert sections[kind].get('section'), kind


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
    assert rows['hooks'][0] == 'warn' and 'no hook fired in the last 2 minutes' in rows['hooks'][1]
    hook.pre_tool(tmp_path, {'tool_name': 'Read', 'tool_input': {}})
    assert {name: status for name, status, _ in setup.doctor(tmp_path)}['hooks'] == 'ok'


def test_doctor_hooks_is_ok_only_when_pre_tool_fired_in_the_last_two_minutes(tmp_path, monkeypatch):
    import datetime
    from wuwei import hook
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: '')
    hooks = lambda: {name: (status, detail) for name, status, detail in setup.doctor(tmp_path)}['hooks']  # noqa: E731
    setup.init(tmp_path)
    for kind in ('refused', 'prompt', 'seat.started'):  # hook rows from earlier today say nothing about now
        ws.record(tmp_path, kind, {})
    status, detail = hooks()
    assert status == 'warn' and detail == ('no hook fired in the last 2 minutes: inside a session, '
                                           'the doors and attestations are off')
    real = ws.now()
    monkeypatch.setattr(ws, 'now', lambda: real - datetime.timedelta(seconds=5))
    hook.pre_tool(tmp_path, {'tool_name': 'Read', 'tool_input': {}})
    monkeypatch.setattr(ws, 'now', lambda: real)
    assert hooks() == ('ok', f'fired 5s ago under {sys.executable} {sys.version.split()[0]}')  # the interpreter the hook ran under
    monkeypatch.setattr(ws, 'now', lambda: real + datetime.timedelta(seconds=121))
    assert hooks()[0] == 'warn'


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


def test_the_plan_skill_has_the_planner_read_tracker_measures_into_the_leads_brief():
    skill = (PLUGIN / 'skills' / 'wuwei-run' / 'SKILL.md').read_text()
    launch = skill.index('Launch the lead')
    read = skill.index('tracker')
    assert read < launch, 'the planner reads tracker measures before it launches the lead'
    step = skill[read:launch]
    assert 'own MCP tools' in step and 'unmeasured' in step and "lead's brief" in step


def test_the_run_skill_starts_already_approved_work_before_it_launches_the_lead():
    skill = (PLUGIN / 'skills' / 'wuwei-run' / 'SKILL.md').read_text()
    start = skill.index('already approved')
    assert start < skill.index('Launch the lead'), 'approved work never waits on a plan pass'
    step = ' '.join(skill[start:skill.index('Launch the lead')].split())
    assert 'no pull request and no running seat' in step


def test_the_contributor_docs_run_the_suite_where_python3_lacks_pytest():
    for doc in ('AGENTS.md', 'CONTRIBUTING.md'):
        text = (PLUGIN / doc).read_text()
        assert '`python3 -m pytest -q`' in text and '`pytest -q` where' in text, doc


def test_the_day_starts_with_wuwei_run_and_the_reference_is_wuwei_rules():
    names = {path.parent.name for path in (PLUGIN / 'skills').glob('*/SKILL.md')}
    assert {'wuwei-run', 'wuwei-rules', 'wuwei-watch', 'wuwei-close'} <= names and 'wuwei' not in names
    stub = (PLUGIN / 'skills' / 'wuwei-plan' / 'SKILL.md').read_text()  # kept for one release so old routines still work
    assert '/wuwei-run' in stub and 'renamed' in stub
    for path in [*(PLUGIN / 'charters').glob('*.md'), *(PLUGIN / 'docs').rglob('*.md'), PLUGIN / 'README.md',
                 *(PLUGIN / 'cli' / 'wuwei').glob('*.py'), *(PLUGIN / 'skills').glob('wuwei-[!p]*/SKILL.md')]:
        assert '/wuwei-plan' not in path.read_text(), path


def test_init_cloud_removes_the_retired_wuwei_skill_and_keeps_a_users_own(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    old = tmp_path / '.claude' / 'skills' / 'wuwei'
    old.mkdir(parents=True)
    (old / 'SKILL.md').write_text('---\nname: wuwei\ndescription: How work runs under WUWEI, the process auditor.\n---\n')
    mine = tmp_path / '.claude' / 'skills' / 'deploy'
    mine.mkdir()
    (mine / 'SKILL.md').write_text('---\nname: deploy\n---\n')
    setup.init(tmp_path, cloud=True)
    assert not old.exists() and (mine / 'SKILL.md').is_file()
    assert (tmp_path / '.claude' / 'skills' / 'wuwei-rules' / 'SKILL.md').is_file()
