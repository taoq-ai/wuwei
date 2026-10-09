"""Specification mode (design 5.10): config, step tables, enforcement and records."""

import json
from pathlib import Path
import shutil

import pytest

from wuwei import workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/spec'


def test_spec_config_defaults_and_validation(tmp_path):
    assert workspace.load_config(tmp_path, raw='')['spec'] == {
        'engine': 'speckit', 'mode': 'strict', 'skip_tiers': ['light']}
    for text, key in (('engine = "kiro"', 'engine'), ('mode = "loud"', 'mode'),
                      ('skip_tiers = ["tiny"]', 'skip_tiers')):
        with pytest.raises(workspace.ConfigError, match=key):
            workspace.load_config(tmp_path, raw=f'[spec]\n{text}\n')
    template = (ROOT / 'templates/workspace/config.toml').read_text()
    assert '[spec]' in template
    assert workspace.load_config(tmp_path, raw=template)['spec'] == {
        'engine': 'speckit', 'mode': 'strict', 'skip_tiers': ['light']}


ARTIFACTS = {
    'speckit': [('specify', 'specs/001-a/spec.md'), ('plan', 'specs/001-a/plan.md'),
                ('tasks', 'specs/001-a/tasks.md'), ('analyze', 'specs/001-a/analysis.md'),
                ('checklist', 'specs/001-a/checklists/requirements.md')],
    'superpowers': [('brainstorming', 'docs/superpowers/specs/2026-10-03-a-design.md'),
                    ('writing-plans', 'docs/superpowers/plans/2026-10-03-a.md')],
    'openspec': [('proposal', 'openspec/changes/archive/2026-10-03-a/proposal.md'),
                 ('specs', 'openspec/changes/archive/2026-10-03-a/specs/cli/spec.md'),
                 ('tasks', 'openspec/changes/archive/2026-10-03-a/tasks.md'),
                 ('validate', 'openspec/changes/archive/2026-10-03-a/validation.json')],
}


def tree(tmp_path, engine):
    target = tmp_path / engine
    shutil.copytree(FIXTURES / engine, target)
    return target


@pytest.mark.parametrize('engine', sorted(ARTIFACTS))
def test_status_complete_and_each_gap(tmp_path, engine):
    from wuwei import specmode
    path = tree(tmp_path, engine)
    assert specmode.status(path, engine, 'A', build=True) is None
    assert specmode.status(path, engine, 'A') is None
    for step, artifact in ARTIFACTS[engine]:
        saved = (path / artifact).read_bytes()
        (path / artifact).unlink()
        gap = specmode.status(path, engine, 'A', build=True)
        assert gap['step'] == step, (artifact, gap)
        assert specmode.status(path, engine, 'A')['step'] == step
        (path / artifact).write_bytes(saved)


@pytest.mark.parametrize('engine, plan, step', [
    ('speckit', 'specs/001-a/tasks.md', 'implement'),
    ('superpowers', 'docs/superpowers/plans/2026-10-03-a.md', 'executing-plans'),
    ('openspec', 'openspec/changes/archive/2026-10-03-a/tasks.md', 'apply')])
def test_unchecked_task_gaps_implementation_only_at_build(tmp_path, engine, plan, step):
    from wuwei import specmode
    path = tree(tmp_path, engine)
    with (path / plan).open('a') as stream:
        stream.write('- [ ] one more\n')
    assert specmode.status(path, engine, 'A') is None
    assert specmode.status(path, engine, 'A', build=True)['step'] == step


def test_speckit_rules(tmp_path):
    from wuwei import specmode
    path = tree(tmp_path, 'speckit')
    feature = path / 'specs/001-a'
    analysis = (feature / 'analysis.md').read_text()
    (feature / 'analysis.md').write_text(analysis + '| A2 | Coverage | HIGH | No test. |\n')
    gap = specmode.status(path, 'speckit', 'A')
    assert gap['step'] == 'analyze' and 'analysis.md' in gap['reason']
    (feature / 'analysis.md').write_text(analysis)
    spec = (feature / 'spec.md').read_text()
    (feature / 'spec.md').write_text(spec.replace('## Clarifications', '## Notes'))
    assert specmode.status(path, 'speckit', 'A')['step'] == 'clarify'
    (feature / 'spec.md').write_bytes(b'\xff\xfe broken')
    gap = specmode.status(path, 'speckit', 'A')
    assert gap['step'] == 'specify' and 'spec.md' in gap['reason']
    (feature / 'spec.md').write_text(spec)
    (feature / 'checklists/requirements.md').write_text('- [ ] Testable\n')
    assert specmode.status(path, 'speckit', 'A')['step'] == 'checklist'
    (feature / 'checklists/requirements.md').write_text('- [x] Testable\n')
    shutil.copytree(feature, path / 'specs/002-a')
    gap = specmode.status(path, 'speckit', 'A')
    assert gap['step'] == 'specify' and 'specs/001-a' in gap['reason'] and 'specs/002-a' in gap['reason']
    shutil.rmtree(path / 'specs/002-a')
    (path / 'specs/001-a').rename(path / 'specs/003-eng-7')
    assert specmode.status(path, 'speckit', 'ENG-7', build=True) is None
    gap = specmode.status(path, 'speckit', 'A')
    assert gap['step'] == 'specify' and gap['command'] == '/speckit.specify'


def test_openspec_validation_and_archive(tmp_path):
    from wuwei import specmode
    path = tree(tmp_path, 'openspec')
    change = path / 'openspec/changes/archive/2026-10-03-a'
    for text in ('not json', '{"items": []}', '{"items": [{"valid": false}]}'):
        (change / 'validation.json').write_text(text)
        gap = specmode.status(path, 'openspec', 'A')
        assert gap['step'] == 'validate' and 'validation.json' in gap['reason']
    (change / 'validation.json').write_text('{"items": [{"valid": true}]}')
    change.rename(path / 'openspec/changes/a')
    assert specmode.status(path, 'openspec', 'A') is None
    assert specmode.status(path, 'openspec', 'A', build=True)['step'] == 'archive'


def test_missing_location_and_own_paths(tmp_path):
    from wuwei import specmode
    gap = specmode.status(tmp_path, 'speckit', 'A')
    assert gap['step'] == 'specify' and gap['command'] == '/speckit.specify'
    assert specmode.status(None, 'speckit', 'A')['step'] == 'specify'
    assert specmode.own('speckit', tmp_path, tmp_path / 'specs/001-a/spec.md')
    assert specmode.own('speckit', tmp_path, tmp_path / '.specify/memory/constitution.md')
    assert not specmode.own('speckit', tmp_path, tmp_path / 'src/app.py')
    assert specmode.own('superpowers', tmp_path, tmp_path / 'docs/superpowers/plans/x.md')
    assert specmode.own('openspec', tmp_path, tmp_path / 'openspec/changes/a/proposal.md')
    path = tree(tmp_path, 'speckit')
    assert specmode.done(path, 'speckit', 'A') == [
        ('specify', 'specs/001-a/spec.md'), ('clarify', 'specs/001-a/spec.md'),
        ('plan', 'specs/001-a/plan.md'), ('tasks', 'specs/001-a/tasks.md'),
        ('analyze', 'specs/001-a/analysis.md'), ('checklist', 'specs/001-a/checklists/requirements.md'),
        ('implement', 'specs/001-a/tasks.md')]


def config(text=''):
    return workspace.load_config(Path('.'), raw=text)


def test_mode_label_and_skip(tmp_path):
    from wuwei import specmode
    assert specmode.mode(config()) == 'strict'
    assert specmode.label(config()) == 'speckit strict'
    assert specmode.mode(config('[spec]\nengine = "none"\n')) == 'off'
    assert specmode.mode(config('[spec]\nmode = "off"\n')) == 'off'
    assert specmode.mode(config('[spec]\nmode = "advisory"\n')) == 'advisory'
    assert specmode.label(config('[security]\nposture = "observe"\n')) == 'speckit advisory'
    cfg = config()
    assert specmode.skip(cfg, {}) is None
    assert specmode.skip(cfg, {'tier': 'standard'}) is None
    assert specmode.skip(cfg, {'tier': 'light'}) == 'lead tier light'
    assert specmode.skip(cfg, {'tier': 'light'}, computed='light') == 'lead tier light'
    assert specmode.skip(cfg, {'tier': 'light'}, computed='standard') is None
    assert specmode.skip(cfg, {'tier': 'light', 'spec': {'value': 'required', 'reason': ''}}) is None
    assert specmode.skip(cfg, {'spec': {'value': 'skipped', 'reason': 'typo fix'}}) == 'owner: typo fix'


def test_once_per_day(tmp_path, monkeypatch):
    from wuwei import specmode
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00+00:00')
    (tmp_path / '.wuwei').mkdir()
    payload = {'item': 'A', 'engine': 'speckit', 'step': 'plan', 'path': 'specs/001-a/plan.md'}
    assert specmode.once(tmp_path, 'spec.step', payload, ('item', 'step')) is True
    assert specmode.once(tmp_path, 'spec.step', payload, ('item', 'step')) is False
    assert specmode.once(tmp_path, 'spec.step', {**payload, 'step': 'tasks'}, ('item', 'step')) is True
    rows = [json.loads(line) for line in
            (tmp_path / '.wuwei/days/2026-10-03/events.jsonl').read_text().splitlines()]
    assert [row['payload']['step'] for row in rows] == ['plan', 'tasks']


def kinds(root, prefix='spec.'):
    path = root / '.wuwei/days/2026-10-03/events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [(row['kind'], row['payload']) for row in rows if row['kind'].startswith(prefix)]


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00+00:00')
    root = tmp_path / 'ws'
    (root / '.wuwei').mkdir(parents=True)
    return root


def test_check_strict_advisory_skipped_off(ws, tmp_path, monkeypatch):
    from wuwei import dispatch, specmode
    repo = tmp_path / 'repo'
    repo.mkdir()
    code, reason = specmode.check(ws, config(), 'A', {}, repo, build=False, where='edit')
    assert code == 1 and 'specify first: /speckit.specify' in reason
    assert specmode.INSTALL['speckit'] in reason and 'wuwei plan set A spec=skipped' in reason
    (repo / '.specify').mkdir()
    assert specmode.INSTALL['speckit'] not in specmode.check(ws, config(), 'A', {}, repo, build=False, where='edit')[1]
    assert kinds(ws) == []
    light = {'tier': 'light'}
    for _ in range(2):
        assert specmode.check(ws, config(), 'A', light, repo, build=False, where='edit') == (0, '')
    assert kinds(ws) == [('spec.skipped', {'item': 'A', 'reason': 'lead tier light'})]
    advisory = config('[spec]\nmode = "advisory"\n')
    for where in ('edit', 'gates'):
        assert specmode.check(ws, advisory, 'B', {}, repo, build=False, where=where) == (0, '')
    assert kinds(ws)[1:] == [('spec.warned', {'item': 'B', 'engine': 'speckit', 'step': 'specify', 'where': 'edit'})]
    off = config('[spec]\nengine = "none"\n')
    assert specmode.check(ws, off, 'C', {}, repo, build=True, where='gates') == (0, '')
    assert len(kinds(ws)) == 2
    calls = []
    monkeypatch.setattr(dispatch, 'tier', lambda root, cfg, row: calls.append(row) or {'computed': 'standard'})
    code, reason = specmode.check(ws, config(), 'D', light, repo, build=True, where='gates')
    assert code == 1 and len(calls) == 1
    recorded = {'tier': 'light', 'gates': {'computed': 'light'}}
    assert specmode.check(ws, config(), 'D', recorded, repo, build=True, where='gates') == (0, '')
    assert len(calls) == 1
    shutil.copytree(FIXTURES / 'speckit/specs', repo / 'specs')
    assert specmode.check(ws, config(), 'A', {}, repo, build=True, where='gates') == (0, '')


def day_state(root, items, seats=None):
    day = root / '.wuwei/days/2026-10-03'
    day.mkdir(parents=True, exist_ok=True)
    (day / 'state.json').write_text(json.dumps({'items': items, 'seats': seats or {}}))
    return day


@pytest.fixture
def item(ws, tmp_path):
    from fakes.integrity import seed
    seed(ws)
    (ws / '.wuwei/config.toml').write_text('')
    repo = tmp_path / 'repo'
    (repo / 'src').mkdir(parents=True)
    (repo / '.specify').mkdir()
    day_state(ws, {'A': {'phase': 'implement', 'status': 'running', 'worktree': str(repo)}})
    return repo


def payload(ws, event, **fields):
    return {'session_id': 's', 'transcript_path': str(ws / 't.jsonl'), 'cwd': str(ws),
            'hook_event_name': event, **fields}


def hook(event, data, monkeypatch, capsys):
    import io
    import sys
    from types import SimpleNamespace
    from wuwei.commands.hook import run
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(data)))
    code = run(SimpleNamespace(event=event))
    return code, capsys.readouterr()


def write(ws, path, tool='Edit'):
    return payload(ws, 'PreToolUse', tool_name=tool, tool_input={'file_path': str(path)})


def test_pre_tool_use_refuses_source_edits_until_the_spec(ws, item, monkeypatch, capsys):
    code, out = hook('PreToolUse', write(ws, item / 'src/app.py'), monkeypatch, capsys)
    assert code == 2 and 'specify first: /speckit.specify' in out.err
    assert [kind for kind, _ in kinds(ws, 'hook.refusal')] == ['hook.refusal']
    assert hook('PreToolUse', write(ws, item / 'specs/001-a/spec.md', 'Write'), monkeypatch, capsys)[0] == 0
    assert hook('PreToolUse', write(ws, ws / 'notes.md', 'Write'), monkeypatch, capsys)[0] == 0
    other = item.parent / 'other'
    other.mkdir()
    assert hook('PreToolUse', write(ws, other / 'x.py', 'Write'), monkeypatch, capsys)[0] == 0
    shutil.copytree(FIXTURES / 'speckit/specs', item / 'specs')
    assert hook('PreToolUse', write(ws, item / 'src/app.py'), monkeypatch, capsys)[0] == 0


def test_post_tool_use_records_each_step_once(ws, item, monkeypatch, capsys):
    source = FIXTURES / 'speckit/specs/001-a'
    target = item / 'specs/001-a'
    (target / 'checklists').mkdir(parents=True)
    for name in ('spec.md', 'plan.md', 'tasks.md', 'analysis.md', 'checklists/requirements.md'):
        (target / name).write_bytes((source / name).read_bytes())
        data = payload(ws, 'PostToolUse', tool_name='Write', tool_input={'file_path': str(target / name)})
        assert hook('PostToolUse', data, monkeypatch, capsys)[0] == 0
    assert hook('PostToolUse', data, monkeypatch, capsys)[0] == 0
    steps = [row['step'] for kind, row in kinds(ws) if kind == 'spec.step']
    assert steps == ['specify', 'clarify', 'plan', 'tasks', 'implement', 'analyze', 'checklist']
    (target / 'plan.md').unlink()
    bash = payload(ws, 'PostToolUse', tool_name='Bash', tool_input={'command': 'true'})
    bash['cwd'] = str(item)
    (target / 'plan.md').write_text('# Plan\n')
    assert hook('PostToolUse', bash, monkeypatch, capsys)[0] == 0
    assert len(kinds(ws)) == 7
    day_state(ws, {'A': {'phase': 'implement', 'status': 'running', 'worktree': str(item), 'tier': 'light'}})
    (ws / '.wuwei/days/2026-10-03/events.jsonl').chmod(0o644)
    (ws / '.wuwei/days/2026-10-03/events.jsonl').unlink()
    assert hook('PostToolUse', data, monkeypatch, capsys)[0] == 0
    assert [kind for kind, _ in kinds(ws)] == ['spec.skipped']


def test_builder_stop_names_its_artifacts(ws, item, monkeypatch):
    from wuwei.guards import spec
    brief = '.wuwei/days/2026-10-03/briefs/builder-1.md'
    day_state(ws, {'A': {'phase': 'implement', 'status': 'running', 'worktree': str(item)}},
              {'builder-1': {'role': 'builder', 'item': 'A', 'brief': brief, 'status': 'running'}})
    shutil.copytree(FIXTURES / 'speckit/specs', item / 'specs')
    transcript = ws / 'builder-1.jsonl'
    transcript.write_text(json.dumps({'type': 'user', 'message': {'content': 'WUWEI brief: ' + brief}}) + '\n')
    stop = payload(ws, 'SubagentStop', agent_type='wuwei:builder', agent_id='builder-1',
                   agent_transcript_path=str(transcript), stop_hook_active=False,
                   last_assistant_message='Blocked: none\n')
    code, reason = spec.check_stop(stop)
    assert code == 1 and 'specs/001-a' in reason
    assert spec.check_stop({**stop, 'last_assistant_message': 'Spec: specs/001-a\n'}) == (0, '')
    assert spec.check_stop({**stop, 'stop_hook_active': True}) == (0, '')
    assert spec.check_stop({**stop, 'agent_type': 'wuwei:sentinel-arch'}) == (0, '')


def test_present_and_detect(tmp_path):
    from wuwei import specmode
    plugins = tmp_path / 'plugins.json'
    cfg = config(f'[scanner.mcp]\nplugins_file = "{plugins}"\n')
    first, second = tmp_path / 'one', tmp_path / 'two'
    first.mkdir()
    second.mkdir()
    assert specmode.present(first, 'speckit', cfg) is False
    assert specmode.present(first, 'superpowers', cfg) is None
    assert specmode.present(first, 'none', cfg) is True
    assert specmode.detect([first, second], cfg) == 'speckit'
    plugins.write_text('{"plugins": {"superpowers@superpowers-marketplace": []}}')
    assert specmode.detect([first, second], cfg) == 'superpowers'
    (second / 'openspec').mkdir()
    assert specmode.detect([first, second], cfg) == 'openspec'
    (first / '.specify').mkdir()
    assert specmode.detect([first, second], cfg) == 'speckit'


# #614: a Claude Code subagent cannot write analysis.md; the seat hands the report to the CLI.

REPORT = (FIXTURES / 'speckit/specs/001-a/analysis.md').read_text()


def analysis(ws, monkeypatch, capsys, *args, stdin=REPORT):
    import io
    import sys
    from wuwei.__main__ import main
    monkeypatch.setenv('WUWEI_WORKSPACE', str(ws))
    monkeypatch.setattr(sys, 'stdin', io.StringIO(stdin))
    code = main(['spec', 'analysis', *args])
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.fixture
def unanalysed(item):
    shutil.copytree(FIXTURES / 'speckit/specs', item / 'specs')
    (item / 'specs/001-a/analysis.md').unlink()
    return item / 'specs/001-a/analysis.md'


def test_spec_analysis_writes_the_report(ws, item, unanalysed, monkeypatch, capsys, tmp_path):
    from wuwei import specmode
    assert specmode.status(item, 'speckit', 'A')['step'] == 'analyze'
    assert analysis(ws, monkeypatch, capsys, 'a')[:2] == (0, 'specs/001-a/analysis.md\n')
    assert unanalysed.read_text() == REPORT and not unanalysed.is_symlink()
    assert specmode.status(item, 'speckit', 'A') is None
    source = tmp_path / 'report.md'
    source.write_text(REPORT + '| A2 | Coverage | HIGH | No test. |\n')
    assert analysis(ws, monkeypatch, capsys, 'A', '--file', str(source), stdin='')[0] == 0
    assert specmode.status(item, 'speckit', 'A')['step'] == 'analyze'
    line = specmode.brief_line(config(), 'A', {}, item, False)
    assert 'bin/wuwei spec analysis a' in line


@pytest.mark.parametrize('case, hint', [
    ('unknown', 'unknown item'), ('no-worktree', 'worktree add'), ('no-dir', '/speckit.specify'),
    ('two-dirs', 'both match'), ('no-spec', 'spec.md'), ('symlink', 'symlink'),
    ('linked-dir', 'symlink'), ('empty', 'empty'),
])
def test_spec_analysis_refusals(ws, item, unanalysed, monkeypatch, capsys, tmp_path, case, hint):
    name, stdin = 'A', REPORT
    outside = tmp_path / 'outside'
    outside.mkdir()
    if case == 'unknown':
        name = 'B'
    if case == 'no-worktree':
        day_state(ws, {'A': {'phase': 'implement', 'status': 'running'}})
    if case == 'no-dir':
        shutil.rmtree(item / 'specs')
    if case == 'two-dirs':
        shutil.copytree(item / 'specs/001-a', item / 'specs/002-a')
    if case == 'no-spec':
        (item / 'specs/001-a/spec.md').unlink()
    if case == 'symlink':
        unanalysed.symlink_to(outside / 'analysis.md')
    if case == 'linked-dir':
        shutil.move(item / 'specs/001-a', outside / '001-a')
        (item / 'specs/001-a').symlink_to(outside / '001-a')
    if case == 'empty':
        stdin = ' \n'
    code, out, err = analysis(ws, monkeypatch, capsys, name, stdin=stdin)
    assert (code, out) == (2, '') and hint in err, err
    assert not (outside / 'analysis.md').exists() and not (outside / '001-a/analysis.md').exists()
    assert not unanalysed.exists() or unanalysed.is_symlink()


@pytest.mark.parametrize('form', ['redirect', 'heredoc'])
def test_builder_seat_runs_spec_analysis(ws, item, unanalysed, monkeypatch, capsys, form):
    from fakes.day import LAUNCHER
    (ws / '.wuwei/config.toml').write_text('[security]\nposture = "strict"\n')
    command = (f'{LAUNCHER} spec analysis a < /tmp/report.md' if form == 'redirect'
               else f"{LAUNCHER} spec analysis a <<'EOF'\n{REPORT}EOF")
    data = payload(ws, 'PreToolUse', tool_name='Bash', tool_input={'command': command},
                   agent_id='builder-1', agent_type='wuwei:builder')
    data['cwd'] = str(item)
    code, out = hook('PreToolUse', data, monkeypatch, capsys)
    assert code == 0, out
    assert [kind for kind, _ in kinds(ws, 'hook.')] == []
