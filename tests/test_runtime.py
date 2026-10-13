"""Runtime dispatch contracts and Codex workspace refusal."""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def setup(tmp_path, monkeypatch, runtime='codex'):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[adapters]\nruntime = "' + runtime + '"\n[codex]\ncommand = ["fake-companion"]\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'codex'))  # #845: never the real rollouts
    return tmp_path


def companion_payloads(root):
    fixture = Path(__file__).parent / 'fixtures/runtime/codex-companion.json'
    return json.loads(fixture.read_text().replace('WORKTREE', str(root)))


def test_claude_returns_plugin_agent_type(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch, 'claude')
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.claude')
    result = adapter.dispatch('builder', str(brief), str(root), True, root=root)
    assert result.exit == 0
    assert result.data['agent_type'].endswith(':builder')
    assert result.data['brief_path'] == str(brief)


def test_codex_wrong_root_cancels(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    calls = []

    payloads = companion_payloads(root)
    payloads['status']['workspaceRoot'] = str(root / 'other')

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        assert argv[-1] == '--json'
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]] if argv[1] != 'cancel' else {}), stderr='')

    monkeypatch.setattr(adapter.subprocess, 'run', run)
    result = adapter.dispatch('builder', str(brief), str(root), True, root=root)
    assert result.exit == 1 and 'workspace' in result.reason
    assert 'cancel' in calls[-1][0]
    assert calls[-1][1]['cwd'] == str(root)


def test_codex_matches_then_polls_and_validates_result(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[-1] == '--json'
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]]), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    job = adapter.dispatch('builder', str(brief), str(root), True, root=root).data
    payloads['status']['job']['status'] = 'running'
    assert adapter.status(job, root=root).data['status'] == 'running'
    payloads['status']['job']['status'] = 'completed'
    assert adapter.status(job, root=root).data['status'] == 'completed'
    result = adapter.result(job, root=root)
    assert result.exit == 0 and result.data['text'].startswith('Blocked: none')
    assert 'usage' not in result.data


def _case_codex_prompt_carries_the_mandate(tmp_path, monkeypatch):
    from wuwei import brief as briefs
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]]), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    assert adapter.dispatch('builder', str(brief), str(root), True, root=root).exit == 0
    assert calls[0][-2].endswith(briefs.mandate(root))


def _case_codex_result_with_a_question_is_its_result(tmp_path, monkeypatch):
    # Part 14: a seat names its question in the result; no record is required.
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    payloads['result']['storedJob']['result']['rawOutput'] = (
        'Which option do you want?\nBlocked: none\nGap: none\nChange: none')
    monkeypatch.setattr(adapter, '_call', lambda *args, **kwargs: adapter.registry.Result(
        0, payloads['result']))
    result = adapter.result({'id': 'j1', 'worktree': str(root), 'role': 'builder'}, root=root)
    assert result.exit == 0 and result.data['text'].startswith('Which option')


def _case_codex_result_preserves_stored_usage(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    usage = {'input_tokens': 17, 'output_tokens': 9, 'cost': 0.04,
             'model': 'codex-test', 'duration': 2.5}
    payloads['result']['storedJob']['result']['usage'] = usage
    monkeypatch.setattr(adapter.subprocess, 'run', lambda argv, **kw:
                        SimpleNamespace(returncode=0, stdout=json.dumps(payloads['result']), stderr=''))
    result = adapter.result({'id': 'j1', 'worktree': str(root)}, root=root)
    assert result.exit == 0
    assert result.data['usage'] == usage


def rollout(root, thread, *events):
    path = root / 'codex/sessions/2026/10/12' / f'rollout-2026-10-12T09-00-00-{thread}.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join((event if isinstance(event, str) else json.dumps(event)) + '\n' for event in events))
    return path


def token_count(primary, secondary):
    return {'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {}, 'rate_limits': {
        'primary': primary, 'secondary': secondary}}}


@pytest.mark.parametrize('thread,events,expected', [
    ('t-1', [token_count({'used_percent': 10.0, 'window_minutes': 300, 'resets_at': 1790600000}, None),
             {'type': 'event_msg', 'payload': {'type': 'agent_message'}},
             token_count({'used_percent': 42.0, 'window_minutes': 300, 'resets_at': 1790611200},
                         {'used_percent': 88, 'window_minutes': 10080, 'resets_at': 1791043200})],
     {'five_hour': {'used_percent': 42.0, 'resets_at': '2026-09-28T16:00:00+00:00'},
      'seven_day': {'used_percent': 88, 'resets_at': '2026-10-03T16:00:00+00:00'}}),
    ('t-1', [token_count({'used_percent': 5, 'window_minutes': 60, 'resets_at': 1790611200},
                         {'used_percent': 88, 'window_minutes': 10080, 'resets_at': 1791043200})],
     {'seven_day': {'used_percent': 88, 'resets_at': '2026-10-03T16:00:00+00:00'}}),
    ('t-1', ['{torn'], None),
    ('t-1', [token_count({'used_percent': 5, 'window_minutes': 300, 'resets_at': 1790611200}, None), '{torn'],
     {'five_hour': {'used_percent': 5, 'resets_at': '2026-09-28T16:00:00+00:00'}}),
    ('t-1', [], None),
    ('t-2', [token_count({'used_percent': 5, 'window_minutes': 300, 'resets_at': 1790611200}, None)], None),
    ('*', [token_count({'used_percent': 5, 'window_minutes': 300, 'resets_at': 1790611200}, None)], None),
    ('../t-1', [], None),
], ids=['last-event', 'other-length-dropped', 'malformed', 'torn-tail', 'no-event', 'no-file', 'glob-id', 'path-id'])
def test_codex_result_reads_the_thread_window_readings(tmp_path, monkeypatch, thread, events, expected):
    # #845: the seat thread's rollout file names the Codex windows; any failure is no reading.
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    payloads['result']['storedJob']['result']['threadId'] = thread
    rollout(root, 't-1' if thread in ('t-2', '*', '../t-1') else thread, *events)
    monkeypatch.setattr(adapter, '_call', lambda *args, **kwargs: adapter.registry.Result(0, payloads['result']))
    result = adapter.result({'id': 'j1', 'worktree': str(root), 'role': 'builder'}, root=root)
    assert result.exit == 0 and result.data['text'].startswith('Blocked: none')
    assert result.data.get('windows') == expected


def _case_codex_rejects_conflicting_nested_workspace_root(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    payloads['status']['job']['workspaceRoot'] = str(root / 'other')
    calls = []
    def run(argv, **kwargs):
        calls.append(argv[1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads.get(argv[1], {})), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    result = adapter.dispatch('builder', str(brief), str(root), True, root=root)
    assert result.exit == 1
    assert calls == ['task', 'status', 'cancel']


def test_codex_error_body_is_unrun(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    monkeypatch.setattr(adapter.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout='{"error":"no job"}', stderr=''))
    result = adapter.status({'id': 'j1', 'worktree': str(root)}, root=root)
    assert result.exit == 2 and 'no job' in result.reason


def _case_codex_result_captures_retro_outside_workspace_tree(tmp_path, monkeypatch):
    (tmp_path / 'workspace').mkdir()
    root = setup(tmp_path / 'workspace', monkeypatch)
    tree = tmp_path / 'tree'
    tree.mkdir()
    adapter = importlib.import_module('adapters.runtime.codex')
    monkeypatch.setattr(adapter, '_call', lambda *args, **kwargs: adapter.registry.Result(
        0, companion_payloads(tree)['result']))
    result = adapter.result({'id': 'j1', 'worktree': str(tree), 'role': 'builder'}, root=root)
    assert result.exit == 0
    event = json.loads((root / '.wuwei/days/2026-09-28/events.jsonl').read_text().splitlines()[0])
    assert event['kind'] == 'retro.captured'


def _case_codex_result_lints_verdict(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    verdict = root / '.wuwei/days/2026-09-28/decisions/gate-goal.md'
    verdict.parent.mkdir(parents=True)
    verdict.write_text('Verdict: PASS\n')
    adapter = importlib.import_module('adapters.runtime.codex')
    monkeypatch.setattr(adapter, '_call', lambda *args, **kwargs: adapter.registry.Result(
        0, companion_payloads(root)['result']))
    result = adapter.result({'id': 'j1', 'worktree': str(root), 'role': 'sentinel-goal', 'started_at': 0}, root=root)
    assert result.exit == 1
    assert 'REJECT' in result.reason


def _case_codex_rejects_role_path_traversal(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    result = adapter.dispatch('../README', str(brief), str(root), True, root=root)
    assert result.exit == 1


@pytest.mark.parametrize("scenario_fn", [
    _case_codex_rejects_conflicting_nested_workspace_root,
    _case_codex_rejects_role_path_traversal,
])
def test_codex_rejects_cases_166(tmp_path, monkeypatch, scenario_fn):
    scenario_fn(tmp_path, monkeypatch)


def codex_task(tmp_path, monkeypatch, text):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'q-1-codex.md'
    brief.write_text(text)
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]]), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    return root, adapter, adapter.dispatch('builder', str(brief), str(root), True, root=root), calls


@pytest.mark.parametrize('text,model', [
    ('Item: A\nModel: m1\n\nReview it.', ['--model', 'm1']),
    ('Item: A\n\nReview it.', []),
    ('Item: A\n\nModel: m1\n', []),
])
def test_codex_takes_the_model_from_the_brief_header(tmp_path, monkeypatch, text, model):
    root, _, job, calls = codex_task(tmp_path, monkeypatch, text)
    assert job.exit == 0 and job.data['brief'] == str(root / 'q-1-codex.md')
    task = calls[0]
    assert task[1] == 'task' and (task[task.index('--model'):task.index('--model') + 2]
                                  if '--model' in task else []) == model


QUALITY = ('Verdict: PASS\nHead: abc1234\nProbe: not run\nVAL: PASS\nBlocked: none\nGap: none\n'
           'Change: none\nSimplicity: none\nDesign: none\n')


def _case_codex_result_lints_only_its_own_verdict(tmp_path, monkeypatch):
    root, adapter, job, _ = codex_task(tmp_path, monkeypatch, 'Item: A\n\nReview it.')
    decisions = root / '.wuwei/days/2026-09-28/decisions'
    decisions.mkdir(parents=True)
    (decisions / 'gate-a-1.md').write_text(QUALITY.replace('Simplicity: none\nDesign: none\n', ''))
    own = decisions / 'gate-q-1-codex.md'
    own.write_text(QUALITY)
    job = {**job.data, 'role': 'sentinel-quality', 'started_at': 0}
    assert adapter.result(job, root=root).exit == 0
    own.write_text('Verdict: PASS\n')
    assert adapter.result(job, root=root).exit == 1


@pytest.mark.parametrize("scenario_fn", [
    _case_codex_result_with_a_question_is_its_result,
    _case_codex_result_preserves_stored_usage,
    _case_codex_result_captures_retro_outside_workspace_tree,
    _case_codex_result_lints_verdict,
    _case_codex_result_lints_only_its_own_verdict,
])
def test_codex_result_cases_96(tmp_path, monkeypatch, scenario_fn):
    scenario_fn(tmp_path, monkeypatch)


def test_codex_starts_one_app_server_at_a_time(tmp_path, monkeypatch):
    # #871: concurrent app-server starts contend on the shared ~/.codex state database; the
    # second task starts only once the first job reports its thread
    import threading
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    log, polls, lock = [], {}, threading.Lock()

    def run(argv, **kwargs):
        with lock:
            if argv[1] == 'task':
                job = f'j{sum(entry[0] == "task" for entry in log) + 1}'
                log.append(('task', job))
                return SimpleNamespace(returncode=0, stdout=json.dumps({'jobId': job}), stderr='')
            job = argv[2]
            polls[job] = polls.get(job, 0) + 1
            thread = f't-{job}' if polls[job] >= 3 else None
            if thread:
                log.append(('thread', job))
            return SimpleNamespace(returncode=0, stderr='', stdout=json.dumps({
                'workspaceRoot': str(root), 'job': {'id': job, 'status': 'running',
                                                    'workspaceRoot': str(root), 'threadId': thread}}))
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    monkeypatch.setattr(adapter.time, 'sleep', lambda seconds: None)
    results = []
    threads = [threading.Thread(target=lambda: results.append(
        adapter.dispatch('builder', str(brief), str(root), True, root=root))) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert [result.exit for result in results] == [0, 0]
    assert log == [('task', 'j1'), ('thread', 'j1'), ('task', 'j2'), ('thread', 'j2')]
    assert (tmp_path / 'codex/wuwei-start.lock').is_file()  # the lock is the host's Codex home's


def test_codex_start_lock_frees_when_the_job_ends_before_a_thread(tmp_path, monkeypatch):
    root = setup(tmp_path, monkeypatch)
    brief = root / 'brief.md'
    brief.write_text('Do task')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    payloads['status']['job']['status'] = 'failed'
    calls = []

    def run(argv, **kwargs):
        calls.append(argv[1])
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]]), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    monkeypatch.setattr(adapter.time, 'sleep', lambda seconds: pytest.fail('no wait after the job ended'))
    assert adapter.dispatch('builder', str(brief), str(root), True, root=root).exit == 0
    assert calls == ['task', 'status']


def test_codex_status_names_the_companion_error(tmp_path, monkeypatch):
    # #871: the failed job's errorMessage reaches the refusal
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads = companion_payloads(root)
    payloads['status']['job'].update(status='failed', errorMessage='failed to initialize sqlite state runtime')
    monkeypatch.setattr(adapter, '_call', lambda *args, **kwargs: adapter.registry.Result(0, payloads['status']))
    data = adapter.status({'id': 'j1', 'worktree': str(root)}, root=root).data
    assert data['status'] == 'failed' and data['error'] == 'failed to initialize sqlite state runtime'
    # a turn that fails inside Codex has no errorMessage; its summary is the failure line
    del payloads['status']['job']['errorMessage']
    payloads['status']['job']['summary'] = 'model no-such-model is not supported'
    assert adapter.status({'id': 'j1', 'worktree': str(root)}, root=root).data['error'] == (
        'model no-such-model is not supported')
    payloads['status']['job']['status'] = 'running'
    assert 'error' not in adapter.status({'id': 'j1', 'worktree': str(root)}, root=root).data


def _case_codex_prompt_asks_for_the_retro_note(tmp_path, monkeypatch):
    # #871: the Gap: and Change: lines check_retro reads, from the one verdict format table
    from wuwei import verdict
    root, _, job, calls = codex_task(tmp_path, monkeypatch, 'Item: A\n\nReview it.')
    contract = verdict.retro_contract()
    assert job.exit == 0 and contract in calls[0][-2]
    for key in verdict.RETRO_KEYS:
        assert verdict.FORMAT[key][0] in contract


@pytest.mark.parametrize("scenario_fn", [
    _case_codex_prompt_carries_the_mandate,
    _case_codex_prompt_asks_for_the_retro_note,
])
def test_codex_prompt_cases_80(tmp_path, monkeypatch, scenario_fn):
    scenario_fn(tmp_path, monkeypatch)


def test_codex_gate_prompt_makes_the_final_message_the_verdict(tmp_path, monkeypatch):
    # #871 L1: the sandbox refuses the day's decisions directory, so the verdict is the final
    # message, in the format the lint reads (verdict.section(), rendered from FORMAT)
    from wuwei import verdict
    root = setup(tmp_path, monkeypatch)
    brief = root / 'q-1-codex.md'
    brief.write_text('Item: A\n\nReview it.')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads, calls = companion_payloads(root), []

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]]), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    assert adapter.dispatch('sentinel-quality', str(brief), str(root), True, root=root).exit == 0
    prompt = calls[0][-2]
    assert verdict.section() in prompt and 'final message is your whole verdict' in prompt
    assert 'plain lines, not in a code block' in prompt and 'WUWEI commits' not in prompt  # B6, B7
    assert f'Write no file outside {root}' in prompt


def test_codex_builder_prompt_leaves_the_commit_to_wuwei(tmp_path, monkeypatch):
    # #871 L2: the worktree's git metadata is outside the sandbox, so WUWEI commits
    root, _, job, calls = codex_task(tmp_path, monkeypatch, 'Item: A\n\nBuild it.')
    assert job.exit == 0 and 'WUWEI commits them' in calls[0][-2]
    assert f'Write no file outside {root}' in calls[0][-2]


def test_codex_commit_line_is_for_builders_only(tmp_path, monkeypatch):
    # #871 B6: nothing commits after a steward job
    root = setup(tmp_path, monkeypatch)
    brief = root / 'steward.md'
    brief.write_text('Item: A\n\nRetro.')
    adapter = importlib.import_module('adapters.runtime.codex')
    payloads, calls = companion_payloads(root), []

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payloads[argv[1]]), stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    assert adapter.dispatch('steward', str(brief), str(root), True, root=root).exit == 0
    assert 'WUWEI commits' not in calls[0][-2]


def test_codex_cancel_calls_the_companion_in_the_worktree(tmp_path, monkeypatch):
    # #871 F3: the adapter wraps the companion's cancel
    root = setup(tmp_path, monkeypatch)
    adapter = importlib.import_module('adapters.runtime.codex')
    calls = []

    def run(argv, **kwargs):
        calls.append((argv[1:], kwargs['cwd']))
        return SimpleNamespace(returncode=0, stdout='{}', stderr='')
    monkeypatch.setattr(adapter.subprocess, 'run', run)
    assert adapter.cancel({'id': 'j0', 'worktree': str(root)}, root=root).exit == 0
    assert calls == [(['cancel', 'j0', '--json'], str(root))]
    assert adapter.cancel({'id': '', 'worktree': str(root)}, root=root).exit == 2
