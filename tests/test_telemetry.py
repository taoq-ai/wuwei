"""Telemetry (#422, design 5.13): a weekly aggregate off the hook path and sharing."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from wuwei import state, telemetry, watch, workspace
from wuwei.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-10-03T12:00:00+00:00'  # a Saturday in 2026-W40; 2026-W39 is final


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\ntimezone = "UTC"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    return tmp_path


def config(root, extra=''):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + extra)
    return workspace.load_config(root)


def write_day(root, name, events, *, data=None, traces=0, decisions=None):
    directory = root / '.wuwei/days' / name
    (directory / 'decisions').mkdir(parents=True, exist_ok=True)
    (directory / 'events.jsonl').write_text(''.join(
        json.dumps({'kind': kind, 'payload': payload, 'ts': f'{name}T{at}:00+00:00'}) + '\n'
        for at, kind, payload in events))
    if traces:
        (directory / 'traces.jsonl').write_text('{"resourceSpans": []}\n' * traces)
    if data is not None:
        (directory / 'state.json').write_text(json.dumps({**state.DAY_DEFAULTS, **data}))
    for identifier, text in (decisions or {}).items():
        (directory / 'decisions' / f'{identifier}.md').write_text(text)
    return directory


def seed_week(root):
    """2026-W39: two days of every signal 5.13 reads; the first is the workspace's earliest."""
    write_day(root, '2026-09-21', [
        ('09:00', 'plan.approved', {'items': ['A', 'B']}),
        ('09:05', 'heartbeat: clock', {'probes': {'refused': {'result': 'ok', 'ms': 80},
                                                  'allowed': {'result': 'ok', 'ms': 100},
                                                  'state_write': {'result': 'ok', 'ms': 120},
                                                  'read_loop': {'result': 'unmeasured', 'value': 'timeout'}}}),
        ('09:10', 'hook.refusal', {'reason': 'r', 'refusals': [{'guard': 'commit_push', 'reason': 'r', 'exit': 1}]}),
        ('09:20', 'hook.refusal', {'reason': 'config.toml: bad'}),
        ('09:30', 'guard.would_refuse', {'guard': 'outward', 'exit': 1, 'reason': 'r', 'area': 'outward'}),
        ('09:40', 'seat launched', {'name': 's1', 'item': 'A'}),
        ('10:00', 'seat.usage', {'item': 'A', 'usage': {'duration': 600}}),
        ('10:00', 'seat stopped', {'name': 's1'}),
        ('10:05', 'state.write', {'phase_changes': {'A': 'gate'}}),
        ('10:06', 'gate.tiered', {'item': 'A', 'computed': 'standard'}),
        ('10:30', 'gate.received', {'item': 'A'}),
        ('10:50', 'gate.received', {'item': 'A'}),
        ('11:00', 'state.write', {'phase_changes': {'A': 'fix'}}),
        ('11:00', 'hook.refusal', {'reason': 'r', 'refusals': [{'guard': 'pr', 'reason': 'r'}]}),
        ('12:00', 'seat launched', {'name': 's2', 'item': 'B'}),
        ('12:00', 'decision.routed', {'id': 'D-1', 'reversibility': 'two-way'}),
        ('12:00', 'decision.routed', {'id': 'D-2', 'reversibility': 'two-way', 'item': 'B'}),
        ('12:30', 'state.recovered', {}),
    ], traces=3, data={
        'items': {'A': {'phase': 'fix'}, 'B': {'phase': 'planned'}},
        'decision_routes': {'D-1': {'recommendation': 'Yes'}, 'D-2': {'recommendation': 'No'}},
        'decision_outcomes': {'D-1': {'option': 'Yes', 'decided_by': 'owner'}}},
        decisions={'D-1': 'Question: Should A ship?\nClass: approach\n', 'D-2': 'Question: Wait?\n'})
    write_day(root, '2026-09-22', [
        ('12:00', 'decision.decided', {'id': 'D-1', 'decided_by': 'owner'}),
        ('14:00', 'decision.decided', {'id': 'D-2', 'decided_by': 'owner'}),
        ('14:10', 'decision.decided', {'id': 'D-3', 'decided_by': 'mandate'}),
        ('14:20', 'decision.decided', {'id': 'D-4', 'decided_by': 'seat'}),
        ('14:30', 'decision.reversed', {'id': 'D-5', 'decided_by': 'owner'}),
        ('15:00', 'negotiation.loop', {'item': 'B'}),
        ('15:10', 'build.parked', {'item': 'B'}),
        ('15:20', 'mcp.decided', {}),
        ('18:00', 'state.write', {'phase_changes': {'A': 'merged'}}),
    ], data={'items': {'A': {'phase': 'merged', 'gates': {'computed': 'standard'}}}})


EXPECTED = {
    'days': 2, 'tool_calls': 3, 'refusals': {'commit_push': 1, 'pr': 1}, 'unmeasured': {'config': 1},
    'warnings': {'outward': 1}, 'refusal_rate': 0.4, 'unmeasured_rate': 0.25, 'first_hour_refusals': 3,
    'hook_latency_ms': {'p50': 100, 'p95': 118, 'max': 120}, 'seats_launched': 2, 'seats_lost': 1,
    'seat_minutes': {'p50': 10, 'p90': 10}, 'phase_entries': {'gate': 1, 'fix': 1, 'merged': 1},
    'plan_to_merge_hours': {'p50': 33, 'p75': 33}, 'gate_rounds_per_item': {'p50': 2, 'max': 2},
    'fix_rounds_per_item': {'p50': 1, 'max': 1}, 'gate_tiers': {'standard': 1}, 'long_loops': 1,
    'stuck_parks': 1, 'decisions': 4, 'decisions_by_class': {'approach': 1, 'other': 3},
    'decided_by': {'owner': 2, 'seat': 1}, 'reversals': 1,
    'owner_wait_hours': {'p50': 25, 'p90': 25.8}, 'owner_asks_per_item': 1, 'unnecessary_asks': 1,
    'owner_actions': 2, 'escaped_by_tier': {'standard': {'merged': 1, 'escaped': 0}},
    'lead_time_merge_hours': 33, 'lead_time_deploy_hours': 'unmeasured', 'deploys_per_week': 'unmeasured',
    'change_failure_rate': 0, 'time_to_restore_hours': 'unmeasured',
}


def test_aggregate_every_metric(ws):
    seed_week(ws)
    found = telemetry.week_file(ws, workspace.load_config(ws), '2026-W39', write=False)
    metrics = found['metrics']
    assert isinstance(metrics.pop('aggregation_ms'), int)
    assert metrics == EXPECTED
    assert set(telemetry.METRICS) == set(EXPECTED) | {'aggregation_ms'}
    assert 'evidence' not in found
    assert found['config'] == {'posture': 'guarded', 'profile': 'strict', 'repositories': 0,
                               'adapters': workspace.load_config(ws)['adapters']}
    assert found['versions']['python'] == f'{sys.version_info[0]}.{sys.version_info[1]}'
    assert (found['schema'], found['week'], found['final']) == (1, '2026-W39', True)


def test_empty_week_is_unmeasured_and_first_hour_only_in_the_earliest_week(ws):
    seed_week(ws)
    write_day(ws, '2026-09-28', [])
    metrics = telemetry.week_file(ws, workspace.load_config(ws), '2026-W40', write=False)['metrics']
    assert (metrics['days'], metrics['tool_calls']) == (1, 'unmeasured')
    assert metrics['refusal_rate'] == metrics['unmeasured_rate'] == metrics['hook_latency_ms'] == 'unmeasured'
    assert metrics['refusals'] == {} and 'first_hour_refusals' not in metrics


def test_vocabularies_match_their_sources():
    from wuwei import decision, guards, registry
    assert telemetry.GUARDS == tuple(sorted(guards.MODULES))
    assert {area for area in guards.AREAS.values() if area} <= set(telemetry.AREAS)
    assert set(telemetry.PHASES) == set(state.PHASES)
    assert telemetry.TIERS == workspace.SCHEMA['repos'][0]['gates']['floor'][2]
    assert set(telemetry.CLASSES) == set(decision.CLASSES)
    assert telemetry.AREAS == workspace.AREAS and telemetry.POSTURES == tuple(workspace.POSTURES)
    assert telemetry.PROFILES == workspace.SCHEMA['profile'][2]
    # #419: load_config mirrors docs.system into adapters.docs.
    assert set(telemetry.ADAPTERS) == set(workspace.SCHEMA['adapters']) | {'docs', 'inbound'}  # inbound: weeks before #810
    assert {port: tuple(registry.known(port)) for port in telemetry.ADAPTERS if port != 'inbound'} == {
        port: names for port, names in telemetry.ADAPTERS.items() if port != 'inbound'}


def test_validate_runs_without_the_wuwei_package(tmp_path):
    # The collector bundles the file alone: only its own directory on sys.path.
    (tmp_path / 'telemetry.py').write_text((ROOT / 'cli/wuwei/telemetry.py').read_text())
    script = ('import telemetry, sys\n'
              'try:\n    telemetry.validate({})\nexcept ValueError as exc:\n    print(exc)\n'
              'print("wuwei" in sys.modules)\n')
    result = subprocess.run([sys.executable, '-S', '-E', '-c', script], cwd=tmp_path, capture_output=True, text=True)
    assert result.stdout.split('\n')[:2] == ['top-level keys; remove .wuwei/metrics/<week>.json, then run bin/wuwei metrics --week <week>', 'False'], result.stderr


def test_week_file_writes_final_weeks_and_keeps_marks(ws):
    seed_week(ws)
    write_day(ws, '2026-09-28', [])
    cfg = workspace.load_config(ws)
    current = telemetry.week_file(ws, cfg, '2026-W40')
    assert current['final'] is False and 'proposals' not in current
    path = ws / '.wuwei/metrics/2026-W39.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'week': '2026-W39', 'shared': 'anonymous', 'ready': True, 'presented': True}))
    final = telemetry.week_file(ws, cfg, '2026-W39')
    assert final['final'] is True and 'proposals' not in final and 'presented' not in final
    assert (final['shared'], final['ready']) == ('anonymous', True)
    assert json.loads(path.read_text()) == final == telemetry.load_week(ws, '2026-W39')
    assert final['metrics']['owner_wait_hours'] == {'p50': 25, 'p90': 25.8}
    assert telemetry.load_week(ws, '2026-W30') is None
    with pytest.raises(ValueError):
        telemetry.load_week(ws, 'bad')


def events(root, prefix='telemetry.'):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return [(row['kind'], {k: v for k, v in row['payload'].items() if k != 'prs_seen'})
            for row in rows if row['kind'].startswith(prefix)]


@pytest.mark.parametrize('limit', ['size', 'time'])
def test_step_skips_past_the_budget_and_keeps_the_previous_file(ws, monkeypatch, limit):
    seed_week(ws)
    cfg = workspace.load_config(ws)
    before = telemetry.week_file(ws, cfg, '2026-W39')
    monkeypatch.setattr(telemetry, 'MAX_DAY_BYTES' if limit == 'size' else 'BUDGET_SECONDS', 100 if limit == 'size' else -1)
    assert telemetry.step(ws, cfg) == f'skipped: {limit}'
    assert events(ws) == [('telemetry.skipped', {'week': '2026-W39', 'reason': limit})]
    assert watch.saved(ws)['telemetry'] == {'week': '2026-W39', 'skipped': limit}
    assert telemetry.load_week(ws, '2026-W39') == before and telemetry.load_week(ws, '2026-W40') is None
    assert telemetry.step(ws, cfg) == 'not due'
    assert len(events(ws)) == 1


def test_step_refreshes_and_finalises_once_a_day(ws, monkeypatch):
    seed_week(ws)
    cfg = workspace.load_config(ws)
    assert telemetry.step(ws, cfg) == '2026-W40'
    assert telemetry.load_week(ws, '2026-W40')['final'] is False
    assert telemetry.load_week(ws, '2026-W39')['final'] is True
    assert watch.saved(ws)['telemetry'] == {'week': '2026-W40'} and events(ws) == []
    assert telemetry.step(ws, cfg) == 'not due'
    monkeypatch.setenv('WUWEI_NOW', '2026-10-04T13:00:00+00:00')
    assert telemetry.step(ws, cfg) == '2026-W40'


def deploying(root, monkeypatch, unread_deploys, result):
    # #586: the real deploy reader over a fake code host; A's pull request is in acme/widget.
    from fakes.code_host import Fake
    from wuwei import metrics, registry
    monkeypatch.setattr(metrics, '_deploys', unread_deploys)
    fake = Fake({'deployments': result})
    monkeypatch.setattr(registry, 'load', lambda kind, settings: fake)
    path = root / '.wuwei/days/2026-09-22/state.json'
    data = json.loads(path.read_text())
    data['items']['A']['pr'] = 'acme/widget#1'
    path.write_text(json.dumps(data))
    return fake, config(root, '[[repos]]\nname = "acme/widget"\npath = "repo"\ndefault_branch = "main"\n')


def test_final_week_reads_the_code_host_once_per_repository(ws, monkeypatch, unread_deploys):
    from wuwei.registry import Result
    seed_week(ws)
    fake, cfg = deploying(ws, monkeypatch, unread_deploys, Result(0, {'source': 'deployments', 'at': [
        '2026-09-22T20:00:00Z', '2026-09-23T09:00:00Z']}))
    found = telemetry.week_file(ws, cfg, '2026-W39', write=False)
    assert [call[0] for call in fake.calls] == ['deployments']
    metrics = found['metrics']
    assert (metrics['deploys_per_week'], metrics['lead_time_deploy_hours']) == (2, 35)
    found['versions']['plugin'] = '0.12.0'
    telemetry.validate(telemetry.payload(found))
    current = telemetry.week_file(ws, cfg, '2026-W40', write=False)['metrics']
    assert len(fake.calls) == 1 and current['deploys_per_week'] == 'unmeasured'


def test_failed_code_host_leaves_the_deploy_keys_unmeasured(ws, monkeypatch, unread_deploys):
    from wuwei.registry import Result
    seed_week(ws)
    _, cfg = deploying(ws, monkeypatch, unread_deploys, Result(2, None, 'offline'))
    assert telemetry.step(ws, cfg) == '2026-W40' and events(ws) == []
    metrics = telemetry.load_week(ws, '2026-W39')['metrics']
    assert metrics['deploys_per_week'] == metrics['lead_time_deploy_hours'] == 'unmeasured'
    assert metrics['lead_time_merge_hours'] == 33


def test_step_off_writes_nothing(ws):
    seed_week(ws)
    cfg = config(ws, '[telemetry]\nenabled = false\n')
    assert telemetry.step(ws, cfg) == 'off'
    assert not (ws / '.wuwei/metrics').exists() and not workspace.day_dir(ws).exists()


def final_week(root, **changes):
    found = {'week': '2026-W39', 'final': True, 'schema': 1,
             'versions': {'plugin': '0.12.0', 'python': '3.12', 'os': 'linux'},
             'config': {'posture': 'guarded', 'profile': 'strict', 'repositories': 1,
                        'adapters': {'tracker': 'none', 'code_host': 'github'}},
             'metrics': {'days': 2, 'warnings': {}, 'escaped_by_tier': 'unmeasured',
                         'fix_rounds_per_item': 'unmeasured'}}
    telemetry.save_week(root, {**found, **changes})
    return found


def test_a_stored_week_with_proposals_still_loads(ws, capsys):
    legacy = {'proposals': [{'rule': 'fast-checks', 'evidence': '5 items', 'command': 'bin/wuwei calibrate --measure'}],
              'evidence': {'verdict_items': 5, 'external_wait_hours': []}, 'presented': True}
    final_week(ws, **legacy)
    found = telemetry.load_week(ws, '2026-W39')
    assert found['proposals'] == legacy['proposals']
    shared = telemetry.validate(telemetry.payload(found, token='a' * 32))
    assert not set(legacy) & set(shared)
    assert main(['telemetry', 'preview']) == 0
    assert 'proposals' not in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        main(['telemetry', 'proposals'])
    assert exc.value.code == 2


CORPUS = {'repository': 'acme/secret-widget', 'path': '/srv/acme/widget/main.py', 'handle': '@pat-lee',
          'ticket': 'ACME-1234', 'item': 'acme-1234-login', 'reason': 'force-push to release-branch refused',
          'time': '2026-09-21T09:10:00'}


def seed_corpus(root):
    """Every record field that carries a name, a path, a reason or a time holds a corpus value."""
    item, reason = CORPUS['item'], CORPUS['reason']
    write_day(root, '2026-09-21', [
        ('09:00', 'plan.approved', {'items': [item]}),
        ('09:10', 'hook.refusal', {'reason': reason, 'target': CORPUS['path'], 'refusals': [
            {'guard': 'commit_push', 'reason': reason, 'exit': 1}]}),
        ('09:20', 'guard.would_refuse', {'guard': 'outward', 'exit': 1, 'reason': reason, 'target': CORPUS['path'],
                                         'session': CORPUS['handle'], 'item': item}),
        ('09:30', 'seat launched', {'name': CORPUS['handle'], 'item': item}),
        ('09:40', 'gate.received', {'item': item, 'role': CORPUS['handle'], 'verdict': reason}),
        ('09:50', 'decision.routed', {'id': 'D-1', 'item': item, 'ticket': CORPUS['ticket']}),
        ('10:00', 'mcp.decided', {'from': CORPUS['handle'], 'text': CORPUS['time']}),
        ('11:00', 'state.write', {'phase_changes': {item: 'merged'}, 'repo': CORPUS['repository']}),
    ], traces=1, data={'items': {item: {'phase': 'merged', 'note': CORPUS['ticket']}}},
        decisions={'D-1': f"Question: Should {item} wait on {CORPUS['ticket']}?\nClass: approach\n"})


def test_payload_carries_nothing_identifying(ws):
    seed_corpus(ws)
    cfg = config(ws, f'[[repos]]\nname = "{CORPUS["repository"]}"\npath = "{CORPUS["path"]}"\n'
                 'default_branch = "release-branch"\n')
    found = telemetry.week_file(ws, cfg, '2026-W39')
    shared = telemetry.payload(found, token='a' * 32)
    assert set(shared) == {'schema', 'week', 'versions', 'config', 'metrics', 'token'}
    found['versions']['plugin'] = '0.12.0'  # a checkout's version may be empty; the rule is tested below
    text = json.dumps(telemetry.validate(telemetry.payload(found, token='a' * 32)))
    for value in [*CORPUS.values(), 'acme', 'pat-lee', 'release-branch', 'D-1', '09:10']:
        assert value not in text, value
    assert set(telemetry.payload(found)) == {'schema', 'week', 'versions', 'config', 'metrics'}


@pytest.mark.parametrize('where', ['value', 'inner key', 'adapter', 'version', 'top-level', 'size'])
@pytest.mark.parametrize('value', sorted(CORPUS.values()))
def test_validate_refuses_each_corpus_value(ws, where, value):
    shared = telemetry.payload(final_week(ws, versions={'plugin': '0.12.0', 'python': '3.12', 'os': 'linux'}))
    telemetry.validate(shared)
    if where == 'value':
        shared['metrics']['days'] = value
    elif where == 'inner key':
        shared['metrics']['warnings'] = {value: 1}
    elif where == 'adapter':
        shared['config']['adapters']['tracker'] = value
    elif where == 'version':
        shared['versions']['plugin'] = value
    elif where == 'top-level':
        shared[value] = 1
    else:
        shared['metrics']['refusals'] = {name: 10 ** 400 for name in telemetry.INNER}
    with pytest.raises(ValueError):
        telemetry.validate(shared)


def test_issue_is_a_table_without_the_token():
    found = {'schema': 1, 'week': '2026-W39', 'token': 'a' * 32, 'versions': {'os': 'linux'},
             'config': {}, 'metrics': {'refusals': {'pr': 2}, 'days': 3}}
    title, body = telemetry.issue(found)
    assert title == 'telemetry: 2026-W39'
    assert body.splitlines() == ['| key | value |', '|---|---|', '| metrics.days | 3 |',
                                 '| metrics.refusals.pr | 2 |', '| schema | 1 |', '| versions.os | linux |',
                                 '| week | 2026-W39 |']


def test_token_is_created_once_private(ws):
    value = telemetry.token(ws)
    path = ws / '.wuwei/metrics/token'
    assert len(value) == 32 and telemetry.token(ws) == value and path.stat().st_mode & 0o777 == 0o600
    path.write_text('nope\n')
    with pytest.raises(ValueError):
        telemetry.token(ws)


class Service:
    def __init__(self, *answers):
        self.answers, self.posts = list(answers), []

    def post(self, url, body, headers=None, timeout=5):
        self.posts.append((url, body, headers))
        answer = self.answers.pop(0) if self.answers else 200
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def service(monkeypatch):
    from wuwei import registry
    fake = Service()
    monkeypatch.setattr(registry, 'watch_service', lambda: fake)
    return fake


VERSIONS = {'versions': {'plugin': '0.12.0', 'python': '3.12', 'os': 'linux'}}


@pytest.mark.parametrize('answer, shared', [(201, True), (409, True), (500, False), (OSError('down'), False)])
def test_anonymous_posts_each_unshared_final_week(ws, service, answer, shared):
    cfg = config(ws, '[telemetry]\nshare = "anonymous"\nendpoint = "https://collector.test/v1"\n')
    final_week(ws, **VERSIONS)
    service.answers = [answer]
    telemetry.step(ws, cfg)
    (url, body, _), = service.posts
    assert url == 'https://collector.test/v1' and body['token'] == telemetry.token(ws) and body['week'] == '2026-W39'
    assert telemetry.load_week(ws, '2026-W39').get('shared') == ('anonymous' if shared else None)
    reason = {500: 'HTTP 500'}.get(answer, 'OSError')
    assert events(ws) == ([('telemetry.shared', {'week': '2026-W39', 'mode': 'anonymous'})] if shared else
                          [('telemetry.unsent', {'week': '2026-W39', 'mode': 'anonymous', 'reason': reason})])


def test_anonymous_tries_only_the_four_newest_weeks_and_needs_an_endpoint(ws, service):
    for number in range(30, 36):
        final_week(ws, week=f'2026-W{number}', **VERSIONS)
    cfg = config(ws, '[telemetry]\nshare = "anonymous"\n')
    telemetry.step(ws, cfg)
    assert service.posts == []
    assert [payload['reason'] for _, payload in events(ws)] == ['no endpoint; set telemetry.endpoint to an https URL'] * 4
    cfg = config(ws, 'endpoint = "https://collector.test/v1"\n')
    telemetry._share(ws, cfg)
    assert [body['week'] for _, body, _ in service.posts] == ['2026-W35', '2026-W34', '2026-W33', '2026-W32']


def test_invalid_payload_is_not_sent(ws, service):
    cfg = config(ws, '[telemetry]\nshare = "anonymous"\nendpoint = "https://collector.test/v1"\n')
    final_week(ws, versions={'plugin': '', 'python': '3.12', 'os': 'linux'})  # a checkout has no version
    telemetry.step(ws, cfg)
    assert service.posts == [] and events(ws) == [
        ('telemetry.unsent', {'week': '2026-W39', 'mode': 'anonymous', 'reason': 'versions'})]


@pytest.mark.parametrize('share', ['', 'off', 'attributed'])
def test_other_modes_post_nothing(ws, service, share):
    cfg = config(ws, f'[telemetry]\nshare = "{share}"\nendpoint = "https://collector.test/v1"\n')
    final_week(ws, **VERSIONS)
    telemetry.step(ws, cfg)
    telemetry._share(ws, cfg)
    assert service.posts == []
    assert events(ws) == ([('telemetry.ready', {'week': '2026-W39'})] if share == 'attributed' else [])


def test_preview_prints_every_mode_and_names_the_one_in_force(ws, capsys):
    assert main(['telemetry', 'preview']) == 1
    assert 'no final week yet' in capsys.readouterr().err
    final_week(ws, **VERSIONS)
    config(ws, '[telemetry]\nshare = "attributed"\n')
    assert main(['telemetry', 'preview']) == 0
    out = capsys.readouterr().out
    assert out.startswith('mode in force: attributed\n')
    assert 'anonymous: nothing is sent: no endpoint' in out and telemetry.token(ws) in out
    assert 'attributed: issue on taoq-ai/wuwei from your gh account (shows your login)' in out
    title, body = telemetry.issue(telemetry.payload(telemetry.load_week(ws, '2026-W39')))
    assert f'{title}\n{body}' in out and 'off: nothing leaves this machine' in out


def test_off_needs_no_confirmation(ws, capsys):
    assert main(['telemetry', 'off']) == 0
    assert workspace.load_config(ws)['telemetry']['share'] == 'off'
    assert events(ws) == [('telemetry.off', {})]
    assert main(['telemetry', 'off']) == 0 and len(events(ws)) == 1


@pytest.fixture
def host(ws, monkeypatch):
    from fakes.code_host import Fake
    from wuwei import integrity, registry
    from wuwei.registry import Result
    fake, answers = Fake({'issue': Result(0, {'number': 5, 'url': 'https://example.test/issues/5'})}), []
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: fake)
    monkeypatch.setattr(integrity, '_host_confirm', lambda digest, prompt=None: answers.pop(0))
    return fake, answers


def test_send_is_attributed_only_and_confirmed_on_the_host(ws, host, capsys, monkeypatch):
    from wuwei import security
    fake, answers = host
    final_week(ws, **VERSIONS)
    assert main(['telemetry', 'send']) == 1
    assert 'not "attributed"' in capsys.readouterr().err
    config(ws, '[telemetry]\nshare = "attributed"\n')
    answers.append(False)
    assert main(['telemetry', 'send']) == 1 and fake.calls == []
    security.initialize(ws / '.wuwei')
    canary = json.loads((ws / '.wuwei/security.json').read_text())['canary']
    from wuwei.commands import telemetry as command
    real = telemetry.issue
    monkeypatch.setattr(command.telemetry, 'issue', lambda found: (real(found)[0], real(found)[1] + canary))
    assert main(['telemetry', 'send']) == 1 and fake.calls == []
    monkeypatch.setattr(command.telemetry, 'issue', real)
    answers.append(True)
    assert main(['telemetry', 'send']) == 0
    (operation, (repo, title, body), _), = fake.calls
    assert (operation, repo) == ('issue', 'taoq-ai/wuwei')
    assert (title, body) == telemetry.issue(telemetry.payload(telemetry.load_week(ws, '2026-W39')))
    assert 'token' not in body
    assert telemetry.load_week(ws, '2026-W39')['shared'] == 'attributed'
    assert events(ws)[-1] == ('telemetry.shared', {'week': '2026-W39', 'mode': 'attributed'})
    assert main(['telemetry', 'send']) == 1 and 'already shared' in capsys.readouterr().err


def test_spans_carry_only_the_attributes(ws):
    seed_corpus(ws)
    day = write_day(ws, '2026-10-03', [
        ('09:00', 'hook.refusal', {'reason': CORPUS['reason'], 'target': CORPUS['path'],
                                   'refusals': [{'guard': 'pr', 'reason': CORPUS['reason'], 'exit': 2}]}),
        ('09:10', 'guard.would_refuse', {'guard': 'outward', 'exit': 1, 'posture': 'observe', 'item': 'A',
                                         'reason': CORPUS['reason'], 'target': CORPUS['path']}),
        ('09:20', 'seat launched', {'name': 's1', 'item': 'A'}),
        ('09:50', 'seat stopped', {'name': 's1'}),
        ('10:00', 'decision.routed', {'id': 'D-1', 'item': 'A'}),
        ('10:10', 'negotiation.loop', {'item': 'A', 'reason': CORPUS['reason']}),
        ('10:20', 'gate.received', {'item': 'A', 'verdict': CORPUS['reason']}),
    ])
    body, mark = telemetry.spans(ws, workspace.load_config(ws), None)
    assert mark == {'day': '2026-10-03', 'offset': (day / 'events.jsonl').stat().st_size}
    spans = body['resourceSpans'][0]['scopeSpans'][0]['spans']
    attributes = [{row['key']: row['value']['stringValue'] for row in span['attributes']} for span in spans]
    assert [span['name'] for span in spans] == ['wuwei.hook', 'wuwei.hook', 'wuwei.seat', 'wuwei.day']
    assert attributes[0] == {'wuwei.event': 'PreToolUse', 'wuwei.guard': 'pr', 'wuwei.outcome': 'unmeasured',
                             'wuwei.reason_code': 'pr.2', 'wuwei.posture': 'guarded'}
    assert attributes[1]['wuwei.outcome'] == 'warn' and attributes[1]['wuwei.item'] == 'A'
    assert int(spans[2]['endTimeUnixNano']) - int(spans[2]['startTimeUnixNano']) == 30 * 60 * 10 ** 9
    assert [event['name'] for event in spans[3]['events']] == ['decision.routed', 'negotiation.loop', 'gate.received']
    assert len({span['traceId'] for span in spans}) == 1 and len({span['spanId'] for span in spans}) == 4
    text = json.dumps(body)
    assert CORPUS['reason'] not in text and CORPUS['path'] not in text
    assert telemetry.spans(ws, workspace.load_config(ws), mark)[0]['resourceSpans'][0]['scopeSpans'][0]['spans'] == []


def test_otlp_metrics_sums_and_gauges():
    from datetime import datetime, timezone
    body = telemetry.otlp_metrics({'metrics': {'days': 2, 'refusal_rate': 0.4, 'tool_calls': 'unmeasured',
                                               'refusals': {'pr': 2}, 'hook_latency_ms': {'p50': 80, 'max': 90.5}}},
                                  datetime(2026, 10, 3, tzinfo=timezone.utc))
    rows = {row['name']: row for row in body['resourceMetrics'][0]['scopeMetrics'][0]['metrics']}
    assert set(rows) == {'wuwei.days', 'wuwei.refusal_rate', 'wuwei.refusals', 'wuwei.hook_latency_ms'}
    assert rows['wuwei.days']['sum']['dataPoints'][0]['asInt'] == '2'
    assert rows['wuwei.refusal_rate']['gauge']['dataPoints'][0]['asDouble'] == 0.4
    point, = rows['wuwei.refusals']['sum']['dataPoints']
    assert point['attributes'] == [{'key': 'wuwei.key', 'value': {'stringValue': 'pr'}}]
    assert len(rows['wuwei.hook_latency_ms']['gauge']['dataPoints']) == 2


@pytest.mark.parametrize('answer', [200, 503])
def test_step_exports_to_the_owners_platform(ws, service, answer, capsys):
    import os
    seed_week(ws)
    (ws / '.wuwei/env').write_text('OTLP_HEADERS=Authorization=Bearer s3cr3t,X-Team=a\n')
    os.chmod(ws / '.wuwei/env', 0o600)
    cfg = config(ws, '[telemetry.otlp]\nendpoint = "https://otel.test/"\nheaders_env = "OTLP_HEADERS"\n')
    state.append_event('hook.refusal', {'refusals': [{'guard': 'pr', 'exit': 1}]}, ws)
    service.answers = [answer, 200]
    telemetry.step(ws, cfg)
    (traces, _, headers), (metrics, body, _) = service.posts
    assert (traces, metrics) == ('https://otel.test/v1/traces', 'https://otel.test/v1/metrics')
    assert headers == {'Authorization': 'Bearer s3cr3t', 'X-Team': 'a'}
    assert body['resourceMetrics'][0]['scopeMetrics'][0]['metrics']
    saved = watch.saved(ws)
    assert (saved.get('otlp_at') is not None) == (answer == 200)
    assert events(ws) == ([] if answer == 200 else
                          [('telemetry.unsent', {'mode': 'otlp', 'reason': 'HTTP 503'})])
    for path in workspace.day_dir(ws).iterdir():
        assert 's3cr3t' not in path.read_text()
    assert 's3cr3t' not in capsys.readouterr().out


def test_otlp_posts_on_every_sweep_and_resends_failed_metrics(ws, service):
    seed_week(ws)
    cfg = config(ws, '[telemetry.otlp]\nendpoint = "https://otel.test/"\n')
    write_day(ws, '2026-10-03', [('09:00', 'hook.refusal', {'refusals': [{'guard': 'pr', 'exit': 1}]})])
    service.answers = [200, 503]
    assert telemetry.step(ws, cfg) == '2026-W40'
    assert telemetry.load_week(ws, '2026-W39').get('otlp') is None
    state.append_event('hook.refusal', {'refusals': [{'guard': 'commit_push', 'exit': 1}]}, ws)
    service.posts = []
    assert telemetry.step(ws, cfg) == 'not due'
    (traces, body, _), (metrics, _, _) = service.posts
    assert (traces, metrics) == ('https://otel.test/v1/traces', 'https://otel.test/v1/metrics')
    guards = [row['value']['stringValue'] for span in body['resourceSpans'][0]['scopeSpans'][0]['spans']
              for row in span['attributes'] if row['key'] == 'wuwei.guard']
    assert guards == ['commit_push']
    assert telemetry.load_week(ws, '2026-W39')['otlp'] is True
    service.posts = []
    telemetry.step(ws, cfg)
    assert service.posts == []


def test_week_stored_with_an_inbound_adapter_still_validates_previews_and_sends(ws, host, capsys):
    # A week recorded before #810 names adapters.inbound; it stays valid and shareable.
    fake, answers = host
    old = {'posture': 'guarded', 'profile': 'strict', 'repositories': 1,
           'adapters': {'tracker': 'none', 'code_host': 'github', 'inbound': 'slack'}}
    final_week(ws, config=old, **VERSIONS)
    telemetry.validate(telemetry.payload(telemetry.load_week(ws, '2026-W39'), token='a' * 32))
    config(ws, '[telemetry]\nshare = "attributed"\n')
    assert main(['telemetry', 'preview']) == 0 and 'inbound' in capsys.readouterr().out
    answers.append(True)
    assert main(['telemetry', 'send']) == 0 and len(fake.calls) == 1


def test_week_stored_with_a_cruise_count_still_validates_and_previews(ws, capsys):
    # A week recorded before #814 counts cruise answers under decided_by; it stays valid.
    final_week(ws, metrics={'days': 2, 'decided_by': {'owner': 2, 'cruise': 1, 'seat': 1}})
    telemetry.validate(telemetry.payload(telemetry.load_week(ws, '2026-W39'), token='a' * 32))
    config(ws, '[telemetry]\nshare = "attributed"\n')
    assert main(['telemetry', 'preview']) == 0 and '"cruise": 1' in capsys.readouterr().out
