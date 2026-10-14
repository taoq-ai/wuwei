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

from wuwei import integrity, registry, workspace

SECTIONS = {'install': 'Install', 'host': 'Host', 'workspace': 'Workspace',
            'gates': 'Gates and adapters', 'pr-flow': 'PR flow', 'day': 'Day and sessions',
            'guards': 'Guards', 'processes': 'Processes'}
DOCS = {'install': 'docs/site/recovery.md#integrity-reconfirm',
        'host': 'docs/site/index.md#start-here',
        'workspace': 'docs/site/configuration.md#workspace-and-repositories',
        'gates': 'docs/site/security.md#ziran-integration',
        'pr-flow': 'docs/site/configuration.md#host-build-and-memory',
        'day': 'docs/site/reference.md#stuck-seats',
        'guards': 'docs/site/reference.md#doctor', 'processes': 'docs/site/reference.md#housekeeping'}
CODES = {'ok': 0, 'warn': 1, 'fail': 1, 'unmeasured': 2, 'waiting': 2}
OUTSIDE = "python3 - <<'EOF'\nprint('gh pr list')\nEOF"  # #323: a heredoc that mentions gh
REINSTALL = 'reinstall the signed release'
LIMITED = 'GitHub rate limit until '  # adapters/_http.RateLimited's text (#738)
FROM = 'WUWEI_DOCTOR_FROM'  # #645: set on the handed-over doctor; the launcher that was invoked
UNLOADED = 'config.toml does not load'


def identity_row(repo, index, path, vcs):
    """#605: the commit and push guard's rule, reason and fix; the fix names what git resolves."""
    from wuwei import commit_push
    identity, name = repo['identity'], f"{repo['name']} identity"
    if not commit_push.unset_identity(identity):
        return _row('workspace', name, 'ok', f"{identity['name']} <{identity['email']}>")
    found = vcs.identity(str(path))
    return _row('workspace', name, 'fail', *commit_push.unset_identity(
        identity, index, found.data if found.exit == 0 and isinstance(found.data, dict) else None))


def _row(section, name, status, value, fix='', apply=None, detail=(), docs=None):
    row = {'section': section, 'name': name, 'status': status, 'value': value}
    if status != 'ok':
        # #362: fixes name the real launcher; no wuwei shim is on PATH.
        row['fix'] = re.sub(r'(?<![\w/@:.-])(?:bin/)?wuwei(?= [a-z-])',
                            lambda _: str(integrity.PLUGIN / 'bin/wuwei'), fix)
        if apply:
            row['apply'] = apply
        row['docs'] = docs or DOCS[section]
    if detail:
        row['detail'] = list(detail)
    return row


def _limited(section, name, reason):
    """#784: a GitHub rate limit is a wait, not a broken credential or tracker."""
    if LIMITED in (reason or ''):
        return _row(section, name, 'waiting', 'rate limited until ' + reason.split(LIMITED, 1)[1],
                    'wait until the reset it names (another job on the same GitHub account '
                    'shares the limit), then run doctor again')


def _capture(function, *args, **kwargs):
    stream = io.StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        code = function(*args, **kwargs)
    return code, stream.getvalue()


def outcome(rows):
    statuses = {row['status'] for row in rows}
    return 1 if statuses & {'warn', 'fail'} else 2 if statuses & {'unmeasured', 'waiting'} else 0


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
    counts = {status: sum(row['status'] == status for row in rows) for status in ('fail', 'warn', 'unmeasured', 'waiting')}
    lines.append('doctor: ' + (', '.join(f'{n} {status}' for status, n in counts.items()) if any(counts.values())
                               else 'ok'))
    return '\n'.join(lines)


_checkout = integrity.development


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
    elif result.exit == 2 and 'page:' not in reason or not ('page:' in reason or 'reconfirm' in reason):
        # #848: doctor reads the cached verdict; the reconfirm fix measures it again.
        rows.append(_row('install', 'integrity', 'fail' if result.exit == 1 else 'unmeasured', reason,
                         'wuwei doctor --fix --apply integrity-reconfirm, which measures it again',
                         apply='integrity-reconfirm' if root is not None else None))
    elif _checkout() and root is not None:
        rows.append(_row('install', 'integrity', 'fail', reason, 'wuwei doctor --fix --apply integrity-reconfirm',
                         apply='integrity-reconfirm'))
    else:
        rows.append(_row('install', 'integrity', 'fail', reason,
                         'review the files named, then wuwei doctor --fix --apply integrity-reconfirm; or ' + REINSTALL))
    markers = plugin / integrity.MARKERS
    count = len(list(markers.iterdir())) if markers.is_dir() else 0
    notice = integrity.restart(config)
    rows.append(_row('install', 'in_use', 'warn', notice, integrity.RESTART) if notice else
                _row('install', 'in_use', 'ok', f'{count} Claude Code process markers (expected)'))
    rows.append(_hooks(root, config))
    rows += _installs(root, config)
    launcher = plugin / 'bin/wuwei'
    rows.append(_row('install', 'launcher', 'ok', str(launcher)) if os.access(launcher, os.X_OK) else
                _row('install', 'launcher', 'fail', f'{launcher} not executable', f'chmod +x {launcher}'))
    version = '.'.join(map(str, sys.version_info[:3]))
    rows.append(_row('install', 'python', 'ok', version) if sys.version_info >= (3, 11) else
                _row('install', 'python', 'fail', version, 'install Python 3.11 or newer'))
    return rows + _invoked(root)


def _invoked(root):
    """#645: on a handed-over doctor, which copy was invoked, which reports, which the hooks measured."""
    invoked, here = os.environ.get(FROM, ''), integrity.PLUGIN / 'bin/wuwei'
    try:
        measured = json.loads((root / '.wuwei/integrity/verdict.json').read_text())['plugin']
    except (OSError, ValueError, KeyError, TypeError):
        measured = None
    measured = measured if isinstance(measured, str) else 'unknown'
    rows = [] if measured == 'unknown' or Path(measured).resolve() == integrity.PLUGIN.resolve() else [
        _row('install', 'hooks copy', 'warn', f'the SessionStart hook last measured plugin integrity from '
             f'{measured}; this report comes from {integrity.PLUGIN}, so the hooks may run another copy',
             f"{Path(measured) / 'bin/wuwei'} doctor")]
    if not invoked or Path(invoked).resolve() == here.resolve():
        return rows
    return rows + [_row('install', 'invoked', 'ok', f'invoked as {invoked}; reported by {here}, the launcher '
                 f'.wuwei/executable names; plugin integrity last measured from {measured} '
                 '(the SessionStart hook measures it)')]


def _hooks(root, config):
    plugin = integrity.PLUGIN
    try:
        hooks = json.loads((plugin / 'hooks/hooks.json').read_text())
        if not isinstance(hooks.get('hooks', {}).get('PreToolUse'), list):
            raise ValueError('no PreToolUse hooks; reinstall the signed release, then run bin/wuwei doctor')
    except (OSError, ValueError, AttributeError) as exc:
        return _row('install', 'hooks', 'fail', f'hooks/hooks.json: {exc}', REINSTALL)
    name = (config['scanner']['mcp']['plugins_file'] if config
            else workspace.SCHEMA['scanner']['mcp']['plugins_file'][1])
    try:
        listed = integrity.registered(root, config) is not None  # from either launcher (#601)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return _row('install', 'hooks', 'unmeasured', f'{name}: {exc}', f'check {name}')
    if listed:
        return _row('install', 'hooks', 'ok', 'registered in Claude Code')
    if (plugin / '.git').exists():
        return _row('install', 'hooks', 'ok', 'development checkout (loaded per session with --plugin-dir)')
    return _row('install', 'hooks', 'fail', f'not listed in {name}', '/plugin install wuwei@wuwei in Claude Code')


def _installs(root, config):
    """One warn row when more than one plugin install is in play (#601), else none."""
    seen = {}

    def add(directory, role):
        seen.setdefault(Path(directory).resolve(), []).append(role)

    add(integrity.PLUGIN, 'this launcher')
    try:
        found = integrity.registered(root, config)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        found = None  # the hooks row reports a broken plugins file
    if found:
        add(found, 'registered in Claude Code; its hooks run')
    recorded = integrity.recorded(root) if root is not None else ''
    if recorded and Path(recorded).exists():
        add(Path(recorded).resolve().parents[1], 'named by .wuwei/executable')
    if len(seen) < 2:
        return []
    canonical = integrity.launcher(root, config)
    others = ', '.join(str(path) for path in seen if path != canonical.resolve().parents[1])
    return [_row('install', 'installs', 'warn',
                 '; '.join(f'{path} ({", ".join(roles)})' for path, roles in seen.items()),
                 f'{canonical} init --upgrade, then remove {others} if you do not use it')]


def _host(root, config):
    adapters = config['adapters']
    rows = []
    if adapters['code_host'] != 'github':
        rows.append(_row('host', 'gh', 'ok', 'not used'))
    elif not shutil.which('gh'):
        rows.append(_row('host', 'gh', 'fail', 'not on PATH', 'install the GitHub CLI, then gh auth login'))
    else:
        result = registry.load('code_host', config).auth_status(root=root)
        rows.append(_limited('host', 'gh', result.reason) or _row(
            'host', 'gh', ('ok', 'fail', 'unmeasured')[result.exit],
            'authenticated' if result.exit == 0 else result.reason,
            'gh auth login' if result.exit == 1 else 'run gh auth status and fix what it names'))
    vcs = registry.load('vcs', config)

    def resolved(path):
        found = vcs.identity(str(path))
        return found.exit == 0 and isinstance(found.data, dict), found

    good, result = resolved(root / '.wuwei' if root else Path.cwd())
    # Repositories set their own identity (repos.identity); a global one is needed only without it.
    own = root is None or config['repos'] and all(
        (repo['identity']['name'] and repo['identity']['email'])
        or resolved((root / Path(repo['path']).expanduser()).resolve())[0] for repo in config['repos'])
    rows.append(_row('host', 'git identity', 'ok', f"{result.data['name']} <{result.data['email']}>") if good else
                _row('host', 'git identity', 'ok', 'not set globally; repositories set their own') if own else
                _row('host', 'git identity', 'fail', result.reason or 'missing',
                     'git config --global user.name "<name>" and git config --global user.email "<email>"'))
    if adapters['scanner'] != 'ziran':
        rows.append(_row('host', 'ziran', 'ok', 'not used'))
    elif shutil.which('ziran'):
        rows.append(_row('host', 'ziran', 'ok', 'on PATH (version checked once per command, minimum 0.39.0)'))
    else:
        rows.append(_row('host', 'ziran', 'fail', 'not on PATH', 'install ZIRAN 0.39.0 or newer'))
    needed = adapters['runtime'] == 'codex' or config['gates']['second_opinion'].startswith('codex:')
    codex = shutil.which('codex')
    rows.append(_row('host', 'codex', 'fail', 'not on PATH', 'install the Codex CLI') if needed and not codex
                else _row('host', 'codex', 'ok', codex or 'not used'))
    try:
        from wuwei import state
        policy = state.read_state(root)['seat_policy'].values() if root else ()
    except (OSError, ValueError):
        policy = ()
    if gap := codex_gap(config, policy):  # #860
        script = _companion(config)
        rows.append(_row('host', 'codex.command', 'warn', gap + (f'; companion found at {script}' if script else ''),
                         "bin/wuwei config set codex.command '[\"node\", \"" + (script or '<path to codex-companion.mjs>')
                         + "\"]'"))
    if adapters['host'] == 'none':
        rows.append(_row('host', 'memory', 'unmeasured', 'adapters.host = "none"', 'set adapters.host = "local"'))
    else:
        result = registry.load('host', config).free_memory()
        if result.exit or type(result.data) is not int:
            rows.append(_row('host', 'memory', 'unmeasured', result.reason or 'free memory unmeasured',
                             'check the host adapter'))
        else:
            from wuwei.guards.agent_launch import free_percent
            mib, floor = result.data // 2**20, config['host']['free_memory_mb']
            pct, share, value = config['host']['min_free_memory_pct'], None, f'{mib} MiB (floor {floor} MiB); '
            try:  # #898: the share free and its floor, beside the MiB floor
                share = free_percent(config, root)
                reading = f'{share}% free ' + (f'(floor {pct}%)' if pct else '(floor off)')
            except ValueError as exc:
                reading = str(exc)
            if mib < floor:
                rows.append(_row('host', 'memory', 'fail', f'{mib} MiB below {floor} MiB',
                                 'free memory, or lower host.free_memory_mb in .wuwei/config.toml'))
            elif pct and share is None:
                rows.append(_row('host', 'memory', 'unmeasured', value + reading,
                                 'check the host adapter, or set host.min_free_memory_pct = 0'))
            elif pct and share < pct:
                rows.append(_row('host', 'memory', 'fail', value + f'{share}% free below the floor {pct}%',
                                 'free memory, or lower host.min_free_memory_pct in .wuwei/config.toml'))
            else:
                rows.append(_row('host', 'memory', 'ok', value + reading))
    return rows


CODEX_GAP = 'codex.command empty: runtime codex unavailable'


def _companion(config):
    """#860: the installed codex plugin's companion script, else None."""
    try:
        plugins = json.loads(Path(config['scanner']['mcp']['plugins_file']).expanduser()
                             .read_text(encoding='utf-8'))['plugins']
        scripts = [Path(row['installPath']) / 'scripts/codex-companion.mjs'
                   for name, rows in plugins.items() if name.startswith('codex@') for row in rows]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return next((str(script) for script in scripts if script.is_file()), None)


def codex_gap(config, policy=()):
    """#860: CODEX_GAP when codex.command is empty and the codex runtime is wanted (the runtime,
    the second opinion, a codex usage window, a seat policy row) or its plugin is installed."""
    if config['codex']['command']:
        return ''
    wanted = ('codex' in (config['adapters']['runtime'], config['gates']['second_opinion'].partition(':')[0])
              or any(config['budget']['codex'].values())
              or any('codex' in (row.get('runtime'), row.get('alternate')) for row in policy if isinstance(row, dict)))
    return CODEX_GAP if wanted or _companion(config) else ''


def _workspace(root, config, error, found):
    from wuwei.commands import init
    if root is None:
        return [_row('workspace', 'workspace', 'fail', error or f'no .wuwei/ found from {Path.cwd()}',
                     'bin/wuwei init --shadow in the directory that holds your repositories')]
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
    for line in lines:
        if 'guide block not written: ' in line:
            rows.append(_row('workspace', 'guide', 'warn', line.split('not written: ', 1)[1].removesuffix('; run bin/wuwei doctor for the fix'),
                             'fix the memory.export_to file as the reason says, then run wuwei init --upgrade'))
    launcher = integrity.launcher(root, config)
    recorded = integrity.recorded(root)
    if recorded and Path(recorded).resolve() == launcher.resolve():
        rows.append(_row('workspace', 'executable', 'ok', recorded))
    else:
        rows.append(_row('workspace', 'executable', 'fail',
                         f'{recorded} is missing' if recorded and not Path(recorded).exists()
                         else f'{recorded} is not {launcher}' if recorded
                         else '.wuwei/executable is missing or empty',
                         'wuwei init --upgrade', apply='init-upgrade'))
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
        rows.append(identity_row(repo, index, path, vcs))
        checks = [command for command in repo['fast_checks'] if command.strip()]
        from wuwei import fast_checks  # #600: none configured is a state, not a finding
        rows.append(_row('workspace', f'{name} fast_checks', 'ok', ', '.join(checks) or fast_checks.NONE))
        for command in checks:  # #520: only checks naming a relative interpreter get a row
            found = fast_checks.interpreter(command, path, repo, root, config)
            if found and found[1] == 'missing':
                rows.append(_row('workspace', f'{name} check interpreter', 'warn',
                                 f'{command.split()[0]} not found in {path}',
                                 'set [checks] python or [checks] bootstrap in .wuwei/config.toml'))
            elif found:
                source = 'main worktree' if found[1] == 'worktree' else found[1]
                rows.append(_row('workspace', f'{name} check interpreter', 'ok', f'{found[0]} ({source})'))
        from wuwei import specmode
        engine = config['spec']['engine']
        found = True if specmode.mode(config) == 'off' else specmode.present(path, engine, config)
        rows.append(_row('workspace', f'{name} spec', 'ok', specmode.label(config)) if found else
                    _row('workspace', f'{name} spec', 'fail', f'{engine} not found in {path}',
                         specmode.INSTALL[engine]) if found is False else
                    _row('workspace', f'{name} spec', 'unmeasured',
                         f"{config['scanner']['mcp']['plugins_file']} is unreadable",
                         f'check scanner.mcp.plugins_file, or run {specmode.INSTALL[engine]}'))
    rows += _calibration(root, config)
    return rows


def _calibration(root, config):
    from wuwei import calibrate, watch
    rows = []
    try:
        approved = calibrate.approved(root)
        rows.append(_row('workspace', 'calibration', 'ok', ', '.join(
            f"{name} {data.get('date', 'undated')}" for name, data in approved.items())) if approved else
            _row('workspace', 'calibration', 'warn', 'never applied', 'wuwei config promote'))
    except (OSError, ValueError) as exc:
        rows.append(_row('workspace', 'calibration', 'unmeasured', str(exc), 'fix .wuwei/calibration.json'))
    try:
        drifted = sorted({row['payload'].get('repo', '?') for row in
                          watch.records(workspace.day_dir(root) / 'events.jsonl')
                          if row['kind'] == 'calibration.drift'})
        rows.append(_row('workspace', 'drift', 'warn', 'calibration drift: ' + ', '.join(drifted), 'wuwei config promote')
                    if drifted else _row('workspace', 'drift', 'ok', 'none today'))
    except watch.ERRORS as exc:
        rows.append(_row('workspace', 'drift', 'unmeasured', str(exc), "fix today's events.jsonl, then run wuwei doctor"))
    rows.append(_row('workspace', 'guards', 'ok', 'enforce (guards.enforce = true)')
                if config['guards']['enforce'] else
                _row('workspace', 'guards', 'ok', "log only (guards.enforce = false); the day report's "
                     '## Shadow section lists what would have been refused; to enforce, run '
                     'bin/wuwei config set guards.enforce true'))
    telemetry = config['telemetry']
    rows.append(_row('workspace', 'telemetry', 'warn', 'sharing not chosen yet',
                     'bin/wuwei config set telemetry.share \'"anonymous"\' (or "attributed" or "off")') if telemetry['enabled'] and not telemetry['share']
                else _row('workspace', 'telemetry', 'ok', f"share {telemetry['share'] or 'off'}"
                          if telemetry['enabled'] else 'disabled'))
    return rows


def _gates(root, config):
    from wuwei.commands import config as config_command
    code, text = _capture(config_command.run, Namespace())
    detail = [line.strip() for line in text.splitlines() if line.strip()] if code else ()
    # #867: a rate limit waits only when no protection finding is due (F2: the finding wins).
    limited = (next((line for line in detail if LIMITED in line), None)
               if code == 2 and not any('missing (' in line for line in detail) else None)
    row = _limited('gates', 'config check', limited) if limited else None  # #867
    if row:
        row['detail'] = detail
    return [row or _row('gates', 'config check', ('ok', 'fail', 'unmeasured')[code], f'exit {code}',
                        'apply the fix each detail line names', docs='docs/site/configuration.md',
                        detail=detail)]


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
               'add "<email>" = {login = "<login>", mention = "<chat id>"} under [shepherd.authors]')]
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
# #847: doctor's own probes, run on demand (exit codes only, no timings): two the edges refuse or
# allow, one the records guard refuses, and the day read in process.
PROBES = ('refused', 'allowed', 'state_write', 'state', 'seats')


def _exit(result, want):
    code, line, _ = result
    if code is None:
        return 'unmeasured', 'timeout'
    if code == want:
        return 'ok', f'exit {code}'
    return 'failed', f'exit {code}' + (f': {line}' if line else '')


def _hook(root, tool, inputs):
    from wuwei.commands.hook import PROBE_SESSION
    return ('hook', 'PreToolUse'), json.dumps({
        'session_id': PROBE_SESSION, 'transcript_path': os.devnull, 'cwd': str(root / '.wuwei'),
        'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': inputs})


def _state(root):
    from wuwei import state
    try:
        state.read_state(root)
    except ValueError as exc:
        return 'failed', str(exc)
    return 'ok', 'readable'


def _seats(root):
    from wuwei import brief, state
    names = brief.stuck(state.read_state(root))
    if not names:
        return 'ok', 'none stuck'
    return 'failed', f'dead: {", ".join(names)}; run {brief.recovery(names[0], {})}'


def measure(root):
    """Every probe once: {name: {result: ok|failed|unmeasured, value}} in PROBES order."""
    from wuwei import watch
    root = Path(root)
    calls = [_hook(root, 'Bash', {'command': 'git push --force origin main'}),
             _hook(root, 'Read', {'file_path': str(root / '.wuwei/config.toml')}),
             _hook(root, 'Write', {'file_path': str(workspace.day_dir(root) / 'events.jsonl'), 'content': ''})]
    found = {}
    for name, check in (('state', _state), ('seats', _seats)):
        try:
            found[name] = check(root)
        except watch.ERRORS as exc:
            found[name] = 'unmeasured', str(exc)
    try:
        (refused, allowed, written), _ = registry.watch_service().probe(calls, root / '.wuwei')
        found.update(refused=_exit(refused, 2), allowed=_exit(allowed, 0), state_write=_exit(written, 2))
    except (OSError, ValueError) as exc:
        found.update({name: ('unmeasured', str(exc)) for name in ('refused', 'allowed', 'state_write')})
    return {name: {'result': found[name][0], 'value': found[name][1]} for name in PROBES}


def _day(root, config, probes):
    from wuwei.commands import status
    rows = [_row('day', 'state', PROBE[probes['state']['result']], probes['state']['value'],
                 "fix today's .wuwei/days/<date>/events.jsonl or state.json, then run wuwei doctor")]
    try:
        found = status.attention(workspace.day_dir(root))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return rows + [_row('day', 'day', 'unmeasured', str(exc), "fix today's events.jsonl, then run wuwei doctor")]
    rows.append(_row('day', 'stuck seats', PROBE[probes['seats']['result']], probes['seats']['value'],
                     'wuwei seat stop <name> --verdict <file>, or wuwei seat stop <name> --unmeasured "<reason>"'))
    for page in found:
        if page['tier'] == 'page':  # wuwei next acts on health pages only
            fix = (f"wuwei why {page['reason']}" if page['source'] == 'item.escalated' else
                   f"read the {page['source']} event in today's .wuwei/days/<date>/events.jsonl, "
                   'act on it, then run wuwei doctor')
            rows.append(_row('day', page['source'], 'fail', str(page['reason']), fix))
    gaps = sum(page.get('count', 1) for page in found if page['source'] == 'traces.gap')
    rows.append(_row('day', 'traces', 'warn' if gaps else 'ok', f'{gaps} gaps today' if gaps else 'no gaps today',
                     "read the traces.gap events in today's .wuwei/days/<date>/events.jsonl, then run wuwei doctor"))
    try:  # #896: the last trace sweep failed; trace checks are unmeasured from its offset on
        from wuwei.scanner import OFF, SWEEP
        mark = json.loads((workspace.day_dir(root) / SWEEP).read_text(encoding='utf-8'))
        if (config['adapters']['scanner'] == 'ziran' and isinstance(mark, dict)
                and isinstance(mark.get('unmeasured'), str)):
            rows.append(_row('day', 'trace sweep', 'unmeasured', mark['unmeasured'],
                             'the next wuwei dispatch receive or wuwei close retries from the last measured span; '
                             f'if it keeps failing, run {OFF} to switch the scanner off',
                             docs='docs/site/security.md#ziran-integration'))
    except (OSError, ValueError):
        pass
    untraced = sum(page.get('count', 1) for page in found if page['source'] == 'subagent.untraced')  # #676
    rows.append(_row('day', 'untraced subagents', 'warn' if untraced else 'ok',
                     f'{untraced} stopped with no seat today' if untraced else 'none today',
                     'launch agents from a session inside the workspace after the morning plan; '
                     'register them with wuwei seat start --role <role> --adhoc "<prompt>"'))
    return rows


def _tracker(root, config):
    """5.11: a configured tracker must answer a backlog read; #842: its duties need it."""
    name = config['adapters']['tracker']
    if name == 'none':
        return _row('day', 'tracker', 'ok', name)
    from wuwei.commands.config import requirements
    names = ', '.join(key for keys in requirements(config).get(('tracker', name), ()) for key in keys)
    try:
        result = registry.load('tracker', config).backlog(config['tracker']['backlog_filter'], root=root)
        reason = result.reason if result.exit else ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        reason = f'tracker unmeasured: {exc}'
    if not reason:
        return _row('day', 'tracker', 'ok', f'{name}: backlog read')
    if found := _limited('day', 'tracker', reason):  # #738
        return found
    fix = f'set {names} in .wuwei/env, or ' if names else ''
    if name == 'github':  # #602: the token, or the owner's gh login under tracker.auth = "gh"
        fix = (f'{fix}bin/wuwei config set tracker.auth \'"gh"\' to use your gh login, or ' if names else
               'run gh auth status (with tracker.board: gh auth refresh -s project), or ')
    return _row('day', 'tracker', 'fail', reason, fix + 'bin/wuwei config set adapters.tracker \'"none"\'')


def _tracker_labels(root, config):
    """#670: the lifecycle labels the tracker lacks; doctor reads, init --upgrade creates."""
    from wuwei import tracker
    result = tracker.labels(root, config, False)
    if result.exit:
        return _row('day', 'tracker labels', 'unmeasured', result.reason,
                    'fix the tracker row, then run wuwei doctor')
    if result.data['missing']:
        return _row('day', 'tracker labels', 'warn', 'missing: ' + ', '.join(
            f'"{name}"' for name in result.data['missing']), 'wuwei init --upgrade')
    return _row('day', 'tracker labels', 'ok', 'none missing')


def _probe_fix(name, probes):
    """A failed guard probe row's fix; damaged files are the integrity row's."""
    if 'plugin integrity' in probes[name]['value']:
        return 'fix the integrity row first'
    if probes[name]['value'] == 'timeout':
        return 'the hook did not answer in time; rerun wuwei doctor when fewer seats run'
    return 'the hook no longer behaves as shipped; ' + REINSTALL


def _guards(root, probes):
    from wuwei.commands.hook import PROBE_SESSION
    rows = [_row('guards', name, PROBE[probes[name]['result']], probes[name]['value'], _probe_fix(name, probes))
            for name in ('refused', 'allowed', 'state_write')] if root is not None else []
    fix = 'upgrade WUWEI: outside a workspace every hook must allow (#323)'
    try:
        with tempfile.TemporaryDirectory() as outside:
            payload = json.dumps({'session_id': PROBE_SESSION, 'transcript_path': os.devnull, 'cwd': outside,
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
    """Every row (or one section's), in section order; reads only. #867: a GitHub rate limit is
    reported as waiting, never waited for (adapters/_http.cap reads WUWEI_RATE_LIMIT_WAIT)."""
    before = os.environ.get('WUWEI_RATE_LIMIT_WAIT')
    os.environ['WUWEI_RATE_LIMIT_WAIT'] = '0'
    try:
        return _diagnose(section)
    finally:
        if before is None:
            os.environ.pop('WUWEI_RATE_LIMIT_WAIT', None)
        else:
            os.environ['WUWEI_RATE_LIMIT_WAIT'] = before


def _diagnose(section):
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
    if section == 'processes':
        if root is None or config is None:
            return [_row('processes', 'housekeeping', 'unmeasured', error or 'no workspace', 'wuwei init')]
        return _processes(root)
    if section == 'pr-flow':
        return pr_flow(config) if config else [
            _row('pr-flow', 'config', 'unmeasured', error or ('no workspace' if root is None else UNLOADED),
                 'fix config.toml first')]
    defaults = config or workspace._validate({}, workspace.SCHEMA, (), '')
    probes = measure(root) if root is not None else None
    rows = [*_install(root, config), *_host(root, defaults), *_workspace(root, config, error, found)]
    if root is not None:
        if config is None:
            rows += [_row('gates', 'gates', 'unmeasured', UNLOADED, 'fix config.toml first'),
                     _row('day', 'day', 'unmeasured', UNLOADED, 'fix config.toml first')]
        else:
            rows += [*_gates(root, config), *pr_flow(config), *_day(root, config, probes),
                     _tracker(root, config)]
            if config['adapters']['tracker'] != 'none':
                rows.append(_tracker_labels(root, config))
    return rows + _guards(root, probes)


def _processes(root):
    from wuwei import watch
    code, findings = watch.housekeeping(root, orphans=True)
    return [_row('processes', row['kind'], 'unmeasured' if row['kind'] == 'unmeasured' else 'warn',
                 row['why'], row['command']) for row in findings] or [
                     _row('processes', 'housekeeping', 'ok', 'no leftovers')]


def _dry(function, args):
    code, text = _capture(function, args)
    if code:
        raise ValueError(text.strip() or f'dry run exit {code} with no output; run the fix command by hand to see its error')
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


def _reconfirm_preview(root):
    result = integrity.check(root)
    if not result.data:
        raise ValueError(result.reason or 'nothing to confirm; run bin/wuwei doctor to see the current verdict')
    return f'installation fingerprint {result.data}\n', result.data


def _reconfirm(root, token):
    result = integrity.reconfirm(root, confirm=lambda value: value == token)
    if result.reason:
        print(result.reason)
    return result.exit


# The --fix allow list (a test pins it): id -> (command shown, preview(root) -> (text, token),
# apply(root, token) -> exit). Decisions (guards.enforce, the code host)
# stay printed. config-set waits for #327's confirmed `config set`.
FIXES = {
    'integrity-reconfirm': ('wuwei doctor --fix --apply integrity-reconfirm', _reconfirm_preview, _reconfirm),
    'init-upgrade': _planned('wuwei init --upgrade', _upgrade),
}


def fix(rows, confirm=None, only=None, widget=False):
    """Preview the allow-listed fixes, ask for one digest, apply each bound to its preview, re-diagnose.
    only narrows the batch to those fix ids; widget prints the batch's Owner step card and applies nothing."""
    import hashlib
    from wuwei import state
    wanted = {row['apply'] for row in rows if row.get('apply') in FIXES}
    if only is not None:
        only = set(only)
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
    if not batch:
        print(notes + 'Nothing to apply', file=sys.stderr if widget else sys.stdout)
        if widget:
            print('[]')
        return outcome(rows)
    from wuwei import sessions
    text = ''.join(f'[{name}] {FIXES[name][0]}\n{preview.rstrip()}\n' for name, preview, _ in batch) + notes
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    command = 'bin/wuwei doctor --fix' + (f" --apply {','.join(sorted(only))}" if only is not None else '')
    if widget:  # #831: one card per batch, the Owner step card the fix itself asks
        print(json.dumps([sessions.owner_card(command, text, digest)], indent=2))
        return outcome(rows)
    print(text, end='')
    if confirm is None:  # #831: the owner's answer on the Owner step card
        if owner := sessions.needs_owner(root, command, text, digest):
            print(owner, file=sys.stderr)
            return 1
    elif not confirm(digest):
        print('wuwei doctor: declined; nothing applied; run bin/wuwei doctor --fix again when you are ready', file=sys.stderr)
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


def _hand_over(args):
    """#645: run the doctor of the install .wuwei/executable names, so every copy prints the same rows;
    returns a warn row only when that launcher could not be run."""
    if os.environ.get(FROM):
        return []
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
    except (OSError, ValueError, TypeError, KeyError):
        return []
    if config['adapters']['host'] == 'none':
        return []
    here, target = integrity.PLUGIN / 'bin/wuwei', integrity.recorded(root)
    if not (target and os.path.isfile(target) and os.access(target, os.X_OK)
            and Path(target).resolve() != here.resolve()):
        return []
    argv = [target, 'doctor', *[f'--{name}' for name in ('fix', 'json', 'widget') if getattr(args, name)]]
    argv += [item for name in ('apply', 'section') if getattr(args, name) for item in (f'--{name}', getattr(args, name))]
    sys.stdout.flush()
    sys.stderr.flush()
    failed = registry.load('host', config).hand_over(target, argv, {**os.environ, FROM: str(here)}, root=root)
    return [_row('install', 'invoked', 'warn', f'could not hand doctor over to {target} '
                 f'({failed.reason}); this report comes from {here}', f'{target} doctor')]


def register(subparsers):
    parser = subparsers.add_parser('doctor', help='Find install, host, workspace and guard problems and their fixes')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fix', action='store_true', help='apply the allow-listed fixes after one host confirmation')
    mode.add_argument('--json', action='store_true', help='print {"exit", "rows"} as JSON')
    parser.add_argument('--widget', action='store_true',
                        help='with --fix: print the batch as its Owner step card for AskUserQuestion; apply nothing')
    parser.add_argument('--apply', metavar='IDS', help='with --fix: apply only these comma-separated fix ids')
    parser.add_argument('--section', choices=['pr-flow', 'processes'], help='print one section only')
    parser.set_defaults(func=run)


def run(args, confirm=None):
    if (args.widget or args.apply) and not args.fix or args.widget and args.apply:
        print('wuwei doctor: --widget and --apply each need --fix, not both; use bin/wuwei doctor --fix --widget or bin/wuwei doctor --fix --apply <labels>', file=sys.stderr)
        return 2
    failed = [] if confirm is not None or args.section == 'processes' else _hand_over(args)
    with redirect_stderr(io.StringIO()):  # Adapters print their reasons; the rows carry them.
        rows = diagnose(args.section) + failed
    if args.section == 'pr-flow':
        from wuwei import state
        try:
            root = workspace.find_workspace()
        except (OSError, ValueError):
            root = None
        if root and state.day_started(workspace.day_dir(root)):
            state.append_event('next.action', {'state': 'pr-flow', 'action': 'pass', 'item': '',
                                               'named': []}, root)
    if args.json:
        print(json.dumps({'exit': outcome(rows), 'rows': rows}))
        return outcome(rows)
    if not args.widget:
        print(render(rows))
    only = [name.strip() for name in args.apply.split(',') if name.strip()] if args.apply else None
    return fix(rows, confirm, only=only, widget=args.widget) if args.fix else outcome(rows)
