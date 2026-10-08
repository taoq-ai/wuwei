"""#556: the novelty gate; a target the workspace never touched runs one level lower (design 5.8.1)."""

import json
from types import SimpleNamespace

import pytest

from wuwei import workspace


TODAY = '2026-10-08'
CONFIG = '''[[repos]]
name = "fixture-org/app"
path = "."
default_branch = "main"
[outbound]
work_channels = ["C1"]
external_channels = ["C2"]
channel_classes = {C3 = "team"}
tiers = [{channel = "C4", tier = "send"}]
people = {"slack:U1" = {email = "pat@example.com"}}
[outbound.owner.slack]
user = "U0OWNER"
dm = "D0OWNER"
[shepherd]
review_channel = "C5"
[environments]
staging = "main"
[deploy]
workflows = ["deploy-production.yml"]
[grants]
standing = [{action = "deploy", target = "repo:fixture-org/exact", scope = "always", decision = "D-9", date = "2026-10-01"},
            {action = "deploy", target = "repo:fixture-org/*", scope = "always", decision = "D-8", date = "2026-10-01"}]
'''


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', TODAY + 'T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.chdir(root)
    return root


def seen(root):
    return json.loads((root / '.wuwei/memory/targets.json').read_text())['targets']


def empty(root):
    (root / '.wuwei/memory').mkdir(exist_ok=True)
    (root / '.wuwei/memory/targets.json').write_text('{"targets": {}}')


def test_keys_find_each_form():
    from wuwei import novelty
    text = ('Touches repo:fixture-org/new. and channel:C9, person:slack:U7 (tool:server/send_message) '
            'dependency:pypi/requests: env:staging; workflow:deploy.yml repo:fixture-org/new '
            'channel:<id> repo:<org>/<name> norepo:fixture-org/x')
    assert novelty.keys(text) == ['repo:fixture-org/new', 'channel:C9', 'person:slack:U7',
                                  'tool:server/send_message', 'dependency:pypi/requests', 'env:staging',
                                  'workflow:deploy.yml']
    assert novelty.keys('deploys to `env:staging` via `workflow:deploy.yml`, [channel:C2](x) "env:prod"') == [
        'env:staging', 'workflow:deploy.yml', 'channel:C2', 'env:prod']
    fields = {'Question': 'On repo:fixture-org/a?', 'Context': 'channel:C9', 'Blast radius': 'env:prod',
              'Reasoning': 'repo:fixture-org/ignored'}
    assert novelty.record_keys(fields) == ['repo:fixture-org/a', 'channel:C9', 'env:prod']


def test_configured(ws):
    from wuwei import novelty
    (ws / '.wuwei/config.toml').write_text(CONFIG)
    found = novelty.configured(workspace.load_config(ws))
    for key in ('repo:fixture-org/app', 'channel:C1', 'channel:C2', 'channel:C3', 'channel:C4', 'channel:C5',
                'channel:D0OWNER', 'person:slack:U1', 'person:slack:U0OWNER', 'env:staging',
                'workflow:deploy-production.yml', 'repo:fixture-org/exact'):
        assert key in found, key
    assert 'repo:fixture-org/*' not in found and 'channel:' not in found


def test_novel_records_and_clear(ws):
    from wuwei import novelty
    config = workspace.load_config(ws)
    assert novelty.novel(ws, config, []) == []
    assert not (ws / '.wuwei/memory/targets.json').exists()
    empty(ws)
    (ws / '.wuwei/config.toml').write_text(CONFIG)
    config = workspace.load_config(ws)
    assert novelty.novel(ws, config, ['repo:fixture-org/new', 'repo:fixture-org/app']) == ['repo:fixture-org/new']
    assert seen(ws) == {'repo:fixture-org/new': {'first_seen': TODAY, 'cleared': None}}
    (ws / '.wuwei/memory/targets.json').write_text(json.dumps(
        {'targets': {'repo:fixture-org/new': {'first_seen': '2026-10-01', 'cleared': None}}}))
    assert novelty.novel(ws, config, ['repo:fixture-org/new']) == ['repo:fixture-org/new']
    assert seen(ws)['repo:fixture-org/new']['first_seen'] == '2026-10-01'
    novelty.clear(ws, 'repo:fixture-org/new', 'D-1')
    row = seen(ws)['repo:fixture-org/new']
    assert row['cleared']['by'] == 'owner' and row['cleared']['evidence'] == 'D-1'
    novelty.clear(ws, 'repo:fixture-org/new', 'D-2')
    assert seen(ws)['repo:fixture-org/new']['cleared']['evidence'] == 'D-1'
    assert novelty.novel(ws, config, ['repo:fixture-org/new']) == []


@pytest.mark.parametrize('text', ['not json', '[]', '{"targets": {"repo:x": {"first_seen": "2026-10-01", "cleared": null}}}',
                                  '{"targets": {"repo:a/b": {"first_seen": "x", "cleared": null}}}',
                                  '{"targets": {"repo:a/b": {"first_seen": "2026-10-01", "cleared": {"by": "seat"}}}}'])
def test_damaged_set_raises(ws, text):
    from wuwei import novelty
    empty(ws)
    (ws / '.wuwei/memory/targets.json').write_text(text)
    with pytest.raises(ValueError, match=r'memory/targets.json.*bin/wuwei init --upgrade'):
        novelty.novel(ws, workspace.load_config(ws), ['repo:fixture-org/new'])


def test_symlinked_set_raises(ws):
    from wuwei import novelty
    empty(ws)
    path = ws / '.wuwei/memory/targets.json'
    path.rename(ws / 'elsewhere.json')
    path.symlink_to(ws / 'elsewhere.json')
    with pytest.raises(ValueError, match='memory/targets.json'):
        novelty.novel(ws, workspace.load_config(ws), ['repo:fixture-org/new'])


def day(root, name, rows=(), drafts=None):
    directory = root / '.wuwei/days' / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'events.jsonl').write_text(''.join(
        json.dumps({'kind': kind, 'payload': payload, 'ts': name + 'T09:00:00+00:00'}) + '\n'
        for kind, payload in rows))
    if drafts is not None:
        (directory / 'state.json').write_text(json.dumps({'drafts': drafts}))


def history(root):
    day(root, TODAY, [('note', {'text': 'x', 'repo': 'fixture-org/forged'}),
                      ('guard.would_refuse', {'target': 'repo:fixture-org/shaped', 'reason': 'r'})])
    day(root, '2026-09-28', [('grant.used', {'target': 'repo:fixture-org/old', 'decision': 'D-1'}),
                             ('fast_checks.record', {'repo': 'fixture-org/kept', 'exit': 0})],
        drafts={'d1': {'channel': 'chat', 'status': 'sent', 'destination': 'C7'},
                'd2': {'channel': 'slack', 'status': 'dropped', 'destination': 'C8'}})
    day(root, '2026-09-07', [('grant.used', {'target': 'repo:fixture-org/ancient'})])


def test_seed_reads_the_last_30_days(ws):
    from wuwei import novelty
    history(ws)
    assert novelty.seed(ws) == 3
    rows = seen(ws)
    assert set(rows) == {'repo:fixture-org/old', 'repo:fixture-org/kept', 'channel:C7'}
    assert all(row['cleared']['by'] == 'seed' and row['first_seen'] == '2026-09-28' for row in rows.values())
    assert novelty.seed(ws) == 0
    empty(ws)
    (ws / '.wuwei/memory/targets.json').write_text(json.dumps(
        {'targets': {'channel:C7': {'first_seen': TODAY, 'cleared': None}}}))
    assert novelty.seed(ws) == 2
    assert seen(ws)['channel:C7']['cleared'] is None


def test_seed_skips_an_unreadable_day(ws, capsys):
    from wuwei import novelty
    history(ws)
    (ws / '.wuwei/days/2026-10-01').mkdir()
    (ws / '.wuwei/days/2026-10-01/events.jsonl').write_text('{broken')
    assert novelty.seed(ws, write=False) == 3
    assert 'warning: novelty seed skipped 2026-10-01' in capsys.readouterr().err
    assert not (ws / '.wuwei/memory/targets.json').exists()


def test_lazy_seed(ws):
    from wuwei import novelty
    history(ws)
    config = workspace.load_config(ws)
    assert novelty.novel(ws, config, ['repo:fixture-org/old', 'repo:fixture-org/new']) == ['repo:fixture-org/new']
    assert seen(ws)['repo:fixture-org/old']['cleared']['by'] == 'seed'


def test_upgrade_seeds_the_seen_set(ws, capsys):
    import shutil
    from wuwei.__main__ import main
    shutil.rmtree(ws / '.wuwei')
    assert main(['init']) == 0
    history(ws)
    capsys.readouterr()
    assert main(['init', '--upgrade', '--dry-run']) == 0
    assert 'Would upgrade memory/targets.json: 3 targets seen in the last 30 days' in capsys.readouterr().out
    assert not (ws / '.wuwei/memory/targets.json').exists()
    assert main(['init', '--upgrade']) == 0
    assert 'Upgraded memory/targets.json: 3 targets seen in the last 30 days' in capsys.readouterr().out
    assert 'repo:fixture-org/old' in seen(ws)
    save(ws, retry('repo:fixture-org/old'), name='D-1.md')
    assert route(ws, capsys, 'D-1') == (0, 'mandate')


# Phase 3: decision route.

from test_decision import save, events  # noqa: E402
from test_decision_classes import record, route  # noqa: E402

NEW = 'repo:fixture-org/new'
FIRST = f'owner\nfirst time for {NEW}; one owner answer on a card clears it'


def retry(target=NEW, cls='retry', **kwargs):
    return record(cls=cls, **kwargs).replace('Context: tests/test_example.py records the failure.',
                                                 f'Context: tests/test_example.py; touches {target}.')


def answer(root, ident, option='A', monkeypatch=None):
    from wuwei.commands.decision import owner_outcome
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    return owner_outcome(SimpleNamespace(id=ident, option=option), root=root)


def test_a_routine_record_on_a_new_repo_asks_once(ws, capsys, monkeypatch):
    from wuwei import state
    save(ws, retry(), name='D-1.md')
    assert route(ws, capsys, 'D-1') == (0, FIRST)
    data = state.read_state(ws)
    assert data['decision_routes']['D-1']['novel'] == [NEW]
    assert next(row for row in events(ws) if row['kind'] == 'decision.routed')['payload']['novel'] == [NEW]
    assert not data.get('decision_outcomes')
    assert seen(ws)[NEW] == {'first_seen': TODAY, 'cleared': None}
    before = len(events(ws))
    assert route(ws, capsys, 'D-1') == (0, 'owner')
    assert len(events(ws)) == before
    from wuwei.__main__ import main
    assert main(['decision', 'show', 'D-1', '--widget']) == 0
    question = json.loads(capsys.readouterr().out)[0]['question']
    assert question.endswith(f'First time for {NEW}: your answer clears it.')
    assert answer(ws, 'D-1', monkeypatch=monkeypatch) == (0, 'A')
    cleared = seen(ws)[NEW]['cleared']
    assert cleared['by'] == 'owner' and cleared['evidence'] == 'D-1'
    save(ws, retry(), name='D-2.md')
    assert route(ws, capsys, 'D-2') == (0, 'mandate')


def test_a_widget_without_novel_is_unchanged(ws, capsys):
    from wuwei.__main__ import main
    save(ws, record(door='one-way', confidence='low'), name='D-1.md')
    assert route(ws, capsys, 'D-1') == (0, 'owner')
    assert main(['decision', 'show', 'D-1', '--widget']) == 0
    assert 'First time' not in capsys.readouterr().out


def test_a_damaged_set_at_answer_time(ws, capsys, monkeypatch):
    from wuwei import state
    save(ws, retry(), name='D-1.md')
    assert route(ws, capsys, 'D-1') == (0, FIRST)
    (ws / '.wuwei/memory/targets.json').write_text('not json')
    code, message = answer(ws, 'D-1', monkeypatch=monkeypatch)
    assert code == 2 and 'D-1 recorded; the seen set was not updated' in message
    assert state.read_state(ws)['decision_outcomes']['D-1']['decided_by'] == 'owner'


def test_a_damaged_set_fails_the_route(ws, capsys):
    from wuwei.__main__ import main
    save(ws, retry(), name='D-1.md')
    empty(ws)
    (ws / '.wuwei/memory/targets.json').write_text('not json')
    assert main(['decision', 'route', 'D-1']) == 2
    assert 'memory/targets.json is damaged' in capsys.readouterr().err


def test_supervised_routes_as_today(ws, capsys, monkeypatch):
    from wuwei import state
    from test_decision import SUPERVISED
    (ws / '.wuwei/config.toml').write_text(SUPERVISED)
    save(ws, retry(cls='design'), name='D-1.md')
    assert route(ws, capsys, 'D-1') == (0, 'seat')
    save(ws, retry(door='one-way'), name='D-2.md')
    assert route(ws, capsys, 'D-2') == (0, 'owner')
    assert state.read_state(ws)['decision_routes']['D-2']['novel'] == [NEW]
    assert answer(ws, 'D-2', monkeypatch=monkeypatch) == (0, 'A')
    assert seen(ws)[NEW]['cleared']['evidence'] == 'D-2'


def test_template_asks_for_keys():
    from wuwei import decision, novelty
    from wuwei.commands.decision import template
    text = template()
    assert decision.lint(text)[0] == 0
    assert 'repo:<org>/<name>' in text and 'workflow:<name>' in text
    assert novelty.keys(text) == []


# Phase 4: outward.

OUTWARD = '''[owner]
name = "Pat Example"
pronouns = "they/them"
[outbound]
work_channels = ["C1"]
[outbound.owner.slack]
user = "U0OWNER"
'''


def post(root, channel, text='The cache is thread safe.'):
    from wuwei.guards.outward import check_tier
    return check_tier({'cwd': str(root), 'tool_name': 'mcp__slack__post_message',
                       'tool_input': {'text': text, 'channel': channel}, 'hook_event_name': 'PreToolUse',
                       'session_id': 'test', 'transcript_path': str(root / 'transcript.jsonl'),
                       'tool_use_id': 'test-call'})


@pytest.fixture
def chat(ws):
    from fakes.integrity import seed
    (ws / '.wuwei/config.toml').write_text(OUTWARD)
    seed(ws)
    return ws


def draft_id(reason):
    import re
    return re.search(r'drafts show (\S+)', reason)[1]


def test_a_first_time_channel_holds_once(chat, capsys):
    from wuwei import drafts
    from wuwei.__main__ import main
    code, reason = post(chat, 'C9')
    assert code == 1 and 'bin/wuwei drafts show ' in reason
    ident = draft_id(reason)
    row = drafts.read(__import__('wuwei.state', fromlist=['x']).read_state(chat))[ident]
    assert 'first time for channel:C9; approving this draft clears it, then the tier table decides' in row['tier_reason']
    capsys.readouterr()
    assert main(['drafts', 'show', ident, '--widget']) == 0
    assert 'first time for channel:C9' in capsys.readouterr().out
    assert post(chat, 'C1') == (0, '')
    assert post(chat, 'U0OWNER') == (0, '')
    assert drafts.approve(chat, ident).exit == 0
    cleared = seen(chat)['channel:C9']['cleared']
    assert cleared['by'] == 'owner' and cleared['evidence'] == ident
    assert post(chat, 'C9') == (0, '')
    assert post(chat, 'C9', 'tests passed') == (0, '')


def test_a_dropped_draft_clears_nothing(chat):
    from wuwei import drafts
    code, reason = post(chat, 'C10')
    assert code == 1
    assert drafts.drop(chat, draft_id(reason)).exit == 0
    assert seen(chat)['channel:C10']['cleared'] is None
    assert post(chat, 'C10')[0] == 1


def test_a_damaged_set_names_the_file_on_send(chat):
    (chat / '.wuwei/memory').mkdir(exist_ok=True)
    (chat / '.wuwei/memory/targets.json').write_text('{')
    code, reason = post(chat, 'C9')
    assert code and 'memory/targets.json is damaged' in reason and 'config check' not in reason


def test_supervised_sends_to_a_first_time_channel(chat):
    with (chat / '.wuwei/config.toml').open('a') as stream:
        stream.write('[autonomy]\nmode = "supervised"\n')
    assert post(chat, 'C9') == (0, '')


# Phase 5: grants.

from test_grants import CONFIG as GRANTS, DEPLOY, run as deploy, events as grant_events  # noqa: E402

PATTERN = ('[grants]\nstanding = [{action = "deploy", target = "repo:fixture-org/*", scope = "always", '
           'decision = "D-8", date = "2026-10-01"}]\n')
FRESH = 'gh workflow run deploy-production.yml -R fixture-org/new'


@pytest.fixture
def granted(tmp_path, monkeypatch):
    from fakes.integrity import seed
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(GRANTS + PATTERN)
    seed(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', TODAY + 'T09:00:00Z')
    return tmp_path


def test_a_standing_pattern_does_not_cover_a_new_repo(granted, monkeypatch):
    assert deploy(granted) == (0, '')
    code, reason = deploy(granted, FRESH)
    assert code == 1 and f'first time for {NEW}' in reason and 'decision show D-1 --widget' in reason
    assert [row['target'] for row in grant_events(granted, 'grant.used')] == ['repo:fixture-org/app']
    assert answer(granted, 'D-1', 'once', monkeypatch) == (0, 'once')
    assert seen(granted)[NEW]['cleared']['evidence'] == 'D-1'
    assert deploy(granted, FRESH) == (0, '') and deploy(granted, FRESH) == (0, '')
    assert grant_events(granted, 'grant.used')[-1]['decision'] == 'D-8'


def test_keep_owner_only_leaves_the_repo_novel(granted, monkeypatch):
    deploy(granted, FRESH)
    assert answer(granted, 'D-1', 'keep', monkeypatch) == (0, 'keep')
    assert seen(granted)[NEW]['cleared'] is None
    code, reason = deploy(granted, FRESH)
    assert code == 1 and 'the owner kept it owner-only (D-1)' in reason
    assert deploy(granted) == (0, '')


def test_supervised_standing_pattern_as_today(granted):
    with (granted / '.wuwei/config.toml').open('a') as stream:
        stream.write('[autonomy]\nmode = "supervised"\n')
    assert deploy(granted, FRESH) == (0, '')


# Phase 7: report and why.

def test_report_and_why(ws, capsys, monkeypatch):
    from wuwei import report
    from wuwei.__main__ import main
    (ws / '.wuwei/config.toml').write_text(CONFIG)
    save(ws, retry(), name='D-1.md')
    assert route(ws, capsys, 'D-1') == (0, FIRST)
    text = report.build(ws)
    assert text.index('## Decisions by class') < text.index('## First time today') < text.index('## Merged')
    assert f'## First time today\n- {NEW}: not cleared\n' in text
    assert main(['why', NEW]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f'target: {NEW}', f'first seen: {TODAY}', 'cleared: not yet; one owner answer on a card clears it']
    assert main(['why', 'D-1']) == 0
    assert f'novel: first time for {NEW}' in capsys.readouterr().out
    assert answer(ws, 'D-1', monkeypatch=monkeypatch) == (0, 'A')
    rows = json.loads((ws / '.wuwei/memory/targets.json').read_text())
    rows['targets'].update({
        'channel:C7': {'first_seen': TODAY, 'cleared': {'by': 'seed', 'evidence': f'days/{TODAY}', 'at': TODAY}},
        'channel:C8': {'first_seen': '2026-10-01', 'cleared': None}})
    (ws / '.wuwei/memory/targets.json').write_text(json.dumps(rows))
    section = report.build(ws).split('## First time today\n')[1].split('\n\n')[0].splitlines()
    assert section == ['- channel:C7: cleared by seed', f'- {NEW}: cleared by owner (D-1)']
    assert main(['why', NEW]) == 0
    assert capsys.readouterr().out.splitlines()[2] == f'cleared: by owner on {TODAY} (D-1)'
    assert main(['why', 'repo:fixture-org/app']) == 0
    assert capsys.readouterr().out.splitlines() == ['target: repo:fixture-org/app', 'seen: configured in config.toml']
    assert main(['why', 'repo:fixture-org/never']) == 0
    assert capsys.readouterr().out.splitlines()[1] == 'not seen yet'


def test_report_without_first_time(ws, capsys):
    from wuwei import report
    save(ws, record(door='one-way', confidence='low'), name='D-1.md')
    route(ws, capsys, 'D-1')
    assert '## First time today\nnone\n' in report.build(ws)


# Phase 8: the three invariants (design 5.8.1; move to tests/test_invariants.py when it exists).

def test_invariant_a_novel_target_never_runs_above_l1(granted, capsys, monkeypatch):
    from wuwei import state
    monkeypatch.chdir(granted)
    save(granted, retry(), name='D-5.md')
    assert route(granted, capsys, 'D-5')[1].startswith('owner\nfirst time for')
    assert 'D-5' not in state.read_state(granted).get('decision_outcomes', {})
    code, reason = post(granted, 'C9')
    assert code == 1 and 'first time for channel:C9' in reason
    assert deploy(granted, FRESH)[0] == 1 and grant_events(granted, 'grant.used') == []


def test_invariant_b_only_an_owner_answer_or_the_seed_clears(ws, capsys):
    from test_decision import SUPERVISED
    from wuwei import novelty, state
    save(ws, retry(), name='D-1.md')
    route(ws, capsys, 'D-1')
    (ws / '.wuwei/config.toml').write_text(SUPERVISED)
    save(ws, retry(cls='design'), name='D-2.md')
    assert route(ws, capsys, 'D-2') == (0, 'seat')
    state.append_event('note', {'text': 'seen', 'repo': 'fixture-org/new'}, ws)
    assert novelty.seed(ws) == 0
    assert seen(ws)[NEW]['cleared'] is None  # a dropped draft: test_a_dropped_draft_clears_nothing


def test_invariant_c_a_seat_cannot_write_the_seen_set(ws):
    from wuwei.guards.protect_state import check_bash, check_file
    call = {'hook_event_name': 'PreToolUse', 'session_id': 'seat', 'cwd': str(ws),
            'transcript_path': str(ws / 'transcript.jsonl')}
    assert check_file({**call, 'tool_name': 'Write', 'tool_input': {'file_path': '.wuwei/memory/targets.json'}})[0] == 1
    assert check_bash({**call, 'tool_name': 'Bash',
                       'tool_input': {'command': 'echo {} > .wuwei/memory/targets.json'}})[0] == 1
