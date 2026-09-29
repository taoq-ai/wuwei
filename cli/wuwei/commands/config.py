"""Validate workspace configuration."""

import os
import sys

from wuwei import registry

from wuwei.exits import CLEAN, FINDINGS
from wuwei.workspace import ConfigError, load_config


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
    return status
