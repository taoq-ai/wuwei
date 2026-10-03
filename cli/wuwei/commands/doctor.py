"""Owner diagnostic: every problem in the install, host, workspace, gates, day and guards, with
its fix; --fix applies the deterministic ones after one digest."""

from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from wuwei import heartbeat, integrity, registry, workspace

SECTIONS = {'install': 'Install', 'host': 'Host', 'workspace': 'Workspace',
            'gates': 'Gates and adapters', 'pr-flow': 'PR flow', 'day': 'Day and sessions',
            'guards': 'Guards'}
DOCS = {'install': 'docs/site/recovery.md#integrity-reconfirm',
        'host': 'docs/site/daily.md#1-install-the-signed-release',
        'workspace': 'docs/site/configuration.md#workspace-and-repositories',
        'gates': 'docs/site/configuration.md#mcp-registry-checks-s3',
        'pr-flow': 'docs/site/configuration.md#host-build-and-memory',
        'day': 'docs/site/reference.md#watch-state',
        'guards': 'docs/site/reference.md#heartbeat'}
CODES = {'ok': 0, 'warn': 1, 'fail': 1, 'unmeasured': 2}
OUTSIDE = "python3 - <<'EOF'\nprint('gh pr list')\nEOF"  # #323: a heredoc that mentions gh
REINSTALL = 'reinstall the signed release'
UNLOADED = 'config.toml does not load'


def _row(section, name, status, value, fix='', apply=None, detail=(), docs=None):
    row = {'section': section, 'name': name, 'status': status, 'value': value}
    if status != 'ok':
        row['fix'] = fix
        if apply:
            row['apply'] = apply
        row['docs'] = docs or DOCS[section]
    if detail:
        row['detail'] = list(detail)
    return row


def _capture(function, *args, **kwargs):
    stream = io.StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        code = function(*args, **kwargs)
    return code, stream.getvalue()


def outcome(rows):
    statuses = {row['status'] for row in rows}
    return 1 if statuses & {'warn', 'fail'} else 2 if 'unmeasured' in statuses else 0


def render(rows):
    lines = []
    for section, title in SECTIONS.items():
        selected = [row for row in rows if row['section'] == section]
        if not selected:
            continue
        lines.append(title)
        for row in selected:
            lines.append(f"  {row['status']:<10} {row['name']}: {row['value']}")
            if row['status'] != 'ok':
                lines += [f"      fix: {row['fix']}", f"      docs: {row['docs']}"]
            lines += [f'      {line}' for line in row.get('detail', ())]
    counts = {status: sum(row['status'] == status for row in rows) for status in ('fail', 'warn', 'unmeasured')}
    lines.append('doctor: ' + (', '.join(f'{n} {status}' for status, n in counts.items()) if any(counts.values())
                               else 'ok'))
    return '\n'.join(lines)


def _checkout():
    return (integrity.PLUGIN / '.git').exists() and not (integrity.PLUGIN / 'MANIFEST.sha256.sig').exists()


def _install(root, config):
    plugin = integrity.PLUGIN
    rows = []
    try:
        version = json.loads((plugin / '.claude-plugin/plugin.json').read_text())['version']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        version = f'version unreadable ({exc})'
    if (plugin / 'MANIFEST.sha256.sig').exists():
        rows.append(_row('install', 'plugin', 'ok', f'{plugin} {version} (signed release)'))
    elif (plugin / '.git').exists():
        rows.append(_row('install', 'plugin', 'ok', f'{plugin} {version} (development checkout)'))
    else:
        rows.append(_row('install', 'plugin', 'fail', f'{plugin} {version}: neither a signed release nor a checkout',
                         REINSTALL))
    if root is None:
        result = (registry.Result(0, reason='development checkout; confirmed per workspace') if _checkout()
                  else integrity.measure())
    else:
        result = integrity.fresh(root)
    reason = result.reason
    if result.exit == 0:
        rows.append(_row('install', 'integrity', 'ok', reason or 'clean'))
    elif 'run wuwei integrity check' in reason or not ('page:' in reason or 'reconfirm' in reason):
        rows.append(_row('install', 'integrity', 'fail' if result.exit == 1 else 'unmeasured', reason,
                         'wuwei integrity check'))
    elif _checkout() and root is not None:
        rows.append(_row('install', 'integrity', 'fail', reason, 'wuwei integrity reconfirm',
                         apply='integrity-reconfirm'))
    else:
        rows.append(_row('install', 'integrity', 'fail', reason,
                         'review the files named, then wuwei integrity reconfirm; or ' + REINSTALL))
    markers = plugin / integrity.MARKERS
    count = len(list(markers.iterdir())) if markers.is_dir() else 0
    notice = integrity.restart(config)
    rows.append(_row('install', 'in_use', 'warn', notice, integrity.RESTART) if notice else
                _row('install', 'in_use', 'ok', f'{count} Claude Code process markers (expected)'))
    rows.append(_hooks(root, config))
    launcher = plugin / 'bin/wuwei'
    rows.append(_row('install', 'launcher', 'ok', str(launcher)) if os.access(launcher, os.X_OK) else
                _row('install', 'launcher', 'fail', f'{launcher} not executable', f'chmod +x {launcher}'))
    version = '.'.join(map(str, sys.version_info[:3]))
    rows.append(_row('install', 'python', 'ok', version) if sys.version_info >= (3, 11) else
                _row('install', 'python', 'fail', version, 'install Python 3.11 or newer'))
    return rows


def _hooks(root, config):
    from wuwei import mcp
    plugin = integrity.PLUGIN
    try:
        hooks = json.loads((plugin / 'hooks/hooks.json').read_text())
        if not isinstance(hooks.get('hooks', {}).get('PreToolUse'), list):
            raise ValueError('no PreToolUse hooks')
    except (OSError, ValueError, AttributeError) as exc:
        return _row('install', 'hooks', 'fail', f'hooks/hooks.json: {exc}', REINSTALL)
    name = config['scanner']['mcp']['plugins_file'] if config else mcp.DEFAULTS['plugins_file']
    path = Path(name).expanduser()
    try:
        data = json.loads(((root or Path.cwd()) / path).read_text())
        listed = any(Path(entry['installPath']).expanduser().resolve() == plugin.resolve()
                     for entries in data['plugins'].values() for entry in entries)
    except FileNotFoundError:
        listed = False
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return _row('install', 'hooks', 'unmeasured', f'{name}: {exc}', f'check {name}')
    if listed:
        return _row('install', 'hooks', 'ok', 'registered in Claude Code')
    if (plugin / '.git').exists():
        return _row('install', 'hooks', 'ok', 'development checkout (loaded per session with --plugin-dir)')
    return _row('install', 'hooks', 'fail', f'not listed in {name}', '/plugin install wuwei@wuwei in Claude Code')


def _host(root, config):
    adapters = config['adapters']
    rows = []
    if adapters['code_host'] != 'github':
        rows.append(_row('host', 'gh', 'ok', 'not used'))
    elif not shutil.which('gh'):
        rows.append(_row('host', 'gh', 'fail', 'not on PATH', 'install the GitHub CLI, then gh auth login'))
    else:
        result = registry.load('code_host', config).auth_status()
        rows.append(_row('host', 'gh', ('ok', 'fail', 'unmeasured')[result.exit],
                         'authenticated' if result.exit == 0 else result.reason,
                         'gh auth login' if result.exit == 1 else 'run gh auth status and fix what it names'))
    vcs = registry.load('vcs', config)

    def resolved(path):
        found = vcs.identity(str(path))
        return found.exit == 0 and isinstance(found.data, dict), found

    good, result = resolved(root / '.wuwei' if root else Path.cwd())
    # Repositories set their own identity (repos.identity); a global one is needed only without it.
    own = config['repos'] and all(
        (repo['identity']['name'] and repo['identity']['email'])
        or resolved((root / Path(repo['path']).expanduser()).resolve())[0] for repo in config['repos'])
    rows.append(_row('host', 'git identity', 'ok', f"{result.data['name']} <{result.data['email']}>") if good else
                _row('host', 'git identity', 'ok', 'not set globally; repositories set their own') if own else
                _row('host', 'git identity', 'fail', result.reason or 'missing',
                     'git config --global user.name "<name>" and git config --global user.email "<email>"'))
    if adapters['scanner'] != 'ziran':
        rows.append(_row('host', 'ziran', 'ok', 'not used'))
    elif shutil.which('ziran'):
        rows.append(_row('host', 'ziran', 'ok', 'on PATH (version checked by every call, minimum 0.39.0)'))
    else:
        rows.append(_row('host', 'ziran', 'fail', 'not on PATH', 'install ZIRAN 0.39.0 or newer'))
    if shutil.which('claude'):
        rows.append(_row('host', 'claude', 'ok', shutil.which('claude')))
    elif adapters['inbound'] != 'none':
        rows.append(_row('host', 'claude', 'fail', 'not on PATH',
                         'install the Claude Code CLI (the listener starts headless sessions with it)'))
    else:
        rows.append(_row('host', 'claude', 'ok', 'not on PATH; only the listener needs it'))
    needed = adapters['runtime'] == 'codex' or config['gates']['second_opinion'].startswith('codex:')
    codex = shutil.which('codex')
    rows.append(_row('host', 'codex', 'fail', 'not on PATH', 'install the Codex CLI') if needed and not codex
                else _row('host', 'codex', 'ok', codex or 'not used'))
    if adapters['host'] == 'none':
        rows.append(_row('host', 'memory', 'unmeasured', 'adapters.host = "none"', 'set adapters.host = "local"'))
    else:
        result = registry.load('host', config).free_memory()
        if result.exit or type(result.data) is not int:
            rows.append(_row('host', 'memory', 'unmeasured', result.reason or 'free memory unmeasured',
                             'check the host adapter'))
        else:
            mib, floor = result.data // 2**20, config['host']['free_memory_mb']
            rows.append(_row('host', 'memory', 'ok', f'{mib} MiB') if mib >= floor else
                        _row('host', 'memory', 'fail', f'{mib} MiB below {floor} MiB',
                             'free memory, or lower host.free_memory_mb in .wuwei/config.toml'))
    manager = 'launchctl' if sys.platform == 'darwin' else 'systemctl'
    rows.append(_row('host', 'service manager', 'ok', manager) if shutil.which(manager) else
                _row('host', 'service manager', 'fail', f'{manager} not on PATH',
                     'the watch and listener need launchd (macOS) or systemd --user (Linux)'))
    return rows


def _workspace(root, config, error, found):
    from wuwei.commands import init
    if root is None:
        return [_row('workspace', 'workspace', 'fail', error or f'no .wuwei/ found from {Path.cwd()}',
                     'wuwei init --shadow in the directory that holds your repositories')]
    rows = [_row('workspace', 'workspace', 'ok', str(root / '.wuwei'))]
    if config is not None and found:
        rows.append(_row('workspace', 'config', 'warn', f'loads; {len(found)} unknown keys',
                         'remove or rename each key named below in .wuwei/config.toml', detail=found))
    elif config is not None:
        rows.append(_row('workspace', 'config', 'ok', 'loads'))
    elif 'delete that line before using [[repos]] tables' in error:
        rows.append(_row('workspace', 'config', 'fail', error, 'wuwei init --upgrade', apply='init-upgrade'))
    else:
        rows.append(_row('workspace', 'config', 'fail', error, f'edit .wuwei/config.toml: {error}'))
    code, text = _capture(init.upgrade, Namespace(path=str(root), dry_run=True))
    lines = text.splitlines()
    upgrades = [line for line in lines if line.startswith('Would upgrade')]
    charters = [line for line in lines if line.startswith('Charter override needs review')]
    if code:
        rows.append(_row('workspace', 'template', 'unmeasured', f'init --upgrade --dry-run exit {code}',
                         'wuwei init --upgrade --dry-run names the problem', detail=lines))
    elif upgrades:
        rows.append(_row('workspace', 'template', 'warn', f'{len(upgrades)} changes', 'wuwei init --upgrade',
                         apply='init-upgrade', detail=upgrades))
    else:
        rows.append(_row('workspace', 'template', 'ok', 'current'))
    if charters and not code:
        rows.append(_row('workspace', 'charter overrides', 'warn', f'{len(charters)} to review',
                         "update each override's version line after reviewing the plugin charter",
                         detail=charters, docs='docs/site/charter-overrides.md'))
    if config is None:
        return rows
    vcs = registry.load('vcs', config)
    for index, repo in enumerate(config['repos']):
        name, branch = repo['name'], repo['default_branch']
        path = (root / Path(repo['path']).expanduser()).resolve()
        if not path.is_dir():
            rows.append(_row('workspace', f'{name} path', 'fail', f'{path} missing',
                             f'edit repos.{index}.path in .wuwei/config.toml'))
            continue
        rows.append(_row('workspace', f'{name} path', 'ok', str(path)))
        if not (path / '.git').exists():
            rows.append(_row('workspace', f'{name} git', 'fail', 'not a git repository',
                             f'clone the repository at {path}, or fix repos.{index}.path'))
            continue
        rows.append(_row('workspace', f'{name} git', 'ok', 'git repository'))
        result = vcs.branches(str(path), branch)
        rows.append(_row('workspace', f'{name} branch', 'ok', branch) if result.exit == 0 and branch in result.data
                    else _row('workspace', f'{name} branch', 'unmeasured' if result.exit == 2 else 'fail',
                              result.reason or f'{branch} not found locally',
                              f'git -C {path} fetch origin {branch}:{branch}'))
        identity = repo['identity']
        if identity['name'] and identity['email']:
            rows.append(_row('workspace', f'{name} identity', 'ok', f"{identity['name']} <{identity['email']}>"))
        else:
            # ponytail: printed edit until #327 ships a confirmed `config set`; then apply='config-set'.
            found = vcs.identity(str(path))
            if found.exit == 0 and isinstance(found.data, dict):
                rows.append(_row('workspace', f'{name} identity', 'warn',
                                 f"empty; the repository resolves {found.data['name']} <{found.data['email']}>",
                                 f'set repos.{index}.identity.name = "{found.data["name"]}" and '
                                 f'repos.{index}.identity.email = "{found.data["email"]}" in .wuwei/config.toml'))
            else:
                rows.append(_row('workspace', f'{name} identity', 'fail', 'empty and unresolved',
                                 f'set repos.{index}.identity in .wuwei/config.toml'))
        checks = [command for command in repo['fast_checks'] if command.strip()]
        rows.append(_row('workspace', f'{name} fast_checks', 'ok', ', '.join(checks)) if checks else
                    _row('workspace', f'{name} fast_checks', 'warn', 'empty',
                         "wuwei config promote (fills it from the calibration; read wuwei calibrate's report first)",
                         apply='config-promote'))
    rows += _calibration(root, config)
    return rows


def _calibration(root, config):
    from wuwei import calibrate, interview, profiles, watch
    from wuwei.commands.status import SHADOW_NUDGE
    rows = []
    try:
        approved = calibrate.approved(root)
        rows.append(_row('workspace', 'calibration', 'ok', ', '.join(
            f"{name} {data.get('date', 'undated')}" for name, data in approved.items())) if approved else
            _row('workspace', 'calibration', 'warn', 'never applied', 'wuwei calibrate, then wuwei config promote'))
    except (OSError, ValueError) as exc:
        rows.append(_row('workspace', 'calibration', 'unmeasured', str(exc), 'fix .wuwei/calibration.json'))
    try:
        drifted = sorted({row['payload'].get('repo', '?') for row in
                          watch.records(workspace.day_dir(root) / 'events.jsonl')
                          if row['kind'] == 'calibration.drift'})
        rows.append(_row('workspace', 'drift', 'warn', 'calibration drift: ' + ', '.join(drifted), 'wuwei calibrate',
                         apply='calibrate') if drifted else _row('workspace', 'drift', 'ok', 'none today'))
    except watch.ERRORS as exc:
        rows.append(_row('workspace', 'drift', 'unmeasured', str(exc), 'wuwei state recover in a host terminal'))
    try:
        answers = interview.load(root, config)
        rows.append(_row('workspace', 'interview', 'ok', f'{len(answers)} answers today' if answers else
                         'none today (wuwei calibrate --interview asks again)'))
    except (OSError, ValueError) as exc:
        rows.append(_row('workspace', 'interview', 'unmeasured', str(exc), 'wuwei calibrate --interview'))
    try:
        name, _ = profiles.load(root, config)
        rows.append(_row('workspace', 'profile', 'ok',
                         f"guards profile {config['profile']}; calibration profile {name or 'none'}"))
    except (OSError, ValueError) as exc:
        rows.append(_row('workspace', 'profile', 'unmeasured', str(exc), 'wuwei calibrate import <profile>'))
    guards, name = config['guards'], workspace.posture(config)[0]
    if name != 'observe':
        rows.append(_row('workspace', 'posture', 'ok', name))
    else:
        from datetime import date
        since = guards['shadow_since']
        days = (workspace.now().date() - date.fromisoformat(since)).days if since else 0
        left = guards['shadow_days'] - days
        rows.append(_row('workspace', 'posture', 'ok', f'observe, {left} days left') if left > 0 else
                    _row('workspace', 'posture', 'warn', SHADOW_NUDGE.format(days=days),
                         'set security.posture = "guarded" in .wuwei/config.toml, or raise guards.shadow_days'))
    return rows


def _gates(root, config):
    from wuwei import mcp
    from wuwei.commands import config as config_command
    code, text = _capture(config_command.run, Namespace())
    rows = [_row('gates', 'config check', ('ok', 'fail', 'unmeasured')[code], f'exit {code}',
                 'apply the fix each detail line names', docs='docs/site/configuration.md',
                 detail=[line.strip() for line in text.splitlines() if line.strip()] if code else ())]
    result = mcp.cached(root)
    rows.append(_row('gates', 'mcp gate', ('ok', 'fail', 'unmeasured')[result.exit], result.reason or 'clean',
                     '' if not result.exit else 'wuwei mcp check' if result.exit == 2
                     else f'{mcp.command(mcp.pending(root))} in a host terminal'))
    legacy = list(Path(root, '.wuwei/ziran').glob('report-*'))
    if legacy:
        rows.append(_row('gates', 'mcp reports', 'warn', f'{len(legacy)} report directories in the v0.12.0 layout',
                         'wuwei doctor --fix', apply='mcp-reports'))
    try:
        record = mcp._read(Path(root).resolve())
    except (OSError, ValueError) as exc:
        return rows + [_row('gates', 'mcp servers', 'unmeasured', str(exc), 'wuwei mcp check')]
    if record and record['day'] == workspace.now().date().isoformat():
        for name, _ in record['unmeasured']:
            rows.append(_row('gates', f'mcp {name}', 'warn', 'unmeasured',
                             f'wuwei mcp decide proceed-unmeasured {name} (or fix the server, then wuwei mcp check)'))
        for name, _ in record['decided']:
            rows.append(_row('gates', f'mcp {name}', 'ok', 'proceeding unmeasured by owner decision'))
        for note in record['reason'].split('; '):
            name, _, value = note.partition(': ')
            if value == 'not attached (unapproved)':
                rows.append(_row('gates', f'mcp {name}', 'ok', value))
    return rows


NONE = {'tracker': 'none: discovery reads no tracker backlog',
        'chat': 'none: no review pings or chat posts; reviewers are requested on the code host only',
        'review_bot': 'none: discovery reads no review-bot findings'}


def pr_flow(config):
    """The settings the PR flow reads, from config alone: empty ones warn with what they block."""
    from wuwei.obligations import _owner_login

    def quoted(key, placeholder):
        return f"""bin/wuwei config set {key} '"{placeholder}"'"""

    shepherd, solo = config['shepherd'], config['shepherd']['min_reviewers'] == 0
    try:
        rows = [_row('pr-flow', 'owner.handles', 'ok', _owner_login(config))]
    except ValueError as exc:
        rows = [_row('pr-flow', 'owner.handles', 'warn',
                     f'{exc}; will block: reviewer selection, review replies and obligations at pr raise',
                     """bin/wuwei config set owner.handles '["<code-host login>"]'""")]
    checks = [('shepherd.lead_login', shepherd['lead_login'], 'the lead review request at pr raise',
               quoted('shepherd.lead_login', '<lead login>')),
              ('shepherd.authors', f"{len(shepherd['authors'])} mapped" if shepherd['authors'] else '',
               'reviewer mentions in the review ping at pr ping',
               'bin/wuwei setup (maps your git email and the bot authors), or add '
               '"<email>" = {login = "<login>", mention = "<chat id>"} under [shepherd.authors]')]
    if config['adapters']['chat'] != 'none':
        checks.append(('shepherd.review_channel', shepherd['review_channel'], 'the review ping at pr ping',
                       quoted('shepherd.review_channel', '<channel id>')))
    for name, value, phase, fix in checks:
        rows.append(_row('pr-flow', name, 'ok', 'not applicable: shepherd.min_reviewers = 0') if solo else
                    _row('pr-flow', name, 'ok', value) if value else
                    _row('pr-flow', name, 'warn', f'empty; will block: {phase}', fix))
    return rows + [_row('pr-flow', f'adapters.{kind}', 'ok',
                        NONE[kind] if config['adapters'][kind] == 'none' else config['adapters'][kind])
                   for kind in NONE]


PROBE = {'ok': 'ok', 'failed': 'fail', 'unmeasured': 'unmeasured'}


def _day(root, config, probes):
    from wuwei.commands import status
    rows = [_row('day', 'state', PROBE[probes['state']['result']], probes['state']['value'],
                 'wuwei state recover in a host terminal'),
            _row('day', 'planner', PROBE[probes['planner']['result']], probes['planner']['value'],
                 'wuwei plan session <session id> --take-over from the live session')]
    try:
        found, watch_health, listen_health, beat, _ = status.scan(workspace.day_dir(root))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return rows + [_row('day', 'day', 'unmeasured', str(exc), 'wuwei state recover in a host terminal')]
    for name, health in (('watch', watch_health), ('listener', listen_health)):
        command = 'watch' if name == 'watch' else 'listen'
        if name == 'listener' and config['adapters']['inbound'] == 'none':
            rows.append(_row('day', name, 'ok', 'not used'))
        elif health == 'alive':
            rows.append(_row('day', name, 'ok', 'alive'))
        elif health == 'off':
            rows.append(_row('day', name, 'warn', 'not installed', f'wuwei {command} install',
                             apply=f'{command}-install'))
        elif health == 'dead':
            rows.append(_row('day', name, 'fail', 'dead', f'wuwei {command} uninstall, then wuwei {command} '
                             f'install (read .wuwei/{command}.stderr.log first)'))
        else:
            rows.append(_row('day', name, 'unmeasured', 'unmeasured', f'wuwei {command} names the problem'))
    rows.append(_row('day', 'heartbeat', {None: 'ok', 'ok': 'ok', 'degraded': 'fail'}.get(beat, 'unmeasured'),
                     beat or 'none today', 'wuwei heartbeat names the failed probe'))
    for page in found:
        if page['tier'] == 'page':
            rows.append(_row('day', page['source'] + (' page' if page['source'] == 'heartbeat' else ''), 'fail',
                             str(page['reason']), 'wuwei nudges'))
    nudges = sum(page['tier'] == 'nudge' for page in found)
    rows.append(_row('day', 'nudges', 'ok', f'{nudges} open (wuwei nudges lists them)'))
    try:
        if ids := _legacy_traces(root):
            rows.append(_row('day', 'trace decisions', 'warn', f'{", ".join(ids)} pending under the pre-#352 rule',
                             'wuwei doctor --fix', apply='trace-decisions'))
    except (OSError, ValueError) as exc:
        rows.append(_row('day', 'trace decisions', 'unmeasured', str(exc), 'wuwei state recover in a host terminal'))
    return rows


LEGACY_TRACE = ('Question: How should this critical tool sequence be investigated?\n'
                'Context: Session has no matching item reservation.\n')
SUPERSEDED = 'superseded by wuwei doctor --fix: tool-sequence decisions apply to item seats only (#352)'


def _legacy_traces(root):
    """Today's pending, unanswered decisions the pre-#352 sweep wrote for a non-seat session."""
    from wuwei import decision, state
    data = state.read_state(root)
    return [path.stem for path in sorted((workspace.day_dir(root) / 'decisions').glob('D-*.md'))
            if not path.is_symlink()
            and (text := path.read_text(encoding='utf-8')).startswith(LEGACY_TRACE)
            and re.search(r'^Outcome: pending$', text, re.M)
            and decision.answered(data, path.stem) is None]


def _guards(root, probes):
    from wuwei.commands.hook import HEARTBEAT_SESSION
    rows = [_row('guards', name, PROBE[probes[name]['result']], probes[name]['value'],
                 'fix the integrity row first' if 'plugin integrity' in probes[name]['value'] else
                 'the hook no longer behaves as shipped; run wuwei integrity check and ' + REINSTALL)
            for name in ('refused', 'allowed', 'state_write', 'read_loop', 'status_line')] if root is not None else []
    fix = 'upgrade WUWEI: outside a workspace every hook must allow (#323)'
    try:
        with tempfile.TemporaryDirectory() as outside:
            payload = json.dumps({'session_id': HEARTBEAT_SESSION, 'transcript_path': os.devnull, 'cwd': outside,
                                  'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
                                  'tool_input': {'command': OUTSIDE}})
            (result,), _ = registry.watch_service().probe([(('hook', 'PreToolUse'), payload)], outside)
        code, line, _ = result
        rows.append(_row('guards', 'outside workspace', 'ok', 'exit 0') if code == 0 else
                    _row('guards', 'outside workspace', 'unmeasured', 'timeout', fix) if code is None else
                    _row('guards', 'outside workspace', 'fail', f'exit {code}: {line}', fix))
    except (OSError, ValueError) as exc:
        rows.append(_row('guards', 'outside workspace', 'unmeasured', str(exc), fix))
    return rows


def diagnose(section=None):
    """Every row (or one section's), in section order; reads only (heartbeat's state.lock aside)."""
    error = None
    try:
        root = workspace.find_workspace()
    except FileNotFoundError:
        root = None
    except ValueError as exc:
        root, error = None, str(exc)
    config, found = None, []
    if root is not None:
        try:
            config = workspace.load_config(root, warnings=found)
        except workspace.ConfigError as exc:
            error = str(exc)
    if section == 'pr-flow':
        return pr_flow(config) if config else [
            _row('pr-flow', 'config', 'unmeasured', error or ('no workspace' if root is None else UNLOADED),
                 'fix config.toml first')]
    defaults = config or workspace._validate({}, workspace.SCHEMA, (), '')
    probes = heartbeat.measure(root) if root is not None else None
    rows = [*_install(root, config), *_host(root, defaults), *_workspace(root, config, error, found)]
    if root is not None:
        if config is None:
            rows += [_row('gates', 'gates', 'unmeasured', UNLOADED, 'fix config.toml first'),
                     _row('day', 'day', 'unmeasured', UNLOADED, 'fix config.toml first')]
        else:
            rows += [*_gates(root, config), *pr_flow(config), *_day(root, config, probes)]
    return rows + _guards(root, probes)


def _dry(function, args):
    code, text = _capture(function, args)
    if code:
        raise ValueError(text.strip() or f'dry run exit {code}')
    return text


def _planned(command, make):
    """A fix previewed by the command's own dry run, applied only while that plan is unchanged."""
    def preview(root):
        text = _dry(*make(root, True))
        return text, text

    def apply(root, token):
        if _dry(*make(root, True)) != token:
            print(f'{command}: changed since the preview; nothing applied')
            return 1
        function, args = make(root, False)
        return function(args)
    return command, preview, apply


def _upgrade(root, dry):
    from wuwei.commands import init
    return init.upgrade, Namespace(path=str(root), dry_run=dry)


def _service(name):
    def make(root, dry):
        from wuwei.commands import watch
        return (lambda args: watch.service(args, name, None),
                Namespace(**{f'{name}_action': 'install'}, once=False, dry_run=dry))
    return make


def _reconfirm_preview(root):
    result = integrity.check(root)
    if not result.data:
        raise ValueError(result.reason or 'nothing to confirm')
    return f'installation fingerprint {result.data}\n', result.data


def _reconfirm(root, token):
    result = integrity.reconfirm(root, confirm=lambda value: value == token)
    if result.reason:
        print(result.reason)
    return result.exit


def _promote_preview(root):
    from wuwei.commands import config
    seen = []
    _, text = _capture(config.promote, Namespace(), confirm=lambda digest, **_: seen.append(digest))
    if not seen:
        raise ValueError(text.strip() or 'nothing to promote')
    # Interview answers and profile settings carry owner decisions (merge.auto, posture): run it yourself.
    if any(line == 'Interview answers:' or line.startswith('Profile ') for line in text.splitlines()):
        raise ValueError('it would also apply interview or profile settings; review them and run it yourself')
    return text.replace('wuwei config promote: declined; nothing written\n', ''), seen[0]


def _promote(root, token):
    from wuwei.commands import config
    return config.promote(Namespace(), confirm=lambda digest, **_: digest == token)


def _supersede_preview(root):
    ids = _legacy_traces(root)
    if not ids:
        raise ValueError('nothing to supersede')
    return ''.join(f'{ident}: Outcome: superseded ({SUPERSEDED})\n' for ident in ids), ids


def _supersede(root, token):
    """Close each previewed record: the Outcome line for the board, an owner outcome for close,
    status and the steward queue."""
    from wuwei import decision, state
    if _legacy_traces(root) != token:
        print('trace-decisions: changed since the preview; nothing applied')
        return 1
    for ident in token:
        path = decision.today_path(ident, root)
        text = path.read_text(encoding='utf-8')
        fields, _ = decision.evaluate(text)
        text = re.sub(r'^Outcome: pending$', 'Outcome: superseded', text, count=1, flags=re.M)
        workspace.atomic_write(path, text + f'Notes: {SUPERSEDED}\n')
        outcome = {'option': 'superseded', 'outcome': 'superseded', 'decided_by': 'owner',
                   'reversibility': fields['Reversibility']}
        state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update({ident: outcome}),
                           root, reserved=False, kind='decision.decided',
                           payload={'id': ident, 'option': 'superseded', 'decided_by': 'owner',
                                    'reversibility': fields['Reversibility']})
    return 0


def _calibrate(root, token):
    from wuwei.commands import calibrate
    return calibrate.run(Namespace(action=None, target=None, repo=None, measure=False, skip=[],
                                   interview=None, questions=False, answer=None))


def _reports_preview(root):
    from wuwei import mcp
    plan = mcp.migrate(root)
    return plan, plan


def _reports(root, token):
    from wuwei import mcp
    if mcp.migrate(root, token) != token:
        print('move legacy MCP reports: changed since the preview; nothing applied')
        return 1
    return 0


# The --fix allow list (a test pins it): id -> (command shown, preview(root) -> (text, token),
# apply(root, token) -> exit). Decisions (mcp decide, security.posture, state recover, the code host)
# stay printed. config-set waits for #327's confirmed `config set`.
FIXES = {
    'integrity-reconfirm': ('wuwei integrity reconfirm', _reconfirm_preview, _reconfirm),
    'init-upgrade': _planned('wuwei init --upgrade', _upgrade),
    'config-promote': ('wuwei config promote', _promote_preview, _promote),
    'calibrate': ('wuwei calibrate', lambda root: (
        "profile the configured repositories; writes today's calibration.md and charter proposals; "
        'config.toml unchanged\n', None), _calibrate),
    'watch-install': _planned('wuwei watch install', _service('watch')),
    'listen-install': _planned('wuwei listen install', _service('listen')),
    'trace-decisions': ('supersede pre-#352 tool-sequence decisions', _supersede_preview, _supersede),
    'mcp-reports': ('move legacy MCP reports', _reports_preview, _reports),
}


def widgets(root, batch):
    """The batch as multi-select widgets of at most four fixes; one fix gets a Skip option."""
    from wuwei import decision
    options = [(name, f'{FIXES[name][0]}: {(text.strip().splitlines() or [""])[0]}')
               for name, text, _ in batch]
    count = -(-len(options) // 4)
    return [decision.widget(decision.gate(root) + 'Apply these doctor fixes'
                            + (f' ({i + 1} of {count})' if count > 1 else '') + '?', 'Fixes',
                            options[i::count] + [('Skip', 'Apply nothing now; doctor lists it again.')]
                            * (len(options[i::count]) == 1),
                            'wuwei doctor --fix --apply <labels>', multi=True)
            for i in range(count)]


def fix(rows, confirm=None, only=None, widget=False):
    """Preview the allow-listed fixes, ask for one digest, apply each bound to its preview, re-diagnose.
    only narrows the batch to those fix ids; widget prints the batch as widgets and applies nothing."""
    import hashlib
    from wuwei import state
    wanted = {row['apply'] for row in rows if row.get('apply') in FIXES}
    if only is not None:
        only = set(only) - {'Skip'}  # the widget's Skip option picked alongside fixes
        unknown = sorted(only - set(FIXES))
        if unknown:
            print(f'wuwei doctor: unknown fix {", ".join(unknown)}; use one of: {", ".join(FIXES)}',
                  file=sys.stderr)
            return 2
        wanted &= only
    held = [f"{row['name']}: {row['fix']}" for row in rows
            if row['status'] != 'ok' and row.get('apply') not in FIXES]
    root = workspace.find_workspace() if wanted else None
    batch = []
    for name in [name for name in FIXES if name in wanted]:
        command, preview, _ = FIXES[name]
        try:
            text, token = preview(root)
        except (OSError, ValueError) as exc:
            held.append(f'{command}: cannot be applied now: {exc}')
            continue
        batch.append((name, text, token))
    notes = 'Not applied:\n' + ''.join(f'  {line}\n' for line in held) if held else ''
    if widget:
        plan = workspace.day_dir(root) / 'plan.md' if root else None
        if batch and not (plan and plan.is_file() and plan.resolve() == plan):
            print('wuwei doctor: no plan today for the question to cite; '
                  'run wuwei doctor --fix in a host terminal', file=sys.stderr)
            return 1
        print(notes, end='', file=sys.stderr)
        print(json.dumps(widgets(root, batch), indent=2))
        return outcome(rows)
    if not batch:
        print(notes + 'Nothing to apply')
        return outcome(rows)
    text = ''.join(f'[{name}] {FIXES[name][0]}\n{preview.rstrip()}\n' for name, preview, _ in batch) + notes
    print(text, end='')
    try:
        accepted = (confirm or (lambda value: integrity._host_confirm(
            value, prompt='Review the fixes above. To apply them all, type:')))(
            hashlib.sha256(text.encode()).hexdigest()[:12])
    except OSError as exc:
        print(f'wuwei doctor: {exc}', file=sys.stderr)
        return 2
    if not accepted:
        print('wuwei doctor: declined; nothing applied', file=sys.stderr)
        return 1
    for name, _, token in batch:
        try:
            code = FIXES[name][2](root, token)
        except (OSError, ValueError) as exc:
            print(f'{name}: {exc}')
            code = 2
        print(f'{name}: exit {code}')
        state.append_event('doctor.fixed', {'fix': name, 'exit': code}, root)
    rows = diagnose()
    print(render(rows))
    return outcome(rows)


def register(subparsers):
    parser = subparsers.add_parser('doctor', help='Find install, host, workspace and guard problems and their fixes')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fix', action='store_true', help='apply the allow-listed fixes after one host confirmation')
    mode.add_argument('--json', action='store_true', help='print {"exit", "rows"} as JSON')
    parser.add_argument('--widget', action='store_true',
                        help='with --fix: print the batch as AskUserQuestion widgets; apply nothing')
    parser.add_argument('--apply', metavar='IDS', help='with --fix: apply only these comma-separated fix ids')
    parser.add_argument('--section', choices=['pr-flow'], help='print one section only')
    parser.set_defaults(func=run)


def run(args, confirm=None):
    if (args.widget or args.apply) and not args.fix or args.widget and args.apply:
        print('wuwei doctor: --widget and --apply each need --fix, not both', file=sys.stderr)
        return 2
    rows = diagnose(args.section)
    if args.json:
        print(json.dumps({'exit': outcome(rows), 'rows': rows}))
        return outcome(rows)
    if not args.widget:
        print(render(rows))
    only = [name.strip() for name in args.apply.split(',') if name.strip()] if args.apply else None
    return fix(rows, confirm, only=only, widget=args.widget) if args.fix else outcome(rows)
