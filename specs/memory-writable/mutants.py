"""usage: python3 -I mutants.py <scratch> <worktree> [mutant name ...]; <scratch>/pt.sh runs pytest -q in $WT.
Apply each mutant to both guards.py copies in a fresh git archive of HEAD, run tests/test_guards.py, report killed or survived."""
import shutil
import subprocess
import sys
from pathlib import Path

S = Path(sys.argv[1])
WT = sys.argv[2]
MUTANTS = {
    'keep for every writer': ("keep=program in ('tee', 'sed', 'truncate', 'rm')", 'keep=True'),
    'lexical path, links not read': ('real := Path(realpath(full))', 'real := Path(normpath(full))'),
    'no literal check': ("re.fullmatch(r'/[\\w./@+-]*', full)", 'full'),
    'any memory segment': (".parent.name == 'memory'", ".parts.count('memory') > 0"),
    'any projects folder': ('real.parent.parent.parent == Path(realpath(ws.PROJECTS))', 'True'),
    'no HOME spelling': ("r'^(~|\\$HOME|\\$\\{HOME\\})(?=/)'", "r'^(~)(?=/)'"),
    'Edit without keep': ('deny(HARNESS) if any(harness(p, keep=True) for p in paths)', 'deny(HARNESS) if any(harness(p) for p in paths)'),
    'redirect without keep': ('any(harness(t, keep=True) for t in targets)', 'any(harness(t) for t in targets)'),
    'held with keep': ('harness(cwd) or any(harness(w, 64) for w in wd)', 'harness(cwd, keep=True) or any(harness(w, 64, True) for w in wd)'),
    'cd with keep': ("any(map(harness, argv[1:]))", "any(harness(a, keep=True) for a in argv[1:])"),
}
for name, (old, new) in [m for m in MUTANTS.items() if not sys.argv[3:] or m[0] in sys.argv[3:]]:
    tree = S / 'mutant'
    shutil.rmtree(tree, ignore_errors=True)
    tree.mkdir(parents=True)
    subprocess.run(f'git -C {WT} archive HEAD | tar -x -C {tree}', shell=True, check=True)
    for rel in ('cli/wuwei/guards.py', '.claude/wuwei/cli/wuwei/guards.py'):
        p = tree / rel
        text = p.read_text()
        assert text.count(old) == 1, (name, rel)
        p.write_text(text.replace(old, new))
    r = subprocess.run([str(S / 'pt.sh'), 'tests/test_guards.py', '-p', 'no:cacheprovider'], env={**__import__('os').environ, 'WT': str(tree)},
                       capture_output=True, text=True)
    last = r.stdout.strip().splitlines()[-1]
    failed = [l.split('::', 1)[1][:90] for l in r.stdout.splitlines() if l.startswith('FAILED')]
    base = {'each_refused_shape'}
    real = [f for f in failed if not any(b in f for b in base)]
    print(f'{name}: {"KILLED" if real else "SURVIVED"} ({len(real)} behavioural failures) {last}')
    for f in real[:3]:
        print('   ', f)
shutil.rmtree(S / 'mutant', ignore_errors=True)
