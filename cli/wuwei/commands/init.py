"""Create a workspace from the shipped skeleton."""

import os
from pathlib import Path
import shutil
import sys
import tempfile

from wuwei.exits import CLEAN, FINDINGS


def register(subparsers):
    parser = subparsers.add_parser("init", help="create a workspace")
    parser.add_argument("path", nargs="?", default=".")
    parser.set_defaults(func=run)


def run(args):
    destination = Path(args.path).expanduser() / ".wuwei"
    if destination.exists() or destination.is_symlink():
        print(f"wuwei init: {destination} already exists; choose another path", file=sys.stderr)
        return FINDINGS
    template = Path(__file__).resolve().parents[3] / "templates/workspace"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".wuwei-init-", dir=destination.parent)
    try:
        shutil.copytree(template, staging, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".gitkeep"))
        os.rename(staging, destination)
    finally:
        if os.path.exists(staging):
            shutil.rmtree(staging)
    print(f"Created {destination.resolve()}")
    return CLEAN
