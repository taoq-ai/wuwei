"""Generated probe for #1230: real git merges into a PR branch, read through evidence.gate_gaps at two trees.

    python3 -I probe.py <main tree> <head tree> <scratch folder>

Each case builds a repository with real git under the scratch folder: a base commit, a PR head that passed quality and
security, then main's change and the push the case names (a merge of main, a conflict resolution, GitHub's update-branch
merge commit, a plain fix). gh.compare is answered from git as GitHub's compare API answers it (three dots: the diff
from the merge base, one patch per file from its first @@ line). Each tree reads every case in its own process with a
fresh workspace; the case folders are deleted at the end. A hole is a case whose owed gate at the head tree is not the
one expected.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

TARGETS = {'plain': ('src/app.py', 'src/other.py'), 'risky': ('src/session.py', 'src/auth_other.py')}
BODY = ['def run():'] + [f'    x_{i} = {i}' for i in range(30)] + ['def later():'] + [f'    y_{i} = {i}' for i in range(30)]
# kind -> (gate owed at the head tree for a plain target, for a risky target)
EXPECT = {'far': ('', ''), 'above': ('', ''), 'adjacent': ('', 'security'), 'conflict-edit': ('', 'security'),
          'conflict-ours': ('', 'security'), 'conflict-add30': ('quality', 'security'), 'evil-revert': ('quality', 'security'),
          'update-branch': ('', ''), 'fix-1': ('', 'security'), 'fix-25': ('quality', 'security'),
          'merge-and-fix': ('quality', 'security'), 'merge-new-file': ('quality', 'security'), 'main-only': ('', '')}


def git(folder, *args, check=True):
    return subprocess.run(['git', '-C', str(folder), *args], check=check, capture_output=True, text=True).stdout.strip()


def write(folder, path, lines):
    (folder / path).parent.mkdir(parents=True, exist_ok=True)
    (folder / path).write_text('\n'.join(lines) + '\n')


def edit(folder, path, old, new):
    text = (folder / path).read_text()
    assert text.count(old) == 1, (path, old)
    (folder / path).write_text(text.replace(old, new))


def build(folder, kind, target, other):
    folder.mkdir(parents=True)
    git(folder, 'init', '-q', '-b', 'main')
    git(folder, 'config', 'user.email', 'probe@example.com')
    git(folder, 'config', 'user.name', 'probe')
    write(folder, target, BODY)
    write(folder, other, [f'o_{i} = {i}' for i in range(40)])
    write(folder, 'src/token.py', ['t = 0'])
    write(folder, 'tests/test_app.py', ['def test_run():', '    assert True'])
    git(folder, 'add', '-A')
    git(folder, 'commit', '-qm', 'base')
    git(folder, 'checkout', '-qb', 'feature')
    edit(folder, target, '    x_10 = 10\n    x_11 = 11\n', "    x_10 = 10\n    pr_a = 1\n    pr_b = 2\n    x_11 = 'pr'\n")
    edit(folder, 'tests/test_app.py', '    assert True\n', '    assert True\n    assert run\n')
    git(folder, 'commit', '-qam', 'pr')
    last = git(folder, 'rev-parse', 'HEAD')
    if kind.startswith('fix'):
        added = ['    fix_0 = 0'] if kind == 'fix-1' else [f'    fix_{i} = {i}' for i in range(25)]
        edit(folder, target, '    y_5 = 5\n', '    y_5 = 5\n' + ''.join(line + '\n' for line in added))
        git(folder, 'commit', '-qam', 'fix')
        return last, git(folder, 'rev-parse', 'HEAD'), git(folder, 'rev-parse', 'main')
    git(folder, 'checkout', '-q', 'main')
    write(folder, 'src/token.py', [f't_{i} = {i}' for i in range(300)])  # main's risky file the PR never touched
    if kind in ('far', 'update-branch', 'merge-and-fix', 'merge-new-file'):
        edit(folder, target, '    y_20 = 20\n', "    y_20 = 'main'\n")
    if kind == 'above':
        edit(folder, target, '    x_4 = 4\n', '    x_4 = 4\ndef main_added():\n    m = 1\n')
    if kind == 'adjacent':
        edit(folder, target, '    x_8 = 8\n', "    x_8 = 'main'\n")
    if kind.startswith('conflict'):
        edit(folder, target, '    x_11 = 11\n', "    x_11 = 'main'\n")
    if kind in ('evil-revert', 'update-branch'):
        edit(folder, other, 'o_20 = 20\n', 'o_20 = 20\n' + ''.join(f'main_{i} = {i}\n' for i in range(30)))
    git(folder, 'commit', '-qam', 'main moves')
    git(folder, 'checkout', '-q', 'feature')
    if kind == 'main-only':  # main moved, the PR head did not: no merge
        return last, last, git(folder, 'rev-parse', 'main')
    message = "Merge branch 'main' into feature" if kind == 'update-branch' else 'merge main'
    merged = subprocess.run(['git', '-C', str(folder), 'merge', '--no-ff', '-q', '-m', message, 'main'], capture_output=True, text=True)
    if kind.startswith('conflict'):
        assert merged.returncode != 0, kind
        git(folder, 'checkout', '--ours', target)
        if kind == 'conflict-edit':
            edit(folder, target, "    x_11 = 'pr'\n", "    x_11 = 'merged'\n")
        if kind == 'conflict-add30':
            edit(folder, target, "    x_11 = 'pr'\n", "    x_11 = 'pr'\n" + ''.join(f'    z_{i} = {i}\n' for i in range(30)))
        git(folder, 'add', target)
        git(folder, 'commit', '-qm', message)
    else:
        assert merged.returncode == 0, (kind, merged.stderr)
    if kind == 'evil-revert':
        git(folder, 'checkout', last, '--', other)
        git(folder, 'commit', '-q', '--amend', '--no-edit')
    if kind == 'merge-new-file':
        write(folder, 'src/new_' + target.split('/')[-1], [f'n_{i} = {i}' for i in range(30)])
        git(folder, 'add', '-A')
        git(folder, 'commit', '-q', '--amend', '--no-edit')
    if kind == 'merge-and-fix':
        edit(folder, target, '    y_5 = 5\n', '    y_5 = 5\n' + ''.join(f'    fix_{i} = {i}\n' for i in range(25)))
        git(folder, 'commit', '-qam', 'fix after the merge')
    return last, git(folder, 'rev-parse', 'HEAD'), git(folder, 'rev-parse', 'main')


def answer(folder, older, newer):
    """GitHub's compare of older...newer: the diff from their merge base, each file's patch from its first @@ line."""
    base = git(folder, 'merge-base', older, newer)
    files = []
    for row in git(folder, 'diff', '--numstat', base, newer).splitlines():
        added, deleted, path = row.split('\t')
        text = git(folder, 'diff', '--no-color', '-U3', base, newer, '--', path)
        files.append({'filename': path, 'additions': int(added), 'deletions': int(deleted), 'patch': text[text.index('\n@@') + 1:]})
    ahead = subprocess.run(['git', '-C', str(folder), 'merge-base', '--is-ancestor', older, newer]).returncode == 0
    return {'status': 'identical' if older == newer else 'ahead' if ahead else 'diverged', 'files': files,
            'merge_base_commit': {'sha': base}}


def judge(tree, cases):
    """Owed gate per case, through the tree's gate_gaps, in this process."""
    import hashlib
    import inspect
    import tempfile
    sys.path.insert(0, str(Path(tree) / 'cli'))
    from wuwei import evidence, gh, ws
    out = {}
    for case in cases:
        folder = Path(case['folder'])
        gh.run = lambda args, timeout=30: answer(folder, *args[1].split('/compare/')[1].split('...'))  # noqa: E731
        root = Path(tempfile.mkdtemp(dir=folder.parent))
        (root / ws.DIR).mkdir()
        ws.write_config(root, {**ws.DEFAULTS, 'repos': ['acme/app']})
        for gate in ('quality', 'security'):
            path = root / ws.DIR / 'verdicts' / 'I-1' / f'{gate}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'Verdict: PASS\nGate: {gate}\nItem: I-1\nPR: acme/app#42\nHead: {case["last"]}\nConfidence: high\n\n## Findings\nnone\n')
            ws.record(root, 'attest', {'path': str(path.relative_to(root)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                       'gate': gate, 'item': 'I-1', 'head': case['last'], 'verdict': 'PASS'})
        extra = {'base': case['base']} if 'base' in inspect.signature(evidence.gate_gaps).parameters else {}
        found = evidence.gate_gaps(root, 'acme/app', 'I-1', ('quality', 'security'), case['head'], ref='acme/app#42', **extra)
        texts = [g['text'] for g in found]
        out[case['id']] = texts[0].split('delta review by ')[1].rstrip(')') if texts else ''
        assert len(texts) <= 1, texts
        shutil.rmtree(root)
    print(json.dumps(out))


def main(main_tree, head_tree, scratch):
    scratch = Path(scratch) / 'probe-1230'
    shutil.rmtree(scratch, ignore_errors=True)
    cases = []
    for kind in EXPECT:
        for column, (cls, (target, other)) in enumerate(TARGETS.items()):
            folder = scratch / f'{kind}-{cls}'
            last, head, base = build(folder, kind, target, other)
            cases.append({'id': f'{kind}/{cls}', 'folder': str(folder), 'last': last, 'head': head, 'base': base,
                          'expect': EXPECT[kind][column]})
    (scratch / 'cases.json').write_text(json.dumps(cases))
    read = {}
    for name, tree in (('main', main_tree), ('head', head_tree)):
        run = subprocess.run([sys.executable, '-I', __file__, 'judge', tree, str(scratch / 'cases.json')], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
        read[name] = json.loads(run.stdout.strip().splitlines()[-1])
    holes = [c['id'] for c in cases if read['head'][c['id']] != c['expect']]
    print(f'{"case":28} {"main":10} {"head":10} expected')
    for c in cases:
        print(f'{c["id"]:28} {read["main"][c["id"]] or "carries":10} {read["head"][c["id"]] or "carries":10} {c["expect"] or "carries"}')
    print(f'generated {len(cases)}, ran gate_gaps at both trees {len(read["main"])} and {len(read["head"])}, holes {len(holes)}: {holes}')
    shutil.rmtree(scratch)
    return 1 if holes else 0


if __name__ == '__main__':
    if sys.argv[1] == 'judge':
        judge(sys.argv[2], json.loads(Path(sys.argv[3]).read_text()))
    else:
        sys.exit(main(*sys.argv[1:4]))
