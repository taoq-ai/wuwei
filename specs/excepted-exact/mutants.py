"""Mutants of each condition in evidence.excepted, run in a copy of the tree: python3 mutants.py <copy>.
Set PYTEST to the pytest program when it is not on PATH."""
import os
import pathlib
import subprocess
import sys
root = pathlib.Path(sys.argv[1])
f = root / 'cli/wuwei/evidence.py'
orig = f.read_text()
M = {
 'M1 substring both ways': ("    return [g for g in found if not {norm(g['text']), norm((GATES.match(g['text']) or ('', ''))[1])} & accepted]",
       "    return [g for g in found if not any(a in norm(g['text']) or norm(g['text']) in a for a in accepted)]"),
 'M2 keep empty accepted': ("head.startswith(row['data'].get('head') or '-')} - {''}", "head.startswith(row['data'].get('head') or '-')}"),
 'M3 no gate form': ("{norm(g['text']), norm((GATES.match(g['text']) or ('', ''))[1])}", "{norm(g['text'])}"),
 'M4 gate form unanchored': ("norm((GATES.match(g['text'])", "norm((GATES.search(g['text'])"),
 'M5 no casefold': ("' '.join(text.casefold().split())", "' '.join(text.split())"),
 'M6 no [waiting]': (".removesuffix('[waiting]')", ""),
 'M7 no end marks': ("' '.join(text.casefold().split()).rstrip(' .,;:!?')", "' '.join(text.casefold().split())"),
 'M8 no str check': ("if isinstance(row['data'].get('gap'), str)\n                and", "if"),
 'M9 any head': ("and row['data'].get('pr') == ref and head.startswith(row['data'].get('head') or '-')}", "and row['data'].get('pr') == ref}"),
 'M10 gate list takes the rest': ("([\\w, ]+)')  # a gate", "(.+)')  # a gate"),
 'M11 not approved too': ("and row['data'].get('kind') == 'exception' and row['data'].get('approved')", "and row['data'].get('kind') == 'exception'"),
 'M12 any pr': ("and row['data'].get('pr') == ref and head", "and head"),
 'M13 no space collapse': ("' '.join(text.casefold().split())", "text.casefold().strip()"),
}
for name, (a, b) in M.items():
    assert orig.count(a) == 1, name
    f.write_text(orig.replace(a, b))
    r = subprocess.run([os.environ.get('PYTEST', 'pytest'), '-q', '-x', '-p', 'no:cacheprovider', 'tests/test_evidence.py', 'tests/test_report.py'], cwd=root, capture_output=True, text=True)
    last = r.stdout.strip().splitlines()[-1]
    failed = [l.split('::')[1].split(' ')[0] for l in r.stdout.splitlines() if l.startswith('FAILED')]
    print(f"{name}: {'killed' if r.returncode else 'SURVIVED'} ({last}) {failed[:1]}")
f.write_text(orig)
