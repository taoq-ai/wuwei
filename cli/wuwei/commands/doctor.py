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


def identity_row(repo, index, path, vcs):
    """#605: the commit and push guard's rule, reason and fix; the fix names what git resolves."""
    from wuwei.guards import commit_push
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
            raise ValueError('no PreToolUse hooks; reinstall the signed release, then run bin/wuwei doctor')
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
    own = root is None or config['repos'] and all(
        (repo['identity']['name'] and repo['identity']['email'])
        or resolved((root / Path(repo['path']).expanduser()).resolve())[0] for repo in config['repos'])
    rows.append(_row('host', 'git identity', 'ok', f"{result.data['name']} <{result.data['email']}>") if good else
                _row('host', 'git identity', 'ok', "not set globally; setup reads each repository's own identity"
                     if root is None else 'not set globally; repositories set their own') if own else
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
                     'bin/wuwei setup --shadow in the directory that holds your repositories')]
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
    upgrades = [line for line in lines if line.startswith('Would upgrade') and 'graph.json' not in line]
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
    launcher = integrity.PLUGIN / 'bin/wuwei'
    try:
        recorded = (root / '.wuwei/executable').read_text(encoding='utf-8').splitlines()[0]
    except (OSError, UnicodeError, IndexError):
        recorded = ''
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
    window = config['consolidation']['archive_after_days']
    try:
        from wuwei import consolidation
        late = [path for path in consolidation.expired(root) if path.parent.name == 'days']
        rows.append(_row('workspace', 'memory tiers', 'warn', f'{len(late)} raw days older than '
                         f'consolidation.archive_after_days ({window}); consolidate has not run',
                         'wuwei consolidate') if late else
                    _row('workspace', 'memory tiers', 'ok', f'within {window} days'))
    except (OSError, ValueError) as exc:
        rows.append(_row('workspace', 'memory tiers', 'unmeasured', str(exc), 'wuwei consolidate'))
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
        mode, hooks = config['worktree']['git_hooks'], f'{name} git hooks'
        found = vcs.hooks_target(str(path)) if mode != 'skip' else None
        if found is None:
            rows.append(_row('workspace', hooks, 'ok', 'skipped (worktree.git_hooks = "skip"); the '
                             'PreToolUse guard still checks git commit and git push'))
        elif found.exit == 2:
            rows.append(_row('workspace', hooks, 'unmeasured', found.reason,
                             f'run git -C {path} config --show-scope --get-all core.hooksPath and fix what it names'))
        elif found.exit:
            rows.append(_row('workspace', hooks, 'warn', found.reason,
                             'fix what the value names, then run wuwei init --upgrade; or set '
                             'worktree.git_hooks = "skip" in .wuwei/config.toml'))
        else:
            chain = (found.data or {}).get('chain', '')
            rows.append(_row('workspace', hooks, 'ok',
                             f'chained with {chain}' if chain and mode == 'chain' else
                             f'replaces {chain} (worktree.git_hooks = "replace")' if chain else 'WUWEI hooks'))
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
    rows += _outbound(config)
    rows.append(_register(root, config))
    rows += _calibration(root, config)
    return rows + [_undo(root)]


def _undo(root):
    """#557: the kinds whose undo ran once in this workspace."""
    from wuwei import undo
    try:
        done = undo.ledger(root)
    except ValueError as exc:
        return _row('workspace', 'undo rehearsals', 'fail', str(exc),
                    'move .wuwei/memory/rehearsals.json aside, then run wuwei undo rehearse commit '
                    'and wuwei undo rehearse decision')
    rehearsed = [kind for kind in undo.REGISTRY if kind in done]
    missing = [kind for kind in undo.REGISTRY if kind not in done]
    return _row('workspace', 'undo rehearsals', 'ok', f'rehearsed: {", ".join(rehearsed) or "none"}; '
                f'not rehearsed: {", ".join(missing) or "none"} (wuwei undo rehearse <kind>)')


def _outbound(config):
    """#496: people without a class and owner send rows for a client or public audience;
    information, nothing refuses on them."""
    from wuwei import outward
    bare = [key for key, entry in config['outbound']['people'].items() if not entry['class']]
    rows = [_row('workspace', 'outbound classes', 'warn', f'{len(bare)} people without a class',
                 'nothing changes until you choose: the bin/wuwei outbound learn card asks the class of '
                 'each person it adds',
                 detail=[f'{key}: team while internal by outbound.company_domains or outbound.code_host_orgs, '
                         'else the connector default class' for key in bare])
            if bare else _row('workspace', 'outbound classes', 'ok', 'every person has a class')]
    strict = workspace.posture(config)[0] == 'strict'
    sends = [f'rule {number} is ignored under strict' if strict
             else f'rule {number} can send to a client or public audience'
             for number, (row, source, _) in enumerate(outward.table(config), 1)
             if source == 'owner' and row['tier'] == 'send' and outward.reaches_client(row, config)]
    rows.append(_row('workspace', 'outbound tiers', 'warn', f'{len(sends)} send rows for a client or public audience',
                     'make the row ask, or remove it', detail=sends) if sends
                else _row('workspace', 'outbound tiers', 'ok', 'no send row for a client or public audience'))
    return rows


def _register(root, config):
    """#552: the register against its config views; warn at most, it decides nothing (A13)."""
    from wuwei import graph
    try:
        register = graph.load(root)
    except ValueError as exc:
        return _row('workspace', 'register', 'warn', str(exc), f'{graph.FIX.replace("bin/wuwei", "wuwei")}')
    if register is None:
        return _row('workspace', 'register', 'warn', 'no .wuwei/graph.json', 'wuwei init --upgrade',
                    apply='init-upgrade')
    drifted = graph.drift(register, config)
    if drifted:
        return _row('workspace', 'register', 'warn', f'config.toml differs from graph.json in {len(drifted)} keys',
                    'wuwei init --upgrade', apply='init-upgrade', detail=drifted)
    return _row('workspace', 'register', 'ok',
                f"{len(register['nodes'])} nodes, {len(register['edges'])} edges; matches config.toml")


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
        count = len(interview.unanswered(root, [repo['name'] for repo in config['repos']]))  # #530
        rows.append(_row('workspace', 'interview', 'warn', f'{count} questions unanswered', interview.HOW)
                    if count else _row('workspace', 'interview', 'ok', 'all setup questions answered'))
    except (OSError, ValueError) as exc:
        rows.append(_row('workspace', 'interview', 'unmeasured', str(exc), 'wuwei calibrate --interview'))
    try:
        name, _ = profiles.load(root, config)
        rows.append(_row('workspace', 'profile', 'ok',
                         f"guards profile {config['profile']}; calibration profile {name or 'none'}"))
    except (OSError, ValueError) as exc:
        rows.append(_row('workspace', 'profile', 'unmeasured', str(exc), 'wuwei calibrate import <profile>'))
    guards, name = config['guards'], workspace.posture(config)[0]
    shown = f'{name} (from {workspace.posture_source(config)})'
    if guards['mode'] == 'shadow':
        rows.append(_row('workspace', 'posture', 'warn', shown, 'wuwei init --upgrade', apply='init-upgrade'))
    elif name != 'observe':
        rows.append(_row('workspace', 'posture', 'ok', shown))
    else:
        from datetime import date
        since = guards['shadow_since']
        days = (workspace.now().date() - date.fromisoformat(since)).days if since else 0
        left = guards['shadow_days'] - days
        rows.append(_row('workspace', 'posture', 'ok', f'{shown}, {left} days left') if left > 0 else
                    _row('workspace', 'posture', 'warn', f'{shown}: ' + SHADOW_NUDGE.format(days=days),
                         'set security.posture = "guarded" in .wuwei/config.toml, or raise guards.shadow_days'))
    if name == 'strict':  # #478: the guard ignores standing grants under strict.
        rows += [_row('workspace', f'grant {index}', 'warn',
                      f"{line['action']} {line['target']} ({line['decision']}) is ignored under strict",
                      f'bin/wuwei grants revoke {index}')
                 for index, line in enumerate(config['grants']['standing'], 1)]
    telemetry = config['telemetry']
    rows.append(_row('workspace', 'telemetry', 'warn', 'sharing not chosen yet (pending interview question)',
                     'bin/wuwei calibrate --interview telemetry') if telemetry['enabled'] and not telemetry['share']
                else _row('workspace', 'telemetry', 'ok', f"share {telemetry['share'] or 'off'}"
                          if telemetry['enabled'] else 'disabled'))
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
    if config['adapters']['scanner'] == 'none':  # #424: no record rows; WUWEI's own servers stay covered.
        try:
            own = json.loads((integrity.PLUGIN / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))
            servers = own.get('mcpServers')
            names = sorted(servers) if isinstance(servers, dict) else []
        except (OSError, ValueError, AttributeError):
            names = []  # the install section already reports an unreadable manifest
        return rows + [_row('gates', f'mcp {name}', 'ok', 'covered by plugin integrity') for name in names]
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


def _docs(root, config):
    """The docs system (#419): its space, credentials and a read of the space, or the markdown root."""
    from wuwei import registry
    from wuwei.commands import config as config_command
    rules, link = config['docs'], 'docs/site/configuration.md#docs'

    def docs_row(status, value, fix=''):
        return [_row('gates', 'docs', status, value, fix, docs=link)]
    if rules['system'] == 'none':
        return docs_row('ok', 'not used')
    if rules['system'] == 'markdown':
        roots = [(root / Path(repo['path']).expanduser() / rules['root']) for repo in config['repos']]
        if not any(path.is_dir() for path in roots):
            return docs_row('fail', f"{rules['root']}/ is not a directory in any configured repository",
                            f"create {rules['root']}/ in the repository or "
                            "bin/wuwei config set docs.root '\"<dir>\"'")
        if rules['publish']:
            return docs_row('warn', 'publish has no effect under markdown',
                            "bin/wuwei config set docs.publish '[]'")
        return docs_row('ok', f"markdown: {rules['root']}/")
    if not rules['space']:
        return docs_row('fail', 'docs.space is empty', "bin/wuwei config set docs.space '\"<page link>\"'")
    for alternatives in config_command.requirements(config).get(('docs', rules['system']), ()):
        if not any(os.environ.get(name) for name in alternatives):
            return docs_row('fail', f'{alternatives[0]} missing', f'add {alternatives[0]} to .wuwei/env')
    result = registry.load('docs', config).read(rules['space'], root=root)
    if result.exit:
        return docs_row('fail', result.reason or 'docs.space unreadable', 'check docs.space and the credential')
    return docs_row('ok', f"{rules['system']}: {result.data['title']}")


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
    try:  # #511: an ok row either way; scheduling is the owner's choice.
        from wuwei import shepherd
        last = shepherd.last_swept(root)
        rows.append(_row('day', 'shepherd', 'ok', (
            f'scheduled ({"launchd" if sys.platform == "darwin" else "systemd"}), last swept {last or "not yet"}'
            if workspace.unit_installed(root, name='shepherd') else
            'runs only in a session; bin/wuwei shepherd schedule runs it overnight'
            + (f'; last headless sweep {last}' if last else ''))))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        rows.append(_row('day', 'shepherd', 'unmeasured', str(exc), 'wuwei state recover in a host terminal'))
    rows.append(_row('day', 'heartbeat', {None: 'ok', 'ok': 'ok', 'degraded': 'fail'}.get(beat, 'unmeasured'),
                     beat or 'none today', 'wuwei heartbeat names the failed probe'))
    rows.append(_row('day', 'stuck seats', PROBE[probes['seats']['result']], probes['seats']['value'],
                     'wuwei seat stop <name> --verdict <file>, or wuwei seat stop <name> --unmeasured "<reason>"'))
    for page in found:
        if page['tier'] == 'page':
            rows.append(_row('day', page['source'] + (' page' if page['source'] == 'heartbeat' else ''), 'fail',
                             str(page['reason']), 'wuwei nudges'))
    nudges = sum(page['tier'] == 'nudge' for page in found)
    rows.append(_row('day', 'nudges', 'ok', f'{nudges} open (wuwei nudges lists them)'))
    gaps = sum(page['source'] == 'traces.gap' for page in found)
    rows.append(_row('day', 'traces', 'warn' if gaps else 'ok', f'{gaps} gaps today' if gaps else 'no gaps today',
                     'read the traces.gap reasons in wuwei nudges, then run wuwei doctor'))
    untraced = sum(page['source'] == 'subagent.untraced' for page in found)  # #676
    rows.append(_row('day', 'untraced subagents', 'warn' if untraced else 'ok',
                     f'{untraced} stopped with no seat today' if untraced else 'none today',
                     'launch agents from a session inside the workspace after the morning plan; under strict '
                     'register them with wuwei seat start --role <role> --adhoc "<prompt>"'))
    try:
        if ids := _legacy_traces(root):
            rows.append(_row('day', 'trace decisions', 'warn', f'{", ".join(ids)} pending under the pre-#352 rule',
                             'wuwei doctor --fix', apply='trace-decisions'))
    except (OSError, ValueError) as exc:
        rows.append(_row('day', 'trace decisions', 'unmeasured', str(exc), 'wuwei state recover in a host terminal'))
    return rows


def _tracker(root, config):
    """5.11: with tickets required, the tracker must answer a backlog read."""
    name = config['adapters']['tracker']
    if name == 'none' or not config['tracker']['required']:
        return _row('day', 'tracker', 'ok', name if name == 'none' else f'{name}, tickets optional')
    from wuwei.commands.config import requirements
    names = ', '.join(key for keys in requirements(config).get(('tracker', name), ()) for key in keys)
    try:
        result = registry.load('tracker', config).backlog(config['tracker']['backlog_filter'], root=root)
        reason = result.reason if result.exit else ''
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        reason = f'tracker unmeasured: {exc}'
    if not reason:
        return _row('day', 'tracker', 'ok', f'{name}: backlog read')
    fix = f'set {names} in .wuwei/env, or ' if names else ''
    if name == 'github':  # #602: the token, or the owner's gh login under tracker.auth = "gh"
        fix = (f'{fix}bin/wuwei config set tracker.auth \'"gh"\' to use your gh login, or ' if names else
               'run gh auth status (with tracker.board: gh auth refresh -s project), or ')
    return _row('day', 'tracker', 'fail', reason, fix + 'bin/wuwei config set tracker.required false')


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
            for name in ('refused', 'allowed', 'state_write', 'read_loop', 'git_read', 'status_line')] if root is not None else []
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
            rows += [*_gates(root, config), *_docs(root, config), *pr_flow(config), *_day(root, config, probes),
                     _tracker(root, config)]
    return rows + _guards(root, probes)


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


def _service(name):
    def make(root, dry):
        from wuwei.commands import watch
        return (lambda args: watch.service(args, name, None),
                Namespace(**{f'{name}_action': 'install'}, once=False, dry_run=dry))
    return make


def _reconfirm_preview(root):
    result = integrity.check(root)
    if not result.data:
        raise ValueError(result.reason or 'nothing to confirm; run bin/wuwei integrity check to see the current verdict')
    return f'installation fingerprint {result.data}\n', result.data


def _reconfirm(root, token):
    result = integrity.reconfirm(root, confirm=lambda value: value == token)
    if result.reason:
        print(result.reason)
    return result.exit


def _supersede_preview(root):
    ids = _legacy_traces(root)
    if not ids:
        raise ValueError('nothing to supersede; run bin/wuwei doctor without --apply supersede')
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
            value, prompt='Apply the fixes above.')))(
            hashlib.sha256(text.encode()).hexdigest()[:12])
    except OSError as exc:
        print(f'wuwei doctor: {exc}', file=sys.stderr)
        return 2
    if not accepted:
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
        print('wuwei doctor: --widget and --apply each need --fix, not both; use bin/wuwei doctor --fix --widget or bin/wuwei doctor --fix --apply <labels>', file=sys.stderr)
        return 2
    with redirect_stderr(io.StringIO()):  # Adapters print their reasons; the rows carry them.
        rows = diagnose(args.section)
    if args.json:
        print(json.dumps({'exit': outcome(rows), 'rows': rows}))
        return outcome(rows)
    if not args.widget:
        print(render(rows))
    only = [name.strip() for name in args.apply.split(',') if name.strip()] if args.apply else None
    return fix(rows, confirm, only=only, widget=args.widget) if args.fix else outcome(rows)
