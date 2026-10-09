"""One-shot workspace setup and the owner config edits."""

from argparse import Namespace
import difflib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import time
import tomllib

from wuwei import calibrate, configtext, references, registry, workspace
from wuwei.commands import config
from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.workspace import ConfigError, load_config


KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*(?:\.(?:[A-Za-z_][A-Za-z0-9_-]*|[0-9]+))*')
IDENTITY = re.compile(r'(.+?) <([^<>\s]+@[^<>\s]+)>')
GITHUB = re.compile(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)'
                    r'([^/\s]+/[^/\s]+?)(?:\.git)?/?')
TOOLS = ('claude', 'gh', 'ziran')
# ponytail: a fixed wait for the first DM message; a flag if owners need longer.
WAIT_SECONDS, POLL_SECONDS = 300, 3
TOKEN_HINT = ("copy the Bot User OAuth Token from your Slack app's OAuth & Permissions page "
              '(remote operation section 2), then run bin/wuwei setup slack again')
DM_HINT = ('in the Slack app settings turn on App Home, Messages Tab, and add the im:history bot scope '
           'under OAuth & Permissions; then run bin/wuwei setup slack again')


def register(subparsers):
    parser = subparsers.add_parser(
        'setup', help='discover repositories, write config, calibrate and interview, apply once '
                      '(owner, host terminal)')
    parser.add_argument('--shadow', action='store_true',
                        help='start or switch to the observe posture (suggested for a first week)')
    parser.add_argument('--posture', metavar='PROFILE', help='starter profile name or local file')
    parser.add_argument('--repos', nargs='+', metavar='DIR',
                        help='directories whose child git repositories to add (default: the workspace)')
    parser.add_argument('target', nargs='?', choices=('slack',),
                        help='slack: connect your owner DM: token, pin, second factor, listener')
    parser.set_defaults(func=run)


def _edit(label, what, confirm, change, root=None):
    """The owner edit frame: validate change(root, raw) -> text, then the digest path."""
    try:
        root = workspace.find_workspace(root)
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


def card_write(root, label, change, keys, card):
    """#529: the owner's answer on a card is the confirmation, as for a learned connector
    (outbound.apply); one config.set event naming the card after the write."""
    from wuwei import state
    code = _edit(label, 'change', lambda *args, **kwargs: True, change, root)
    if code == CLEAN:
        state.append_event('config.set', {'keys': keys, 'card': card}, root)
    return code


def _settle(raw, settings):
    """raw with the settings applied; a table set to a single value raises naming it."""
    additions, edits = calibrate.settle(raw, settings)
    for dotted, current, _ in edits:  # settle lists only a table answered with a non-table
        raise ValueError(f'{dotted}: a table; set one of its keys'
                         + (f', for example {dotted}.default' if 'default' in current else ''))
    return calibrate.apply(raw, additions)


def _parts(key):
    if not KEY.fullmatch(key):
        raise ValueError(f'{key}: expected a dotted key such as owner.name or repos.0.merge_deploys; use a dotted key such as owner.name')
    parts = [int(p) if p.isdigit() else p for p in key.split('.')]
    if isinstance(parts[-1], int):
        raise ValueError(f'{key}: name a key, not a list index; use the key itself, for example repos.0.merge_deploys')
    return parts


def write_value(raw, key, value, mode='replace'):
    """The one config writer entry point (#494); #492 passes mode='append' for list keys."""
    parts = _parts(key)
    path, name = tuple(parts[:-1]), parts[-1]
    if mode not in ('replace', 'append'):
        raise ValueError(f'{mode}: unknown mode; use replace or append')
    if mode == 'append':
        current = (calibrate._table(tomllib.loads(raw), path) or {}).get(name, [])
        if not isinstance(current, list) or not isinstance(value, list):
            raise ValueError(f'{key}: append needs a list; use replace')
        value = [*current, *(v for v in value if v not in current)]
    return _settle(raw, [(path, name, value)])


def effective(config, parts):
    """The loaded value at a dotted key's parts; KeyError or IndexError when it has none."""
    for part in parts:
        config = config[part]
    return config


def merged(config, parts, value, replace=False):
    """#492: the settings for one key: a list gets the effective items plus the new ones, a
    named-entry table one setting per entry; replace writes the value as given."""
    rule = configtext.declared(parts)
    table = isinstance(rule, dict) and '*' in rule
    if replace and not (isinstance(rule, list) or table):
        raise ValueError(f"{'.'.join(map(str, parts))}: --replace applies to a list or a "
                         'named-entry table; remove --replace')
    if not replace and isinstance(rule, list) and isinstance(value, list) and value:  # #604: [] empties it
        try:
            current = effective(config, parts)
        except (KeyError, IndexError):  # repos.<n> past the end: settle names the layout
            current = []
        return [(tuple(parts[:-1]), parts[-1], [*current, *(item for item in value if item not in current)])]
    if not replace and table and isinstance(value, dict):
        return [(tuple(parts), name, item) for name, item in value.items()]
    return [(tuple(parts[:-1]), parts[-1], value)]


def _choice(parts, value):
    """#579: a bare word is the string it names when the key is a string with fixed choices
    (pace.default = fast), since a decision title cannot carry a quote."""
    node = configtext.declared(parts)
    return ({'value': value} if isinstance(node, tuple) and node[0] is str and len(node) > 2
            and value in node[2] else None)


def assignment(title):
    """#529: (key, value) for a decision option title `<dotted key> = <TOML value>`, else None."""
    key, separator, value = title.partition(' = ')
    try:
        parts = _parts(key)
        try:
            parsed = tomllib.loads(f'value = {value}\n')
        except tomllib.TOMLDecodeError:
            parsed = _choice(parts, value)
            if parsed is None:
                raise
    except (ValueError, tomllib.TOMLDecodeError):
        return None
    return (key, parsed['value']) if separator and list(parsed) == ['value'] else None


def _from_card(args, root, change):
    """#529: write the value the owner picked on the decision card, then record the card."""
    from wuwei import decision, sessions, state
    from wuwei.commands.decision import owner_outcome
    card = args.from_card
    ask = (f'config set: {card} has no recorded answer "{args.key} = {args.value}"; nothing written. '
           f'Ask the card with bin/wuwei decision show {card} --widget and run the record command '
           'for the picked option.')
    try:
        fields, _ = decision.evaluate(decision.today_path(card, root).read_text(encoding='utf-8'))
        wanted = assignment(f'{args.key} = {args.value}')
    except (OSError, ValueError) as exc:
        print(f'config set: {exc}; {ask}', file=sys.stderr)
        return FINDINGS
    option = next((row[0] for row in decision.options(fields)
                   if wanted and assignment(row[1]) == wanted and sessions.card_answered(root, card, row[1])), None)
    answered = decision.answered(state.read_state(root), card)
    if option is None or answered not in (None, option):
        print(ask, file=sys.stderr)
        return FINDINGS
    code = card_write(root, 'config set', change, [args.key], card)
    if code or answered == option:
        return code
    code, message = owner_outcome(Namespace(id=card, option=option), root=root)
    if code:
        print(f'config set: {message}', file=sys.stderr)
    return code


def set_value(args, confirm=None):
    """Owner action: set one config value after a host-terminal digest, or (#529) from the
    owner's answer on a card outside strict."""
    def change(root, raw):
        parts = _parts(args.key)
        node = configtext.declared(parts)
        try:
            parsed = tomllib.loads(f'value = {args.value}\n')
        except tomllib.TOMLDecodeError:
            if node is None:
                parsed = {}
            else:
                kind, example = configtext.describe(node)
                raise ValueError(f"{args.key}: {args.value!r} is not TOML; pass {kind}, for example '{example}'") from None
        if list(parsed) != ['value']:
            raise ValueError(f'{args.value!r}: expected one TOML value; pass one TOML value, for example \'"standard"\' or false')
        return _settle(raw, merged(load_config(root, raw=raw), parts, parsed['value'],
                                   getattr(args, 'replace', False)))

    from wuwei import interview, sessions
    try:
        root = workspace.find_workspace()
        posture = workspace.posture(load_config(root))[0]
    except (OSError, ValueError):
        return _edit('config set', 'change', confirm, change)  # it reports the reason
    card, session = getattr(args, 'from_card', None), sessions.current() and confirm is None
    command = shlex.join(['bin/wuwei', 'config', 'set', args.key, args.value])
    if posture == 'strict' and session:
        print(f'config set: under strict a card answer is not a confirmation; nothing written. '
              f'Run {command} in a host terminal.', file=sys.stderr)
        return FINDINGS
    if card and posture != 'strict':
        return _from_card(args, root, change)
    if session:  # never a /dev/tty read that comes back empty in a session
        qid = interview.card_for(args.key)
        print('config set: in a session a card answer confirms the change; nothing written. ' + (
            f'Run bin/wuwei calibrate --questions {qid}, ask the widget, then run its record '
            f'command wuwei calibrate --answer "{qid}=<label>".' if qid else
            f'Write a decision whose option titles read {args.key} = <value> and route it. Ask it with '
            f'bin/wuwei decision show D-n --widget, then run bin/wuwei config set {args.key} <value> '
            '--from-card D-n.'), file=sys.stderr)
        return FINDINGS
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
                raise ValueError('--identity: expected "Name <email>"; pass --identity "Name <email>"')
            repo['identity'] = {'name': found[1], 'email': found[2]}
        return repo_tables(raw, [repo])

    return _edit('config add-repo', 'repository', confirm, change)


def _yes(question, default):
    """One preference on the setup terminal; empty takes the default, a closed stdin is no.

    ponytail: local prompt until a shared y/N prompt lands (#354).
    """
    try:
        reply = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except EOFError:
        return False
    return default if not reply else reply in ('y', 'yes')


def _owed(name, path, branch):
    return (f'bin/wuwei config add-repo --name {shlex.quote(name or "owner/repo")} --path {shlex.quote(path)} '
            f'--branch {shlex.quote(branch or "<default branch>")}')


def _tracker_links(repo, path):
    """Tracker hosts a repository's README, CONTRIBUTING or PR template links (5.11); shown only."""
    files = [*repo.glob('README*'), *repo.glob('CONTRIBUTING*'), *repo.glob('.github/PULL_REQUEST_TEMPLATE*')]
    found = []
    for file in sorted(f for f in files if f.is_file() and not f.is_symlink()):
        text = file.read_text(encoding='utf-8', errors='replace')[:200_000]
        found += [f'tracker links: {host} ({path}/{file.relative_to(repo)})'
                  for host in ('linear.app', 'atlassian.net') if host in text]
    return found


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
        lines.extend(_tracker_links(candidate, path))
        if (candidate / '.git').is_file():
            lines.append(f'{path}: worktree, not added')
            continue
        remote = vcs.remote_url(resolved)
        url = remote.data['url'] if remote.exit == 0 else None
        found = GITHUB.fullmatch(url) if url else None
        if url and not found:  # The host only: a remote URL can carry credentials.
            from wuwei.interview import BACKLOG
            host = re.match(r'(?:[A-Za-z][A-Za-z0-9+.-]*://)?(?:[^@/]*@)?([A-Za-z0-9.-]+)', url)
            lines.append(f'{path}: {host[1] if host else "its origin"} is not GitHub; WUWEI reads GitHub '
                         f'only today (other code hosts: {BACKLOG})')
        try:  # No origin: where gh repo create would put it, under the measured login.
            name = references.repository(found[1] if found else f'{login}/{candidate.name}' if url == '' and login
                                         else '')
        except ValueError:
            name = None
        if name in configured:
            continue
        if any(repo['name'] == name for repo in repos):
            lines.append(f'{path}: {name} already listed, not added')
            continue
        branch = hub.default_branch(name) if found and name and auth == 0 else None
        why = (branch.reason if branch else 'gh is not signed in') if found else None
        branch = branch.data['branch'] if branch and branch.exit == 0 else None
        if name and not branch and (local := vcs.default_branch(resolved)).exit == 0:
            branch, source = local.data['branch'], local.data['source']
            lines.append(f'{path}: default branch {branch} (from {source}; gh could not read it: {why})' if found
                         else f'{path}: no GitHub remote; proposed as {name}, default branch {branch} (from {source})')
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
    named = next((name for repo in config['repos'] if (name := repo['identity']['name'].strip())), '')
    if named and not config['owner']['name'].strip():
        settings.append((('owner',), 'name', named))
    handles = config['owner']['handles']
    if login:
        try:  # Only when no code-host login is there yet; chat IDs stay.
            obligations._owner_login({'owner': {'handles': [*handles, login]}})
            settings.append((('owner',), 'handles', [*handles, login]))
        except ValueError:
            pass
        if not config['shepherd']['lead_login']:
            settings.append((('shepherd',), 'lead_login', login))
    owner = config['outbound']['owner']  # #495: the owner's identity per channel class.
    if login and not owner['code_host']:
        settings.append((('outbound', 'owner'), 'code_host', login))
    email = next((found for repo in config['repos'] if (found := repo['identity']['email'].strip())), '')
    if email and not owner['mail']:
        settings.append((('outbound', 'owner'), 'mail', email))
    authors = {email.strip().casefold(): login for repo in config['repos']
               if login and (email := repo['identity']['email']).strip()}
    for result in results:
        authors.update(result.get('bots') or {})
    mapped = {email.casefold() for email in config['shepherd']['authors']}
    return settings + [(('shepherd', 'authors'), email, {'login': who})
                       for email, who in sorted(authors.items()) if email not in mapped]


def run(args, confirm=None):
    """Owner action: init, discover, one proposal and one digest, then doctor and one Ready or Next line."""
    from wuwei import integrity
    try:
        return slack(confirm) if getattr(args, 'target', None) == 'slack' else _setup(args, confirm)
    except EOFError:
        print('wuwei setup: interview interrupted; nothing written; run bin/wuwei setup again to start over', file=sys.stderr)
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
    from wuwei.commands import calibrate as calibrate_command, doctor, init, watch

    # The interview and the digest both need this terminal; nothing is written yet.
    if not sys.stdin.isatty():
        raise OSError(integrity.HOST_TERMINAL)
    try:
        root = workspace.find_workspace()
    except FileNotFoundError:
        init.run(SimpleNamespace(path='.', shadow=args.shadow, upgrade=False, dry_run=False, menu_bar=False,
                                 honeytoken_path=security.DEFAULT_HONEYTOKEN_PATH, status_line=False))
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
        owed = found['owed'] or [_owed(None, '<path>', None)]
        print(ending([], owed[:1], owed[1:])[0])
        return FINDINGS
    names = [repo['name'] for repo in staged_cfg['repos']]
    extra = []
    if found['tools']['ziran'] and cfg['adapters']['scanner'] == 'none' and _yes(
            'ZIRAN is installed. Turn on its security scans (adapters.scanner = "ziran")?', False):
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
                print(f'wuwei setup: refused: {key} ({why}); nothing written; run bin/wuwei setup again with a value config check accepts', file=sys.stderr)
            return FINDINGS
        for where, rule in flagged:
            print(f'Flagged {where} ({rule}), not proposed')
        profiles.record(root, accepted, names)
    snapshot_path = root / '.wuwei/calibration.json'
    picked = {}
    # #615: the survey runs before the interview so the deploys question recommends from its facts.
    results = calibrate.survey(root, staged_cfg, list(enumerate(staged_cfg['repos'])), style=True)
    if found['repos'] or not snapshot_path.exists():
        from wuwei import docs, specmode
        paths = [(root / Path(repo['path']).expanduser()).resolve() for repo in staged_cfg['repos']]
        engine = specmode.detect(paths, staged_cfg)
        link = docs.detect(paths)
        picked = interview.ask(
            [row['id'] for row in interview.QUESTIONS if not (args.shadow and row['id'] == 'autonomy')], names,
            first={'spec': next(label for label, _, effect in interview.question('spec')['choices']
                                if effect == {'spec.engine': engine}),
                   'deploys': {r['repo']['name']: interview.deploys_first(r['facts']) for r in results}},
            **({'defaults': {'docs': link}} if link else {}))
        if args.shadow:
            picked['autonomy'] = 'Autonomous'  # the flag answered it, so the first day does not ask again
        interview.record(root, staged_cfg, picked)
    unmeasured = [f"{r['repo']['name']}: {command}" for r in results
                  for command, (_, note) in r['checks'].items() if note == calibrate.UNMEASURED]
    if unmeasured:
        print('Test runner found: ' + '; '.join(unmeasured))
        if _yes('Run your tests once now to see if they are fast enough for every push?', True):
            runner = registry.load('checks', staged_cfg)
            for r in results:
                r['checks'] = calibrate.classify(r['checkout'], r['facts']['fast_checks'], runner,
                                                 staged_cfg['calibrate']['fast_check_seconds'], root)
    extra += identity(staged_cfg, found['login'], results)
    text, diff, edits, summary, snapshot = config.proposal(root, raw, staged, staged_cfg, results, extra)
    if text == raw and snapshot_path.exists():
        print('Nothing to propose')
    else:
        if config.offer(root, raw, text, summary, label='setup', what='setup', confirm=confirm,
                        snapshot=snapshot):
            return FINDINGS
        calibrate_command.record(root, results, diff, edits, None)
    optional = []
    if 'chat' in picked and interview.effects('chat', picked['chat']).get('adapters.chat') == 'slack' \
            and load_config(root)['adapters']['inbound'] == 'none':
        print('Slack: connecting your DM now (bin/wuwei setup slack)')
        if connect(root, confirm):
            optional.append('bin/wuwei setup slack')
    try:
        if 'statusLine' not in init.settings(root)[1] and _yes(
                'Show the WUWEI status line in Claude Code for this project?', True):
            init.status_line(root)
            print('Status line: added to .claude/settings.json')
    except (OSError, ValueError) as exc:
        print(f'wuwei setup: status line not written: {exc}; run bin/wuwei setup again to add it', file=sys.stderr)
        optional.append('put the statusLine from bin/wuwei init into .claude/settings.json')
    if picked.get('allowlist') and interview.effects('allowlist', picked['allowlist']).get('allowlist'):
        try:  # #530: the terminal answer is the confirmation
            for rule in init.allow(root):
                print(f'Wrote .claude/settings.local.json: {rule}')
        except (OSError, ValueError) as exc:
            print(f'wuwei setup: allowlist not written: {exc}; run bin/wuwei calibrate --interview allowlist',
                  file=sys.stderr)
            optional.append('bin/wuwei calibrate --interview allowlist')
    platform = watch.service_platform()
    if platform in ('darwin', 'linux') and not workspace.watch_unit(root, platform)[1].exists() and _yes(
            'Install the watch service, which supervises the day and your pull requests in the background?', False):
        try:
            watch.service(SimpleNamespace(watch_action='install', once=False, dry_run=False), 'watch', None)
        except (OSError, ValueError) as exc:
            print(f'wuwei setup: watch install: {exc}; run bin/wuwei watch install in a host terminal', file=sys.stderr)
    gate = mcp.check(root)
    if gate.reason:
        print(gate.reason, file=sys.stderr)
    final = load_config(root)
    required = [f'set {name} in .wuwei/env' for name in config.missing(final)]
    if gate.exit == 2 and mcp.unmeasured(root):
        required.append('bin/wuwei mcp decide proceed-unmeasured '
                        + ' '.join(map(shlex.quote, mcp.unmeasured(root))))
    elif gate.exit:
        waiting = mcp.pending(root)
        required.append(mcp.command(waiting) if waiting else 'bin/wuwei mcp check')
    optional = found['owed'] + optional
    if not final['owner']['name'].strip():
        optional.append('bin/wuwei config set owner.name \'"<your name>"\'')
    proposals = workspace.day_dir(root) / 'proposals'
    if proposals.is_dir() and any(proposals.iterdir()):
        optional.append('bin/wuwei promote')
    text, code = ending(doctor.diagnose(), required, optional, gate.exit)
    print(text)
    return code


def slack(confirm=None):
    """Owner action: connect the owner DM, then the config check; the highest exit of both."""
    from types import SimpleNamespace
    from wuwei import integrity

    if not sys.stdin.isatty():
        raise OSError(integrity.HOST_TERMINAL)
    code = connect(workspace.find_workspace(), confirm)
    return max(code, config.run(SimpleNamespace()))


def connect(root, confirm=None):
    """Token, DM channel, pin and both adapters, TOTP secret, listener; a value already set is kept."""
    import base64
    import getpass
    import secrets
    from types import SimpleNamespace
    from wuwei import env, remote
    from wuwei.commands import watch

    env.load(root)
    new = {}
    for name in ('SLACK_BOT_TOKEN', 'SLACK_OWNER_DM_CHANNEL'):
        if os.environ.get(name):
            print(f'{name}: already set, kept')
    if not os.environ.get('SLACK_BOT_TOKEN'):
        token = getpass.getpass('Slack bot token (hidden; Enter to skip): ').strip()
        if not re.fullmatch(r'xoxb-[A-Za-z0-9-]+', token):
            print('wuwei setup slack: ' + ('no bot token' if not token else 'that is not a bot token')
                  + f'; {TOKEN_HINT}', file=sys.stderr)
            return FINDINGS
        new['SLACK_BOT_TOKEN'] = token
    if not os.environ.get('SLACK_OWNER_DM_CHANNEL'):
        channel = input('Owner DM channel ID (open your direct message with the app; the ID starts with D '
                        'and is in the conversation details or link): ').strip()
        if not re.fullmatch(r'D[A-Z0-9]+', channel):
            print('wuwei setup slack: ' + ('no DM channel ID' if not channel else 'that is not a DM channel ID')
                  + '; it starts with D. Find it in the details or link of your direct message with the app. '
                  'Then run bin/wuwei setup slack again', file=sys.stderr)
            return FINDINGS
        new['SLACK_OWNER_DM_CHANNEL'] = channel
    if new:
        env.write(root, new)
        env.load(root)
        print(f'Saved {" and ".join(new)} to .wuwei/env (mode 0600)')
    settings = [(('adapters',), 'chat', 'slack'), (('adapters',), 'inbound', 'slack')]
    current = load_config(root)
    pin = current['control_plane']['owner']
    if re.fullmatch(remote.PIN, pin):
        print('control_plane.owner: already set, kept')
    else:
        found = _first_dm(root, os.environ['SLACK_OWNER_DM_CHANNEL'])
        if found.exit:
            print('wuwei setup slack: ' + (f'{found.reason}; ' if found.reason else
                                           'no message from the DM in 5 minutes; ') + DM_HINT, file=sys.stderr)
            return found.exit
        print(f'Message from {found.data}: pin it as control_plane.owner so only this sender '
              'can command WUWEI from the DM.')
        settings.append((('control_plane',), 'owner', found.data))
        pin = found.data
    if re.fullmatch(remote.PIN, pin) and not current['outbound']['owner']['slack']['user']:
        # #495: the owner's user id; SLACK_OWNER_DM_CHANNEL is the app DM, never the owner's own.
        settings.append((('outbound', 'owner', 'slack'), 'user', pin.split('/')[1]))
    code = _edit('setup slack', 'Slack settings', confirm, lambda root, raw: _settle(raw, settings))
    if code:
        return code
    if os.environ.get('WUWEI_TOTP_SECRET'):
        print('WUWEI_TOTP_SECRET: already set, kept')
    else:
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        env.write(root, {'WUWEI_TOTP_SECRET': secret})
        env.load(root)
        print('Saved WUWEI_TOTP_SECRET to .wuwei/env, the second factor for plan and ask. Add it to an '
              'authenticator app by manual key entry (time based, SHA1, 6 digits, 30 seconds) or as a QR '
              'code of this URI made on this host:\n'
              f'otpauth://totp/WUWEI:owner?secret={secret}&issuer=WUWEI&algorithm=SHA1&digits=6&period=30')
        print('Never paste the secret or the URI into a website.')
    platform = watch.service_platform()
    if platform not in ('darwin', 'linux'):
        print('Listener: run bin/wuwei listen in a terminal that stays open')
        return CLEAN
    try:  # The listener reads .wuwei/env once at start: an installed one is restarted.
        for action in (('uninstall',) if workspace.watch_unit(root, platform, name='listen')[1].exists()
                       else ()) + ('install',):
            watch.service(SimpleNamespace(listen_action=action, once=False, dry_run=False), 'listen', None)
    except (OSError, ValueError) as exc:
        print(f'wuwei setup slack: listener: {exc}; run bin/wuwei listen install', file=sys.stderr)
        return FINDINGS
    return CLEAN


def _first_dm(root, channel):
    """Result with the sender of the first DM message after now; exit 1 when none came in time."""
    from wuwei.registry import Result

    inbound = registry.load('inbound', {'adapters': {'inbound': 'slack'}})
    start = int(workspace.now().timestamp())
    print('Send any message to the app in Slack now; waiting up to 5 minutes.', flush=True)
    for _ in range(WAIT_SECONDS // POLL_SECONDS):
        result = inbound.poll(str(start), root=root)
        if result.exit:
            return result
        # The poll reads 300 s back, so older messages are filtered here.
        sender = next((event['sender'] for event in result.data
                       if event['channel'] == channel and float(event['ts']) >= start), None)
        if sender:
            return Result(0, sender)
        time.sleep(POLL_SECONDS)
    return Result(1, None)


def ending(rows, required, optional, gate=0):
    """(text, exit): an Optional line when anything is left, then one Ready or Next line.

    Required: what is passed in, the MCP gate, and failing or unmeasured Install and Workspace
    doctor rows; every other doctor row is optional.
    """
    from wuwei.commands import doctor

    blocking = [row for row in rows if row['section'] in ('install', 'workspace')
                and row['status'] in ('fail', 'unmeasured')]
    steps = required + [row.get('fix') or 'bin/wuwei doctor' for row in blocking]
    others = sum(row['status'] != 'ok' for row in rows if row not in blocking and row['name'] != 'mcp gate')
    parts = optional + ([f'{others} more in bin/wuwei doctor'] if others else [])
    text = ('Optional: ' + '; '.join(parts) + '\n' if parts else '') + (
        f'Next: {steps[0]}' if steps else 'Ready: run /wuwei:wuwei-plan')
    return text, max([FINDINGS if steps else CLEAN, gate,
                      *(doctor.CODES[row['status']] for row in blocking)])
