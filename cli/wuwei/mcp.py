"""S3 discovery, persistent registry gate and host-confirmed decisions."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from wuwei import decision, redact, registry, state, workspace
from wuwei.integrity import PLUGIN
from wuwei.exits import ADAPTER_DATA, DAMAGED, RACE, SYMLINK

DECLINED = 'MCP registry owner confirmation declined; rerun it in a host terminal and answer y'

DEFAULTS = {'project_file': '.mcp.json',
            'plugins_file': '~/.claude/plugins/installed_plugins.json',
            'user_file': '~/.claude.json'}
COVERED = 'WUWEI plugin.json servers covered by plugin integrity (signed manifest), not scanned'
NOT_CHECKED = 'MCP registry: not checked (security.areas.mcp = "off")'
NO_SCANNER = 'mcp: not measured (no scanner configured; set adapters.scanner = "ziran" to measure)'
DECIDE = 'bin/wuwei mcp decide'
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}')
# Registry storage beside the per-server report directories.
STORAGE = ('servers', 'snapshots', 'snapshot-backup')
REPORT = re.compile(r'\.wuwei/ziran/(' + NAME.pattern + r')/([0-9a-f]{64})\.json')
SEVERITIES = workspace.SCHEMA['scanner']['severity_threshold'][2]
# An exact version only: @latest, ranges and 1.x are unpinned.
PINNED = re.compile(r'(?:@[^/@\s]+/)?[^@=\s]+(?:@|==)\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.]+)?')


def _json(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or any(key in value for key in ('error', 'errors')):
        raise ValueError(f'invalid registry input; {DAMAGED}')
    return value


def discover(root, config, covered=None, plugins=None, projects=None):
    settings = config['scanner']['mcp']
    repos = {root, *((root / Path(repo['path']).expanduser()).resolve() for repo in config['repos'])}
    files = []

    def add(path, *, user=False, required=False, key=None, repo=None):
        try:
            data = _json(path)
        except FileNotFoundError:
            if required or path.is_symlink():
                raise
            return
        entries = data.get('mcpServers', {} if user else data)
        if not isinstance(entries, dict) or any(not isinstance(v, dict) for v in entries.values()):
            raise ValueError(f'invalid MCP server map; {DAMAGED}')
        key = key or path.resolve()
        if entries and key not in files:
            files.append(key)
            if repo is not None and projects is not None:
                projects[key] = repo

    for repo in sorted(repos):
        add(repo / settings['project_file'], repo=repo)
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
        raise ValueError(f'invalid installed plugin registry; {DAMAGED}')
    for entries in data['plugins'].values():
        if not isinstance(entries, list):
            raise ValueError(f'invalid plugin installations; {DAMAGED}')
        for entry in entries:
            if not isinstance(entry, dict) or entry.get('scope') not in ('user', 'project', 'local'):
                raise ValueError(f'invalid plugin installation scope; {DAMAGED}')
            if entry['scope'] != 'user':
                project = entry.get('projectPath')
                if not isinstance(project, str) or not project:
                    raise ValueError(f'missing plugin project path; {DAMAGED}')
                if (root / Path(project).expanduser()).resolve() not in repos:
                    continue
            path = entry.get('installPath')
            if not isinstance(path, str) or not path:
                raise ValueError(f'missing plugin install path; {ADAPTER_DATA}')
            directory = root / Path(path).expanduser()
            if not directory.is_dir():
                raise OSError('installed plugin directory unavailable; reinstall the plugin, then run bin/wuwei doctor')
            add(directory / '.mcp.json')
            manifest = directory / '.claude-plugin/plugin.json'
            if directory.resolve() == PLUGIN:
                # Signed manifest (7.1): integrity measures WUWEI's own servers, not the registry.
                if covered is not None:
                    covered.append(manifest)
            else:
                # Inline servers under top-level mcpServers, keyed by install directory:
                # ${CLAUDE_PLUGIN_ROOT} is that directory even when plugin.json is a symlink.
                key = directory.resolve() / '.claude-plugin/plugin.json'
                add(manifest, user=True, key=key)
                if plugins is not None:
                    plugins.add(key)
    return files


def _worktree_of(path, repo):
    """A git worktree of repo: its .git file points into repo's git directory."""
    try:
        text = (path / '.git').read_text(encoding='utf-8')
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return False
    if not text.startswith('gitdir:'):
        return False
    return (path / text[len('gitdir:'):].strip()).resolve().is_relative_to((repo / '.git').resolve())


def _approval(root, settings, repo):
    """Whether Claude Code would attach a project server at the repo or any item worktree."""
    def read(path):
        try:
            return _json(path)
        except FileNotFoundError:
            if path.is_symlink():
                raise
            return {}

    user = read(root / Path(settings['user_file']).expanduser())
    projects = user.get('projects', {})
    if not isinstance(projects, dict) or any(not isinstance(v, dict) for v in projects.values()):
        raise ValueError(f'invalid MCP approval state; {DAMAGED}')
    worktrees = root / 'worktrees'
    keys = {repo, *(path.resolve() for path in (worktrees.iterdir() if worktrees.is_dir() else ())
                    if _worktree_of(path, repo))}
    common = read((root / Path(settings['user_file']).expanduser()).parent / '.claude/settings.json')
    projects = [(Path(name).resolve(), value) for name, value in projects.items()]
    states = []
    for key in keys:
        sources = [common, read(key / '.claude/settings.json'), read(key / '.claude/settings.local.json'),
                   *(value for path, value in projects if path == key)]
        enabled, disabled, everything = set(), set(), False
        for source in sources:
            for field in ('enabledMcpjsonServers', 'disabledMcpjsonServers'):
                names = source.get(field, [])
                if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
                    raise ValueError(f'invalid MCP approval state; {DAMAGED}')
            if source.get('enableAllProjectMcpServers') not in (None, True, False):
                raise ValueError(f'invalid MCP approval state; {DAMAGED}')
            enabled.update(source.get('enabledMcpjsonServers', []))
            disabled.update(source.get('disabledMcpjsonServers', []))
            everything = everything or source.get('enableAllProjectMcpServers') is True
        states.append((enabled, disabled, everything))
    return lambda name: any(name not in disabled and (everything or name in enabled)
                            for enabled, disabled, everything in states)


def digest(data):
    """A report's name: SHA-256 of its canonical JSON, so key order or whitespace is not a new result."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _path(root, name):
    path = root / '.wuwei/ziran' / name
    if path.resolve() != path:
        raise ValueError(f'registry storage must not use symlinks; {SYMLINK}')
    return path


@contextmanager
def _lock(root):
    path = _path(root, 'registry.lock')
    path.parent.mkdir(exist_ok=True)
    with path.open('a') as lock:
        state.lock_ex(lock, 'registry.lock')
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
        raise ValueError(f'invalid registry status; {DAMAGED}')
    # A v0.11.0 record has no posture fields: its pending decision keeps blocking.
    data.setdefault('severities', list(SEVERITIES))
    if not isinstance(data['severities'], list) or any(s not in SEVERITIES for s in data['severities']):
        raise ValueError(f'invalid registry status; {DAMAGED}')
    _pairs(data.setdefault('unmeasured', []))
    _pairs(data.setdefault('decided', []))
    return data


def _pairs(value):
    """[server name, definition digest] pairs."""
    if not isinstance(value, list) or any(
            not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str)
            or not NAME.fullmatch(pair[0]) or not isinstance(pair[1], str)
            or not re.fullmatch(r'[0-9a-f]{64}', pair[1]) for pair in value):
        raise ValueError(f'invalid registry server pairs; {DAMAGED}')
    return value


def _write(root, record):
    workspace.atomic_write(_path(root, 'status.json'), json.dumps(record) + '\n', mode=0o444)


def _servers(path, plugin):
    """Each server as a one-server config, plugin roots expanded as Claude Code starts them."""
    data = _json(path)
    entries = data.get('mcpServers', data)
    if not isinstance(entries, dict) or any(not isinstance(v, dict) for v in entries.values()):
        raise ValueError(f'invalid MCP server map; {DAMAGED}')
    servers = []
    for name, entry in entries.items():
        if not NAME.fullmatch(name):
            raise ValueError(f'invalid MCP server name; {DAMAGED}')
        body = json.dumps({'mcpServers': {name: entry}}, sort_keys=True)
        if plugin:
            body = body.replace('${CLAUDE_PLUGIN_ROOT}', json.dumps(str(path.parents[1]))[1:-1])
        body += '\n'
        servers.append((name, entry, body, hashlib.sha256(body.encode()).hexdigest()))
    return servers


def _server_file(root, path, name, body):
    """Stable per (source, name), so the scanner's snapshot baseline carries between checks."""
    target = _path(root, 'servers') / (hashlib.sha256(f'{path}\0{name}'.encode()).hexdigest() + '.json')
    target.parent.mkdir(exist_ok=True)
    workspace.atomic_write(target, body, mode=0o600)
    return target


def _unpinned(entry):
    """A uvx, npx or pipx run launcher without an exact package version."""
    command, args = entry.get('command'), entry.get('args', [])
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        raise ValueError(f'invalid MCP server entry; {DAMAGED}')
    tokens = [*command.split(), *args] if isinstance(command, str) else []
    if tokens and Path(tokens[0]).name == 'env':
        tokens = tokens[1:]
        while tokens and '=' in tokens[0] and not tokens[0].startswith('-'):
            tokens = tokens[1:]
    if not tokens:
        return False
    rest = tokens[1:]
    launcher = Path(tokens[0]).name
    if launcher == 'pipx' and rest[:1] == ['run']:
        rest = rest[1:]
    elif launcher not in ('uvx', 'npx'):
        return False
    flag = next((flag for flag in ('--from', '--spec', '-p', '--package') if flag in rest[:-1]), None)
    spec = rest[rest.index(flag) + 1] if flag else next((t for t in rest if not t.startswith('-')), '')
    return not PINNED.fullmatch(spec)


def _accepted(root):
    """Owner-decided (name, digest) pairs from proceed-unmeasured records, and the accepted
    report baseline: server name to (report digests, day of the latest decision)."""
    pairs, baseline = [], {}
    for path in sorted(_path(root, '.').glob('accepted-*.json')):
        if path.is_symlink():
            raise ValueError(f'registry storage must not use symlinks; {SYMLINK}')
        data = _json(path)
        pairs.extend(_pairs(data.get('servers', [])))
        day = re.match(r'\.wuwei/days/(\d{4}-\d{2}-\d{2})/', str(data.get('decision', '')))
        for name, digest in _pairs(data.get('baseline', [])):
            digests, latest = baseline.get(name, (set(), ''))
            baseline[name] = (digests | {digest}, max(latest, day[1] if day else ''))
    return pairs, baseline


def _failure(exc):
    return registry.Result(2, reason=f'MCP registry unmeasured: {type(exc).__name__}; check configuration and scanner reports; run bin/wuwei doctor --section gates')


def command(pending):
    """The one host-terminal command that answers the pending MCP decision."""
    return f'{DECIDE} {Path(pending).stem} proceed'


def _waiting(record):
    """One line for a pending finding batch (#351, #350): what was found and the command."""
    pending = record['pending']
    return (f"MCP registry findings ({', '.join(record['severities'])}) await the owner ({Path(pending).stem}): "
            f'run {command(pending)} (or defer) in a host terminal')


def pending(root):
    """The pending MCP decision path, or None; it survives the day rollover."""
    record = _read(Path(root).resolve())
    return record and record['pending']


def _result(record):
    code = max(record['exit'], int(bool(record['pending'])))
    reason = _waiting(record) if code == 1 else record['reason']
    return registry.Result(code, reason=reason)


def _gate(record, block):
    """The launch posture: a check that could not run always blocks; the rest per block."""
    if record['exit'] == 2 and not record['unmeasured'] or record['unmeasured'] and 'unmeasured' in block:
        return registry.Result(2, reason=record['reason'])
    if record['pending'] and set(record['severities']) & set(block):
        return registry.Result(1, reason=_waiting(record))
    return registry.Result(0, reason=record['reason'])


def cached(root):
    """The launch gate under the mcp posture level (#331)."""
    try:
        root = Path(root).resolve()
        config = workspace.load_config(root)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _failure(exc)
    name, levels = workspace.posture(config)
    level = levels['mcp']
    if level == 'off':
        return registry.Result(0, reason=NOT_CHECKED)
    if config['adapters']['scanner'] == 'none':  # #424: no scanner is a choice, the gate is off.
        return registry.Result(0, reason=NO_SCANNER)
    block = config['scanner']['mcp']['block']
    if level == 'block':  # strict: the pre-#325 list
        block = sorted({*block, 'critical', 'high', 'unmeasured'})
    result = _cached(root, block)
    if not result.exit:
        return result
    if level == 'warn' and name == 'observe':
        return registry.Result(0, reason=f'{result.reason} (mcp: warn, security.areas.mcp)')
    # Floor (#331): under guarded and strict, scanner.mcp.block findings and a check that
    # could not run block whatever the mcp level is.
    note = 'floor: scanner.mcp.block' if level == 'warn' else 'security.areas.mcp'
    return registry.Result(result.exit, reason=f'{result.reason} (mcp: {level}, {note})')


def _cached(root, block):
    try:
        data = _read(root)
        if data is None:
            if discover(root, workspace.load_config(root)):
                return registry.Result(2, reason='MCP registry unmeasured: run the morning plan or wuwei mcp check')
            return registry.Result(0)
        if data['day'] != workspace.now().date().isoformat():
            return registry.Result(2, reason='MCP registry unmeasured: morning check is stale; run bin/wuwei mcp check')
        return _gate(data, block)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _failure(exc)


def unmeasured(root):
    """Today's in-scope servers the registry did not measure, decided or not."""
    data = _read(Path(root).resolve())
    if data is None or data['day'] != workspace.now().date().isoformat():
        return []
    return sorted({name for name, _ in data['unmeasured'] + data['decided']})


# The owner's answer: mcp decide records the outcome and, on proceed, the baseline (#350).
RECORD = 'wuwei mcp decide {id} "<label>"'


def findings(root):
    """One line per server: finding counts by severity, highest first, from today's last completed
    check since the last owner proceed. Only validated names and severities; scanner text stays out."""
    from collections import Counter
    from wuwei import watch
    rows = watch.records(workspace.day_dir(root) / 'events.jsonl')
    # ponytail: the window is today since the last proceed; earlier days' findings stay in their logs.
    start = max((index for index, row in enumerate(rows) if row['kind'] == 'mcp.decided'
                 and row['payload'].get('outcome') == 'proceed'), default=-1) + 1
    batch, last = [], []
    for row in rows[start:]:
        if row['kind'] == 'mcp.finding':
            batch.append(row)
        elif row['kind'] == 'mcp.checked':
            batch, last = [], batch
    counts = {}
    for row in last:
        name, severity = row['payload'].get('server_name'), row['payload'].get('severity')
        name = name if isinstance(name, str) and NAME.fullmatch(name) else 'unnamed server'
        counts.setdefault(name, Counter())[severity if severity in SEVERITIES else 'unknown'] += 1
    return [f'{name}: ' + ', '.join(f'{counts[name][s]} {s}' for s in (*SEVERITIES, 'unknown')
                                    if counts[name][s]) for name in sorted(counts)]


def widget(root):
    """Today's pending registry decision as a widget, its proceed option carrying the findings."""
    root = Path(root).resolve()
    data = _read(root)
    if not data or not data['pending'] or data['day'] != workspace.now().date().isoformat():
        return []
    path = root / data['pending']
    identifier = path.stem
    if path != decision.today_path(identifier, root):
        return []  # an earlier day's record: the question guard cannot cite it today
    fields, _ = decision.evaluate(path.read_text(encoding='utf-8'), decision.LENSES)
    question = decision.record_widget(identifier, fields, RECORD,
                                      workspace.verbosity(workspace.load_config(root), 'decisions'))
    for option in question['options']:
        if decision.option_id(fields, option['label']) == 'proceed':
            option['description'] = '\n'.join([option['description'], *findings(root)])
    return [question]


def launch(root=None, path=None):
    """Scope the gate before reading evidence, also for direct runtime port calls."""
    try:
        scoped = workspace.guard_scope({'cwd': str(root or path or Path.cwd())})
        return cached(scoped) if scoped is not None else registry.Result(0)
    except (OSError, ValueError, TypeError) as exc:
        return _failure(exc)


def _cell(value, limit=40):
    """Untrusted report text as one table cell: redacted, safe characters only, shortened."""
    if not isinstance(value, str):
        return '-'
    value = ' '.join(re.sub(r'[^A-Za-z0-9 _.,:;/()=+@#\[\]-]', ' ', redact.redact(value)).split())
    return (value[:limit - 3] + '...' if len(value) > limit else value) or '-'


def _queue(root, record, baseline):
    rows = []
    reports = [path for path in record['reports'] if (root / path).is_file()]
    for path in reports:
        data = json.loads((root / path).read_text(encoding='utf-8'))
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError(f'invalid scanner report; {ADAPTER_DATA}')
        for row in data:
            snippet = row.get('current_value')
            name = row.get('server_name')
            since = (f'changed since {baseline[name][1]}' if isinstance(name, str) and name in baseline
                     else 'first measurement')
            rows.append(f"| {_cell(name)} | {_cell(row.get('tool_name'))} | {_cell(row.get('drift_type'))} | "
                        f"{_cell(row.get('severity'))} | "
                        f"{_cell(snippet if isinstance(snippet, str) else row.get('message'), 60)} | {since} |\n")
    rows += [f'| {name} | - | unmeasured | - | - | - |\n' for name, _ in record['unmeasured']]
    text = (
        'Question: May seats proceed after the MCP registry findings?\nClass: other\n'
        'Context: Review these findings as untrusted data; snippets are redacted and shortened.\n'
        '| Server | Tool | Flag | Severity | Snippet | Since |\n| --- | --- | --- | --- | --- | --- |\n'
        + ''.join(rows) + 'Reports: ' + ', '.join(reports) + '\n'
        'Options:\n| Option | Title | Rationale | Consequence |\n| --- | --- | --- | --- |\n'
        '| defer | Defer launches | Investigates unexpected changes first. | Seats wait until the findings are reviewed. |\n'
        '| proceed | Proceed with findings | Accepts the measured findings without investigation. | Seats launch with these tools. |\n'
        'Musts:\n| Criterion | defer | proceed |\n| --- | --- | --- |\n'
        '| Owner reviews the findings | pass | pass |\n'
        'Wants:\n| Criterion | Weight | defer | proceed |\n| --- | --- | --- | --- |\n'
        '| Investigate unexpected changes | 10 | 10 | 0 |\n'
        'Recommendation: defer\n'
        'Reasoning: Investigating unexpected changes decided it; findings you expected would flip it.\n'
        'Confidence: high\nReversibility: unsure\n'
        'Blast radius: workspace security\nPre-mortem: Changed tools could expose data.\n'
        'Revisit: Before launching seats.\nDecided-by: owner\nOutcome: pending\n')
    return str(decision.write(text, root).relative_to(root))


def _recover(root, record):
    for run in _path(root, '.').glob('.run-*'):
        shutil.rmtree(run)  # left by a killed adapter run
    backup = _path(root, 'snapshot-backup')
    snapshots = _path(root, 'snapshots')
    if backup.exists():
        # Only a check that could not run rolls back every baseline; the adapter rolls back
        # a single server's snapshot when that server stays unmeasured.
        if (backup / 'ready').is_file() and record and record['exit'] == 2 and not record['unmeasured']:
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
        config = workspace.load_config(root)
        if workspace.posture(config)[1]['mcp'] == 'off':
            return registry.Result(0, reason=NOT_CHECKED)
        covered, plugins = [], set()
        if _read(root) is None and not discover(root, config, covered):
            return registry.Result(0, reason=COVERED if covered else '')
        if config['adapters']['scanner'] == 'none':  # #424: servers attached, the gate is off; say so once a day.
            from wuwei import watch
            # ponytail: racy marker, two first checks of the day may both print the line.
            if any(row['kind'] == 'mcp.checked' and row['payload'].get('scanner') == 'none'
                   for row in watch.records(workspace.day_dir(root) / 'events.jsonl')):
                return registry.Result(0)
            state.append_event('mcp.checked', {'exit': 0, 'servers': {}, 'scanner': 'none'}, root)
            return registry.Result(0, reason=NO_SCANNER)
        with _lock(root):
            old = _read(root)
            _recover(root, old)
            record = {'exit': 2, 'day': workspace.now().date().isoformat(),
                      'generation': uuid.uuid4().hex, 'pending': old['pending'] if old else None,
                      'reports': old['reports'] if old and old['pending'] else [],
                      'severities': old['severities'] if old and old['pending'] else [],
                      'unmeasured': [], 'decided': [],
                      'reason': 'MCP registry unmeasured: check incomplete'}
            _write(root, record)
            config = workspace.load_config(root)
            block = config['scanner']['mcp']['block']
            projects = {}
            files = discover(root, config, covered, plugins, projects)
            _backup(root)
            scanner = registry.load('scanner', config) if files else None
            accepted, baseline = _accepted(root)
            findings, notes, servers, by_report = [], [], {}, {}
            for path in files:
                attached = _approval(root, config['scanner']['mcp'], projects[path]) if path in projects else None
                for name, entry, body, digest in _servers(path, path in plugins):
                    if attached is not None and not attached(name):
                        # Claude Code never starts it here, so neither does the check.
                        notes.append(f'{name}: not attached (unapproved)')
                        continue
                    servers[name] = 'unmeasured'
                    if _unpinned(entry):
                        # The scanner would start it, fetching code nobody reviewed.
                        reason = 'unpinned launcher'
                    else:
                        folder = _path(root, name)
                        seen = set(folder.glob('*.json')) if folder.is_dir() else set()
                        # One server per call: an unreachable server never hides another's findings.
                        result = scanner.mcp([_server_file(root, path, name, body)], root=root)
                        if (not isinstance(result, registry.Result) or type(result.exit) is not int
                                or result.exit not in (0, 1, 2)):
                            raise ValueError(f'invalid scanner result; {ADAPTER_DATA}')
                        if result.exit == 2 and result.data is None:
                            # #424: the scanner itself could not start (not on PATH, wrong
                            # version): the check could not run, not one unmeasured server.
                            record.update(unmeasured=[], decided=[],
                                          reason=f'MCP registry could not run: {result.reason}')
                            _write(root, record)
                            _recover(root, record)
                            return registry.Result(2, reason=record['reason'])
                        if result.exit != 2:
                            # A partial run (exit 2) stores no report, so its data is ignored.
                            [report] = result.data['reports']
                            match = REPORT.fullmatch(report)
                            if not match or match[1] != name or not (root / report).is_file():
                                raise ValueError(f'invalid scanner report; {ADAPTER_DATA}')
                            servers[name] = 'unchanged' if root / report in seen else 'new'
                            if match[2] in baseline.get(name, ((), ''))[0]:
                                notes.append(f'{name}: accepted findings, unchanged since {baseline[name][1]}')
                                continue
                            findings.extend(result.data['findings'])
                            by_report[report] = result.data['findings']
                            continue
                        reason = result.reason or 'scanner check incomplete'
                    pair = [name, digest]
                    notes.append(f'{name}: {reason}')
                    if pair in accepted:
                        record['decided'].append(pair)
                        notes.append(f'{name}: proceeding unmeasured by owner decision')
                    else:
                        record['unmeasured'].append(pair)
            for row in findings:
                safe = {key: row[key] for key in ('server_name', 'drift_type', 'severity', 'tool_name')}
                state.append_event('mcp.finding', safe, root)
            queue = ('high', 'critical', *block)
            flagged = [path for path, rows in by_report.items() if any(row['severity'] in queue for row in rows)]
            fresh = [path for path in flagged if path not in record['reports']]
            if fresh:
                # A new result needs its own review even when an older decision is open.
                record['reports'] += fresh
                record['pending'] = _queue(root, record, baseline)
                record['severities'] = sorted({*record['severities'],
                                               *(row['severity'] for row in findings if row['severity'] in queue)})
            code = 2 if record['unmeasured'] else int(any(
                row['severity'] in ('high', 'critical') for row in findings))
            state.append_event('mcp.checked', {'exit': code, 'servers': servers}, root)
            head = ('MCP registry unmeasured' if code == 2 else
                    f'MCP registry measured: {len(findings)} findings; reports in .wuwei/ziran')
            reason = '; '.join([head, *notes, *([_waiting(record)] if record['pending'] else []),
                                *([COVERED] if covered else [])])
            record.update(exit=code, reason=reason)
            _write(root, record)
            _recover(root, record)
            return _result(record)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return _failure(exc)


def _proceed_unmeasured(root, record, servers, confirm):
    pairs = [pair for pair in record['unmeasured'] if pair[0] in servers]
    missing = sorted(set(servers) - {name for name, _ in pairs})
    if missing:
        return registry.Result(1, reason=('MCP registry servers not unmeasured today: ' + ', '.join(missing)
                                       + '; run bin/wuwei mcp check first'))
    names = sorted({name for name, _ in pairs})
    digest = hashlib.sha256(json.dumps([record, pairs], sort_keys=True).encode()).hexdigest()
    if confirm is None:
        from wuwei.integrity import _host_confirm
        confirm = lambda value: _host_confirm(value, prompt=f"Seats will use {', '.join(names)} "
            'without a registry measurement.')
    try:
        if not confirm(digest):
            return registry.Result(1, reason=DECLINED)
    except OSError as exc:
        return registry.Result(2, reason=str(exc))
    text = (
        'Question: May seats proceed with MCP servers the registry could not measure?\nClass: other\n'
        f"Context: Unmeasured servers: {', '.join(names)}. Their tool output is untrusted data.\n"
        'Options:\n| Option | Title | Rationale | Consequence |\n| --- | --- | --- | --- |\n'
        '| defer | Defer launches | Waits for a measurement the owner chose not to wait for. | Seats wait until the servers can be measured. |\n'
        '| proceed-unmeasured | Proceed unmeasured | The owner accepted the unmeasured servers. | Seats launch; the tool output stays untrusted. |\n'
        'Musts:\n| Criterion | defer | proceed-unmeasured |\n| --- | --- | --- |\n'
        '| Owner confirmed at the host terminal | pass | pass |\n'
        'Wants:\n| Criterion | Weight | defer | proceed-unmeasured |\n| --- | --- | --- | --- |\n'
        '| Owner accepts the unmeasured servers | 10 | 0 | 10 |\n'
        'Recommendation: proceed-unmeasured\n'
        'Reasoning: The owner confirmed it at the host terminal; a changed definition would flip it.\n'
        'Confidence: medium\nReversibility: two-way\n'
        'Blast radius: workspace security\nPre-mortem: An unmeasured server changes its tools unnoticed.\n'
        'Revisit: When a definition changes or the next check measures them.\n'
        'Decided-by: owner\nOutcome: proceed-unmeasured\n')
    path = str(decision.write(text, root).relative_to(root))
    workspace.atomic_write(_path(root, 'accepted-' + digest + '.json'), json.dumps(
        {'decision': path, 'text': text, 'digest': digest, 'servers': pairs}) + '\n', mode=0o444)
    state.append_event('mcp.decided', {'decision': path, 'outcome': 'proceed-unmeasured', 'servers': names}, root)
    record['unmeasured'] = [pair for pair in record['unmeasured'] if pair not in pairs]
    record['decided'] += pairs
    record['reason'] += ''.join(f'; {name}: proceeding unmeasured by owner decision' for name in names)
    if not record['unmeasured'] and record['exit'] == 2:
        record['exit'] = 1 if record['pending'] else 0
    _write(root, record)
    return registry.Result(0)


def decide(root, identifier=None, option=None, *, servers=None, confirm=None, note=None):
    """Record the owner's answer to the pending MCP decision: y/N at the host terminal, or
    the planner session's asked gate question (#354)."""
    try:
        root = Path(root).resolve()
        with _lock(root):
            record = _read(root)
            if (record is None or record['day'] != workspace.now().date().isoformat()
                    or record['exit'] == 2 and not record['unmeasured']):
                status = cached(root)
                if status.exit == 2:
                    return status
                return (registry.Result(2, reason='MCP registry unmeasured: run wuwei mcp check') if servers
                        else registry.Result(1, reason='MCP registry has no pending decision; run bin/wuwei mcp check for the current state'))
            if servers:
                return _proceed_unmeasured(root, record, servers, confirm)
            waiting = record['pending']
            if not waiting:
                return registry.Result(1, reason='MCP registry has no pending decision; run bin/wuwei mcp check for the current state')
            identifier = identifier or Path(waiting).stem
            if Path(waiting).stem != identifier:
                return registry.Result(1, reason=f'{identifier} is not the pending MCP decision; run {command(waiting)}')
            path = root / waiting
            if path.resolve() != path:
                raise ValueError(f'decision must not use symlinks; {SYMLINK}')
            text = path.read_text(encoding='utf-8')
            fields, scores = decision.evaluate(text)
            option = decision.option_id(fields, option or '')
            if option not in scores:
                return registry.Result(1, reason=f'{identifier} options: ' + ', '.join(scores) + f'; run bin/wuwei mcp decide {identifier} <option>')
            digest = hashlib.sha256((json.dumps([record, option], sort_keys=True) + text).encode()).hexdigest()
            try:
                where = (('at the host terminal' if confirm(digest) else '') if confirm else
                         decision.owner_confirm(root, identifier, digest,
                                                f'{identifier}: record {option}.\n' + fields['Context']))
            except OSError as exc:
                return registry.Result(2, reason=str(exc))
            if not where:
                return registry.Result(1, reason=DECLINED)
            if path.read_text(encoding='utf-8') != text:
                raise ValueError(f'decision changed during confirmation; {RACE}')
            workspace.atomic_write(path, decision.owner_record(text, option, where, note))
            if option == 'proceed':
                baseline = [[m[1], m[2]] for m in map(REPORT.fullmatch, record['reports']) if m]
                workspace.atomic_write(_path(root, 'accepted-' + digest + '.json'), json.dumps(
                    {'decision': waiting, 'text': text, 'digest': digest, 'baseline': baseline}) + '\n', mode=0o444)
                unmeasured = bool(record['unmeasured'])
                record.update(pending=None, reports=[], severities=[], exit=2 if unmeasured else 0,
                              reason=record['reason'] if unmeasured else '')
                _write(root, record)
            state.append_event('mcp.decided', {'decision': waiting, 'outcome': option}, root)
        if option != 'proceed':
            # The gate keeps its answer; a later proceed still works.
            return registry.Result(1, reason=f'{identifier} recorded: {option}; to accept later, run {command(waiting)}')
        rerun = check(root)
        return registry.Result(rerun.exit, reason=f'{identifier} recorded: proceed; {rerun.reason}'.rstrip('; '))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _failure(exc)


def migrate(root, token=None):
    """Plan, and with the plan as token apply, the move of v0.12.0 report-* directories to
    <server>/<digest>.json; directories the status record still references stay."""
    root = Path(root).resolve()
    with _lock(root):
        record = _read(root)
        referenced = {Path(path).parts[2] for path in record['reports']} if record else set()
        plan, steps = [], []
        for folder in sorted(_path(root, '.').glob('report-*')):
            if folder.is_symlink() or not folder.is_dir() or folder.name in referenced:
                continue
            where, file = folder.relative_to(root), folder / 'registry-watch-report.json'
            names = [path.name for path in folder.iterdir()]
            try:
                data = json.loads(file.read_text(encoding='utf-8')) if names == [file.name] else None
            except (OSError, ValueError):
                data = None
            rows = data if isinstance(data, list) and all(isinstance(row, dict) for row in data) else []
            servers = {row.get('server_name') for row in rows}
            name = servers.pop() if len(servers) == 1 else None
            target = None
            if isinstance(name, str) and NAME.fullmatch(name) and name not in STORAGE:
                target = _path(root, name) / (digest(data) + '.json')
            if not names or data == []:
                plan.append(f'remove {where} ({"clean" if names else "empty"})')
                steps.append((folder, None, None))
            elif target and target.exists():
                plan.append(f'remove {where} (duplicate of {target.relative_to(root)})')
                steps.append((folder, None, None))
            elif target:
                plan.append(f'move {file.relative_to(root)} -> {target.relative_to(root)}')
                steps.append((folder, file, target))
            else:
                plan.append(f'keep {where}: unreadable')
        text = ''.join(line + '\n' for line in plan)
        if token == text:
            for folder, file, target in steps:
                if file:
                    target.parent.mkdir(exist_ok=True)
                    os.replace(file, target)
                shutil.rmtree(folder)
        return text
