"""Mutants of the forge-door rule, run with pytest's interpreter:

    python specs/forge-door/mutants.py <tree> <scratch dir>

Each mutant edits both copies of guards.py (cli/ and .claude/wuwei/cli/) in a fresh copy of <tree>,
so the vendored drift test cannot be the kill, then runs tests/test_guards.py and tests/test_hook.py
and prints the first failing test (-x)."""

import shutil
import subprocess
import sys
from pathlib import Path

MUTANTS = [
    ('M1 drop the lookbehind', r"(?<![\w/.])wuwei", r"wuwei"),
    ('M2 the lookbehind allows a dot', r"(?<![\w/.])wuwei", r"(?<![\w/])wuwei"),
    ('M3 drop the lookahead', r"wuwei(?![\w/-])'", r"wuwei'"),
    ('M4 hook only, no record', r"r'\b(hook|record)\b')", r"r'\bhook\b')"),
    ('M5 drop the -- skip', r"( --)*( hook\b", r"( hook\b"),
    ('M6 drop the filled subcommand', r"( hook\b| {FILLED})", r"( hook\b)"),
    ('M7 drop the bare CLI', r"|(^\S*|-\w*m ?)wuwei( --)*$|", '|'),
    ('M8 drop hook after a filled word', r"|{FILLED} (-- )*hook\b'", "'"),
    ('M9 drop __main__.py', r"wuwei(/__main__\.py|\.__main__)?", r"wuwei(\.__main__)?"),
    ('M10 drop .__main__', r"wuwei(/__main__\.py|\.__main__)?", r"wuwei(/__main__\.py)?"),
    ('M11 a filled program is no runner', 'runner = re.search(FILLED, program) or ', 'runner = '),
    ('M12 a shell is no runner', ' or program in SHELLS or any(', ' or any('),
    ('M13 only the program is read as python', "any(Path(a).name.startswith(('python', 'pypy')) for a in argv)",
     "program.startswith(('python', 'pypy'))"),
    ('M14 no pypy', "(('python', 'pypy'))", "('python')"),
    ('M15 the wuwei program needs a runner', "runner or program == 'wuwei') and", 'runner) and'),
    ('M16 drop the code rule', 'if runner and (forged or hooked', 'if runner and (hooked'),
    ('M17 FORGE not a door word', r"(r'\.wuwei[/.]*(/ledger|(?![\w./-]))',), FORGE)", r"(r'\.wuwei[/.]*(/ledger|(?![\w./-]))',))"),
    ('M18 any for all', 'all(re.search(w, command) for w in FORGE)', 'any(re.search(w, command) for w in FORGE)'),
    ('M19 the CLI rule skips the program word', "CLI, ' '.join(argv)", "CLI, ' '.join(argv[1:])"),
    ('M20 the bare CLI only after -m', r"(^\S*|-\w*m ?)wuwei( --)*$", r"-\w*m ?wuwei( --)*$"),
    ('M21 the bare CLI unanchored', r"(^\S*|-\w*m ?)wuwei( --)*$", r"\S*wuwei( --)*$"),
    ('M22 the bare CLI takes no --', r"(^\S*|-\w*m ?)wuwei( --)*$", r"(^\S*|-\w*m ?)wuwei$"),
    ('M23 only $ fills a word', r"(?=\S*[$`*?\[{])", r"(?=\S*[$])"),
    ('M24 a filled word read at every position', r"FILLED = r'(?<!\S)(?=\S*[$`*?\[{])\S*+'", r"FILLED = r'[$`*?\[{]\S*'"),
    ('M25 two filled words need no hook', 'forged or hooked and re.match', 'forged or re.match'),
    ('M26 two filled words anywhere', "re.match(f'{FILLED} (-- )*{FILLED}'", "re.search(f'{FILLED} (-- )*{FILLED}'"),
    ('M27 drop the two filled words', " or hooked and re.match(f'{FILLED} (-- )*{FILLED}', ' '.join(argv))", ''),
    ('M28 forged without a runner', 'if runner and (forged or', 'if forged or (runner and'),
    ('M29 hooked reads hooks too', r"re.search(r'\bhook\b', command)", r"re.search(r'\bhook', command)"),
]


def main():
    tree, scratch = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    killed = 0
    for name, old, new in MUTANTS:
        work = scratch / name.split()[0]
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(tree, work)
        for path in (work / 'cli/wuwei/guards.py', work / '.claude/wuwei/cli/wuwei/guards.py'):
            text = path.read_text()
            assert text.count(old) == 1, (name, path)
            path.write_text(text.replace(old, new))
        done = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', 'tests/test_guards.py', 'tests/test_hook.py'],
                              cwd=work, capture_output=True, text=True)
        failed = [line.split(' - ')[0].removeprefix('FAILED ') for line in done.stdout.splitlines() if line.startswith('FAILED')]
        killed += bool(failed)
        print(f'{name}: {"killed" if failed else "SURVIVED"} by {len(failed)}; first: {failed[:2]}', flush=True)
        shutil.rmtree(work)
    print(f'{killed} of {len(MUTANTS)} killed')


if __name__ == '__main__':
    main()
