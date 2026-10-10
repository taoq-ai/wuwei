"""Run the test files a diff against origin/main touches, and the tests that import them (#685).

Usage: python3 scripts/changed_tests.py [pytest args]
Exit 0 nothing to run, 2 the diff could not be read, otherwise pytest's exit code.
"""

import ast
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WHOLE_SUITE = {'tests/conftest.py', 'pyproject.toml'}


def changed(root):
    """Paths the branch changed against the merge base with origin/main, plus untracked files."""
    run = lambda *args: subprocess.run(args, cwd=root, check=True, capture_output=True, text=True).stdout.split()
    return set(run('git', 'diff', '--name-only', '--merge-base', 'origin/main')) | set(
        run('git', 'ls-files', '--others', '--exclude-standard'))


def module(path):
    """The import name of a Python file under cli/, adapters/ or tests/, else None."""
    if not path.endswith('.py') or path.split('/')[0] not in ('cli', 'adapters', 'tests'):
        return None
    name = path.removeprefix('cli/').removeprefix('tests/').removesuffix('.py').removesuffix('/__init__')
    return name.replace('/', '.')


def imports(source):
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names |= {node.module} | {f'{node.module}.{alias.name}' for alias in node.names}
    return names


def select(paths, root):
    """Sorted test paths to run for the changed paths, or ['tests'] for the whole suite."""
    # ponytail: direct imports and file-name mentions only; a module reached through
    # wuwei.__main__ dispatch or a file read through a glob is missed. CI runs the full suite.
    if paths & WHOLE_SUITE:
        return ['tests']
    root = Path(root)
    tests = {}
    for p in (root / 'tests').glob('test_*.py'):
        source = p.read_text()
        tests[str(p.relative_to(root))] = source, imports(source)
    selected = {p for p in paths if p in tests}
    modules = {module(p) for p in paths} - {None}
    names = {Path(p).name for p in paths if module(p) is None}
    while True:
        found = {p for p, (source, imported) in tests.items()
                 if imported & modules or any(name in source for name in names)} - selected
        if not found:
            return sorted(selected)
        selected |= found
        modules |= {module(p) for p in found}


def main(argv):
    try:
        paths = changed(ROOT)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f'changed_tests: cannot read the diff against origin/main: {error}', file=sys.stderr)
        return 2
    files = select(paths, ROOT)
    if not files:
        print('changed_tests: no test touched by the diff')
        return 0
    print('changed_tests:', ' '.join(files), flush=True)
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', *argv, *files], cwd=ROOT).returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
