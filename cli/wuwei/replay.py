"""Recorded audits: a PR's code-host answers, the workspace and the clock, kept so a later version
can be held to the same answer (golden tests from real days)."""

import json
from pathlib import Path
import shutil

from wuwei import evidence, gh, ws

KEEP = ('config.toml', 'plan.json', 'ledger.jsonl', 'ledger', 'verdicts')


def record(root, repo, number, directory):
    directory = Path(directory)
    copy = directory / 'workspace'
    (copy / ws.DIR).mkdir(parents=True, exist_ok=True)
    for name in KEEP:
        source = Path(root) / ws.DIR / name
        if source.is_dir():
            shutil.copytree(source, copy / ws.DIR / name, dirs_exist_ok=True)
        elif source.is_file():
            shutil.copy2(source, copy / ws.DIR / name)
    calls, real = {}, gh.run

    def recording(args, timeout=30):
        try:
            calls[json.dumps(args)] = {'out': real(args, timeout)}
        except gh.GhError as exc:
            calls[json.dumps(args)] = {'error': str(exc)}
            raise
        return calls[json.dumps(args)]['out']
    gh.run = recording
    try:
        found = evidence.gaps(copy, repo, number)
    finally:
        gh.run = real
    shutil.rmtree(copy / ws.DIR / 'cache', ignore_errors=True)
    case = {'repo': repo, 'number': number, 'now': ws.now().isoformat(), 'gh': calls, 'expected': found}
    (directory / 'case.json').write_text(json.dumps(case, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return found
