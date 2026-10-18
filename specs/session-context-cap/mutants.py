"""Mutants of hook.session_start for session-context-cap. Each runs in a fresh `git archive` copy of the
given commit under <scratch>, applies one textual change to cli/wuwei/hook.py, and runs the session
start tests. A mutant that no test fails is a hole.
    python -I specs/session-context-cap/mutants.py <repo> <sha> <scratch> <pytest>
"""

import subprocess
import sys
import tempfile
from pathlib import Path

MUTANTS = {
    'M1 no final cut at 10,000': ("'\\n\\n'.join(parts)[:10000]", "'\\n\\n'.join(parts)"),
    'M2 board room ten times larger': ('> 9900', '> 99000'),
    'M3 Done left out': ('(?:Decisions|Done)', '(?:Decisions)'),
    'M4 no left-out count': ("lines + [f'{cut} more items left out; `wuwei status` lists them all.'] if cut else lines", 'lines'),
    'M5 no planner.md path': ('your charter {charters / "planner.md"}, ', ''),
    'M6 drops from the top': ('lines, cut = lines[:-1], cut + 1', 'lines, cut = lines[1:], cut + 1'),
    'M7 no way': ("read('_way.md').strip(), ", ''),
    'M8 no CLI line': ("f'WUWEI CLI: {cli} (call it by this path; it is not on PATH)', ", ''),
}
repo, sha, scratch, pytest = sys.argv[1:5]
holes = 0
for name, (old, new) in MUTANTS.items():
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        archive = subprocess.run(['git', '-C', repo, 'archive', sha], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', folder], input=archive, check=True)
        hook = Path(folder) / 'cli' / 'wuwei' / 'hook.py'
        text = hook.read_text(encoding='utf-8')
        assert text.count(old) == 1, (name, old)
        hook.write_text(text.replace(old, new), encoding='utf-8')
        run = subprocess.run([pytest, '-q', '-p', 'no:cacheprovider', 'tests/test_charters.py', 'tests/test_hook.py',
                              '-k', 'session_start'], cwd=folder, capture_output=True, text=True)
        last = run.stdout.strip().splitlines()[-1]
        holes += run.returncode == 0
        print(f"{name}: {'HOLE' if run.returncode == 0 else 'killed'} ({last})")
print(f'{len(MUTANTS)} mutants, {len(MUTANTS) - holes} killed, {holes} holes')
