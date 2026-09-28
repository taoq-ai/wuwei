"""Validate workspace configuration."""

import sys

from wuwei.exits import CLEAN, FINDINGS
from wuwei.workspace import ConfigError, load_config


def register(subparsers):
    parser = subparsers.add_parser("config", help="inspect workspace configuration")
    actions = parser.add_subparsers(dest="action", required=True)
    check = actions.add_parser("check", help="validate config.toml")
    check.set_defaults(func=run)


def run(args):
    try:
        load_config()
    except ConfigError as exc:
        print(f"wuwei config check: {exc}", file=sys.stderr)
        return FINDINGS
    return CLEAN
