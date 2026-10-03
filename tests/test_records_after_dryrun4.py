"""Issue 247 acceptance: operator records and owner actions after the fourth dry run."""

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei import plan, registry, state, workspace
from wuwei.__main__ import main
from test_intraday_intake import candidate
from test_signal_status import NOW, cli, day

ROOT = Path(__file__).resolve().parents[1]
DUE = {'kind': 'steward.due', 'payload': {'tool_calls': 51}}
RUN = {'kind': 'steward.run', 'payload': {'trigger': 'tool-calls', 'brief': 'b', 'tool_calls': 51}}


@pytest.mark.parametrize('events,count', [([DUE, RUN], 0), ([RUN, DUE], 1)])
def test_steward_run_clears_earlier_due_nudge(tmp_path, monkeypatch, capsys, events, count):
    day(tmp_path, {'cap': 1, 'items': {}, 'gate_approved': True},
        [{**event, 'ts': NOW} for event in events])
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    assert main(['nudges', '--json']) == 0
    rows = [row for row in json.loads(capsys.readouterr().out) if row['source'] == 'steward.due']
    assert len(rows) == count
    assert main(['status', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['nudges'] == count


def test_steward_ack_id_is_documented(tmp_path):
    result = cli(tmp_path, 'steward', 'ack', '--help')
    assert result.returncode == 0
    text = ' '.join(result.stdout.split())
    assert '-fix-3' in text and 'requires planner acknowledgement' in text and 'steward.due' in text
    reference = (ROOT / 'docs/site/reference.md').read_text()
    assert 'steward ack' in reference and '-fix-3' in reference


def test_merged_item_reads_done(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / '.wuwei/memory').mkdir(parents=True)
    (root / '.wuwei/memory/goals.md').write_text(
        '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\n'
        'target: 1\ndate: 2026-10-30\npriority: 1\n')
    (root / '.wuwei/config.toml').write_text(
        '[adapters]\ntts = "none"\ncalendar = "none"\ncode_host = "none"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T10:00:00+02:00')
    monkeypatch.chdir(root)
    plan.propose({'goals': ['G-1'], 'cap': 2,
                  'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
                  'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
                  'sweep': {'manual': 'measured: none'},
                  'candidates': [candidate('DIVIDE-1')]}, root)
    plan.approve(['DIVIDE-1'], root, goals_confirmed=True)
    for phase in ('implement', 'gate', 'raised'):
        assert main(['state', 'transition', 'DIVIDE-1', phase]) == 0
    capsys.readouterr()
    assert main(['state', 'get', 'items.DIVIDE-1.status']) == 0
    assert json.loads(capsys.readouterr().out) == 'queued'
    assert main(['state', 'transition', 'DIVIDE-1', 'merged']) == 0
    capsys.readouterr()
    assert main(['state', 'get', 'items.DIVIDE-1.status']) == 0
    assert json.loads(capsys.readouterr().out) == 'done'
    record = {'agent_id': 'builder-1', 'agent_type': 'builder',
              'fields': {'Blocked': 'none', 'Gap': 'none', 'Change': 'none'},
              'missing': [], 'invalid': []}
    evidence = workspace.day_dir(root) / 'retro/role.json'
    evidence.parent.mkdir()
    evidence.write_text(json.dumps(record))
    state.append_event('retro.captured', {**record,
                       'evidence': evidence.relative_to(root).as_posix()}, root)
    from wuwei import retro
    assert '| DIVIDE-1 | merged | done |' in retro.compile(root).read_text()


@pytest.fixture
def steward_root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'],
        items={'A': {'phase': 'planned', 'status': 'queued'}}), tmp_path, reserved=False)
    return tmp_path


def test_one_close_steward_review_per_day(steward_root, monkeypatch, capsys):
    from wuwei import steward
    from wuwei.commands import close
    root = steward_root
    day_dir = workspace.day_dir(root)
    calls = []
    fake = SimpleNamespace(dispatch=lambda *args, **kwargs: calls.append(args)
                           or registry.Result(0, {'agent_type': 'wuwei:steward'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.closing, 'check', lambda _root: (1, 'OWED: retro'))

    def briefs():
        return sorted((day_dir / 'briefs').glob('steward-*.md'))

    def runs():
        return [row for row in (json.loads(line) for line in
                                (day_dir / 'events.jsonl').read_text().splitlines())
                if row['kind'] == 'steward.run']

    assert close.run(SimpleNamespace(check=None)) == 1
    first, = briefs()
    assert [row['payload']['trigger'] for row in runs()] == ['close']
    assert len(calls) == 1
    capsys.readouterr()
    assert main(['steward', 'run', '--trigger', 'close']) == 0
    brief_path = first.relative_to(root).as_posix()
    assert (capsys.readouterr().out
            == f'steward: close review already ran today (brief {brief_path})\n')
    assert close.run(SimpleNamespace(check=None)) == 1
    assert briefs() == [first] and len(runs()) == 1 and len(calls) == 1
    assert steward.run(root, trigger='sweep') == 0
    assert len(briefs()) == 2 and len(calls) == 2


def test_retro_skill_does_not_ask_for_second_close_review():
    text = (ROOT / 'skills/wuwei-retro/SKILL.md').read_text()
    step = next(line for line in text.splitlines() if line.startswith('1. '))
    assert "if today's close review has not run" not in text
    assert 'wuwei close' in step and 'steward_launch' in step


@pytest.mark.parametrize('config', [
    'repos = []\n[[repos]]\nname = "a/b"\npath = "r"\ndefault_branch = "main"\n',
    'nonsense = 1\n[security]\nposture = "strict"\n',
])
def test_config_error_names_config_toml(tmp_path, monkeypatch, capsys, config):
    from wuwei.guards import integrity
    from wuwei.commands import hook
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(config)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    with pytest.raises(workspace.ConfigError) as caught:
        workspace.load_config(tmp_path)
    assert str(caught.value).startswith('config.toml: ')
    assert str(tmp_path) not in str(caught.value)
    payload = {'cwd': str(tmp_path), 'tool_name': 'Bash', 'tool_input': {'command': 'ls'},
               'hook_event_name': 'PreToolUse', 'session_id': 'test',
               'transcript_path': str(tmp_path / 'transcript.jsonl')}
    code, message = integrity.check(payload)
    assert code == 2 and message.startswith('config.toml:')
    code, message = integrity.session_start({'cwd': str(tmp_path)})
    assert code == 2 and message.startswith('config.toml:')
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    assert hook.run(SimpleNamespace(event='PreToolUse')) == 2
    reason = json.loads(capsys.readouterr().out)['hookSpecificOutput']['permissionDecisionReason']
    assert reason.startswith('config.toml:')


def test_report_prints_mapping_metrics_as_json(tmp_path, monkeypatch, capsys):
    from wuwei import metrics
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(root)
    state._write_state(lambda data: data.update(items={}), root, reserved=False)
    rework = {'mean_per_pr': 0, 'median_per_pr': 0, 'p90_per_pr': 0.0, 'share_with_rework': 0.0}
    real = metrics.collect
    monkeypatch.setattr('wuwei.report.metrics.collect',
                        lambda root=None: {**real(root), 'review_rework': rework})
    capsys.readouterr()
    assert main(['report']) == 0
    out = capsys.readouterr().out
    report_text = out + ''.join(path.read_text() for path in
                                workspace.day_dir(root).glob('report*.md'))
    value = report_text.split('Review rework: ')[1].split('; baseline')[0]
    assert json.loads(value) == rework
    assert "{'" not in report_text


def test_init_says_where_output_goes(tmp_path):
    plain = tmp_path / 'plain'
    plain.mkdir()
    result = cli(plain, 'init')
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert 'statusLine' in json.loads(lines[1])
    assert '.claude/settings.json' in lines[2] and 'statusLine' in lines[2]
    assert '.wuwei/' not in lines
    repo = tmp_path / 'repo'
    (repo / '.git').mkdir(parents=True)
    lines = cli(repo, 'init').stdout.splitlines()
    index = next(i for i, line in enumerate(lines) if '.gitignore' in line)
    assert lines[index + 1:index + 3] == ['.wuwei/', '.claude/']


def test_reference_lists_drafts_approve_digest():
    reference = (ROOT / 'docs/site/reference.md').read_text()
    assert '| `bin/wuwei drafts approve <id>` | yes |' in reference
    assert '| `bin/wuwei drafts drop <id>` | no |' in reference
