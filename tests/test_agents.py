"""Agent generation and the checked-in golden output."""

import json
from pathlib import Path
import pytest

from wuwei.commands import agents


ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    'planner', 'lead', 'builder', 'sentinel-arch', 'sentinel-quality',
    'sentinel-security', 'sentinel-goal', 'shepherd', 'steward',
)


@pytest.fixture
def plugin(tmp_path):
    (tmp_path / 'charters').mkdir()
    (tmp_path / 'agents').mkdir()
    for name in ('_common', '_common-authoring', *ROLES):
        (tmp_path / 'charters' / f'{name}.md').write_text(
            f'---\nversion: 1.0.0\n---\n# {name} body\n', encoding='utf-8')
    (tmp_path / 'agents/allowlist.json').write_text(
        json.dumps({role: ['Read'] for role in ROLES}), encoding='utf-8')
    return tmp_path


def test_build_generates_all_roles_with_ordered_charter_content(plugin):
    assert agents.build(plugin) == 0
    assert {p.stem for p in (plugin / 'agents').glob('*.md')} == set(ROLES)
    body = (plugin / 'agents/builder.md').read_text(encoding='utf-8')
    assert body.startswith('---\nname: builder\ndescription: ')
    assert '\ntools: Read\n---\n' in body
    assert body.index('# _common body') < body.index('# _common-authoring body')
    assert body.index('# _common-authoring body') < body.index('# builder body')
    assert body.count('version: 1.0.0') == 3
    assert agents.check(plugin) == 0


def test_charter_edit_without_regeneration_is_drift(plugin):
    assert agents.build(plugin) == 0
    (plugin / 'charters/builder.md').write_text(
        '---\nversion: 1.0.1\n---\n# changed builder body\n', encoding='utf-8')
    assert agents.check(plugin) == 1
    assert agents.build(plugin) == 0
    assert agents.check(plugin) == 0


def test_version_only_charter_edit_is_drift(plugin):
    assert agents.build(plugin) == 0
    charter = plugin / 'charters/builder.md'
    charter.write_text(charter.read_text(encoding='utf-8').replace('1.0.0', '1.0.1'),
                       encoding='utf-8')
    assert agents.check(plugin) == 1


def test_missing_and_extra_agent_files_are_drift(plugin):
    assert agents.build(plugin) == 0
    (plugin / 'agents/lead.md').unlink()
    (plugin / 'agents/extra.md').write_text('# extra\n', encoding='utf-8')
    assert agents.check(plugin) == 1


@pytest.mark.parametrize('data', [
    {'builder': ['Read']},
    {role: [] for role in ROLES},
    {role: ['*'] for role in ROLES},
    {role: ['Read', 'Read'] for role in ROLES},
])
def test_invalid_allowlist_fails_closed(plugin, data, capsys):
    (plugin / 'agents/allowlist.json').write_text(json.dumps(data), encoding='utf-8')
    assert agents.build(plugin) == 2
    assert agents.check(plugin) == 2
    assert 'wuwei agents build:' in capsys.readouterr().err
    assert not (plugin / 'agents/builder.md').exists()


def test_missing_or_invalid_charter_fails_closed_before_writes(plugin):
    (plugin / 'charters/sentinel-goal.md').unlink()
    assert agents.build(plugin) == 2
    assert not (plugin / 'agents/planner.md').exists()
    (plugin / 'charters/sentinel-goal.md').write_text('no version\n', encoding='utf-8')
    assert agents.check(plugin) == 2


def test_checked_in_agents_match_charters_and_allowlist():
    assert agents.check(ROOT) == 0
    matrix = json.loads((ROOT / 'agents/allowlist.json').read_text(encoding='utf-8'))
    assert set(matrix) == set(ROLES)
    assert all(matrix.values())
    assert all('Agent' not in matrix[role] for role in ROLES if role != 'planner')
    assert all(tool not in matrix['builder'] for tool in ('WebFetch', 'WebSearch'))


SENTINELS = ('sentinel-arch', 'sentinel-quality', 'sentinel-security', 'sentinel-goal')


@pytest.mark.parametrize('role', SENTINELS)
def test_every_sentinel_verdict_example_passes_the_lint(tmp_path, role):
    # #665: the example each checked-in sentinel agent shows is a verdict the lint accepts.
    from wuwei import verdict
    text = (ROOT / 'agents' / f'{role}.md').read_text(encoding='utf-8')
    example = text.split('## Verdict format\n')[1].split('```text\n')[1].split('```')[0]
    path = tmp_path / 'decisions' / f'gate-{role}.md'
    path.parent.mkdir()
    path.write_text(example, encoding='utf-8')
    assert verdict.lint_file(path, role=role) == (0, 'OK: FIX')


def test_only_sentinels_carry_the_verdict_format(plugin):
    from wuwei import verdict
    for role in ROLES:
        text = (ROOT / 'agents' / f'{role}.md').read_text(encoding='utf-8')
        assert ('## Verdict format' in text) == (role in SENTINELS), role
    assert agents.build(plugin) == 0
    for role in ROLES:
        body = (plugin / 'agents' / f'{role}.md').read_text(encoding='utf-8')
        assert (('# _common body\n\n' + verdict.section()) in body) == (role in SENTINELS), role


@pytest.mark.parametrize('name', ['_common', 'sentinel-arch'])
def test_charter_with_its_own_verdict_format_fails_build(plugin, capsys, name):
    charter = plugin / 'charters' / f'{name}.md'
    charter.write_text(charter.read_text(encoding='utf-8') + '## Verdict format\n', encoding='utf-8')
    assert agents.build(plugin) == 2
    assert agents.check(plugin) == 2
    assert 'Verdict format' in capsys.readouterr().err
    assert not list((plugin / 'agents').glob('*.md'))


def test_format_change_without_rebuild_is_drift(plugin, monkeypatch, capsys):
    from wuwei import verdict
    assert agents.build(plugin) == 0
    monkeypatch.setitem(verdict.FORMAT, 'Probe', ('`Probe: <changed>`', 'Probe: not run'))
    assert agents.check(plugin) == 1
    assert 'drift in sentinel-' in capsys.readouterr().err
