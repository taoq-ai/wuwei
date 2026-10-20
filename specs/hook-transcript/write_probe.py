"""hook-transcript probe: writes under the harness projects folder, run for real under bash and read by the guards.

Usage: python3 -I specs/hook-transcript/write_probe.py <tree> <empty scratch folder>

<tree> is a `git archive` copy whose cli/ is imported (main or the head). Each generated command runs under real bash with
HOME set to a scratch home holding .claude/projects/-repo/s.jsonl, from a case folder below the scratch folder. A command
"lands" when the projects folder differs afterwards (a file added, removed, linked or changed). A hole is a command that
lands and that guards.bash passes. Reads are a class of their own: they must pass and land nothing.
"""

import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TREE, SCRATCH = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(TREE / 'cli'))
from wuwei import guards  # noqa: E402

HOME = SCRATCH / 'home'
PATHS = ['~/.claude/projects/-repo/s.jsonl', '$HOME/.claude/projects/-repo/s.jsonl', '"$HOME"/.claude/projects/-repo/s.jsonl',
         f'{HOME}/.claude/projects/-repo/s.jsonl', '~//.claude//projects//-repo/s.jsonl', '~/./.claude/./projects/./-repo/s.jsonl',
         '~/x/../.claude/projects/-repo/s.jsonl', '~/.claude/x/../projects/-repo/s.jsonl', '~/.c*/projects/-repo/s.jsonl',
         '~/.claude/proj*/-repo/s.jsonl', '~/.claude/pro[j]ects/-repo/s.jsonl', '~/.claude/{projects,y}/-repo/s.jsonl',
         '~/.claude%2Fprojects/-repo/s.jsonl', '~/.claude/projects/-repo/n.jsonl', '~/.claude/projects']
WRITES = ['echo x >> {p}', 'printf x > {p}', 'echo x | tee -a {p}', 'cp ~/src.jsonl {p}', 'dd if=/dev/zero of={p} bs=1 count=1 2>/dev/null',
          'sed -i s/a/b/ {p}', 'truncate -s 0 {p}', 'rm -rf {p}', 'mv ~/src.jsonl {p}', 'ln -sf ~/src.jsonl {p}', 'find {p} -delete',
          'python3 -c "open(\'{p}\', \'a\').write(\'x\')"']
WRAP = ['{w}', 'cd ~ && {w}', 'env A=1 {w}', 'true; {w}', 'nice -n 1 {w}', 'timeout 5 {w}', 'if true; then {w}; fi', '{{ {w}; }}']
DIRS = ['cd ~/.claude/projects/-repo && {w}', 'cd ~/.claude && cd projects/-repo && {w}', 'pushd ~/.claude/projects/-repo > /dev/null && {w}',
        'env -C ~/.claude/projects/-repo {w}', 'env --chdir=$HOME/.claude/projects/-repo {w}', '(cd ~/.claude/projects/-repo; {w})',
        'cd ~/.claude//projects/./-repo && {w}', 'cd ~/x/../.claude/projects/-repo && {w}']
LOCAL = ['echo x >> s.jsonl', 'printf x > s.jsonl', 'echo x | tee -a s.jsonl', 'cp ~/src.jsonl s.jsonl', 'rm -f s.jsonl',
         'sed -i s/a/b/ s.jsonl', 'python3 -c "open(\'s.jsonl\', \'a\').write(\'x\')"']
READS = ['cat {p}', 'grep -c a {p}', 'python3 - < {p}', 'wc -l < {p}', 'tail -n 1 {p} > ~/copy.jsonl', 'cat {p} | python3 -c "import sys"']
if shutil.which('sudo'):
    DIRS.append('sudo -D ~/.claude/projects/-repo {w}')


def state():
    found = []
    for path in sorted((HOME / '.claude' / 'projects').rglob('*')):
        found.append((str(path.relative_to(HOME)), path.is_symlink(), path.read_bytes() if path.is_file() else b''))
    return hashlib.sha256(repr(found).encode()).hexdigest()


def reset():
    shutil.rmtree(HOME, ignore_errors=True)
    for folder in ('.claude/projects/-repo', '.claude/x', 'x'):
        (HOME / folder).mkdir(parents=True, exist_ok=True)
    (HOME / '.claude' / 'projects' / '-repo' / 's.jsonl').write_text('a\n')
    (HOME / 'src.jsonl').write_text('forged\n')


def main():
    if any(SCRATCH.iterdir()):
        raise SystemExit(f'{SCRATCH} is not empty')
    case = SCRATCH / 'case'
    case.mkdir()
    (case / '.wuwei').mkdir()
    reset()
    clean = state()
    commands = [(x.format(w=w.format(p=p)), 'write') for w, p, x in itertools.product(WRITES, PATHS, WRAP)]
    commands += [(d.format(w=w), 'write') for d, w in itertools.product(DIRS, LOCAL)]
    commands += [(r.format(p=p), 'read') for r, p in itertools.product(READS, PATHS[:4])]
    counts, holes, refused_reads = {'generated': len(commands), 'landed': 0, 'refused': 0}, [], []
    for command, kind in commands:
        reset()
        subprocess.run(['bash', '-c', command], cwd=case, env={**os.environ, 'HOME': str(HOME)}, capture_output=True, timeout=20)
        landed = state() != clean
        refused = (guards.bash(case, command, str(case), 's1') or {}).get('decision') == 'deny'
        counts['landed'] += landed
        counts['refused'] += refused
        if landed and not refused:
            holes.append(command)
        if kind == 'read' and (refused or landed):
            refused_reads.append(command)
    print(json.dumps({**counts, 'holes': len(holes), 'hole_commands': holes, 'reads_refused_or_landed': refused_reads}, indent=1))


if __name__ == '__main__':
    main()
