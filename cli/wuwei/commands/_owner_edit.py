"""Shared owner edit CLI flow for goals and voice."""

import os
from pathlib import Path
import sys
import tempfile

from wuwei import promotion, registry, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(actions):
    edit = actions.add_parser('edit', help='edit owner memory and promote the result')
    edit.add_argument('--file', type=Path)
    edit.set_defaults(func=run)


def run(args):
    name = args.command
    try:
        root = workspace.find_workspace()
        if args.file is not None:
            text = args.file.read_text(encoding='utf-8')
        else:
            target = promotion.safe_path(root, f'.wuwei/memory/{name}.md', label='target')
            with tempfile.TemporaryDirectory(prefix='wuwei-owner-edit-') as directory:
                draft = Path(directory) / target.name
                draft.write_text(target.read_text(encoding='utf-8'), encoding='utf-8')
                editor = registry.load('editor', {'adapters': {'editor': 'local'}})
                result = editor.edit(draft, os.environ.get('EDITOR') or 'vi', root=root)
                if result.exit:
                    raise OSError(result.reason)
                text = draft.read_text(encoding='utf-8')
        saved = 'saved' if promotion.owner_edit(root, name, text) else 'unchanged'
        if name == 'goals':
            from wuwei.goals import parse
            ids = list(parse(text))
            print(f"goals: {len(ids)} goal{'s' * (len(ids) != 1)} {saved} ({', '.join(ids)})")
        else:
            print(f'voice: {saved}')
        return CLEAN
    except (ValueError, PermissionError) as exc:
        print(f'wuwei {name} edit: {exc}', file=sys.stderr)
        return FINDINGS
    except (OSError, UnicodeError, TypeError) as exc:
        print(f'wuwei {name} edit: {exc}', file=sys.stderr)
        return UNRUN
