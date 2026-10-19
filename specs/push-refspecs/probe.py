"""Generated combinatorial probe for item push-refspecs, run under real bash with a stub git on PATH that logs each call and
then execs real git 2.43. Classes: refspec spellings (sources x destination spellings, deletes, the matching refspec, + refspecs,
source-only words, glob pairs) x quoting (plain, single, double, backslash, $'..') x position (alone, after a branch); options
(--all, --branches, --mirror, --tags, --prune, --delete and abbreviations) x position (before the remote, after it, last) x
refspecs; normalisation inputs (//, %xx, /./, /../ in a destination) and working-directory wrappers (cd, env -C, sudo -D).
Each command runs from a clone on feature and from a worktree of it on main, against the bare remote gh.git that stands for the
code host. The guard reads each command with guards.TEMP moved off the probe folder (so gh.git is not a scratch remote) and the
origin read as o/r, default branch main. A hole: the guard passes and the remote's main moved, appeared or vanished.

Usage: python3 probe.py <tree> <empty folder>
Prints generated, ran (the stub logged a git push), holes, and refusals of commands that left main alone, with rows.json."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TREE, BASE = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(TREE / 'cli'))
from wuwei import gh, guards  # noqa: E402

if BASE.exists():
    shutil.rmtree(BASE)
BIN, HOME, ROOT, GH, C, CM = (BASE / n for n in ('bin', 'home', 'root', 'gh.git', 'c', 'cm'))
for d in (BIN, HOME, ROOT / '.wuwei'):
    d.mkdir(parents=True)
REAL = shutil.which('git')
LOG = BASE / 'stub.log'
(BIN / 'git').write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {LOG}\nexec {REAL} "$@"\n')
(BIN / 'git').chmod(0o755)
ENV = {**os.environ, 'HOME': str(HOME), 'GIT_CEILING_DIRECTORIES': str(BASE), 'GIT_CONFIG_NOSYSTEM': '1',
       'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}
ENV.pop('GIT_CONFIG_GLOBAL', None)
os.environ.update({k: ENV[k] for k in ('HOME', 'GIT_CEILING_DIRECTORIES', 'GIT_CONFIG_NOSYSTEM')})
os.environ.pop('GIT_CONFIG_GLOBAL', None)


def git(*args, at=BASE):
    return subprocess.run([REAL, *args], cwd=at, env=ENV, check=True, capture_output=True, text=True).stdout.strip()


git('init', '-q', '--bare', str(GH))
git('init', '-q', '-b', 'main', str(C))
git('commit', '-q', '--allow-empty', '-m', 'base', at=C)
git('remote', 'add', 'origin', str(GH), at=C)
git('push', '-q', 'origin', 'main', 'main:feature', 'main:f/x', at=C)
git('fetch', '-q', 'origin', at=C)
git('commit', '-q', '--allow-empty', '-m', 'ahead on main', at=C)  # every push that names main moves it
git('branch', 'f/main', at=C)  # refs/heads/f/* onto refs/heads/* reaches main
git('switch', '-q', '-c', 'feature', 'HEAD~1', at=C)
git('commit', '-q', '--allow-empty', '-m', 'ahead on feature', at=C)  # feature onto main is a fast-forward
git('branch', 'f/x', at=C)
git('tag', 'v1', at=C)
git('worktree', 'add', '-q', str(CM), 'main', at=C)
X0 = git('rev-parse', 'refs/heads/main', at=GH)


def snapshot(at):
    return git('for-each-ref', '--format=%(refname) %(objectname)', at=at).splitlines()


START = {GH: snapshot(GH), C: snapshot(C)}


def restore():
    for at, start in START.items():
        now = {line.split()[0] for line in snapshot(at)}
        keep = dict(line.split() for line in start)
        script = ''.join(f'delete {r}\n' for r in now - set(keep)) + ''.join(f'update {r} {o}\n' for r, o in keep.items())
        subprocess.run([REAL, 'update-ref', '--no-deref', '--stdin'], cwd=at, env=ENV, input=script, text=True, check=True)


SRCS = ['feature', 'HEAD', 'main', 'heads/feature', 'refs/heads/feature', ':/ahead on feature', 'feature~0', 'v1', '@', '']
DSTS = ['main', 'heads/main', 'refs/heads/main', 'HEAD', '', 'feature', 'heads/feature', 'refs/heads/feature', 'refs/heads/f/main',
        'f/main', 'refs/f/main', 'refs/remotes/origin/main', 'MAIN', 'tags/main', 'refs/heads//main', 'refs/heads/%6dain',
        'refs/heads/./main', 'refs/heads/x/../main', 'main/']
GLOBS = ['refs/heads/*', 'refs/heads/f/*', '*', 'refs/*', 'heads/*', 'refs/heads/m*', 'refs/heads/*n', 'refs/tags/*', 'refs/heads/f*',
         'refs/heads/*/main', 'refs/remotes/origin/*']
WORDS = list(dict.fromkeys([s + ':' + d for s in SRCS for d in DSTS] + ['+feature:' + d for d in DSTS] + ['+:']
                           + [w for w in SRCS + DSTS if w] + [a + ':' + b for a in GLOBS for b in GLOBS] + GLOBS
                           + ['+refs/heads/*:refs/heads/*', '+refs/heads/f/*:refs/heads/f/*']))
QUOTES = {'plain': lambda w: w, 'single': lambda w: f"'{w}'", 'double': lambda w: f'"{w}"',
          'backslash': lambda w: ''.join('\\' + ch if ch in "*: '\"~@" else ch for ch in w), 'dollar': lambda w: f"$'{w}'"}
OPTS = ['--all', '--al', '--a', '--branches', '--bra', '--b', '--mirror', '--mirr', '--m', '--tags', '--follow-tags', '--prune',
        '--delete', '-d', '--atomic', '--no-verify', '-o x', '--push-option=x', '-q', '--no-all']
TAILS = ['', 'feature', 'main', 'heads/main', "'refs/heads/*:refs/heads/*'", 'refs/heads/f/*:refs/heads/f/*', ':', 'feature:feature',
         'feature:heads/main', 'f/x']
WRAPPED = ['cd {D} && git push origin {W}', 'env -C {D} git push origin {W}', 'sudo -D {D} git push origin {W}',
           'git -C {D} push origin {W}']
commands = [f'git push origin {q(w)}' for w in WORDS for q in QUOTES.values()]
commands += [f'git push origin feature {QUOTES[q](w)}' for w in WORDS for q in ('plain', 'single')]
commands += [form.format(o=o, t=t) for o in OPTS for t in TAILS
             for form in ('git push {o} origin {t}', 'git push origin {o} {t}', 'git push origin {t} {o}')]
commands += [f.replace('{D}', str(d)).replace('{W}', w) for f in WRAPPED for d in (C, CM)
             for w in ('heads/main', 'feature:refs/heads/main', 'refs/heads/./main', 'refs/heads//main', ':', "'refs/heads/*'", '--all')]
commands = [' '.join(c.split(' ')).rstrip() for c in dict.fromkeys(commands)]

guards.TEMP = (str(BASE / 'nowhere'),)  # gh.git is no scratch remote: it stands for the code host
guards.origin = lambda cwd: 'o/r'
gh.default_branch = lambda repo: 'main'
rows, ran, holes = [], 0, []
for name, cwd in (('c on feature', C), ('cm on main', CM)):
    for command in commands:
        decision = guards.bash(str(ROOT), command, str(cwd), 's1')
        LOG.write_text('')
        done = subprocess.run(['bash', '-c', command], cwd=cwd, env={**ENV, 'PATH': f'{BIN}:{ENV["PATH"]}'},
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        did = any(line.split(' ')[:1] == ['push'] or ' push ' in f' {line} ' for line in LOG.read_text().splitlines())
        ran += did
        moved = subprocess.run([REAL, '--git-dir', str(GH), 'rev-parse', '-q', '--verify', 'refs/heads/main'], env=ENV,
                               capture_output=True, text=True).stdout.strip() != X0
        row = {'command': command, 'cwd': name, 'decision': decision and decision['decision'], 'ran': did, 'moved': moved,
               'exit': done.returncode}
        rows.append(row)
        if decision is None and moved:
            holes.append(row)
        restore()
(BASE / 'rows.json').write_text(json.dumps(rows, indent=1))
print(json.dumps({'generated': len(rows), 'ran_door_program': ran, 'holes': len(holes),
                  'moved_main': sum(r['moved'] for r in rows), 'guard_passed': sum(r['decision'] is None for r in rows),
                  'refused_main_unmoved': sum(r['decision'] is not None and not r['moved'] for r in rows),
                  'refused_main_unmoved_git_exit_0': sum(r['decision'] is not None and not r['moved'] and r['exit'] == 0 for r in rows)}))
for h in holes:
    print('HOLE', json.dumps(h))
