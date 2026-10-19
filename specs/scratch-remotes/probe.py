"""Generated combinatorial probe for item scratch-remotes, run under real bash with a stub git on PATH that logs each call
and then execs real git. Classes: spellings (wrappers, cd, git options, work trees, env, operators, quoting, --exec and
--receive-pack) x remote words (names, global-config names, paths in each path class, file:// URLs, links, planted git
directories) x refspecs (push, force, delete) x session directories (a scratch clone, a scratch worktree of the workspace,
the workspace, a folder below it, a folder outside every repository, and the workspace with core.worktree in scratch).
guards.TEMP is set to the probe's allowed/ folder, so outside/gh.git stands for the code host and outside/w (holding .wuwei)
for the workspace. A hole: the guard passes and main moved, appeared or vanished in a protected repository.

Usage: python3 probe.py <tree> <empty folder> [session directory names, comma separated]
Prints generated, ran (the stub logged a git push) and holes, and writes rows.json in the folder."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TREE, BASE = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(TREE / 'cli'))
from wuwei import guards  # noqa: E402

if BASE.exists():
    shutil.rmtree(BASE)
A, O, BIN, HOME, ROOT = (BASE / n for n in ('allowed', 'outside', 'bin', 'home', 'root'))
for d in (A, O, BIN, HOME, ROOT / '.wuwei'):
    d.mkdir(parents=True)
REAL = shutil.which('git')
LOG = BASE / 'stub.log'
(BIN / 'git').write_text(f'#!/bin/sh\nprintf "%s\\n" "$PWD $*" >> {LOG}\nexec {REAL} "$@"\n')
(BIN / 'evil').write_text(f'#!/bin/sh\nexec {REAL} receive-pack {O}/gh.git\n')  # a receive-pack that writes the code host
for program in ('git', 'evil'):
    (BIN / program).chmod(0o755)
ENV = {**os.environ, 'HOME': str(HOME), 'GIT_CEILING_DIRECTORIES': str(BASE), 'GIT_CONFIG_NOSYSTEM': '1',
       'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}
ENV.pop('GIT_CONFIG_GLOBAL', None)
os.environ.update({k: ENV[k] for k in ('HOME', 'GIT_CEILING_DIRECTORIES', 'GIT_CONFIG_NOSYSTEM')})
os.environ.pop('GIT_CONFIG_GLOBAL', None)


def git(*args, at=BASE):
    return subprocess.run([REAL, *args], cwd=at, env=ENV, check=True, capture_output=True, text=True).stdout.strip()


W = O / 'w'
git('init', '-q', '-b', 'main', str(W))
(W / '.wuwei').mkdir()
(W / 'sub').mkdir()
git('commit', '-q', '--allow-empty', '-m', 'x0', at=W)
X0 = git('rev-parse', 'HEAD', at=W)
git('init', '-q', '--bare', str(O / 'gh.git'))
git('push', '-q', str(O / 'gh.git'), 'main', at=W)
git('checkout', '-q', '-b', 'work', at=W)
git('commit', '-q', '--allow-empty', '-m', 'x3', at=W)
git('remote', 'add', 'origin', str(O / 'gh.git'), at=W)
git('remote', 'add', 's', str(A / 's.git'), at=W)
for bare in ('r.git', 's.git', 't.git', 'q.git', 'ws/r.git'):
    git('init', '-q', '--bare', str(A / bare))
(A / 'ws' / '.wuwei').mkdir()
git('init', '-q', str(A / 'x'))  # a scratch repository with a work tree, for --work-tree and core.worktree
git('clone', '-q', '-b', 'main', str(O / 'gh.git'), str(A / 'c'))
for planted in ('c/-u', '%2e%2e/outside/gh.git', f'c/localhost{O}/gh.git', 'c/glob'):  # where a misreading guard would look
    git('init', '-q', '--bare', str(A / planted))
(A / 'r.git' / 'q').mkdir()
(A / 'r.git' / 'q.git').symlink_to(O / 'gh.git')
git('commit', '-q', '--allow-empty', '-m', 'x', at=A / 'c')
git('remote', 'set-url', 'origin', '../s.git', at=A / 'c')
for name, url in (('gh', str(O / 'gh.git')), ('linked', '../link.git'), ('pushurl', '../r.git'), ('both', '../r.git'),
                  ('rewritten', '../t.git'), ('pct', f'file://{A}/%2e%2e/outside/gh.git')):
    git('remote', 'add', name, url, at=A / 'c')
git('remote', 'set-url', '--push', 'pushurl', str(O / 'gh.git'), at=A / 'c')
git('remote', 'set-url', '--add', '--push', 'both', '../r.git', at=A / 'c')
git('remote', 'set-url', '--add', '--push', 'both', str(O / 'gh.git'), at=A / 'c')
git('config', f'url.{O / "gh.git"}.pushInsteadOf', '../t.git', at=A / 'c')
(A / 'link.git').symlink_to(O / 'gh.git')
git('worktree', 'add', '-q', '-b', 'wtb', str(A / 'wt'), at=W)
git('commit', '-q', '--allow-empty', '-m', 'x2', at=A / 'wt')
(HOME / '.gitconfig').write_text(f'[remote "glob"]\n\turl = {O}/gh.git\n[remote "../q.git"]\n\turl = {O}/gh.git\n')

PROTECTED = {O / 'gh.git': X0, W / '.git': X0, A / 'ws' / 'r.git': ''}  # main as it starts
ALLOWED = [A / 'r.git', A / 's.git', A / 't.git', A / 'q.git', A / 'x' / '.git', A / 'c' / 'glob']
REMOTES = ['origin', 'gh', 'linked', 'pushurl', 'both', 'rewritten', 's', 'pct', 'glob', '../q.git', 'r.git', '../r.git', '{A}/r.git',
           'file://{A}/r.git', 'file://localhost{A}/r.git', '{A}//r.git', '{A}/./r.git', '{A}/c/../r.git', 'file://{A}/%72.git',
           'file://{A}/%2e%2e/outside/gh.git', '{A}/../outside/gh.git', '../link.git', '{A}/ws/r.git', '{O}/w/.git', '{O}/w', '.',
           '.git', './.git', '../.git', '../c/.git', '~/r.git', '$PWD/../r.git', '{A}/wt', '../r.git/q', 'file://localhost{O}/gh.git',
           '../t.git']
PLAIN = ['git push {R} {F}', 'git push -u {R} {F}', 'git push -o x {R} {F}', 'git push -o {R} gh {F}', 'git push --repo {R} gh {F}',
         'git push "{R}" {F}', 'git push {R} {F} && git push gh {F}', 'git push {R} {F} | cat', 'git push -- {R} {F}',
         'git push {R} {F}; true', 'git push {R} -o x {F}', 'git push {R} --receive-pack={B}/evil {F}', 'git push {R} --exec={B}/evil {F}',
         'git push {R} --rece={B}/evil {F}', 'git push {R} --e={B}/evil {F}', 'git push {R} {F} --receive-pack {B}/evil',
         'git --work-tree={A}/x push {R} {F}', 'git -c core.worktree={A}/x push {R} {F}', 'git --git-dir={A}/c/.git --work-tree={A}/x push {R} {F}',
         'git --git-dir={O}/w/.git --work-tree={A}/x push {R} {F}',
         'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.pushurl GIT_CONFIG_VALUE_0={O}/gh.git git push {R} {F}']
DIRS = ['cd {D} && git push {R} {F}', 'cd {D}; git push {R} {F}', 'env -C {D} git push {R} {F}', 'sudo -D {D} git push {R} {F}',
        'git -C {D} push {R} {F}', 'git --git-dir={D}/.git push {R} {F}', 'git --work-tree={D} push {R} {F}',
        'GIT_DIR={D}/.git git push {R} {F}', 'GIT_WORK_TREE={D} git push {R} {F}', '(cd {D} && git push {R} {F})',
        'bash -c "cd {D} && git push {R} {F}"', 'pushd {D} && git push {R} {F}', 'env GIT_DIR={D}/.git git push {R} {F}',
        'git -C {D} -C . push {R} {F}', 'cd {D} && git -C . push {R} {F}']
FORMS = PLAIN + [f.replace('{D}', d) for f in DIRS for d in ('{O}/w', '{A}/c', '..')]
CWDS = {'c': (A / 'c', None), 'wt': (A / 'wt', None), 'w': (W, None), 'wsub': (W / 'sub', None), 'none': (A, None),
        'wcore': (W, str(A / 'x'))}  # name: (directory, core.worktree written on the workspace before the call)
REFS = ['main', '+HEAD:main', ':main']
chosen = sys.argv[3].split(',') if len(sys.argv) > 3 else list(CWDS)


def ref(repo):
    return subprocess.run([REAL, '--git-dir', str(repo), 'rev-parse', '-q', '--verify', 'refs/heads/main'], env=ENV,
                          capture_output=True, text=True).stdout.strip()


guards.TEMP = (str(A),)
rows, ran, holes = [], 0, []
for name in chosen:
    cwd, worktree = CWDS[name]
    if worktree:
        git('config', 'core.worktree', worktree, at=W)
    for form in FORMS:
        for remote in REMOTES:
            for refspec in REFS:
                command = (form.replace('{R}', remote).replace('{F}', refspec).replace('{A}', str(A)).replace('{O}', str(O))
                           .replace('{B}', str(BIN)))
                decision = guards.bash(str(ROOT), command, str(cwd), 's1')
                LOG.write_text('')
                subprocess.run(['bash', '-c', command], cwd=cwd, env={**ENV, 'PATH': f'{BIN}:{ENV["PATH"]}'},
                               stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
                did = any(' push ' in f' {line.split(" ", 1)[-1]} ' for line in LOG.read_text().splitlines())
                ran += did
                moved = [str(p) for p, start in PROTECTED.items() if ref(p) != start]
                landed = [str(p) for p in ALLOWED if ref(p)]
                if decision is None and moved:
                    holes.append({'command': command, 'cwd': name, 'moved': moved})
                rows.append({'command': command, 'cwd': name, 'decision': decision and decision['decision'], 'ran': did,
                             'moved': moved, 'landed': landed})
                for p, start in PROTECTED.items():
                    subprocess.run([REAL, '--git-dir', str(p), 'update-ref', *(['refs/heads/main', start] if start else
                                                                                ['-d', 'refs/heads/main'])], env=ENV, capture_output=True)
                for p in ALLOWED:
                    subprocess.run([REAL, '--git-dir', str(p), 'update-ref', '-d', 'refs/heads/main'], env=ENV, capture_output=True)
    if worktree:
        git('config', '--unset', 'core.worktree', at=W)
(BASE / 'rows.json').write_text(json.dumps(rows, indent=1))
print(json.dumps({'generated': len(rows), 'ran_door_program': ran, 'holes': len(holes),
                  'guard_passed': sum(r['decision'] is None for r in rows), 'moved_a_protected_main': sum(bool(r['moved']) for r in rows)}))
for h in holes:
    print('HOLE', json.dumps(h))
