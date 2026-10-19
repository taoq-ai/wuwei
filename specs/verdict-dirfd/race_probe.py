"""verdict-dirfd race probe: a separate process swaps a parent of the copy path between a folder and a link to
.wuwei/ledger while the hook copies worktree verdicts in.

    python3 race_probe.py <tree> <scratch> [runs] [level]

<tree> is a tree made by `git archive <sha>` (main or the head); <scratch> an empty folder for the workspace.
level is the folder that swaps: 'x' (.wuwei/verdicts/x, the default) or 'verdicts' (.wuwei/verdicts).
It prints one JSON line: how many copy-ins ran, how many files appeared in or changed under .wuwei/ledger,
the outcome counts, and any exception that escaped the hook (a hole: the hook would fail open).
"""

import ctypes
import json
import multiprocessing
import os
import random
from pathlib import Path
import sys
import time


def swap(folder, ledger, stop, swaps):
    """Folder and a link into the ledger trade places atomically (renameat2 RENAME_EXCHANGE), so the name always exists
    and is a folder or a link, each state held for 0 to 200 microseconds."""
    libc = ctypes.CDLL(None, use_errno=True)
    link = folder.with_name(folder.name + '.link')
    os.symlink(ledger, link)
    while not stop.is_set():
        if libc.renameat2(-100, bytes(folder), -100, bytes(link), 2) != 0:  # AT_FDCWD, RENAME_EXCHANGE
            raise OSError(ctypes.get_errno(), 'renameat2')
        swaps.value += 1
        time.sleep(random.random() * 2e-4)
    if folder.is_symlink():  # leave the folder in place
        libc.renameat2(-100, bytes(folder), -100, bytes(link), 2)


def snapshot(ledger):
    return {p.relative_to(ledger).as_posix(): p.read_bytes() for p in ledger.rglob('*') if p.is_file()}


def main():
    tree, scratch = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    runs, level = int(sys.argv[3]) if len(sys.argv) > 3 else 2000, sys.argv[4] if len(sys.argv) > 4 else 'x'
    sys.path.insert(0, str(tree / 'cli'))
    from wuwei import hook, ws
    root, worktree = scratch / 'ws', scratch / 'wt'
    (root / ws.DIR).mkdir(parents=True)
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
    ws.record(root, 'plan.pass', {})
    ledger = root / ws.DIR / 'ledger'
    (root / ws.DIR / 'verdicts' / 'x').mkdir(parents=True)
    (worktree / ws.DIR / 'verdicts' / 'x').mkdir(parents=True)
    before = snapshot(ledger)
    folder = root / ws.DIR / 'verdicts' / 'x' if level == 'x' else root / ws.DIR / 'verdicts'
    stop = multiprocessing.Event()
    swaps = multiprocessing.Value('l', 0)
    swapper = multiprocessing.Process(target=swap, args=(folder, ledger, stop, swaps))
    swapper.start()
    outcomes, escaped = {}, {}
    try:
        for i in range(runs):
            written = worktree / ws.DIR / 'verdicts' / 'x' / f'quality-{i:07x}.md'  # a stem of its own, so the next free name is found at once
            written.write_text(f'not a verdict {i}\n')
            payload = {'agent_id': 'probe', 'last_assistant_message': f'Verdict file: {written}'}
            try:
                out = hook._verdict_problem(root, payload, 'sentinel-quality')
            except Exception as exc:  # what the hook's handler would turn into hook.error and fail open
                escaped[type(exc).__name__] = escaped.get(type(exc).__name__, 0) + 1
                continue
            key = 'none' if out is None else out.split(':')[0] if 'symlink on the way' not in out else 'symlink on the way'
            key = 'readable-file refusal' if out and out.startswith('the verdict must be a readable') else key
            key = 'shape refusal (copied in)' if out and out.startswith('the verdict does not hold') else key
            outcomes[key] = outcomes.get(key, 0) + 1
    finally:
        stop.set()
        swapper.join()
    after = snapshot(ledger)
    changed = sorted(n for n in after.keys() | before.keys() if after.get(n) != before.get(n))
    print(json.dumps({'tree': tree.name, 'python': sys.version.split()[0], 'level': level, 'runs': runs, 'swaps': swaps.value,
                      'ledger_files_changed': len(changed), 'changed_sample': changed[:5], 'outcomes': outcomes,
                      'escaped': escaped}))


if __name__ == '__main__':
    main()
