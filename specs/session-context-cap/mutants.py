"""Mutants of hook.session_start for session-context-cap. Each runs in a fresh `git archive` copy of the
given commit under <scratch>, applies one textual change to cli/wuwei/hook.py and to its vendored copy
under .claude/, and runs the four test files that hold it. A mutant that no test fails is a hole; a
kill counts only when a test fails, not on a collection error or a timeout.
    python -I specs/session-context-cap/mutants.py <repo> <sha> <scratch> <pytest>
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

COND = "len('\\n\\n'.join(parts + ['\\n'.join(lines + left(cut))])) >= SESSION_CAP"
MUTANTS = {
    'L1 >= CAP to > CAP': (COND, COND.replace('>= SESSION_CAP', '> SESSION_CAP')),
    'L2 >= CAP to >= CAP - 1': (COND, COND.replace('>= SESSION_CAP', '>= SESSION_CAP - 1')),
    'L3 >= CAP to >= CAP + 1': (COND, COND.replace('>= SESSION_CAP', '>= SESSION_CAP + 1')),
    'L4 >= CAP to > CAP - 1 (equivalent on integers)': (COND, COND.replace('>= SESSION_CAP', '> SESSION_CAP - 1')),
    'L5 cap 10001': ('SESSION_CAP = 10000', 'SESSION_CAP = 10001'),
    'L6 cap 9999': ('SESSION_CAP = 10000', 'SESSION_CAP = 9999'),
    'L7 measure without the left-out line': (COND, COND.replace('lines + left(cut)', 'lines')),
    'L8 measure with the next count': (COND, COND.replace('left(cut)', 'left(cut + 1)')),
    'L9 measure with one join newline': (COND, COND.replace("'\\n\\n'.join(parts", "'\\n'.join(parts")),
    'D1 drop one line, not the whole item': ('lines[:at[-1]]', 'lines[:-1]'),
    'D2 drop the first item': ('lines[:at[-1]]', 'lines[:at[0]]'),
    'D3 any line starting with a dash is an item': ('x.startswith(items)', "x.startswith('- ')"),
    'D4 the item shape without its ids': ('for row in found)', "for row in found) and ('- ',)"),
    'D5 the item id without its space': ("f'- {row[\"item\"]} '", "f'- {row[\"item\"]}'"),
    'D6 no item guard': ('(at := [n for n, x in enumerate(lines) if x.startswith(items)])',
                         '((at := [n for n, x in enumerate(lines) if x.startswith(items)]) or True)'),
    'C1 no final cut': ("'\\n\\n'.join(parts)[:SESSION_CAP])", "'\\n\\n'.join(parts))"),
    'C2 final cut at CAP - 1': ("'\\n\\n'.join(parts)[:SESSION_CAP])", "'\\n\\n'.join(parts)[:SESSION_CAP - 1])"),
    'W1 always plural': ('"s" if cut > 1 else ""', '"s" if cut > 0 else ""'),
    'W2 plural from three': ('"s" if cut > 1 else ""', '"s" if cut > 2 else ""'),
    'W3 left-out line from two': ('* (cut > 0)', '* (cut > 1)'),
    'W4 left-out line at zero': ('* (cut > 0)', '* (cut >= 0)'),
    'R1 Done left out': ('(?:Decisions|Done)', '(?:Decisions)'),
    'R2 no planner.md path': ('your charter {charters / "planner.md"}, ', ''),
    'R3 no way': ("read('_way.md').strip(), ", ''),
    'R4 no CLI line': ("f'WUWEI CLI: {cli} (call it by this path; it is not on PATH)', ", ''),
    'R5 board before the rules': ("parts.append('\\n'.join(lines + left(cut)))", "parts.insert(1, '\\n'.join(lines + left(cut)))"),
}
repo, sha, scratch, pytest = sys.argv[1:5]
holes = 0
for name, (old, new) in MUTANTS.items():
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        archive = subprocess.run(['git', '-C', repo, 'archive', sha], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', folder], input=archive, check=True)
        for hook in (Path(folder) / 'cli' / 'wuwei' / 'hook.py', Path(folder) / '.claude' / 'wuwei' / 'cli' / 'wuwei' / 'hook.py'):
            text = hook.read_text(encoding='utf-8')
            assert text.count(old) == 1, (name, old)
            hook.write_text(text.replace(old, new), encoding='utf-8')
        run = subprocess.run([pytest, '-q', '-p', 'no:cacheprovider', 'tests/test_charters.py', 'tests/test_hook.py',
                              'tests/test_codex.py', 'tests/test_setup.py'], cwd=folder, capture_output=True, text=True)
        failed = re.findall(r'^FAILED (\S+)', run.stdout, re.M)
        sweep = sum('board_fills' in test for test in failed)
        holes += not failed
        print(f"{name}: {'killed' if failed else 'HOLE'}, sweep points failed {sweep} of 80, other tests failed "
              f"{len(failed) - sweep} ({run.stdout.strip().splitlines()[-1]})")
print(f'{len(MUTANTS)} mutants, {len(MUTANTS) - holes} killed, {holes} holes')
