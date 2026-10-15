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
    assert lines <= 2500, f'{lines} runtime lines: the constitution budget is 2500'


def test_hooks_json_routes_every_event_to_the_cli():
    hooks = json.loads((PLUGIN / 'hooks' / 'hooks.json').read_text())['hooks']
    assert set(hooks) == {'SessionStart', 'PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop'}
    for event, entries in hooks.items():
        assert entries[0]['hooks'][0]['args'] == ['hook', event]


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
