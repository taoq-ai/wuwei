"""The docs obligation, the item value, pages, close and publishing (#419)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from wuwei import registry, state, workspace
from wuwei.registry import Result

ROOT = Path(__file__).resolve().parents[1]
NOTION = json.loads((ROOT / 'tests/fixtures/docs/recordings.json').read_text())['notion']
SPACE = 'https://www.notion.so/Docs-home-00000000111122223333444444444444'


def config_of(system='notion', **docs):
    config = {'docs': {'system': system, 'required_tiers': ['standard', 'full'], 'space': SPACE,
                       'root': 'docs', 'publish': ['report', 'retro'], 'auto': [],
                       'strict_close': True}}
    config['docs'].update(docs)
    return config


def row(tier=None, docs=None):
    value = {'gates': {'tier': tier} if tier else {}}
    if docs is not None:
        value['docs'] = docs
    return value


@pytest.mark.parametrize('tier,value,system,required,unmet,shown', [
    ('light', None, 'notion', False, False, 'n/a'),
    ('standard', None, 'notion', True, True, 'missing'),
    ('full', None, 'notion', True, True, 'missing'),
    (None, None, 'notion', False, False, 'n/a'),
    ('standard', {'value': 'none', 'reason': 'internal'}, 'notion', True, False, 'none'),
    ('standard', {'value': 'new', 'reason': ''}, 'markdown', True, False, 'new'),
    ('standard', None, 'none', False, False, 'n/a'),
    ('full', None, 'none', False, False, 'n/a'),
])
def test_obligation(tier, value, system, required, unmet, shown):
    from wuwei import docs
    config, current = config_of(system), row(tier, value)
    assert docs.required(config, current) is required
    assert docs.unmet(config, current) is unmet
    assert docs.shown(config, current) == shown


def write_config(root, system='notion', extra=''):
    (root / '.wuwei/config.toml').write_text(
        '[owner]\nname = "Pat Example"\npronouns = "they/them"\n'
        f'[docs]\nsystem = "{system}"\nspace = "{SPACE}"\n' + extra)


@pytest.fixture
def day(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T12:00:00Z')
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    (tmp_path / '.wuwei').mkdir()
    write_config(tmp_path)
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['X'],
        items={'X': {'phase': 'planned', 'status': 'queued'}}), tmp_path, reserved=False)
    return tmp_path


def fake_docs(monkeypatch, read=Result(0, {'id': 'p', 'title': 'T', 'link': 'L', 'updated': 'U'})):
    calls = []
    original = registry.load

    def reader(ref, *, root=None):
        calls.append(ref)
        return read
    monkeypatch.setattr(registry, 'load', lambda kind, config: SimpleNamespace(read=reader)
                        if kind == 'docs' else original(kind, config))
    return calls


def events(root, kind):
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row['payload'] for row in map(json.loads, path.read_text().splitlines())
            if row['kind'] == kind] if path.exists() else []


def item(root, name='X'):
    return state.read_state(root)['items'][name]


def test_plan_set_none_through_the_cli(day):
    import os
    import subprocess
    import sys
    environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'cli')}
    result = subprocess.run([sys.executable, '-P', '-m', 'wuwei', 'plan', 'set', 'X', 'docs=none',
                             '--reason', 'internal refactor'], cwd=day, env=environment,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert item(day)['docs'] == {'value': 'none', 'reason': 'internal refactor'}
    payload, = events(day, 'docs.set')
    assert {key: payload[key] for key in ('item', 'value', 'reason')} == {
        'item': 'X', 'value': 'none', 'reason': 'internal refactor'}


def test_plan_set_refusals(day, monkeypatch):
    from wuwei.__main__ import main
    calls = fake_docs(monkeypatch)
    assert main(['plan', 'set', 'X', 'docs=none']) == 1
    assert main(['plan', 'set', 'Y', 'docs=none', '--reason', 'why']) == 1
    assert main(['plan', 'set', 'X', 'ticket=1']) == 2
    assert main(['plan', 'set', 'X', 'docs=']) == 2
    assert 'docs' not in item(day) and calls == []
    fake_docs(monkeypatch, Result(1, None, 'no page'))
    assert main(['plan', 'set', 'X', f'docs={SPACE}']) == 1
    fake_docs(monkeypatch, Result(2, None, 'notion.read: could not run'))
    assert main(['plan', 'set', 'X', f'docs={SPACE}']) == 2
    assert 'docs' not in item(day) and events(day, 'docs.set') == []
    calls = fake_docs(monkeypatch)
    assert main(['plan', 'set', 'X', f'docs={SPACE}']) == 0
    assert calls == [SPACE] and item(day)['docs'] == {'value': SPACE, 'reason': ''}
    assert main(['plan', 'set', 'X', 'docs=new']) == 0
    assert item(day)['docs']['value'] == 'new'
    write_config(day, 'none')
    assert main(['plan', 'set', 'X', 'docs=new']) == 1


def test_plan_set_markdown(day, monkeypatch, capsys):
    from wuwei import docs
    write_config(day, 'markdown')
    with pytest.raises(state.StateError, match='no worktree'):
        docs.assign('X', 'docs/x.md', '', day)
    tree = day / 'tree'
    (tree / 'docs').mkdir(parents=True)
    (tree / 'docs/x.md').write_text('# X\n')
    (tree / 'other').mkdir()
    (tree / 'other/x.md').write_text('# X\n')
    state._write_state(lambda data: data['items']['X'].update(worktree=str(tree)), day, reserved=False)
    with pytest.raises(state.StateError, match='bin/wuwei docs page X'):
        docs.assign('X', 'new', '', day)
    for value in ('../x.md', 'other/x.md', 'docs/../other/x.md', str(tree / 'docs/x.md'),
                  'docs/missing.md'):
        with pytest.raises(state.StateError):
            docs.assign('X', value, '', day)
    assert docs.assign('X', 'docs/x.md', '', day) == 'X: docs docs/x.md'
    assert item(day)['docs'] == {'value': 'docs/x.md', 'reason': ''}


GOALS = ('# Goals\n\n## G-1\noutcome: Releases are safer\nmeasure: rollbacks\ntarget: 0\n'
         'date: 2026-12-31\npriority: 1\n')
PR = {'title': 'Add a dry-run flag to sync', 'url': 'https://github.com/acme/widget/pull/7',
      'body': '## Summary\nAdds it.\n\n## How to use\nRun `sync --dry-run` first.\n\n## Tests\nUnit.'}


def recorded(day, monkeypatch, pr=PR, ticket='ABC-1', scope='Add a dry-run flag\nSecond line'):
    directory = workspace.day_dir(day)
    (directory / 'proposal.json').write_text(json.dumps({'candidates': [
        {'id': 'X', 'goal': 'G-1', 'scope': scope, 'evidence': 'Two failed syncs last week.'}]}))
    (day / '.wuwei/memory').mkdir(exist_ok=True)
    (day / '.wuwei/memory/goals.md').write_text(GOALS)

    def update(data):
        if pr:
            data['items']['X']['pr'] = 'acme/widget#7'
        if ticket:
            data['tickets'] = {'X': {'id': ticket}}
    state._write_state(update, day, reserved=False)
    original = registry.load
    host = SimpleNamespace(pr=lambda ref, root=None: Result(0, {**(pr or {}), 'repo': 'acme/widget'}),
                           files=lambda ref, root=None: Result(0, [{'path': 'docs/X.md'}]))
    monkeypatch.setattr(registry, 'load', lambda kind, config: host if kind == 'code_host'
                        else original(kind, config))
    return host


def test_render_from_records(day, monkeypatch):
    from wuwei import docs
    recorded(day, monkeypatch)
    title, body = docs.render(day, workspace.load_config(day), state.read_state(day), 'X')
    assert title == 'X: Add a dry-run flag'
    assert body == ('### What changed\nAdd a dry-run flag\nSecond line\n'
                    'Pull request: Add a dry-run flag to sync\n\n'
                    '### Why\nGoal: Releases are safer\nTwo failed syncs last week.\n\n'
                    '### How to use it\nRun `sync --dry-run` first.\n\n'
                    '### Links\n- Pull request: https://github.com/acme/widget/pull/7\n'
                    '- Ticket: ABC-1\n')


def test_render_without_pr_or_ticket(day, monkeypatch):
    from wuwei import docs
    recorded(day, monkeypatch, pr=None, ticket=None)
    _, body = docs.render(day, workspace.load_config(day), state.read_state(day), 'X')
    assert '### Links' not in body and 'Pull request' not in body and '### How to use' not in body


def test_render_without_scope(day, monkeypatch):
    from wuwei import docs
    recorded(day, monkeypatch, scope='')
    with pytest.raises(state.StateError, match='scope'):
        docs.render(day, workspace.load_config(day), state.read_state(day), 'X')


@pytest.mark.parametrize('text', ['see /opt/x/y', 'see ~/x', 'at C:\\x', 'in .wuwei/days',
                                  'state.json', 'the events.jsonl file', 'key sekrit-value-123'])
def test_check_refuses_raw_records_paths_and_credentials(monkeypatch, text):
    from wuwei import docs, redact
    monkeypatch.setattr(redact, 'VALUES', {'sekrit-value-123'})
    with pytest.raises(state.StateError):
        docs.check('Fine line.\n' + text)


def test_check_accepts_links_and_relative_paths():
    from wuwei import docs
    docs.check('See https://example.com/a/b and docs/x.md (decisions/D-1.md).')


def notion_replay(monkeypatch, *answers):
    from test_docs_port import replay
    monkeypatch.setenv('NOTION_TOKEN', 'private-notion-token')
    return replay(monkeypatch, *answers)


def drafts_of(root):
    return [row for row in state.read_state(root).get('drafts', {}).values() if row['channel'] == 'docs']


def test_docs_page_queues_a_draft(day, monkeypatch, capsys):
    from wuwei.__main__ import main
    recorded(day, monkeypatch)
    calls = notion_replay(monkeypatch)
    assert main(['docs', 'page', 'X']) == 0
    row, = drafts_of(day)
    assert f'bin/wuwei drafts show {row["id"]} --widget' in capsys.readouterr().out
    draft = row['inputs']['draft']
    assert draft['title'] == 'X: Add a dry-run flag' and draft['parent'] == SPACE and draft['ref'] == ''
    for text in ('Add a dry-run flag to sync', 'Goal: Releases are safer', 'Two failed syncs',
                 'Run `sync --dry-run` first.', '- Pull request: https://github.com/acme/widget/pull/7',
                 '- Ticket: ABC-1'):
        assert text in draft['body']
    assert str(day) not in json.dumps(row)
    assert item(day)['docs'] == {'value': 'new', 'reason': ''}
    assert calls == [] and events(day, 'docs.written') == []


def test_docs_page_auto_writes(day, monkeypatch, capsys):
    from wuwei.__main__ import main
    write_config(day, extra='auto = ["page"]\n')
    recorded(day, monkeypatch)
    calls = notion_replay(monkeypatch, NOTION['create'])
    assert main(['docs', 'page', 'X']) == 0, capsys.readouterr().err
    assert [call[0] for call in calls] == ['POST']
    payload, = events(day, 'docs.written')
    payload.pop('prs_seen')
    assert payload == {'item': 'X', 'kind': 'page', 'adapter': 'notion',
                       'page': NOTION['create']['url'], 'draft': None}
    assert item(day)['docs'] == {'value': NOTION['create']['url'], 'reason': ''}
    assert drafts_of(day) == []


def test_docs_page_appends_to_a_recorded_page(day, monkeypatch):
    from wuwei import docs
    recorded(day, monkeypatch)
    state._write_state(lambda data: data['items']['X'].update(
        docs={'value': NOTION['create']['url'], 'reason': ''}), day, reserved=False)
    assert docs.page(day, 'X')[0] == 0
    draft = drafts_of(day)[0]['inputs']['draft']
    assert draft['ref'] == NOTION['create']['url'] and draft['body'].startswith('## 2026-10-03\n')


def test_docs_page_refusals(day, monkeypatch, capsys):
    from wuwei import docs
    from wuwei.__main__ import main
    recorded(day, monkeypatch)
    proposal = workspace.day_dir(day) / 'proposal.json'
    proposal.write_text(proposal.read_text().replace('Two failed syncs', 'See /var/log/sync for two failed syncs'))
    assert main(['docs', 'page', 'X']) == 1
    assert 'absolute path' in capsys.readouterr().err
    assert drafts_of(day) == [] and 'docs' not in item(day)
    docs.assign('X', 'none', 'internal refactor', day)
    assert main(['docs', 'page', 'X']) == 1
    assert main(['docs', 'page', 'Y']) == 1
    write_config(day, 'none')
    assert main(['docs', 'page', 'X']) == 2
    assert events(day, 'adapter: none')[0]['kind'] == 'docs'


def markdown_day(day, monkeypatch, extra=''):
    write_config(day, 'markdown', extra)
    recorded(day, monkeypatch)
    tree = day / 'tree'
    tree.mkdir()
    state._write_state(lambda data: data['items']['X'].update(worktree=str(tree)), day, reserved=False)
    return tree


def test_markdown_page_is_a_file_in_the_worktree(day, monkeypatch):
    from wuwei import docs
    tree = markdown_day(day, monkeypatch)
    assert docs.page(day, 'X') == (0, 'docs: wrote page docs/X.md')
    page = tree / 'docs/X.md'
    first = page.read_text()
    assert first.startswith('# X: Add a dry-run flag\n\n### What changed\n')
    assert item(day)['docs'] == {'value': 'docs/X.md', 'reason': ''}
    payload, = events(day, 'docs.written')
    assert payload['page'] == 'docs/X.md' and payload['adapter'] == 'markdown'
    assert drafts_of(day) == [] and str(tree) not in json.dumps(events(day, 'docs.written'))
    assert docs.page(day, 'X')[0] == 0
    assert page.read_text().startswith(first) and '\n## 2026-10-03\n### What changed' in page.read_text()


def test_markdown_page_needs_a_worktree(day, monkeypatch):
    from wuwei import docs
    write_config(day, 'markdown')
    recorded(day, monkeypatch)
    with pytest.raises(state.StateError, match='no worktree'):
        docs.page(day, 'X')


def test_markdown_page_strict_humanizer_refuses(day, monkeypatch):
    from wuwei import docs
    tree = markdown_day(day, monkeypatch, '[outward]\nhumanize_strict = true\n')
    proposal = workspace.day_dir(day) / 'proposal.json'
    proposal.write_text(proposal.read_text().replace('Two failed syncs', 'A pivotal fix after two failed syncs'))
    code, reason = docs.page(day, 'X')
    assert code == 1 and 'ai tells' in reason
    assert not (tree / 'docs').exists() and events(day, 'docs.written') == []


def merged(day, docs_value=None, tier='standard', name='X', written_before=False, written_after=False):
    from wuwei import docs
    def setup(data):
        data['items'].setdefault(name, {'phase': 'planned', 'status': 'queued'})
        data['items'][name].update(pr='acme/widget#7', gates={'tier': tier})
        if docs_value:
            data['items'][name]['docs'] = {'value': docs_value, 'reason': 'why' if docs_value == 'none' else ''}
    state._write_state(setup, day, reserved=False)
    for phase in ('implement', 'gate', 'raised'):
        state.transition(name, phase, day)
    draft = {'kind': 'page', 'item': name}
    if written_before:
        state._write_state(lambda data: None, day, reserved=False, kind='docs.written',
                           payload={'item': name, 'kind': 'page', 'adapter': 'notion', 'page': 'p', 'draft': None})
    state.transition(name, 'merged', day)
    if written_after:
        docs.record(day, draft, 'notion', 'p')


def close_of(day):
    from wuwei import docs
    return docs.close(day)


def test_close_names_a_missing_value(day):
    merged(day)
    code, text = close_of(day)
    assert code == 1 and text.startswith('X: no docs value (tier standard); bin/wuwei plan set X docs=')


@pytest.mark.parametrize('kwargs', [{'docs_value': 'none'}, {'tier': 'light'},
                                    {'docs_value': 'new', 'written_after': True}])
def test_close_is_clean(day, kwargs):
    merged(day, **kwargs)
    assert close_of(day) == (0, '')


def test_close_ignores_unmerged_items(day):
    state._write_state(lambda data: data['items']['X'].update(gates={'tier': 'standard'}), day, reserved=False)
    assert close_of(day) == (0, '')


def test_close_names_a_page_not_written_since_the_merge(day):
    merged(day, 'new', written_before=True)
    assert close_of(day) == (1, 'X: docs page new not written since the merge; bin/wuwei docs page X')


def test_close_names_a_pending_draft(day):
    merged(day, 'new')
    state._write_state(lambda data: data.update(drafts={'draft-1': {
        'id': 'draft-1', 'channel': 'docs', 'operation': 'write', 'status': 'pending', 'item': 'X',
        'inputs': {'draft': {'kind': 'page', 'item': 'X'}}}}), day, reserved=False)
    assert close_of(day) == (1, 'X: docs draft draft-1 pending; bin/wuwei drafts approve draft-1')


@pytest.mark.parametrize('path,expected', [('docs/X.md', 0), ('docs/other.md', 1)])
def test_close_markdown_checks_the_pull_request(day, monkeypatch, path, expected):
    write_config(day, 'markdown')
    recorded(day, monkeypatch)
    merged(day, path)
    code, text = close_of(day)
    assert code == expected
    if expected:
        assert text.startswith(f'X: docs page {path} is not in acme/widget#7;')


def test_close_code_host_failure_is_unmeasured(day, monkeypatch):
    write_config(day, 'markdown')
    host = recorded(day, monkeypatch)
    host.files = lambda ref, root=None: Result(2, None, 'gh: could not run')
    merged(day, 'docs/X.md')
    code, text = close_of(day)
    assert code == 2 and text.startswith('docs unmeasured: ')


@pytest.mark.parametrize('system,extra', [('notion', 'strict_close = false\n'), ('none', '')])
def test_close_off(day, system, extra):
    merged(day)
    write_config(day, system, extra)
    assert close_of(day) == (0, '')


def test_closing_check_includes_the_docs_line(day, monkeypatch):
    from wuwei import closing, docs, pr_actions
    monkeypatch.setattr(pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(pr_actions, 'check', lambda root, closing=False, rows=None: (0, ''))
    monkeypatch.setattr(closing, 'unresolved', lambda root, rows: (0, ''))
    monkeypatch.setattr(closing, 'retro', lambda root: (0, ''))
    monkeypatch.setattr('wuwei.closing.obligations.evaluate', lambda root: {'exit': 0})
    merged(day)
    code, text = closing.check(day)
    assert code == 1 and 'X: no docs value' in text
    docs.assign('X', 'none', 'internal refactor', day)
    assert closing.check(day) == (0, '')


def quiet_metrics(monkeypatch):
    keys = ('escaped_defects', 'review_rework', 'owner_intervention', 'lead_time')
    monkeypatch.setattr('wuwei.metrics.collect', lambda root: {
        **dict.fromkeys(keys, 0), 'baseline': dict.fromkeys(keys, 0)})


def test_report_docs_section(day, monkeypatch):
    from wuwei import report
    quiet_metrics(monkeypatch)
    merged(day, 'none')
    merged(day, name='Y')
    text = report.build(day)
    assert '\n## Docs\n- X: none (why)\n- Y: missing\n' in text
    write_config(day, extra='strict_close = false\n')
    text = report.build(day)
    assert '- Y: missing\n- Y: no docs value (tier standard); bin/wuwei plan set Y docs=' in text
    write_config(day, 'none')
    assert '## Docs' not in report.build(day)


def test_report_publishes_once(day, monkeypatch, capsys):
    from wuwei.__main__ import main
    quiet_metrics(monkeypatch)
    monkeypatch.chdir(day)
    write_config(day, extra='publish = ["report"]\n')
    merged(day, 'none')
    assert main(['report']) == 0
    out = capsys.readouterr().out
    assert '# WUWEI report 2026-10-03' in out
    row, = drafts_of(day)
    assert row['id'] in out
    draft = row['inputs']['draft']
    assert draft['title'] == 'Report 2026-10-03' and draft['kind'] == 'report' and draft['ref'] == ''
    assert [line for line in draft['body'].splitlines() if line.startswith('## ')] == [
        '## Merged', '## Parked', '## Decisions answered', '## Carry', '## Docs']
    assert '- X: none (why)' in draft['body']
    assert main(['report']) == 0
    assert f'already {row["id"]}' in capsys.readouterr().out and len(drafts_of(day)) == 1


def test_report_without_publish_stores_nothing(day, monkeypatch, capsys):
    from wuwei.__main__ import main
    quiet_metrics(monkeypatch)
    monkeypatch.chdir(day)
    write_config(day, extra='publish = []\n')
    assert main(['report']) == 0 and drafts_of(day) == []


def test_publish_retro(day, monkeypatch, capsys):
    from wuwei.__main__ import main
    assert main(['docs', 'publish', 'retro']) == 1
    assert 'wuwei retro' in capsys.readouterr().err
    path = workspace.day_dir(day) / 'retro/2026-10-03.md'
    path.parent.mkdir()
    path.write_text('# Steward retro 2026-10-03\n\n## Metrics\n{}\n\n## Applied\n'
                    '- `.wuwei/charters/builder.md`\n## Proposed\nnone\n')
    assert main(['docs', 'publish', 'retro']) == 0
    draft = drafts_of(day)[0]['inputs']['draft']
    assert draft['title'] == 'Retro 2026-10-03'
    assert draft['body'] == '## Applied\n- `charters/builder.md`\n\n## Proposed\nnone\n'


def test_publish_under_markdown_and_without_a_report(day, capsys):
    from wuwei.__main__ import main
    assert main(['docs', 'publish', 'report']) == 1
    assert 'wuwei report' in capsys.readouterr().err
    write_config(day, 'markdown')
    assert main(['docs', 'publish', 'report']) == 0
    assert 'no effect under markdown' in capsys.readouterr().out and drafts_of(day) == []


def test_detect_finds_the_first_docs_link(tmp_path):
    from wuwei import docs
    one, two = tmp_path / 'one', tmp_path / 'two'
    one.mkdir()
    two.mkdir()
    wiki = 'https://example.atlassian.net/wiki/spaces/DOCS/pages/1/Home'
    (one / 'README.md').write_text(f'Docs live at [the wiki]({wiki}).\n')
    (one / 'CONTRIBUTING.md').write_text('See https://www.notion.so/Docs-00000000111122223333444444444444\n')
    assert docs.detect([one, two]) == wiki
    assert docs.detect([two]) is None
