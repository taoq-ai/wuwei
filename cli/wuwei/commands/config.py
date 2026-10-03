"""Validate workspace configuration."""

import os
import re
import sys

from wuwei import env, outward, registry, workspace

from wuwei.exits import CLEAN, FINDINGS, UNRUN, SYMLINK
from wuwei.workspace import ConfigError, load_config


PIN_MISSING = 'control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)'


def register(subparsers):
    parser = subparsers.add_parser("config", help="inspect workspace configuration")
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser("check", help="validate config.toml")
    check.set_defaults(func=run)
    parser = actions.add_parser('promote', help='apply the calibration proposal (owner, host terminal)')
    parser.add_argument('--measure', action='store_true',
                        help='time each test runner once through the checks port (runs repository commands)')
    parser.set_defaults(func=promote)
    from wuwei.commands import setup
    parser = actions.add_parser('set', help='set one config value (owner, host terminal)')
    parser.add_argument('key', help='dotted key, for example owner.verbosity.default or repos.0.merge_deploys')
    parser.add_argument('value', help='one TOML value, for example \'"standard"\' or false')
    parser.set_defaults(func=setup.set_value)
    parser = actions.add_parser('add-repo', help='add one repository (owner, host terminal)')
    parser.add_argument('--name', required=True, help='owner/repo')
    parser.add_argument('--path', required=True, help='relative to the workspace, or absolute')
    parser.add_argument('--branch', required=True, help='the default branch')
    parser.add_argument('--identity', help='commit identity, "Name <email>"')
    parser.set_defaults(func=setup.add_repo)


def run(args):
    found = []
    try:
        config = load_config(warnings=found)
    except ConfigError as exc:
        print(f"wuwei config check: {exc}", file=sys.stderr)
        return FINDINGS
    for text in found:  # #353: unknown keys warn below strict; the exit code ignores them.
        print(f'wuwei config check: warning: {text}', file=sys.stderr)
    print('Credentials:')
    status = CLEAN
    needed = requirements(config)
    for kind, name in config['adapters'].items():
        if name == 'none':
            continue
        label = f'{kind}.{name}'
        if (kind, name) == ('code_host', 'github'):
            result = registry.load(kind, config).auth_status()
            print(f'  {label}: gh auth: ' + ('set' if result.exit == 0 else
                  'missing' if result.exit == 1 else 'unmeasured'))
            if result.exit == 2:
                print(result.reason, file=sys.stderr)
            status = max(status, result.exit)
        elif (kind, name) == ('runtime', 'codex'):
            present = bool(config['codex']['command'])
            print(f'  {label}: codex.command: {"set" if present else "missing"}')
            status = max(status, CLEAN if present else FINDINGS)
        elif (kind, name) in needed:
            for alternatives in needed[kind, name]:
                present = any(os.environ.get(key) for key in alternatives)
                fields = ', '.join(f'{key}: {"set" if os.environ.get(key) else "missing"}'
                                   for key in alternatives)
                suffix = ' (one required)' if len(alternatives) > 1 else ''
                print(f'  {label}: {fields}{suffix}')
                status = max(status, CLEAN if present else FINDINGS)
        else:
            print(f'  {label}: no credential variables required')
    # Reported, not a finding: the outward lint already fails closed without a name.
    print('Owner:\n  ' + ('owner.name: set' if config['owner']['name'].strip() else outward.OWNER_UNSET))
    # Reported, not a finding (#331): a floor violation already failed load_config above.
    name, levels = workspace.posture(config)
    print(f'Posture: {name} (from {workspace.posture_source(config)})')
    for area in workspace.AREAS:
        mark = (' (floor)' if area in workspace.FLOORS else
                ' (security.areas)' if config['security']['areas'][area] else '')
        print(f'  {area}: {levels[area]}{mark}')
    print('  owner-only actions block in every posture: deploys, merges and approvals, '
          'approve-tier messages')
    block = config['scanner']['mcp']['block']
    if block:  # Reported, not a finding (#351): the list against the posture default.
        ignored = levels['mcp'] == 'off' or name == 'observe' and levels['mcp'] == 'warn'
        print(f'  scanner.mcp.block ({", ".join(block)}): ' + (
            f'no effect under {name} (mcp: {levels["mcp"]}); remove the key' if ignored else
            f'blocks launches at these severities on top of the {name} default'))
    if config['adapters']['inbound'] != 'none':
        from wuwei.remote import PIN
        pin = config['control_plane']['owner']
        valid = bool(re.fullmatch(PIN, pin))
        print('Control plane:\n  ' + ('control_plane.owner: set' if valid else
              'control_plane.owner: invalid (expected <team id>/<user id>)' if pin else PIN_MISSING))
        status = max(status, CLEAN if valid else FINDINGS)
        # Reported, not a finding: without it a confirm reply is the second factor.
        print('  WUWEI_TOTP_SECRET: ' + ('set' if os.environ.get('WUWEI_TOTP_SECRET') else
                                        'missing (confirm replies are the only second factor)'))
    # Design 4.5 and 9.1: the publishing guarantee lives in host rules and the credential layout.
    host = registry.load('code_host', config)
    print('Host protections:')
    for repo in config['repos']:
        status = max(status, _protection(host, repo, config['shepherd']['min_reviewers'] == 0,
                                         config['shepherd']['review_gate_check']))
    print('Seat credentials:')
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        status = max(status, _token(host, name))
    return status


def requirements(config):
    """Credential variables per selected adapter; each tuple needs one of its names."""
    needed = {
        ('tracker', 'linear'): [('LINEAR_API_KEY',)],
        ('chat', 'slack'): [('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN'), ('SLACK_OWNER_DM_CHANNEL',)],
        ('inbound', 'slack'): [('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN'), ('SLACK_OWNER_DM_CHANNEL',)],
        ('review_bot', 'greptile'): [('GREPTILE_API_KEY',)],
        ('calendar', 'ics'): [('WUWEI_CALENDAR_URL',)],
    }
    if config['chat']['identity'] == 'custom_app':
        needed['chat', 'slack'][0] = ('SLACK_BOT_TOKEN',)
    return needed


def missing(config):
    """Offline findings of config check: credential variables, codex.command, owner pin."""
    from wuwei.remote import PIN
    needed = requirements(config)
    names = [' or '.join(alternatives) for kind, name in config['adapters'].items()
             for alternatives in needed.get((kind, name), ())
             if not any(os.environ.get(key) for key in alternatives)]
    if config['adapters']['runtime'] == 'codex' and not config['codex']['command']:
        names.append('codex.command')
    if (config['adapters']['inbound'] != 'none'
            and not re.fullmatch(PIN, config['control_plane']['owner'])):
        names.append('control_plane.owner')
    return names


def read(root):
    """(path, raw text) of config.toml, refusing a symlinked config or calibration snapshot."""
    path = root / '.wuwei/config.toml'
    if path.is_symlink() or (root / '.wuwei/calibration.json').is_symlink():
        raise ValueError(f'config.toml and calibration.json must not be symlinks; {SYMLINK}')
    return path, path.read_text(encoding='utf-8')


def proposal(root, raw, base, config, results, extra=()):
    """(text, diff, edits, summary, snapshot): the calibration of base, diffed against raw."""
    import difflib
    import json
    from wuwei import calibrate, interview, profiles, workspace

    answers = interview.load(root, config)
    name, imported = profiles.load(root, config)
    asked = interview.settings(answers, config)
    # An interview answer wins over the profile for the same key, and both over a setup default.
    imported = [s for s in imported if s[:2] not in {a[:2] for a in asked}]
    owned = {s[:2] for s in imported + asked}
    text, diff, edits = calibrate.propose(
        base, results, [s for s in extra if s[:2] not in owned] + imported + asked)
    if base != raw:
        diff = ''.join(difflib.unified_diff(raw.splitlines(keepends=True), text.splitlines(keepends=True),
                                            'config.toml', 'config.toml (proposed)'))
    today = workspace.now().date().isoformat()
    snapshot = {r['repo']['name']: {**calibrate.drift_facts(r['facts']),
                                    'baseline': r['baseline'] or 'unmeasured', 'date': today}
                for r in results}
    summary = (diff or 'No config.toml changes\n') + ''.join(
        f'Config differs; edit by hand: {key}\n' for key, _, _ in edits) + (
        'Interview answers:\n' + ''.join(line + '\n' for line in interview.describe(answers, config))
        if answers else '') + ''.join(
        f"Profile {name}: {'.'.join(map(str, (*path, key)))} = {json.dumps(value)}\n"
        for path, key, value in imported) + ''.join(
        f"Flagged {f['kind']}: {f['source']} ({f['value']})\n" for r in results
        for f in r['findings'] if f['kind'] in ('instruction_like', 'unsafe')) + ''.join(
        f'CI only, not proposed as a fast check: {repo}: {command} ({note})\n'
        for repo, command, note in calibrate.ci_only(results)) + (
        'Approved calibration for .wuwei/calibration.json:\n'
        + json.dumps(snapshot, indent=2, sort_keys=True) + '\n')
    return text, diff, edits, summary, snapshot


def offer(root, raw, text, summary, *, label, what, confirm=None, snapshot=None):
    """The one owner digest path: print, confirm on the host terminal, re-read, write."""
    import hashlib
    import json
    from wuwei import integrity, workspace

    print(summary, end='')
    digest = hashlib.sha256(summary.encode()).hexdigest()[:12]
    if not (confirm or integrity._host_confirm)(
            digest, prompt=f'Apply the {what} above.'):
        print(f'wuwei {label}: declined; nothing written; rerun it in a host terminal and answer y', file=sys.stderr)
        return FINDINGS
    path = root / '.wuwei/config.toml'
    if path.read_text(encoding='utf-8') != raw:
        raise ValueError('config.toml changed during confirmation; nothing written, run it again')
    if text != raw:
        workspace.atomic_write(path, text)
    if snapshot is not None:
        workspace.atomic_write(root / '.wuwei/calibration.json',
                               json.dumps(snapshot, indent=2, sort_keys=True) + '\n')
    print(f'Applied the {what}' + (' and recorded .wuwei/calibration.json' if snapshot is not None else ''))
    return CLEAN


def promote(args, confirm=None):
    """Owner action: recompute the calibration, show it, and apply it after a terminal digest."""
    from wuwei import calibrate, workspace

    try:
        root = workspace.find_workspace()
        config = load_config(root)
        _, raw = read(root)
        if not config['repos']:
            raise ValueError(calibrate.NO_REPOS)
        results = calibrate.survey(root, config, list(enumerate(config['repos'])), style=False,
                                   measure=getattr(args, 'measure', False))
        text, _, _, summary, snapshot = proposal(root, raw, raw, config, results)
        return offer(root, raw, text, summary, label='config promote', what='calibration',
                     confirm=confirm, snapshot=snapshot)
    except ConfigError as exc:
        print(f'wuwei config promote: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'wuwei config promote: {exc}', file=sys.stderr)
        return UNRUN


def _protection(host, repo, solo, gate):
    branch = repo['default_branch']
    label = f"  {repo['name']} {branch}"
    result = host.protection(repo['name'], branch)
    try:
        if result.exit:
            raise ValueError(result.reason)
        data = result.data
        names = sorted({check['name'] for check in data['required_checks']})
        listed = ', '.join(names)
        absent = [name for name in repo['review_required_checks'] if name not in names]
        rows = [
            # Information only: a 404 means unprotected or no admin; rulesets still measure below.
            ('protected ref', 'ok', '') if data['classic'] else
            ('classic protection', 'none visible (404: unprotected or no admin)', ''),
            ('required checks', f'ok ({listed})' if names and not absent else None,
             f'require status checks on {branch}' + (': ' + ', '.join(absent) if absent else '')
             + (f'; required now: {listed}' if names else '')),
            ('required reviews', 'ok' if data['approvals'] >= 1 else
             'ok (solo owner: shepherd.min_reviewers = 0)' if solo else None,
             f'require at least 1 approving review on {branch}, '
             'or set shepherd.min_reviewers = 0 for a solo owner'
             + (f'; the required check {gate} (shepherd.review_gate_check) may be satisfying it'
                if gate in names else '')),
            ('force pushes', 'ok' if data['allow_force_pushes'] is False else None,
             f'block force pushes on {branch}'),
            ('deletions', 'ok' if data['allow_deletions'] is False else None,
             f'block deletions of {branch}'),
        ]
    except (KeyError, TypeError, ValueError):
        print(f'{label}: protection: unmeasured')
        print(result.reason or f"{repo['name']}: unreadable protection result", file=sys.stderr)
        return UNRUN
    for name, state, fix in rows:
        print(f'{label}: {name}: {state or f"missing ({fix})"}')
    if all(state for _, state, _ in rows):
        return CLEAN
    print(f"{label}: fix in https://github.com/{repo['name']}/settings/branches")
    if not data['classic']:  # Nothing to overwrite: one PUT sets the whole recommended layout.
        import shlex
        from urllib.parse import quote
        contexts = repo['review_required_checks']
        argv = ['gh', 'api', '-X', 'PUT', f"repos/{repo['name']}/branches/{quote(branch, safe='')}/protection",
                '-F', 'enforce_admins=false', '-F', 'restrictions=null',
                '-F', 'allow_force_pushes=false', '-F', 'allow_deletions=false',
                '-F', 'required_pull_request_reviews=null' if solo else
                'required_pull_request_reviews[required_approving_review_count]=1',
                *(['-F', 'required_status_checks[strict]=false',
                   *(arg for name in contexts for arg in ('-f', f'required_status_checks[contexts][]={name}'))]
                  if contexts else ['-F', 'required_status_checks=null'])]
        print(f'{label}: or run in your own terminal: {shlex.join(argv)}')
    return FINDINGS


def _token(host, name):
    if not os.environ.get(name):
        print(f'  {name}: not set')
        return CLEAN
    source = '.wuwei/env' if name in env._loaded else 'the environment'
    if name in env._shadowed:
        print(f'  {name} ({source}): unmeasured')
        print(f'{name}: the environment value shadows the .wuwei/env value, which was not measured; unset it in the environment, or remove it from .wuwei/env',
              file=sys.stderr)
        return UNRUN
    result = host.token_scopes(name)
    scopes = result.data.get('scopes') if result.exit == 0 and isinstance(result.data, dict) else None
    if not scopes or not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
        print(f'  {name} ({source}): unmeasured')
        print(result.reason or f'{name}: unreadable scopes', file=sys.stderr)
        return UNRUN
    if all(scope.startswith('read:') for scope in scopes):
        print(f'  {name} ({source}): read-only')
        return CLEAN
    print(f"  {name} ({source}): write scopes {', '.join(scopes)}; remove it from {source}, "
          "seats can read it (publish from the owner's own gh login)")
    return FINDINGS
