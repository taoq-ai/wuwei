"""Mutants of each new condition, applied to cli/wuwei/ and .claude/wuwei/cli/wuwei/ in a scratch copy, run one at a time.

    python3 specs/ready-door-exception/mutants.py <scratch copy of the tree>

Mutant 8 (a "verdict " gap without the " not counted: " check) is equivalent: only evidence.uncounted prints a gap
that starts "verdict ".
"""
import subprocess, sys
from pathlib import Path
T = Path(sys.argv[1])
M = [
 ('guards.py', "found = evidence.excepted(root, ref, head, found) if ref else found", "found = found"),
 ('guards.py', "pr['body'], READY, f'{repo}#{number}')", "pr['body'], READY, '')"),
 ('guards.py', "pr['body'], READY, f'{repo}#{number}')", "pr['body'], READY, f'{repo}#{number + 1}')"),
 ('guards.py', "found = evidence.excepted(root, ref, head, found) if ref", "found = evidence.excepted(root, ref, 'a' * 40, found) if ref"),
 ('evidence.py', "gone = any(GATES.match(g['text']) for g in found if g not in kept)", "gone = False"),
 ('evidence.py', "gone = any(GATES.match(g['text']) for g in found if g not in kept)", "gone = any(True for g in found if g not in kept)"),
 ('evidence.py', "return [g for g in kept if not (gone and g['text'].startswith('verdict ') and ' not counted: ' in g['text'])]", "return [g for g in kept if not gone]"),
 ('evidence.py', "return [g for g in kept if not (gone and g['text'].startswith('verdict ') and ' not counted: ' in g['text'])]", "return [g for g in kept if not (gone and ' not counted: ' in g['text'])]"),
 ('evidence.py', "return [g for g in kept if not (gone and g['text'].startswith('verdict ') and ' not counted: ' in g['text'])]", "return [g for g in kept if not (gone and g['text'].startswith('verdict '))]"),
]
for i, (f, old, new) in enumerate(M):
    paths = [T / 'cli/wuwei' / f, T / '.claude/wuwei/cli/wuwei' / f]
    saved = [p.read_text() for p in paths]
    assert all(s.count(old) == 1 for s in saved), (i, f)
    for p, s in zip(paths, saved): p.write_text(s.replace(old, new))
    r = subprocess.run(['uv', 'run', '--no-project', '--with', 'pytest', '--python', '3.13', 'python', '-m', 'pytest', '-q', '-x',
                        '-p', 'no:cacheprovider', 'tests/test_guards.py', 'tests/test_evidence.py'], cwd=T, capture_output=True, text=True)
    for p, s in zip(paths, saved): p.write_text(s)
    fails = [l for l in r.stdout.splitlines() if l.startswith('FAILED')]
    print(i, f, 'KILLED' if r.returncode else 'SURVIVED', fails[:1], r.stdout.strip().splitlines()[-1])
