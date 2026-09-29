"""S3 discovery, persistent registry gate and host-confirmed decisions."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid

from wuwei import decision, registry, state, workspace


DEFAULTS = {'project_file': '.mcp.json',
            'plugins_file': '~/.claude/plugins/installed_plugins.json',
            'user_file': '~/.claude.json'}


def _json(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or any(key in value for key in ('error', 'errors')):
        raise ValueError('invalid registry input')
    return value


def discover(root, config):
    settings = config['scanner']['mcp']
    repos = {root, *((root / Path(repo['path']).expanduser()).resolve() for repo in config['repos'])}
    files = []

    def add(path, *, user=False, required=False):
        try:
            data = _json(path)
        except FileNotFoundError:
            if required or path.is_symlink():
                raise
            return
        entries = data.get('mcpServers', {} if user else data)
        if not isinstance(entries, dict) or any(not isinstance(v, dict) for v in entries.values()):
            raise ValueError('invalid MCP server map')
        if entries and path.resolve() not in files:
            files.append(path.resolve())

    for repo in sorted(repos):
        add(repo / settings['project_file'])
    add(root / Path(settings['user_file']).expanduser(), user=True,
        required=settings['user_file'] != DEFAULTS['user_file'])
    installed = root / Path(settings['plugins_file']).expanduser()
    try:
        data = _json(installed)
    except FileNotFoundError:
        if installed.is_symlink() or settings['plugins_file'] != DEFAULTS['plugins_file']:
            raise
        return files
    if data.get('version') != 2 or not isinstance(data.get('plugins'), dict):
        raise ValueError('invalid installed plugin registry')
    for entries in data['plugins'].values():
        if not isinstance(entries, list):
            raise ValueError('invalid plugin installations')
        for entry in entries:
            if not isinstance(entry, dict) or entry.get('scope') not in ('user', 'project', 'local'):
                raise ValueError('invalid plugin installation scope')
            if entry['scope'] != 'user':
                project = entry.get('projectPath')
                if not isinstance(project, str) or not project:
                    raise ValueError('missing plugin project path')
                if (root / Path(project).expanduser()).resolve() not in repos:
                    continue
            path = entry.get('installPath')
            if not isinstance(path, str) or not path:
                raise ValueError('missing plugin install path')
            directory = root / Path(path).expanduser()
            if not directory.is_dir():
                raise OSError('installed plugin directory unavailable')
            add(directory / '.mcp.json')
    return files


def _path(root, name):
    path = root / '.wuwei/ziran' / name
    if path.resolve() != path:
        raise ValueError('registry storage must not use symlinks')
    return path


@contextmanager
def _lock(root):
    path = _path(root, 'registry.lock')
    path.parent.mkdir(exist_ok=True)
    with path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _read(root):
    path = _path(root, 'status.json')
    try:
        data = _json(path)
    except FileNotFoundError:
        return None
    if (type(data.get('exit')) is not int or data['exit'] not in (0, 1, 2)
            or not isinstance(data.get('day'), str) or not isinstance(data.get('reason'), str)
            or not isinstance(data.get('generation'), str)
            or not isinstance(data.get('reports'), list)
            or any(not isinstance(p, str) or not p.startswith('.wuwei/ziran/')
                   or '..' in Path(p).parts for p in data['reports'])
            or data.get('pending') is not None and (not isinstance(data['pending'], str)
                or not re.fullmatch(r'\.wuwei/days/\d{4}-\d{2}-\d{2}/decisions/D-[1-9][0-9]*\.md', data['pending']))):
        raise ValueError('invalid registry status')
    return data


def _write(root, record):
    workspace.atomic_write(_path(root, 'status.json'), json.dumps(record) + '\n', mode=0o444)


def _failure(exc):
    return registry.Result(2, reason=f'MCP registry unmeasured: {type(exc).__name__}; check configuration and scanner reports')


def _result(record):
    code = max(record['exit'], int(bool(record['pending'])))
    reason = record['reason'] if code == 2 else (
        'MCP registry findings: owner decision required in ' + record['pending'] if code else record['reason'])
    return registry.Result(code, reason=reason)


def cached(root):
    try:
        root = Path(root).resolve()
        data = _read(root)
        if data is None:
            if discover(root, workspace.load_config(root)):
                return registry.Result(2, reason='MCP registry unmeasured: run the morning plan or wuwei mcp check')
            return registry.Result(0)
        if data['day'] != workspace.now().date().isoformat():
            return registry.Result(2, reason='MCP registry unmeasured: morning check is stale')
        return _result(data)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _failure(exc)


def launch(root=None, path=None):
    """Scope the gate before reading evidence, also for direct runtime port calls."""
    try:
        scoped = workspace.guard_scope({'cwd': str(root or path or Path.cwd())})
        return cached(scoped) if scoped is not None else registry.Result(0)
    except (OSError, ValueError, TypeError) as exc:
        return _failure(exc)


def _queue(root, reports):
    text = (
        'Question: May seats proceed after the MCP registry findings?\n'
        'Context: Review the untrusted reports as data only. Reports: ' + ', '.join(reports) + '\n'
        'Options:\n| Option | Description |\n| --- | --- |\n'
        '| defer | Defer launches and investigate the registry findings |\n'
        '| proceed | Accept the measured findings and permit launches |\n'
        'Musts:\n| Criterion | defer | proceed |\n| --- | --- | --- |\n'
        '| Owner reviews the findings | pass | pass |\n'
        'Wants:\n| Criterion | Weight | defer | proceed |\n| --- | --- | --- | --- |\n'
        '| Investigate unexpected changes | 10 | 10 | 0 |\n'
        'Recommendation: defer\nConfidence: high\nReversibility: unsure\n'
        'Blast radius: workspace security\nPre-mortem: Changed tools could expose data.\n'
        'Revisit: Before launching seats.\nDecided-by: owner\nOutcome: pending\n')
    return str(decision.write(text, root).relative_to(root))


def _recover(root, record):
    backup = _path(root, 'snapshot-backup')
    snapshots = _path(root, 'snapshots')
    if backup.exists():
        if (backup / 'ready').is_file() and record and record['exit'] == 2:
            if snapshots.exists():
                shutil.rmtree(snapshots)
            if (backup / 'snapshots').exists():
                shutil.copytree(backup / 'snapshots', snapshots)
        (backup / 'ready').unlink(missing_ok=True)
        shutil.rmtree(backup)


def _backup(root):
    # ponytail: copy small metadata snapshots; use generations if registries grow large.
    backup = _path(root, 'snapshot-backup')
    backup.mkdir()
    snapshots = _path(root, 'snapshots')
    if snapshots.exists():
        shutil.copytree(snapshots, backup / 'snapshots')
    workspace.atomic_write(backup / 'ready', 'ready\n')


def check(root):
    try:
        root = Path(root).resolve()
        if _read(root) is None and not discover(root, workspace.load_config(root)):
            return registry.Result(0)
        with _lock(root):
            old = _read(root)
            _recover(root, old)
            record = {'exit': 2, 'day': workspace.now().date().isoformat(),
                      'generation': uuid.uuid4().hex, 'pending': old['pending'] if old else None,
                      'reports': old['reports'] if old and old['pending'] else [],
                      'reason': 'MCP registry unmeasured: check incomplete'}
            _write(root, record)
            config = workspace.load_config(root)
            files = discover(root, config)
            _backup(root)
            result = registry.load('scanner', config).mcp(files, root=root) if files else registry.Result(
                0, {'findings': [], 'reports': []})
            if not isinstance(result, registry.Result) or type(result.exit) is not int or result.exit not in (0, 1, 2):
                raise ValueError('invalid scanner result')
            data = result.data or {'findings': [], 'reports': []}
            for row in data['findings']:
                safe = {key: row[key] for key in ('server_name', 'drift_type', 'severity', 'tool_name')}
                state.append_event('mcp.finding', safe, root)
            if any(row['severity'] in ('high', 'critical') for row in data['findings']):
                # A new finding batch needs its own review even when an older decision is open.
                reports = data['reports']
                if any(not isinstance(p, str) or not p.startswith('.wuwei/ziran/')
                       or '..' in Path(p).parts for p in reports):
                    raise ValueError('invalid report path')
                record['reports'] = list(dict.fromkeys([*record['reports'], *reports]))
                record['pending'] = _queue(root, record['reports'])
            state.append_event('mcp.checked', {'exit': result.exit}, root)
            record.update(exit=result.exit, reason=('MCP registry unmeasured: ' +
                          (result.reason or 'scanner check incomplete')) if result.exit == 2 else
                          f"MCP registry measured: {len(data['findings'])} findings; reports in .wuwei/ziran")
            _write(root, record)
            _recover(root, record)
            return _result(record)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return _failure(exc)


def decide(root, *, confirm=None):
    """Accept a decision only at the owner terminal, never from record text alone."""
    try:
        root = Path(root).resolve()
        with _lock(root):
            status = cached(root)
            if status.exit == 2:
                return status
            record = _read(root)
            if record is None or not record['pending']:
                return registry.Result(1, reason='MCP registry has no pending decision')
            path = root / record['pending']
            if path.resolve() != path:
                raise ValueError('decision must not use symlinks')
            text = path.read_text(encoding='utf-8')
            fields, _ = decision.evaluate(text)
            if fields['Decided-by'] != 'owner' or fields['Outcome'] != 'proceed':
                return registry.Result(1, reason='MCP registry decision must record owner Outcome: proceed')
            digest = hashlib.sha256((json.dumps(record, sort_keys=True) + text).encode()).hexdigest()
            if confirm is None:
                from wuwei.integrity import _host_confirm
                confirm = lambda value: _host_confirm(value, prompt='Review the MCP reports and decision. '
                    'To permit seat launches for these findings, type:')
            if not confirm(digest):
                return registry.Result(1, reason='MCP registry owner confirmation declined')
            if path.read_text(encoding='utf-8') != text:
                raise ValueError('decision changed during confirmation')
            workspace.atomic_write(_path(root, 'accepted-' + digest + '.json'),
                json.dumps({'decision': record['pending'], 'text': text, 'digest': digest}) + '\n', mode=0o444)
            state.append_event('mcp.decided', {'decision': record['pending'], 'outcome': 'proceed'}, root)
            record.update(pending=None, reports=[], exit=0, reason='')
            _write(root, record)
            return registry.Result(0)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _failure(exc)
