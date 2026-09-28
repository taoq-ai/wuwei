"""Create a workspace from the shipped skeleton."""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from wuwei.exits import CLEAN, FINDINGS
from wuwei import workspace
from wuwei.guards.deploy import PERMISSIONS_DENY


def register(subparsers):
    parser = subparsers.add_parser("init", help="create a workspace")
    parser.add_argument("path", nargs="?", default=".")
    parser.set_defaults(func=run)


def run(args):
    destination = Path(args.path).expanduser() / ".wuwei"
    if destination.exists() or destination.is_symlink():
        print(f"wuwei init: {destination} already exists; choose another path", file=sys.stderr)
        return FINDINGS
    settings = destination.parent / '.claude/settings.json'
    if settings.parent.is_symlink() or settings.is_symlink():
        raise ValueError('workspace settings must not be symlinks')
    if destination.parent.resolve() == Path.home().resolve():
        raise ValueError('workspace settings must not be owner global settings')
    data = json.loads(settings.read_text()) if settings.exists() else {}
    if not isinstance(data, dict) or not isinstance(data.get('permissions', {}), dict):
        raise ValueError('workspace settings and permissions must be objects')
    permissions = data.setdefault('permissions', {})
    denials = permissions.setdefault('deny', [])
    if not isinstance(denials, list) or not all(isinstance(rule, str) for rule in denials):
        raise ValueError('workspace permissions.deny must be a list of strings')
    permissions['deny'] = list(dict.fromkeys([*denials, *PERMISSIONS_DENY]))
    template = Path(__file__).resolve().parents[3] / "templates/workspace"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".wuwei-init-", dir=destination.parent)
    try:
        shutil.copytree(template, staging, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".gitkeep"))
        executable = Path(__file__).resolve().parents[3] / "bin/wuwei"
        (Path(staging) / "executable").write_text(str(executable) + "\n")
        settings.parent.mkdir(exist_ok=True)
        workspace.atomic_write(settings, json.dumps(data, indent=2) + '\n')
        os.rename(staging, destination)
    finally:
        if os.path.exists(staging):
            shutil.rmtree(staging)
    print(f"Created {destination.resolve()}")
    return CLEAN
