"""One-shot workspace setup and the owner config edits."""

import difflib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import tomllib

from wuwei import calibrate, references, registry, workspace
from wuwei.commands import config
from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.workspace import ConfigError, load_config


KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*(?:\.(?:[A-Za-z_][A-Za-z0-9_-]*|[0-9]+))*')
IDENTITY = re.compile(r'(.+?) <([^<>\s]+@[^<>\s]+)>')
GITHUB = re.compile(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)'
                    r'([^/\s]+/[^/\s]+?)(?:\.git)?/?')
TOOLS = ('claude', 'gh', 'ziran')


def register(subparsers):
    parser = subparsers.add_parser(
        'setup', help='discover repositories, write config, calibrate and interview, apply once '
                      '(owner, host terminal)')
    parser.add_argument('--shadow', action='store_true',
                        help='start or switch to the observe posture (suggested for a first week)')
    parser.add_argument('--posture', metavar='PROFILE', help='starter profile name or local file')
    parser.add_argument('--repos', nargs='+', metavar='DIR',
                        help='directories whose child git repositories to add (default: the workspace)')
    parser.set_defaults(func=run)


def _edit(label, what, confirm, change):
    """The owner edit frame: validate change(root, raw) -> text, then the digest path."""
    try:
        root = workspace.find_workspace()
        _, raw = config.read(root)
    except (OSError, ValueError) as exc:
        print(f'wuwei {label}: {exc}', file=sys.stderr)
        return UNRUN
    try:
        load_config(root, raw=raw)
        text = change(root, raw)
        if text == raw:
            print('No config.toml changes')
            return CLEAN
        load_config(root, raw=text)
        diff = ''.join(difflib.unified_diff(raw.splitlines(keepends=True), text.splitlines(keepends=True),
                                            'config.toml', 'config.toml (proposed)'))
    except ValueError as exc:  # ConfigError, a TOML error and calibrate.LAYOUT included
        print(f'wuwei {label}: {exc}', file=sys.stderr)
        return FINDINGS
    try:
        return config.offer(root, raw, text, diff, label=label, what=what, confirm=confirm)
    except (OSError, ValueError) as exc:
        print(f'wuwei {label}: {exc}', file=sys.stderr)
        return UNRUN


def set_value(args, confirm=None):
    """Owner action: set one config value after a host-terminal digest."""
    def change(root, raw):
        if not KEY.fullmatch(args.key):
            raise ValueError(f'{args.key}: expected a dotted key such as owner.name or repos.0.merge_deploys')
        parts = [int(p) if p.isdigit() else p for p in args.key.split('.')]
        if isinstance(parts[-1], int):
            raise ValueError(f'{args.key}: name a key, not a list index')
        parsed = tomllib.loads(f'value = {args.value}\n')
        if list(parsed) != ['value']:
            raise ValueError(f'{args.value!r}: expected one TOML value')
        additions, edits = calibrate.settle(raw, [(tuple(parts[:-1]), parts[-1], parsed['value'])])
        for dotted, current, _ in edits:
            if isinstance(current, dict):
                raise ValueError(f'{dotted}: a table; set one of its keys'
                                 + (f', for example {dotted}.default' if 'default' in current else ''))
            raise ValueError(f'{dotted}: not a one-line assignment; edit config.toml by hand')
        return calibrate.apply(raw, additions)

    return _edit('config set', 'change', confirm, change)


def repo_tables(raw, repos):
    """raw plus one [[repos]] table per repository; every value escaped through json.dumps."""
    text = raw if raw.endswith('\n') else raw + '\n'
    for repo in repos:
        text += ''.join(f'\n[[repos]]\nname = {json.dumps(repo["name"])}\npath = {json.dumps(repo["path"])}\n'
                        f'default_branch = {json.dumps(repo["default_branch"])}\n')
        if repo.get('identity'):
            text += (f'identity = {{name = {json.dumps(repo["identity"]["name"])}, '
                     f'email = {json.dumps(repo["identity"]["email"])}}}\n')
    return text


def add_repo(args, confirm=None):
    """Owner action: add one [[repos]] table after a host-terminal digest."""
    def change(root, raw):
        repo = {'name': references.repository(args.name), 'path': args.path, 'default_branch': args.branch}
        if args.identity is not None:
            found = IDENTITY.fullmatch(args.identity)
            if not found:
                raise ValueError('--identity: expected "Name <email>"')
            repo['identity'] = {'name': found[1], 'email': found[2]}
        return repo_tables(raw, [repo])

    return _edit('config add-repo', 'repository', confirm, change)


def _owed(name, path, branch):
    return (f'bin/wuwei config add-repo --name {shlex.quote(name or "owner/repo")} --path {shlex.quote(path)} '
            f'--branch {shlex.quote(branch or "<default branch>")}')


def discover(root, dirs, config):
    """Repositories, host facts and owed commands; reads git config and gh only, never guesses."""
    hub, vcs = registry.load('code_host', config), registry.load('vcs', config)
    tools = {name: shutil.which(name) is not None for name in TOOLS}
    auth = hub.auth_status().exit
    viewer = hub.viewer_login() if auth == 0 else None
    login = viewer.data['login'] if viewer and viewer.exit == 0 else None
    memory = registry.load('host', config).free_memory(root=root)
    lines = [f'Host: {sys.platform}', *(f'{name}: {"on PATH" if on else "missing"}' for name, on in tools.items()),
             f'code host auth: {("set", "missing", "unmeasured")[auth]}',
             f'code host login: {login or "unmeasured"}',
             f'free memory: {memory.data // 1048576} MiB' if memory.exit == 0 else 'free memory: unmeasured']
    configured = {repo['name'] for repo in config['repos']} | {
        (root / Path(repo['path']).expanduser()).resolve() for repo in config['repos']}
    candidates = [root] if (root / '.git').exists() else []
    for directory in dirs:
        candidates += sorted(child for child in Path(directory).iterdir()
                             if child.is_dir() and not child.is_symlink() and not child.name.startswith('.')
                             and (child / '.git').exists())
    repos, owed, seen = [], [], set()
    for candidate in candidates:
        resolved = candidate.resolve()
        path = os.path.relpath(resolved, root) if resolved.is_relative_to(root) else str(resolved)
        if resolved in seen or resolved in configured:
            continue
        seen.add(resolved)
        if (candidate / '.git').is_file():
            lines.append(f'{path}: worktree, not added')
            continue
        remote = vcs.remote_url(resolved)
        found = GITHUB.fullmatch(remote.data['url']) if remote.exit == 0 else None
        try:
            name = references.repository(found[1]) if found else None
        except ValueError:
            name = None
        if name in configured:
            continue
        if any(repo['name'] == name for repo in repos):
            lines.append(f'{path}: {name} already listed, not added')
            continue
        branch = hub.default_branch(name) if name and auth == 0 else None
        branch = branch.data['branch'] if branch and branch.exit == 0 else None
        if not (name and branch):
            owed.append(_owed(name, path, branch))
            continue
        repo = {'name': name, 'path': path, 'default_branch': branch}
        who = vcs.identity(resolved)
        if who.exit == 0:
            flagged = calibrate.instruction_like(f"{who.data['name']} {who.data['email']}")
            if flagged:
                lines.append(f'{path}: identity flagged ({flagged[0][1]}), not proposed')
            else:
                repo['identity'] = {'name': who.data['name'], 'email': who.data['email']}
        repos.append(repo)
    return {'repos': repos, 'lines': lines, 'owed': owed, 'tools': tools, 'login': login}


def identity(config, login, results):
    """Settings from the measured login and bot authors; never overrides what the owner set."""
    from wuwei import obligations

    settings = []
    handles = config['owner']['handles']
    if login:
        try:  # Only when no code-host login is there yet; chat IDs stay.
            obligations._owner_login({'owner': {'handles': [*handles, login]}})
            settings.append((('owner',), 'handles', [*handles, login]))
        except ValueError:
            pass
        if not config['shepherd']['lead_login']:
            settings.append((('shepherd',), 'lead_login', login))
    authors = {email.strip().casefold(): login for repo in config['repos']
               if login and (email := repo['identity']['email']).strip()}
    for result in results:
        authors.update(result.get('bots') or {})
    mapped = {email.casefold() for email in config['shepherd']['authors']}
    return settings + [(('shepherd', 'authors'), email, {'login': who})
                       for email, who in sorted(authors.items()) if email not in mapped]


def run(args, confirm=None):
    """Owner action: init, discover, one proposal and one digest, then the checks and what is owed."""
    from wuwei import integrity
    try:
        return _setup(args, confirm)
    except EOFError:
        print('wuwei setup: interview interrupted; nothing written', file=sys.stderr)
        return UNRUN
    except ConfigError as exc:
        print(f'wuwei setup: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'wuwei setup: {exc}', file=sys.stderr)
        return UNRUN
    finally:
        if integrity.other_versions():  # #353: another version's hooks still run
            print(integrity.RESTART)


def _setup(args, confirm):
    from types import SimpleNamespace
    from wuwei import integrity, interview, mcp, profiles, security
    from wuwei.commands import calibrate as calibrate_command, init

    # The interview and the digest both need this terminal; nothing is written yet.
    if not sys.stdin.isatty():
        raise OSError(integrity.HOST_TERMINAL)
    try:
        root = workspace.find_workspace()
    except FileNotFoundError:
        init.run(SimpleNamespace(path='.', shadow=args.shadow, upgrade=False, dry_run=False, menu_bar=False,
                                 honeytoken_path=security.DEFAULT_HONEYTOKEN_PATH))
        root = workspace.find_workspace()
        print('To run owner commands from any directory, add to your shell profile:\n'
              f'export WUWEI_WORKSPACE={shlex.quote(str(root))}')
        if not args.shadow:
            print('Suggested for a first week: bin/wuwei setup --shadow (guards record instead of refusing)')
    _, raw = config.read(root)
    cfg = load_config(root, raw=raw)
    found = discover(root, args.repos or [root], cfg)
    print('\n'.join(found['lines']))
    staged = init._stamp(repo_tables(raw, found['repos']))
    staged_cfg = load_config(root, raw=staged)
    if not staged_cfg['repos']:
        print('Still owed:\n' + ''.join(f'  {line}\n' for line in found['owed'] or [_owed(None, '<path>', None)]),
              end='')
        return FINDINGS
    names = [repo['name'] for repo in staged_cfg['repos']]
    extra = []
    if found['tools']['ziran'] and cfg['adapters']['scanner'] == 'none':
        extra.append((('adapters',), 'scanner', 'ziran'))
    if args.shadow and workspace.posture(cfg)[0] != 'observe':
        extra += [(('security',), 'posture', 'observe'),
                  (('guards',), 'shadow_since', workspace.now().date().isoformat())]
    if args.posture:
        if re.match(r'[A-Za-z][A-Za-z0-9+.-]*://', args.posture):
            raise ValueError('--posture: a starter name or a local file; use calibrate import for a URL')
        accepted, refused, flagged = profiles.review(profiles.read(args.posture), staged_cfg, names)
        if refused:
            for key, why in refused:
                print(f'wuwei setup: refused: {key} ({why}); nothing written', file=sys.stderr)
            return FINDINGS
        for where, rule in flagged:
            print(f'Flagged {where} ({rule}), not proposed')
        profiles.record(root, accepted, names)
    snapshot_path = root / '.wuwei/calibration.json'
    if found['repos'] or not snapshot_path.exists():
        interview.record(root, staged_cfg, interview.ask([], names))
    results = calibrate.survey(root, staged_cfg, list(enumerate(staged_cfg['repos'])), style=True)
    extra += identity(staged_cfg, found['login'], results)
    text, diff, edits, summary, snapshot = config.proposal(root, raw, staged, staged_cfg, results, extra)
    if text == raw and snapshot_path.exists():
        print('Nothing to propose')
    else:
        if config.offer(root, raw, text, summary, label='setup', what='setup', confirm=confirm,
                        snapshot=snapshot):
            return FINDINGS
        calibrate_command.record(root, results, diff, edits, None)
    check = config.run(SimpleNamespace())
    gate = mcp.check(root)
    if gate.reason:
        print(gate.reason, file=sys.stderr)
    final = load_config(root)
    owed = found['owed'] + [f'set {name} in .wuwei/env' for name in config.missing(final)]
    if not final['owner']['name'].strip():
        owed.append('bin/wuwei config set owner.name \'"<your name>"\'')
    proposals = workspace.day_dir(root) / 'proposals'
    if proposals.is_dir() and any(proposals.iterdir()):
        owed.append('bin/wuwei promote')
    if gate.exit == 2 and mcp.unmeasured(root):
        owed.append('bin/wuwei mcp decide proceed-unmeasured ' + ' '.join(map(shlex.quote, mcp.unmeasured(root))))
    elif gate.exit:
        waiting = mcp.pending(root)
        owed.append(mcp.command(waiting) if waiting else 'bin/wuwei mcp check')
    print('Still owed:\n' + ''.join(f'  {line}\n' for line in owed or ['nothing']) + 'Next: /wuwei plan')
    return max(check, gate.exit)
