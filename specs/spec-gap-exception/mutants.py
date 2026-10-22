"""Mutants of each changed condition, applied to cli/wuwei/ and .claude/wuwei/cli/wuwei/ in a scratch copy, run one at a time.

    python3 specs/spec-gap-exception/mutants.py <scratch copy of the tree>
"""
import subprocess
import sys
from pathlib import Path

T = Path(sys.argv[1])
SEP = r"re.split(r'\.\s|\?', tail[cut:], maxsplit=1)[0]"
M = [
    ('guards.py', 'r"template\'s sections|changed lines|open [0-9]+ days"', 'r"specs/|openspec/|no spec in the diff|template\'s sections|changed lines|open [0-9]+ days"'),
    ('guards.py', 'r"template\'s sections|changed lines|open [0-9]+ days"', 'r"changed lines|open [0-9]+ days"'),
    ('guards.py', 'r"template\'s sections|changed lines|open [0-9]+ days"', 'r"template\'s sections|open [0-9]+ days"'),
    ('guards.py', 'r"template\'s sections|changed lines|open [0-9]+ days"', 'r"template\'s sections|changed lines"'),
    ('guards.py', 'r"template\'s sections|changed lines|open [0-9]+ days"', 'r"specs/|template\'s sections|changed lines|open [0-9]+ days"'),
    ('guards.py', 'r"template\'s sections|changed lines|open [0-9]+ days"', 'r"no spec in the diff|template\'s sections|changed lines|open [0-9]+ days"'),
    ('hook.py', "tail[:(cut := tail.rfind('|') + 1)]", "tail[:(cut := 0)]"),
    ('hook.py', "tail[:(cut := tail.rfind('|') + 1)]", "tail[:(cut := tail.find('|') + 1)]"),
    ('hook.py', "tail[:(cut := tail.rfind('|') + 1)]", "tail[:(cut := tail.rfind('|'))]"),
    ('hook.py', SEP, "tail[cut:]"),
    ('hook.py', SEP, r"re.split(r'\.\s', tail[cut:], maxsplit=1)[0]"),
    ('hook.py', SEP, r"re.split(r'\?', tail[cut:], maxsplit=1)[0]"),
]
TESTS = ['tests/test_guards.py', 'tests/test_hook.py', 'tests/test_evidence.py']
for i, (f, old, new) in enumerate(M):
    paths = [T / 'cli/wuwei' / f, T / '.claude/wuwei/cli/wuwei' / f]
    saved = [p.read_text() for p in paths]
    assert all(s.count(old) == 1 for s in saved), (i, f)
    for p, s in zip(paths, saved):
        p.write_text(s.replace(old, new))
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', *TESTS], cwd=T, capture_output=True, text=True)
    for p, s in zip(paths, saved):
        p.write_text(s)
    fails = [line for line in r.stdout.splitlines() if line.startswith('FAILED')]
    print(i, f, 'KILLED' if r.returncode else 'SURVIVED', fails[:1], r.stdout.strip().splitlines()[-1])
