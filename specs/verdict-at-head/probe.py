"""Main-versus-head probe of evidence.gate_gaps over generated verdict histories.

Usage: PROBE_TMP=<scratch folder> python3 -I probe.py <main tree> <head tree> [<moves file>]

Each tree is a checkout of this repository. The probe runs gate_gaps from each tree in its own
process with a fake code host, over every history it generates, and lists each case whose gate
result moves. It also checks two properties at each tree and counts their holes:

- ignored: a verdict that is not at an ancestor of the PR head, or a PASS not for this PR (for
  this repository when no PR is read), never changes the result;
- no-clear: a PASS at the same or an older head than a counted FIX of its gate, appended to a
  history that owes the gate, leaves the gate owed.
"""

import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO, REF = 'acme/app', 'acme/app#42'
OLD, MID, HEAD, NEW, OTHER = ('b' * 40, 'd' * 40, 'a' * 40, 'e' * 40, 'c' * 40)
NAMES = {OLD: 'old', MID: 'mid', HEAD: 'head', NEW: 'new', OTHER: 'other'}
# strict ancestry: OLD < MID < HEAD < NEW on the PR's line; OTHER grew from OLD off it
STRICT = {(OLD, MID), (OLD, HEAD), (MID, HEAD), (OLD, NEW), (MID, NEW), (HEAD, NEW), (OLD, OTHER)}
PRS = ('this', 'other-pr', 'other-repo', 'repo-only', 'imported')
PR_TEXT = {'this': REF, 'other-pr': 'acme/app#7', 'other-repo': 'acme/other#42', 'repo-only': REPO}
DELTAS = {'small': 10, 'big': 300}  # lines of src/app.py from a pass to the head


def ancestor(older, newer):
    return older[:7] == newer[:7] or any(o.startswith(older[:7]) and n.startswith(newer[:7]) for o, n in STRICT)


def histories():
    """(gates, history) pairs; an atom is (gate, verdict, head, pr form)."""
    two = list(itertools.product(('quality', 'arch'), ('PASS', 'FIX'), NAMES, PRS))
    three = list(itertools.product(('quality',), ('PASS', 'FIX'), (OLD, MID, HEAD, OTHER), ('this', 'other-pr')))
    for n in (1, 2):
        for h in itertools.product(two, repeat=n):
            yield ('arch', 'quality'), h
    for h in itertools.product(three, repeat=3):
        yield ('quality',), h


def counted(atom, ref):
    """The rule under test: at an ancestor of the PR head, and a PASS for this PR (this repository with no PR read)."""
    gate, verdict, head, pr = atom
    on = verdict != 'PASS' or pr in ('this', 'repo-only', 'imported') or not ref and pr == 'other-pr'
    return on and ancestor(head, HEAD)


def run_tree(tree):
    sys.path.insert(0, str(Path(tree) / 'cli'))
    from wuwei import evidence, gh, ws
    calls = []

    def fake(args, timeout=30):
        calls.append(args)
        path = args[1]
        if args[0] == 'api' and '/compare/' in path:
            older, newer = path.split('/compare/')[1].split('...')
            status = 'identical' if older[:7] == newer[:7] else 'ahead' if ancestor(older, newer) else 'diverged'
            return {'status': status, 'files': [{'filename': 'src/app.py', 'additions': fake.lines, 'deletions': 0}]}
        raise AssertionError(f'unexpected gh call {args}')

    gh.run = fake
    base = Path(tempfile.mkdtemp(prefix='probe-', dir=os.environ.get('PROBE_TMP')))

    def read(gates, history, ref, delta):
        root = Path(tempfile.mkdtemp(dir=base))
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': [REPO], 'owner_paths': []})
        for n, (gate, verdict, head, pr) in enumerate(history):
            path = root / ws.DIR / 'verdicts' / 'I-1' / f'{gate}-{n}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            said = 'Breaking: no\n' if gate == 'arch' else ''
            path.write_text(f'Verdict: {verdict}\nGate: {gate}\nItem: I-1\nPR: {PR_TEXT.get(pr, REF)}\nHead: {head}\n'
                            f'Confidence: high\n{said}\n## Findings\nnone\n')
            row = {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'gate': gate, 'item': 'I-1', 'head': head, 'verdict': verdict}
            if pr == 'imported':  # a 0.34 verdict: a short head and no PR
                row.update(imported=True, head=head[:7])
            else:
                row['pr'] = PR_TEXT[pr]
            ws.record(root, 'attest', row)
        fake.lines, before = DELTAS[delta], len(calls)
        try:
            found = [g['text'] for g in evidence.gate_gaps(root, REPO, 'I-1', gates, HEAD, ref=ref)]
        except Exception as exc:  # noqa: BLE001  the probe reports any raise as a result
            found = [f'raised {type(exc).__name__}: {exc}']
        shutil.rmtree(root)
        return found, len(calls) - before

    def owes(found, gate):
        return any(t.startswith('gates missing') and gate in t.split(': ', 1)[1].split(', ') for t in found)

    out, holes = {}, {'ignored': [], 'no-clear': []}
    for gates, history in histories():
        for ref in (REF, ''):
            for delta in DELTAS:
                if len(history) == 3 and delta == 'small':
                    continue
                key = json.dumps([gates, [[g, v, NAMES[h], p] for g, v, h, p in history], ref, delta])
                found, cost = read(gates, history, ref, delta)
                out[key] = {'found': found, 'calls': cost}
                kept = tuple(a for a in history if counted(a, ref))
                if kept != history and read(gates, kept, ref, delta)[0] != found:
                    holes['ignored'].append(key)
                gate, verdict, head, _ = last = history[-1]
                prefix = history[:-1]
                fixed = any(a[0] == gate and a[1] == 'FIX' and counted(a, ref) and ancestor(head, a[2]) for a in prefix)
                if verdict == 'PASS' and counted(last, ref) and fixed and not owes(found, gate) \
                        and owes(read(gates, prefix, ref, delta)[0], gate):
                    holes['no-clear'].append(key)
    shutil.rmtree(base)
    json.dump({'results': out, 'holes': holes}, sys.stdout)


def main(main_tree, head_tree, moves_file=None):
    def owed(found):
        """The gates a result owes; a delta review counts as owed only when no gate is named missing."""
        named = {g for t in found if t.startswith('gates missing') for g in t.split(': ', 1)[1].split(', ')}
        return named or {t for t in found if t.startswith('no gate passed')} and {'delta'}

    runs = [subprocess.Popen([sys.executable, '-I', __file__, '--run', tree], stdout=subprocess.PIPE, text=True)
            for tree in (main_tree, head_tree)]  # both trees at once
    old, new = (json.loads(run.communicate()[0]) for run in runs)
    if any(run.returncode for run in runs):
        sys.exit('a tree run failed')
    moved = [k for k in new['results'] if old['results'][k]['found'] != new['results'][k]['found']]
    lines = [f'{k}\n  main: {old["results"][k]["found"]}\n  head: {new["results"][k]["found"]}' for k in moved]
    print(f'cases generated: {len(new["results"])}')
    print(f'cases whose gate result moves: {len(moved)}')
    classes, looser = {}, set()
    for k in moved:
        _, history, ref, _ = json.loads(k)
        before, after = owed(old['results'][k]['found']), owed(new['results'][k]['found'])
        way = 'head owes less' if before - after - {'delta'} or before == {'delta'} and not after else \
            'head owes more' if after - before else 'same gates, other text'
        cause = 'a PASS for another PR or repository' if any(
            v == 'PASS' and (p == 'other-repo' or p == 'other-pr' and ref) for _, v, _, p in history) else 'the walk'
        classes[(way, cause)] = classes.get((way, cause), 0) + 1
        if (way, cause) == ('head owes less', 'the walk'):
            looser.add(tuple((g, v, h) for g, v, h, _ in history))
    for (way, cause), n in sorted(classes.items()):
        print(f'  {n}: {way}, from {cause}')
    print(f'distinct verdict shapes where the walk owes less: {len(looser)}; each holds a PASS at the head '
          f'attested before the last verdict: {all(("PASS", "head") in {(v, h) for _, v, h in s[:-1]} for s in looser)}')
    for name, data in (('main', old), ('head', new)):
        calls = sum(r['calls'] for r in data['results'].values())
        print(f'{name}: ignored holes {len(data["holes"]["ignored"])}, no-clear holes {len(data["holes"]["no-clear"])}, '
              f'compare calls {calls}')
    for hole in new['holes']['ignored'] + new['holes']['no-clear']:
        print('head hole:', hole)
    if moves_file:
        Path(moves_file).write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    if sys.argv[1] == '--run':
        run_tree(sys.argv[2])
    else:
        main(*sys.argv[1:])
