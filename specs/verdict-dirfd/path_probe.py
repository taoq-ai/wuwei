"""verdict-dirfd path probe: a link at every name the copy-in walks or creates, and one handed-back path per path class.

    python3 path_probe.py <tree> <scratch>

<tree> is a tree made by `git archive <sha>`; <scratch> an empty folder. For each case it builds a fresh workspace and a
worktree verdict, plants the case, and runs SubagentStop with stop_hook_active set (a refusal is then recorded as
verdict.missing). It prints one JSON object: case -> outcome (attest, verdict.missing or hook.error), whether any ledger
file changed other than by its own appended rows, whether the ledger chain still verifies, and whether a file outside
the workspace changed. Links point into the ledger (folders at the ledger folder, files at the ledger file) or at
themselves (a loop).
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(sys.argv[1]).resolve() / 'cli'))
from wuwei import hook, ws  # noqa: E402

VERDICT = ('Verdict: PASS\nGate: quality\nItem: I-1\nPR: acme/app#42\nHead: 0123456789abcdef0123456789abcdef01234567\n'
           'Confidence: high\n\n## Findings\nnone\n')
NAMES = {'verdicts': 'verdicts', 'folder': 'verdicts/x', 'final': 'verdicts/x/quality-abc1234.md',
         'temp': 'verdicts/x/.quality-abc1234.md.{pid}.{tid}.tmp'}
CLASSES = {'plain': '{wt}/.wuwei/verdicts/x/quality-abc1234.md', 'double-slash': '{wt}//.wuwei//verdicts//x//quality-abc1234.md',
           'percent': '{wt}/.wuwei/verdicts/x/quality%2Dabc1234.md', 'dot': '{wt}/./.wuwei/./verdicts/./x/./quality-abc1234.md',
           'dotdot': '{wt}/.wuwei/verdicts/x/../x/quality-abc1234.md'}


def ledger_state(root):
    return {p.name: p.read_bytes() for p in (root / ws.DIR / 'ledger').rglob('*') if p.is_file()}


def run(scratch, case, plant, handed):
    base = scratch / case
    root, worktree, outside = base / 'ws', base / 'wt', base / 'outside'
    (root / ws.DIR).mkdir(parents=True)
    outside.mkdir()
    (outside / 'held.md').write_text('outside\n')
    ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
    ws.record(root, 'plan.pass', {})
    (worktree / ws.DIR / 'verdicts' / 'x').mkdir(parents=True)
    (worktree / ws.DIR / 'verdicts' / 'x' / 'quality-abc1234.md').write_text(VERDICT)
    ledger = root / ws.DIR / 'ledger'
    journal = next(ledger.glob('*.jsonl'))
    if plant:
        name, aim = plant
        link = root / ws.DIR / NAMES[name].format(pid=4242, tid=7)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(link if aim == 'loop' else ledger if name in ('verdicts', 'folder') else journal)
    before = ledger_state(root)
    out = hook.handle(root, 'SubagentStop', {'session_id': 's1', 'agent_id': 'probe', 'agent_type': 'wuwei:sentinel-quality',
                                             'stop_hook_active': True, 'cwd': str(root),
                                             'last_assistant_message': 'Verdict file: ' + handed.format(wt=worktree)})
    after = ledger_state(root)
    kinds = [r['kind'] for r in ws.ledger(root)]
    return {'outcome': next((k for k in ('attest', 'verdict.missing', 'hook.error') if k in kinds), str(out)),
            'ledger_rewritten': after.keys() != before.keys() or any(not after[n].startswith(before[n]) for n in before),
            'chain_ok': ws.verify(root) == [], 'outside_changed': (outside / 'held.md').read_text() != 'outside\n'}


def main():
    scratch = Path(sys.argv[2]).resolve()
    kept = ws.os.getpid, ws.threading.get_ident
    ws.os.getpid, ws.threading.get_ident = (lambda: 4242), (lambda: 7)  # the temporary name the 'temp' case plants
    try:
        rows = {'no link': run(scratch, 'none', None, CLASSES['plain'])}
        for name in NAMES:
            for aim in ('ledger', 'loop'):
                rows[f'link at {name} -> {aim}'] = run(scratch, f'{name}-{aim}', (name, aim), CLASSES['plain'])
        for label, handed in CLASSES.items():
            rows[f'path class {label}'] = run(scratch, f'class-{label}', None, handed)
    finally:  # interpreter shutdown needs the real thread id
        ws.os.getpid, ws.threading.get_ident = kept
    print(json.dumps({'python': sys.version.split()[0], 'rows': rows}, indent=1))


if __name__ == '__main__':
    main()
