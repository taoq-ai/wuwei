"""#952: background leftovers, using fake host measurements and signals only."""

import json
import os
import signal
from types import SimpleNamespace

import pytest

from adapters.host import local
from fakes import records
from wuwei import registry, state, watch, workspace
from wuwei.__main__ import main
from wuwei.commands import close, doctor, next as next_command
from wuwei.registry import Result

TERMINATE = local.terminate_process


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-13T12:00:00+00:00')
    monkeypatch.setenv('WUWEI_SESSION_ID', 'S')
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/memory').mkdir()
    (tmp_path / '.wuwei/memory/spine.md').write_text('# Memory\n')
    (tmp_path / '.wuwei/memory/index.md').write_text('')
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname="acme/repo"\npath="repo"\ndefault_branch="main"\n')
    records.write(tmp_path, {'planner_session_id': 'S', 'gate_approved': True,
                           'items': {'x': {'phase': 'merged', 'pr': 'acme/repo#1'}},
                           'approved_items': ['x']})
    (workspace.day_dir(tmp_path) / 'plan.md').write_text('# Plan\n')
    return tmp_path


@pytest.fixture
def host(monkeypatch):
    class Host:
        rows = {}
        killed = []
        def processes(self, root=None, **kwargs):
            return Result(0, self.rows.copy())
        def terminate_process(self, record, grace, root=None):
            assert self.rows[record['pid']]['command'] == record['command']
            self.killed.append(record['pid'])
            self.rows.pop(record['pid'])
            return Result(0, True)
    host = Host()
    host.rows, host.killed = {}, []
    real = registry.load
    monkeypatch.setattr(registry, 'load', lambda port, config: host if port == 'host' else real(port, config))
    return host


def started(root, host, pid=41001, item='x', purpose='pr-wait', prs=None, directory=None, session='S'):
    row = {'pid': pid, 'ppid': 42, 'etime': '01:00', 'command': f'python next --background {pid}',
           'identity': 'Tue Oct 13 11:00:00 2026', 'cwd': None}
    host.rows[pid] = row
    record = {**row, 'item': item, 'purpose': purpose, 'prs': prs or ['acme/repo#1'],
              'session_id': session, 'day': (directory or workspace.day_dir(root)).name,
              'started_at': '2026-10-13T11:00:00+00:00'}
    state.append_event('process.started', record, root, directory=directory)
    return record


def _case_merged_wait_reaped(root, host):
    started(root, host)
    code, rows = watch.housekeeping(root, reap=True)
    assert code == 0 and host.killed == [41001]
    assert any(row['kind'] == 'process.reaped' for row in watch.records(workspace.day_dir(root) / 'events.jsonl'))


def _case_duplicate_wait_keeps_oldest(root, host):
    records.write(root, {'items': {'x': {'phase': 'raised', 'pr': 'acme/repo#1'}}})
    started(root, host, 41001)
    started(root, host, 41002)
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == [41002]


@pytest.mark.parametrize('change', [{'command': 'git cat-file --batch'}, {'identity': 'new start'}])
def test_pid_reuse_never_killed(root, host, change):
    started(root, host)
    host.rows[41001].update(change)
    watch.housekeeping(root, reap=True)
    assert host.killed == []


def _case_hung_init_orphan_in_worktree_owner_only(root, host):
    tree = root / 'item-tree'
    tree.mkdir()
    records.write(root, {'items': {'x': {'phase': 'merged', 'worktree': str(tree)}}})
    host.rows = {41003: {'pid': 41003, 'ppid': 1, 'command': 'git cat-file --batch',
                         'identity': 'old', 'cwd': str(tree), 'etime': '05:00'},
                 41004: {'pid': 41004, 'ppid': 1, 'command': 'unrelated',
                         'identity': 'old', 'cwd': str(root.parent), 'etime': '05:00'}}
    code, rows = watch.housekeeping(root, reap=True, orphans=True)
    assert code == 1 and host.killed == []
    assert len([r for r in rows if r['kind'] == 'orphan']) == 1
    assert 'kill -TERM 41003' in str(rows) and '41004' not in str(rows)
    assert 'git -C' in str(rows) and 'worktree remove' in str(rows)
    assert not any('Owner step' in r.get('why', '') for r in rows)


@pytest.mark.parametrize('phase,status', [('parked', 'queued'), ('planned', 'done')])
def test_terminal_item_background(root, host, phase, status):
    records.write(root, {'items': {'x': {'phase': phase, 'status': status, **({'resume_phase': 'raised'} if phase == 'parked' else {})}}})
    started(root, host, purpose='sleep')
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == [41001]


def _case_cached_closed_pr_and_closed_day(root, host):
    records.write(root, {'items': {'x': {'phase': 'raised', 'pr': 'acme/repo#1'}}})
    started(root, host)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'pulls': [{'ref': 'acme/repo#1', 'state': 'closed'}]}))
    assert watch.housekeeping(root, reap=True)[0] == 0
    started(root, host, 41002, item='day', purpose='sleep')
    state.append_event('day.closed', {}, root)
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == [41001, 41002]


def _case_seat_inactivity_and_recent_transcript(root, host):
    transcript = root / 'transcript.jsonl'
    transcript.write_text('{}\n')
    old = workspace.now().timestamp() - 20000
    os.utime(transcript, (old, old))
    records.write(root, {'seats': {'builder-x': {'role': 'builder', 'item': 'x', 'status': 'running',
                        'started_at': '2026-10-13T01:00:00+00:00', 'transcript': str(transcript)}}})
    code, rows = watch.housekeeping(root)
    assert code == 1 and any(r['command'] == 'wuwei seat stop builder-x --verdict' for r in rows)
    now = workspace.now().timestamp()
    os.utime(transcript, (now, now))
    assert watch.housekeeping(root)[0] == 0
    assert host.killed == []


def _case_session_next_and_doctor_show_findings(root, host, monkeypatch):
    from wuwei.guards import lifecycle
    started(root, host)
    monkeypatch.setattr(lifecycle, 'scoped', lambda payload: (root, workspace.load_config(root)))
    assert 'housekeeping' in lifecycle.session_start({'cwd': str(root)})[1].lower()
    row = next_command.step(root)
    assert row['state'] == 'set' and row['duties'][0]['duty'] == 'housekeeping'
    assert row['duties'][0]['record'] == 'wuwei next --housekeeping'
    assert doctor.diagnose('processes')[0]['status'] == 'warn'
    assert host.killed == []


def _case_close_reaps_before_steward(root, host, monkeypatch):
    started(root, host)
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(close.closing, 'unresolved', lambda *a, **k: (0, ''))
    monkeypatch.setattr(close.closing, 'check', lambda root: (1, 'retro owed'))
    def steward(*args, **kwargs):
        assert host.killed == [41001]
    monkeypatch.setattr(close.steward, 'run', steward)
    assert close.run(SimpleNamespace(check=None, widget=False, why=False)) == 1


def _case_background_registration_and_wrapping(root, host, monkeypatch):
    pid = os.getpid()
    host.rows[pid] = {'pid': pid, 'ppid': 42, 'command': 'python next --background',
                      'identity': 'start', 'etime': '00:00', 'cwd': None}
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    assert main(['next', '--background', '--', 'sleep', '1']) == 0
    event = next(r['payload'] for r in watch.records(workspace.day_dir(root) / 'events.jsonl')
                 if r['kind'] == 'process.started')
    assert event['pid'] == pid and event['purpose'] == 'sleep' and event['started_at']
    row = next_command.resolve(next_command._row('wait', 'wait', 'wuwei pr wait', 'background'), root)
    assert 'next --background -- wuwei pr wait' in row['command']


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_host_process_snapshot(monkeypatch, platform, isolated_process_table):
    monkeypatch.setattr(local.sys, 'platform', platform)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        text = ('PID PPID ELAPSED STARTED COMMAND\n'
                '41001 42 01:02 Tue Oct 13 11:00:00 2026 python worker\n')
        return SimpleNamespace(returncode=0, stdout=text)
    monkeypatch.setattr(local.subprocess, 'run', run)
    result = isolated_process_table()
    assert result.exit == 0 and result.data[41001]['command'] == 'python worker'
    assert 'pid,ppid,etime,lstart,command' in calls[0]


@pytest.mark.parametrize('survives', [False, True, 'reused'])
def test_term_then_recheck_before_kill(monkeypatch, survives):
    record = {'pid': 41001, 'command': 'python worker', 'identity': 'start'}
    calls = []
    def processes(root=None, **kwargs):
        row = dict(record)
        if calls:
            if not survives:
                return Result(0, {})
            if survives == 'reused':
                row['command'] = 'unrelated'
        return Result(0, {41001: row})
    monkeypatch.setattr(local, 'processes', processes, raising=False)
    monkeypatch.setattr(local.os, 'kill', lambda pid, sig: calls.append((pid, sig)))
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    TERMINATE(record, 0)
    assert calls == [(41001, signal.SIGTERM)] + ([(41001, signal.SIGKILL)] if survives is True else [])


def _case_process_read_failure_is_unmeasured(root, host):
    host.processes = lambda **kwargs: Result(2, None, 'ps unavailable')
    assert watch.housekeeping(root)[0] == 2
    assert doctor.diagnose('processes')[0]['status'] == 'unmeasured'


def _case_prior_day_wait_uses_latest_cached_state(root, host):
    prior = root / '.wuwei/days/2026-10-12'
    records.write(root, {'items': {'x': {'phase': 'raised', 'pr': 'acme/repo#1'}}}, directory=prior)
    started(root, host, directory=prior)
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == [41001]
    receipt = next(row['payload'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
                   if row['kind'] == 'process.reaped')
    assert receipt['source_day'] == prior.name


def _case_unknown_pr_state_does_not_reap(root, host):
    records.write(root, {'items': {'x': {'phase': 'raised', 'pr': 'acme/repo#1'}}})
    started(root, host)
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == []


def _case_unreadable_transcript_still_reports_stale_seat(root, host, monkeypatch):
    from pathlib import Path
    records.write(root, {'seats': {'s': {'role': 'builder', 'item': 'x', 'status': 'running',
                        'started_at': '2026-10-13T01:00:00+00:00', 'transcript': 'unreadable'}}})
    real = Path.stat
    def stat(path, *args, **kwargs):
        if path.name == 'unreadable':
            raise PermissionError('not readable')
        return real(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat)
    code, rows = watch.housekeeping(root)
    assert code == 1 and rows[0]['kind'] == 'seat'


def _case_live_item_protects_shared_worktree(root, host):
    tree = root / 'tree'
    tree.mkdir()
    records.write(root, {'items': {'x': {'phase': 'merged', 'worktree': 'tree'},
                                  'y': {'phase': 'implement', 'worktree': 'tree'}}})
    assert watch.housekeeping(root)[1] == []


def _case_set_one_shot_run_stays_unwrapped(root, host, monkeypatch):
    monkeypatch.setattr(next_command, '_resolve', lambda row, root: row)
    row = {'state': 'set', 'action': 'set', 'launches': [
        {'kind': 'build', 'action': 'run', 'item': 'x', 'command': 'wuwei build next x'}]}
    found = next_command.resolve(row, root)
    assert found['launches'][0]['command'] == 'wuwei build next x'


def _case_close_does_not_reap_active_build_on_refusal(root, host, monkeypatch):
    records.write(root, {'items': {'x': {'phase': 'implement'}}})
    started(root, host, purpose='build')
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda root: (0, []))
    def unresolved(*args, **kwargs):
        kwargs['open_items'].append('x')
        return 1, 'x is still open'
    monkeypatch.setattr(close.closing, 'unresolved', unresolved)
    assert close.run(SimpleNamespace(check=None, widget=False, why=False)) == 1
    assert host.killed == []


def _case_codex_build_without_seat_is_recovered_not_killed(root, host):
    records.write(root, {'builds': {'x': {'status': 'running', 'runtime': 'codex', 'job': {'id': 'job'},
                        'started_at': '2026-10-13T01:00:00+00:00',
                        'brief': 'brief.md', 'worktree': 'tree'}}})
    code, rows = watch.housekeeping(root)
    assert code == 1 and rows[0]['kind'] == 'build'
    assert rows[0]['command'] == 'wuwei build x brief.md tree'
    assert host.killed == []


def _case_prior_seat_is_listed_without_clock_override(root, host):
    prior = root / '.wuwei/days/2026-10-12'
    records.write(root, {'seats': {'s': {'role': 'builder', 'item': 'x', 'status': 'running',
                        'started_at': '2026-10-12T01:00:00+00:00'}}}, directory=prior)
    code, rows = watch.housekeeping(root, reap=True, orphans=True)
    assert code == 1 and len(rows) == 1
    assert rows[0]['kind'] == 'historical-seat' and '2026-10-12' in rows[0]['why']
    assert '--day' not in str(rows) and 'WUWEI_NOW' not in str(rows)
    assert not any(row.get('kind') == 'seat' for row in next_command.step(root).get('launches', []))
    with pytest.raises(SystemExit):
        main(['seat', 'stop', 's', '--verdict', '--day', '2026-10-12'])


def _case_duplicate_wait_ignores_obsolete_pr_snapshots(root, host):
    records.write(root, {'items': {'x': {'phase': 'raised', 'pr': 'acme/repo#2'},
                                  'old': {'phase': 'merged', 'pr': 'acme/repo#1'}}})
    started(root, host, prs=['acme/repo#1'])
    started(root, host, 41002, prs=['acme/repo#1', 'acme/repo#2'])
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == [41002]


def _case_background_wait_records_no_pr_snapshot(root, host, monkeypatch):
    records.write(root, {'claimed_prs': ['acme/repo#2']})
    host.rows[os.getpid()] = {'pid': os.getpid(), 'command': 'python background', 'identity': 'start', 'ppid': 42}
    monkeypatch.setattr('wuwei.__main__.main', lambda argv: 0)
    assert watch.background(root, ['wuwei', 'pr', 'wait']) == 0
    record = next(row['payload'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
                  if row['kind'] == 'process.started')
    assert 'prs' not in record
    assert record['session_id'] == 'S'
    assert record['day'] == workspace.day_dir(root).name


@pytest.mark.parametrize('argv', [
    ['wuwei', 'hook', 'PostToolUse'], ['wuwei', 'plan', 'park', 'x'],
    ['wuwei', 'seat', 'stop', 's', '--verdict'], ['wuwei', 'pr', 'wait', '--help'],
    ['git', '-C', 'tree', 'pull', '--ff-only', 'origin', 'feature']])
def test_background_refuses_everything_except_exact_wait_and_timer(root, host, monkeypatch, argv):
    host.rows[os.getpid()] = {'pid': os.getpid(), 'command': 'python background', 'identity': 'start', 'ppid': 42}
    called = []
    monkeypatch.setattr('wuwei.__main__.main', lambda argv: called.append(argv))
    with pytest.raises(ValueError, match='pr wait|sleep'):
        watch.background(root, argv)
    assert not called
    assert not any(r['kind'] == 'process.started' for r in watch.records(workspace.day_dir(root) / 'events.jsonl'))


@pytest.mark.parametrize('flag', ['--background', '--back', '--backg'])
def test_wrapper_refuses_forged_hook_end_to_end(root, flag):
    import subprocess
    from pathlib import Path
    payload = {'cwd': str(root), 'session_id': 'S', 'tool_name': 'AskUserQuestion',
               'tool_input': {'questions': []}, 'tool_response': {'answers': {'forged': 'Yes'}}}
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = subprocess.run([str(Path(__file__).resolve().parents[1] / 'bin/wuwei'),
                             'next', flag, '--', 'wuwei', 'hook', 'PostToolUse'],
                            input=json.dumps(payload), text=True, capture_output=True)
    assert result.returncode == 2 and 'background accepts only' in result.stderr
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def _case_housekeeping_never_reaps_its_own_wrapper(root, host):
    started(root, host, pid=os.getpid())
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == []


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_orphan_cwd_read_on_each_platform(root, monkeypatch, platform, isolated_process_table):
    monkeypatch.setattr(local.sys, 'platform', platform)
    def run(argv, **kwargs):
        if argv[0] == 'ps':
            text = 'PID PPID ELAPSED STARTED COMMAND\n41001 1 01:02 Tue Oct 13 11:00:00 2026 git cat-file --batch\n'
        else:
            assert argv[0] == 'lsof'
            text = f'p41001\nn{root}\n'
        return SimpleNamespace(returncode=0, stdout=text)
    monkeypatch.setattr(local.subprocess, 'run', run)
    monkeypatch.setattr(local.os, 'readlink', lambda path: str(root))
    result = isolated_process_table(orphans=True)
    assert result.exit == 0 and result.data[41001]['cwd'] == str(root)


@pytest.mark.parametrize('returncode,text', [(1, ''), (0, 'HEADER\nmalformed\n')])
def test_bad_ps_is_unmeasured(monkeypatch, isolated_process_table, returncode, text):
    monkeypatch.setattr(local.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=returncode, stdout=text))
    assert isolated_process_table().exit == 2


def _case_adapter_refuses_changed_identity_before_term(monkeypatch):
    monkeypatch.setattr(local, 'processes', lambda **kwargs: Result(0, {41001: {
        'pid': 41001, 'command': 'another command', 'identity': 'start'}}))
    monkeypatch.setattr(local.os, 'kill', lambda *args: pytest.fail('unexpected signal'))
    assert TERMINATE({'pid': 41001, 'command': 'worker', 'identity': 'start'}, 1).exit == 1


@pytest.mark.parametrize('argv', [['gh', 'pr', 'merge', '--admin'], ['git', '-C', 'tree', 'push', '--force']])
def test_background_refuses_unoffered_native_commands(root, host, monkeypatch, argv):
    host.rows[os.getpid()] = {'pid': os.getpid(), 'command': 'python background', 'identity': 'start', 'ppid': 42}
    monkeypatch.setattr('shutil.which', lambda command: command)
    host.hand_over = lambda *a, **kw: pytest.fail('unapproved native command executed')
    with pytest.raises(ValueError, match='pr wait|sleep'):
        watch.background(root, argv)


def _case_prior_codex_job_has_no_fabricated_recovery(root, host):
    prior = root / '.wuwei/days/2026-10-12'
    records.write(root, {'builds': {'old': {'status': 'running', 'runtime': 'codex', 'job': {'id': 'job'},
                        'started_at': '2026-10-12T01:00:00+00:00',
                        'brief': 'brief.md', 'worktree': 'tree'}}}, directory=prior)
    assert watch.housekeeping(root, reap=True)[1] == []
    assert host.killed == []


@pytest.mark.parametrize('purpose', ['build', 'scanner', 'park', 'seat'])
def test_old_one_shot_records_are_never_reaped(root, host, purpose):
    started(root, host, purpose=purpose)
    watch.housekeeping(root, reap=True, closing=True)
    assert host.killed == []


def test_next_rejects_junk(root):
    assert main(['next', 'junk']) == 2


def _case_active_codex_broker_and_ancestors_are_not_orphans(root, host):
    records.write(root, {'items': {'x': {'phase': 'implement', 'worktree': 'tree'}}})
    def process(pid, ppid, cwd):
        return {'pid': pid, 'ppid': ppid, 'command': 'broker', 'cwd': str(cwd), 'identity': 'start'}
    host.rows = {41001: process(41001, 1, root / 'tree/subdir'),
                 os.getpid(): process(os.getpid(), 41002, root),
                 41002: process(41002, 41003, root), 41003: process(41003, 1, root)}
    assert watch.housekeeping(root, reap=True, orphans=True)[1] == []


def _case_ps_failure_is_a_finding_without_stopping_next(root, host, monkeypatch):
    from wuwei.guards import lifecycle
    host.processes = lambda **kw: Result(2, None, 'ps unavailable')
    findings = []
    assert next_command.step(root, findings=findings)['state'] != 'unmeasured'
    assert findings[0]['kind'] == 'unmeasured'
    monkeypatch.setattr(lifecycle, 'scoped', lambda payload: (root, workspace.load_config(root)))
    code, text = lifecycle.session_start({'cwd': str(root)})
    assert code == 2 and 'ps unavailable' in text and 'Next:' in text


def _case_failed_reap_is_reported_once_without_repeating_duty(root, host):
    started(root, host)
    calls = []
    host.terminate_process = lambda *a, **kw: calls.append(1) or Result(2, False, 'still visible after SIGKILL')
    assert watch.housekeeping(root, reap=True)[0] == 2
    findings = []
    row = next_command.step(root, findings=findings)
    assert not any(r['duty'] == 'housekeeping' for r in row.get('duties', []))
    assert len([r for r in findings if 'SIGKILL' in r['why']]) == 1
    watch.housekeeping(root, reap=True)
    assert calls == [1]


def _case_fast_checks_do_not_request_orphan_cwds(root, host, monkeypatch):
    from wuwei.guards import lifecycle
    modes = []
    host.processes = lambda **kw: modes.append(kw.get('orphans', False)) or Result(0, {})
    next_command.step(root)
    monkeypatch.setattr(lifecycle, 'scoped', lambda payload: (root, workspace.load_config(root)))
    lifecycle.session_start({'cwd': str(root)})
    doctor.diagnose('processes')
    watch.housekeeping(root, reap=True)
    assert modes == [False, False, True, False]


@pytest.mark.parametrize('platform', ['linux', 'darwin'])
def test_cwd_failure_stays_on_pid(root, monkeypatch, platform, isolated_process_table):
    monkeypatch.setattr(local.sys, 'platform', platform)
    def run(argv, **kwargs):
        if argv[0] == 'lsof':
            raise local.subprocess.TimeoutExpired(argv, 5)
        return SimpleNamespace(returncode=0, stdout='HEADER\n41001 1 01:02 Tue Oct 13 11:00:00 2026 agent\n')
    monkeypatch.setattr(local.subprocess, 'run', run)
    monkeypatch.setattr(local.os, 'readlink', lambda path: (_ for _ in ()).throw(PermissionError('denied')))
    result = isolated_process_table(orphans=True)
    assert result.exit == 0 and result.data[41001]['cwd'] is None
    assert result.data[41001]['error']


def _case_cwd_read_error_is_listed_not_raised(root, host):
    host.rows = {41001: {'pid': 41001, 'ppid': 1, 'command': 'agent', 'cwd': None, 'error': 'denied'}}
    code, rows = watch.housekeeping(root, reap=True, orphans=True)
    assert code == 2 and len(rows) == 1 and '41001' in rows[0]['why']


def test_targeted_kill_uses_ps_pid_and_c_locale(monkeypatch, isolated_process_table):
    calls, signals = [], []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        text = 'HEADER\n41001 42 01:02 Tue Oct 13 11:00:00 2026 worker\n' if not signals else 'HEADER\n'
        return SimpleNamespace(returncode=0, stdout=text)
    monkeypatch.setattr(local, 'processes', isolated_process_table)
    monkeypatch.setattr(local.subprocess, 'run', run)
    monkeypatch.setattr(local.os, 'kill', lambda *args: signals.append(args))
    monkeypatch.setattr('time.sleep', lambda n: None)
    assert TERMINATE({'pid': 41001, 'command': 'worker', 'identity': 'Tue Oct 13 11:00:00 2026'}, 0).data is True
    assert all('-p' in argv and '41001' in argv and '-u' not in argv for argv, kw in calls)
    assert all(kw['env']['LC_ALL'] == 'C' for argv, kw in calls)


def _case_zombie_after_term_reports_signalled(monkeypatch):
    calls = []
    row = {'pid': 41001, 'command': 'worker', 'identity': 'start'}
    monkeypatch.setattr(local, 'processes', lambda **kw: Result(0, {41001: {
        **row, 'command': '<defunct>' if calls else 'worker'}}))
    monkeypatch.setattr(local.os, 'kill', lambda *a: calls.append(a))
    monkeypatch.setattr('time.sleep', lambda n: None)
    result = TERMINATE(row, 0)
    assert result.exit == 0 and result.data is True and 'signalled' in result.reason
    assert calls == [(41001, signal.SIGTERM)]


def _case_history_ignores_non_process_payloads(root, host, monkeypatch):
    started(root, host)
    state.append_event('irrelevant', {'large': 'payload'}, root)
    decode = watch._rows
    def rows(text):
        assert 'irrelevant' not in text
        return decode(text)
    monkeypatch.setattr(watch, '_rows', rows)
    assert watch.housekeeping(root)[0] == 1


def _case_session_omits_historical_seat(root, host, monkeypatch):
    from wuwei.guards import lifecycle
    prior = root / '.wuwei/days/2026-10-12'
    records.write(root, {'seats': {'old-seat': {'role': 'builder', 'item': 'x', 'status': 'running',
                        'started_at': '2026-10-12T01:00:00+00:00'}}}, directory=prior)
    monkeypatch.setattr(lifecycle, 'scoped', lambda payload: (root, workspace.load_config(root)))
    code, text = lifecycle.session_start({'cwd': str(root)})
    assert code == 0 and 'old-seat' not in text
    assert 'old-seat' in str(doctor.diagnose('processes'))


def waiting_pr(root):
    from test_next import approved
    approved(root, {'P': ('raised', {'pr': 'example/project#7'})})
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({
        'fetched_at': workspace.now().isoformat(), 'pulls': [
            {'ref': 'example/project#7', 'state': 'open', 'checks': 'pending', 'labels': []}]}))


def _case_four_rounds_keep_needed_wait_without_respawning(root, host):
    waiting_pr(root)
    started(root, host, 1001, item='day')
    offered = []
    for pid in range(1002, 1006):
        row = next_command.step(root)
        offered.append((row['action'], row.get('command')))
        if row['action'] == 'background':
            started(root, host, pid, item='day')
        watch.housekeeping(root, reap=True)
    assert offered == [('wait', 'wuwei status --line')] * 4
    assert host.killed == [] and set(host.rows) == {1001}
    host.rows.clear()
    assert next_command.step(root)['action'] == 'background'


def _case_session_orients_with_recorded_wrapper(root, host, monkeypatch):
    from wuwei.guards import lifecycle
    waiting_pr(root)
    monkeypatch.setattr(lifecycle, 'scoped', lambda payload: (root, workspace.load_config(root)))
    before = (workspace.day_dir(root) / 'events.jsonl').read_bytes()
    code, text = lifecycle.session_start({'cwd': str(root)})
    assert code == 0 and '\nwuwei next --background -- wuwei pr wait\n' in text
    assert (workspace.day_dir(root) / 'events.jsonl').read_bytes() == before


def test_host_none_fast_checks_are_silent_and_read_only(root, monkeypatch, capsys):
    from wuwei.guards import lifecycle
    config = root / '.wuwei/config.toml'
    config.write_text('[adapters]\nhost="none"\n' + config.read_text())
    monkeypatch.setattr(lifecycle, 'scoped', lambda payload: (root, workspace.load_config(root)))
    before = (workspace.day_dir(root) / 'events.jsonl').read_bytes()
    for _ in range(4):
        next_command.step(root)
    code, text = lifecycle.session_start({'cwd': str(root)})
    assert (workspace.day_dir(root) / 'events.jsonl').read_bytes() == before
    assert code == 0 and not capsys.readouterr().err
    assert doctor.diagnose('processes')[0]['status'] == 'unmeasured'


def _case_historical_cleanup_is_only_in_explicit_inspection_and_close(root, host, monkeypatch, capsys):
    from wuwei.guards import lifecycle
    prior = root / '.wuwei/days/2026-10-12'
    records.write(root, {'seats': {'old-seat': {'role': 'builder', 'item': 'x', 'status': 'running',
                        'started_at': '2026-10-12T01:00:00+00:00'}}}, directory=prior)
    (root / 'finished-tree').mkdir()
    records.write(root, {'items': {'x': {'phase': 'merged', 'worktree': 'finished-tree'}}})
    monkeypatch.setattr('wuwei.derive.stale', lambda *a: [])
    monkeypatch.setattr(next_command, '_supervise', lambda *a: None)
    monkeypatch.setattr(lifecycle, 'scoped', lambda payload: (root, workspace.load_config(root)))
    for _ in range(2):
        assert main(['next', '--json']) == 0
        output = capsys.readouterr()
        assert 'old-seat' not in output.err and 'finished-tree' not in output.err
        code, text = lifecycle.session_start({'cwd': str(root)})
        assert code == 0 and 'old-seat' not in text and 'finished-tree' not in text
    assert main(['next', '--housekeeping']) == 0
    output = capsys.readouterr().out
    assert 'old-seat' not in output and 'finished-tree' not in output
    found = str(doctor.diagnose('processes'))
    assert 'old-seat' in found and 'finished-tree' in found
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(close.closing, 'unresolved', lambda *a, **kw: (0, ''))
    monkeypatch.setattr(close.closing, 'check', lambda root: (1, 'retro owed'))
    monkeypatch.setattr(close.steward, 'run', lambda *a, **kw: None)
    close.run(SimpleNamespace(check=None, widget=False, why=False))
    output = capsys.readouterr().out
    assert 'old-seat' in output and 'finished-tree' in output


def _case_general_orphans_listed_once_per_day_across_doctor_and_close(root, host, monkeypatch, capsys):
    host.rows = {41001: {'pid': 41001, 'ppid': 1, 'command': 'podman', 'identity': 'start', 'cwd': str(root)}}
    assert 'kill -TERM 41001' in str(doctor.diagnose('processes'))
    host.rows[41001]['command'] = 'podman changed its argv'
    assert 'kill -TERM 41001' not in str(doctor.diagnose('processes'))
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(close.closing, 'unresolved', lambda *a, **kw: (0, ''))
    monkeypatch.setattr(close.closing, 'check', lambda root: (1, 'retro owed'))
    monkeypatch.setattr(close.steward, 'run', lambda *a, **kw: None)
    close.run(SimpleNamespace(check=None, widget=False, why=False))
    assert 'kill -TERM 41001' not in capsys.readouterr().out
    monkeypatch.setenv('WUWEI_NOW', '2026-10-14T12:00:00+00:00')
    assert 'kill -TERM 41001' in str(doctor.diagnose('processes'))
    assert 'kill -TERM 41001' not in str(doctor.diagnose('processes'))
    assert host.killed == []


def _case_orphan_outside_workspace_never_gets_kill_suggestion(root, host):
    tree = root.parent / 'outside-tree'
    tree.mkdir()
    (root / 'escape').symlink_to(tree, target_is_directory=True)
    records.write(root, {'items': {'x': {'phase': 'merged', 'worktree': str(tree)}}})
    host.rows = {pid: {'pid': pid, 'ppid': 1, 'command': 'unrelated', 'identity': 'start', 'cwd': str(cwd)}
                 for pid, cwd in [(41001, tree), (41002, root / 'escape'), (41003, root.parent)]}
    assert 'kill -TERM' not in str(doctor.diagnose('processes'))
    assert host.killed == []


@pytest.mark.parametrize('scope', ['other-session', 'prior-day'])
def test_obsolete_wait_does_not_make_current_session_passive(root, host, scope):
    waiting_pr(root)
    prior = root / '.wuwei/days/2026-10-12'
    if scope == 'prior-day':
        records.write(root, {}, directory=prior)
    started(root, host, 1001, item='day',
            directory=prior if scope == 'prior-day' else None,
            session='other' if scope == 'other-session' else 'S')
    live = []
    _, findings = watch.housekeeping(root, live_waits=live)
    assert live == []
    assert any(row['kind'] == 'process' for row in findings)
    row = next_command.step(root)
    assert row['action'] == 'set' and row['duties'][0]['duty'] == 'housekeeping'
    # A current wait survives even when an older wait belongs to another scope.
    started(root, host, 1002, item='day')
    assert watch.housekeeping(root, reap=True)[0] == 0
    assert host.killed == [1001]
    assert next_command.step(root)['action'] == 'wait'
    host.rows.clear()
    assert next_command.step(root)['action'] == 'background'


def _case_close_only_blocks_on_reap_failure_in_this_run(root, host, monkeypatch, capsys):
    started(root, host)
    host.terminate_process = lambda *a, **kw: Result(2, False, 'termination failed')
    monkeypatch.setattr(workspace, 'guard_scope', lambda payload: root)
    monkeypatch.setattr(close.pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(close.closing, 'unresolved', lambda *a, **kw: (0, ''))
    monkeypatch.setattr(close.closing, 'check', lambda root: (1, 'retro owed'))
    calls = []
    monkeypatch.setattr(close.steward, 'run', lambda *a, **kw: calls.append('steward'))
    args = SimpleNamespace(check=None, widget=False, why=False)
    assert close.run(args) == 2
    assert calls == []
    # A historical failure and a new inspection error are both informational.
    host.rows[41002] = {'pid': 41002, 'ppid': 1, 'command': 'worker', 'error': 'lsof unavailable'}
    assert close.run(args) == 1
    assert calls == ['steward']
    assert 'termination failed' in capsys.readouterr().out


@pytest.mark.parametrize('argv', [['anything'], ['wuwei', 'pr', 'wait']])
def test_housekeeping_with_background_refuses_extra_arguments(root, host, capsys, argv):
    started(root, host)
    before = (workspace.day_dir(root) / 'events.jsonl').read_bytes()
    assert main(['next', '--background', '--housekeeping', '--', *argv]) == 2
    assert 'no positional arguments' in capsys.readouterr().err
    assert host.killed == []
    assert (workspace.day_dir(root) / 'events.jsonl').read_bytes() == before


@pytest.mark.parametrize(
    "case",
    [
    _case_merged_wait_reaped,
    _case_duplicate_wait_keeps_oldest,
    _case_hung_init_orphan_in_worktree_owner_only,
    _case_cached_closed_pr_and_closed_day,
    _case_seat_inactivity_and_recent_transcript,
    _case_process_read_failure_is_unmeasured,
    _case_prior_day_wait_uses_latest_cached_state,
    _case_unknown_pr_state_does_not_reap,
    _case_live_item_protects_shared_worktree,
    _case_codex_build_without_seat_is_recovered_not_killed,
    _case_prior_seat_is_listed_without_clock_override,
    _case_duplicate_wait_ignores_obsolete_pr_snapshots,
    _case_housekeeping_never_reaps_its_own_wrapper,
    _case_prior_codex_job_has_no_fabricated_recovery,
    _case_active_codex_broker_and_ancestors_are_not_orphans,
    _case_failed_reap_is_reported_once_without_repeating_duty,
    _case_cwd_read_error_is_listed_not_raised,
    _case_four_rounds_keep_needed_wait_without_respawning,
    _case_orphan_outside_workspace_never_gets_kill_suggestion,
    ],
    ids=[
    'merged_wait_reaped',
    'duplicate_wait_keeps_oldest',
    'hung_init_orphan_in_worktree_owner_only',
    'cached_closed_pr_and_closed_day',
    'seat_inactivity_and_recent_transcript',
    'process_read_failure_is_unmeasured',
    'prior_day_wait_uses_latest_cached_state',
    'unknown_pr_state_does_not_reap',
    'live_item_protects_shared_worktree',
    'codex_build_without_seat_is_recovered_not_killed',
    'prior_seat_is_listed_without_clock_override',
    'duplicate_wait_ignores_obsolete_pr_snapshots',
    'housekeeping_never_reaps_its_own_wrapper',
    'prior_codex_job_has_no_fabricated_recovery',
    'active_codex_broker_and_ancestors_are_not_orphans',
    'failed_reap_is_reported_once_without_repeating_duty',
    'cwd_read_error_is_listed_not_raised',
    'four_rounds_keep_needed_wait_without_respawning',
    'orphan_outside_workspace_never_gets_kill_suggestion',
    ],
)
def test_housekeeping_host_cases(root, host, case):
    case(root, host)


@pytest.mark.parametrize(
    "case",
    [
    _case_session_next_and_doctor_show_findings,
    _case_close_reaps_before_steward,
    _case_background_registration_and_wrapping,
    _case_unreadable_transcript_still_reports_stale_seat,
    _case_set_one_shot_run_stays_unwrapped,
    _case_close_does_not_reap_active_build_on_refusal,
    _case_background_wait_records_no_pr_snapshot,
    _case_ps_failure_is_a_finding_without_stopping_next,
    _case_fast_checks_do_not_request_orphan_cwds,
    _case_history_ignores_non_process_payloads,
    _case_session_omits_historical_seat,
    _case_session_orients_with_recorded_wrapper,
    ],
    ids=[
    'session_next_and_doctor_show_findings',
    'close_reaps_before_steward',
    'background_registration_and_wrapping',
    'unreadable_transcript_still_reports_stale_seat',
    'set_one_shot_run_stays_unwrapped',
    'close_does_not_reap_active_build_on_refusal',
    'background_wait_records_no_pr_snapshot',
    'ps_failure_is_a_finding_without_stopping_next',
    'fast_checks_do_not_request_orphan_cwds',
    'history_ignores_non_process_payloads',
    'session_omits_historical_seat',
    'session_orients_with_recorded_wrapper',
    ],
)
def test_housekeeping_command_cases(root, host, monkeypatch, case):
    case(root, host, monkeypatch)


@pytest.mark.parametrize(
    "case",
    [
    _case_adapter_refuses_changed_identity_before_term,
    _case_zombie_after_term_reports_signalled,
    ],
    ids=[
    'adapter_refuses_changed_identity_before_term',
    'zombie_after_term_reports_signalled',
    ],
)
def test_adapter_termination_cases(monkeypatch, case):
    case(monkeypatch)


@pytest.mark.parametrize(
    "case",
    [
    _case_historical_cleanup_is_only_in_explicit_inspection_and_close,
    _case_general_orphans_listed_once_per_day_across_doctor_and_close,
    _case_close_only_blocks_on_reap_failure_in_this_run,
    ],
    ids=[
    'historical_cleanup_is_only_in_explicit_inspection_and_close',
    'general_orphans_listed_once_per_day_across_doctor_and_close',
    'close_only_blocks_on_reap_failure_in_this_run',
    ],
)
def test_housekeeping_close_cases(root, host, monkeypatch, capsys, case):
    case(root, host, monkeypatch, capsys)
