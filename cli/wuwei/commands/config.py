"""Validate workspace configuration."""

import os
import re
import sys

from wuwei import env, outward, registry

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.workspace import ConfigError, load_config


PIN_MISSING = 'control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)'


def register(subparsers):
    parser = subparsers.add_parser("config", help="inspect workspace configuration")
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser("check", help="validate config.toml")
    check.set_defaults(func=run)


def run(args):
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"wuwei config check: {exc}", file=sys.stderr)
        return FINDINGS
    print('Credentials:')
    status = CLEAN
    requirements = {
        ('tracker', 'linear'): [('LINEAR_API_KEY',)],
        ('chat', 'slack'): [('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN'), ('SLACK_OWNER_DM_CHANNEL',)],
        ('inbound', 'slack'): [('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN'), ('SLACK_OWNER_DM_CHANNEL',)],
        ('review_bot', 'greptile'): [('GREPTILE_API_KEY',)],
        ('calendar', 'ics'): [('WUWEI_CALENDAR_URL',)],
    }
    if config['chat']['identity'] == 'custom_app':
        requirements['chat', 'slack'][0] = ('SLACK_BOT_TOKEN',)
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
        elif (kind, name) in requirements:
            for alternatives in requirements[kind, name]:
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
        status = max(status, _protection(host, repo, config['shepherd']['min_reviewers'] == 0))
    print('Seat credentials:')
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        status = max(status, _token(host, name))
    return status


def _protection(host, repo, solo):
    branch = repo['default_branch']
    label = f"  {repo['name']} {branch}"
    result = host.protection(repo['name'], branch)
    if result.exit and 'branch protection absent' in result.reason:
        print(f'{label}: protected ref: missing (protect {branch}: require status checks and '
              'at least 1 approving review, block force pushes and deletions)')
        return FINDINGS
    try:
        if result.exit:
            raise ValueError(result.reason)
        data = result.data
        names = {check['name'] for check in data['required_checks']}
        absent = [name for name in repo['review_required_checks'] if name not in names]
        rows = [
            ('protected ref', 'ok', ''),
            ('required checks', 'ok' if names and not absent else None,
             f'require status checks on {branch}' + (': ' + ', '.join(absent) if absent else '')),
            ('required reviews', 'ok' if data['approvals'] >= 1 else
             'ok (solo owner: shepherd.min_reviewers = 0)' if solo else None,
             f'require at least 1 approving review on {branch}, '
             'or set shepherd.min_reviewers = 0 for a solo owner'),
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
    return CLEAN if all(state for _, state, _ in rows) else FINDINGS


def _token(host, name):
    if not os.environ.get(name):
        print(f'  {name}: not set')
        return CLEAN
    source = '.wuwei/env' if name in env._loaded else 'the environment'
    if name in env._shadowed:
        print(f'  {name} ({source}): unmeasured')
        print(f'{name}: the environment value shadows the .wuwei/env value, which was not measured',
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
