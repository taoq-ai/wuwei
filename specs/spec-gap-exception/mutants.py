"""Mutants of each changed condition, applied to cli/wuwei/ and .claude/wuwei/cli/wuwei/ in a scratch copy, run one at a time.

    python3 specs/spec-gap-exception/mutants.py <scratch copy of the tree>
"""
import subprocess
import sys
from pathlib import Path

T = Path(sys.argv[1])
SEP = r"re.split(r'\.\s|\?', tail[cut:], maxsplit=1)[0]"
CUT = "tail[:(cut := tail.rfind('|') + 1 if ': |' in tail else 0)]"
PROCESS = 'r"template\'s sections|changed lines|open [0-9]+ days"'
CELL = 'row[:row.rfind("|", 1, 100) + 1] or row[:100] if len(row) > 100 else row'
LISTED = ("        return [_unchecked(e['path'], gh.file(repo, e['path'], head)) for e in entries\n"
          "                if rule == 'checked' and e.get('type') == 'file' and e['name'].endswith('.md')]")
M = [
    ('guards.py', PROCESS, 'r"specs/|openspec/|no spec in the diff|template\'s sections|changed lines|open [0-9]+ days"'),
    ('guards.py', PROCESS, 'r"changed lines|open [0-9]+ days"'),
    ('guards.py', PROCESS, 'r"template\'s sections|open [0-9]+ days"'),
    ('guards.py', PROCESS, 'r"template\'s sections|changed lines"'),
    ('guards.py', PROCESS, 'r"specs/|template\'s sections|changed lines|open [0-9]+ days"'),
    ('guards.py', PROCESS, 'r"no spec in the diff|template\'s sections|changed lines|open [0-9]+ days"'),
    ('hook.py', CUT, "tail[:(cut := tail.rfind('|') + 1)]"),  # round 1: every gap reads to its last |
    ('hook.py', CUT, "tail[:(cut := tail.rfind('|') + 1 if '|' in tail else 0)]"),
    ('hook.py', CUT, "tail[:(cut := tail.rfind('|') + 1 if ': |' not in tail else 0)]"),
    ('hook.py', CUT, "tail[:(cut := tail.rfind('|') + 1 if ': |' in tail else len(tail))]"),
    ('hook.py', CUT, "tail[:(cut := 0)]"),
    ('hook.py', CUT, "tail[:(cut := tail.find('|') + 1 if ': |' in tail else 0)]"),
    ('hook.py', CUT, "tail[:(cut := tail.rfind('|') if ': |' in tail else 0)]"),
    ('hook.py', SEP, "tail[cut:]"),
    ('hook.py', SEP, r"re.split(r'\.\s', tail[cut:], maxsplit=1)[0]"),
    ('hook.py', SEP, r"re.split(r'\?', tail[cut:], maxsplit=1)[0]"),
    ('evidence.py', '    return found\n', '    return found[:1]\n'),  # main: only the first open row
    ('evidence.py', LISTED, LISTED.replace('return [_unchecked', 'return [p for p in [_unchecked') + ' if p][:1]'),  # main: first checklist
    ('evidence.py', 'for problem in _rule(repo, feature + name, rule, head))', 'for problem in _rule(repo, feature + name, rule, head)[:1])'),
    ('evidence.py', CELL, 'row[:100]'),  # main: cut at 100 characters
    ('evidence.py', CELL, 'row[:row.rfind("|", 1, 100) + 1] if len(row) > 100 else row'),
    ('evidence.py', CELL, CELL.replace('rfind("|", 1, 100)', 'rfind("|", 0, 100)')),
    ('evidence.py', CELL, CELL.replace('rfind("|", 1, 100)', 'rfind("|", 1, 101)')),
    ('evidence.py', CELL, CELL.replace('len(row) > 100', 'len(row) >= 100')),
    ('evidence.py', CELL, 'row'),  # whole rows
]
TESTS = ['tests/test_guards.py', 'tests/test_hook.py', 'tests/test_evidence.py']
for i, (f, old, new) in enumerate(M):
    paths = [T / 'cli/wuwei' / f, T / '.claude/wuwei/cli/wuwei' / f]
    saved = [p.read_text() for p in paths]
    assert all(s.count(old) == 1 for s in saved), (i, f)
    for p, s in zip(paths, saved):
        p.write_text(s.replace(old, new))
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', *TESTS, *sys.argv[2:]], cwd=T,
                       capture_output=True, text=True)
    for p, s in zip(paths, saved):
        p.write_text(s)
    fails = [line for line in r.stdout.splitlines() if line.startswith('FAILED')]
    print(i, f, 'KILLED' if r.returncode else 'SURVIVED', fails[:1], r.stdout.strip().splitlines()[-1], flush=True)
