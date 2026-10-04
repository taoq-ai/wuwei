"""Markdown pages as files in the item's worktree: no network, no credential, and not an
outward write (the page ships in the item's pull request)."""

from datetime import datetime, timezone
from pathlib import Path

from .._http import Failure, operation
from wuwei.registry import Result


def read(ref, *, root=None):
    path = Path(ref)
    if path.is_symlink() or not path.is_file():
        return Result(1, None, 'markdown.read: no page at that path')
    text = path.read_text(encoding='utf-8')
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith('# ')), path.stem)
    updated = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    return Result(0, {'id': str(path), 'title': title, 'link': str(path), 'updated': updated})


@operation('markdown.write')
def write(draft, *, root=None):
    from wuwei import workspace
    parent = Path(draft['parent'])
    target = Path(draft['ref'] or parent / f"{draft['item']}.md")
    if target.is_symlink() or not target.resolve().is_relative_to(parent.resolve()):
        raise Failure('page path must be a plain file under the docs root')
    target.parent.mkdir(parents=True, exist_ok=True)
    if draft['ref']:
        text = target.read_text(encoding='utf-8') + '\n' + draft['body']
    else:
        text = f"# {draft['title']}\n\n{draft['body']}"
    workspace.atomic_write(target, text)
    return {'id': str(target), 'link': str(target)}
