"""verdict-closed mutants: python3 mutants.py <sha> <scratch dir>. Each mutant runs in a fresh `git archive` copy."""

import subprocess
import sys
from pathlib import Path

MUTANTS = {
    'M1 count from 1': ('cli/wuwei/hook.py', 'range(2, 999)', 'range(1, 999)'),
    'M2 no stem strip': ('cli/wuwei/hook.py', "re.sub(r'(?<=[0-9a-f]{7})-[0-9]+$', '', p.stem)", 'p.stem'),
    'M3 a dangling link counts as free': ('cli/wuwei/hook.py', '{q.name for q in p.parent.iterdir()}',
                                          '{q.name for q in p.parent.iterdir() if q.exists()}'),
    'M4 shape refusal names stem-2': ('cli/wuwei/hook.py', "verdict to {free(path)} beside", "verdict to {path.stem}-2.md beside"),
    'M5 copy-in refusal names stem-2': ('cli/wuwei/hook.py', 'beside it as {free(copy)}', 'beside it as {copy.stem}-2.md'),
    'M6 other-seat refusal names stem-2': ('cli/wuwei/hook.py', 'Write yours to {free(path)}', 'Write yours to {path.stem}-2.md'),
    'M7 strip only after 8 hex': ('cli/wuwei/hook.py', '(?<=[0-9a-f]{7})', '(?<=[0-9a-f]{8})'),
    'M8 strip any -digits': ('cli/wuwei/hook.py', "r'(?<=[0-9a-f]{7})-[0-9]+$'", "r'-[0-9]+$'"),
    'M9 rule 6 loses the Probes sentence': ('charters/_gate.md', 'Closed findings go under ## Probes', 'Closed findings go under ## Notes'),
}

sha, scratch = sys.argv[1], Path(sys.argv[2]).resolve()
for name, (path, old, new) in MUTANTS.items():
    tree = scratch / ('mutant-' + name.split()[0])
    subprocess.run(['rm', '-rf', str(tree)], check=True)
    tree.mkdir(parents=True)
    archive = subprocess.run(['git', 'archive', sha], check=True, capture_output=True).stdout
    subprocess.run(['tar', '-x', '-C', str(tree)], input=archive, check=True)
    target = tree / path
    text = target.read_text(encoding='utf-8')
    assert text.count(old) == 1, (name, old)
    target.write_text(text.replace(old, new), encoding='utf-8')
    if path.startswith('charters/'):
        subprocess.run([str(tree / 'bin' / 'wuwei'), 'agents', 'build'], cwd=tree, check=True, capture_output=True)
    run = subprocess.run(['/root/.local/bin/pytest', '-q', '-p', 'no:cacheprovider', 'tests/test_hook.py', 'tests/test_charters.py'],
                         cwd=tree, capture_output=True, text=True)
    failed = sorted({line.split('::')[1].split(' ')[0] for line in run.stdout.splitlines() if line.startswith('FAILED')})
    print(f'{name}: {"killed" if run.returncode else "SURVIVED"} by {len(failed)}: {", ".join(failed)}')
