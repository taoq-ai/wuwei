"""Generated combinatorial probe for item push-force-clusters, run under real bash with a stub git on PATH that logs each call
and then execs real git. A bare remote gh.git (push options advertised) holds main and div, each a commit the clone c lacks,
so only a force push moves either.

Classes:
- cluster: every short cluster of git push's flags (v q n d u 4 6), none to two before f and none or one after it, with -o
  and a value after f (-fox, -fo=x, -fo.x, -fo/x), x three positions (before the remote, after it, after the refspec) x the
  targets div, div:div, refs/heads/div and main.
- spelling: the item's five clusters and -fo=x quoted ('-4f', "-4f", \\-4f) x positions x div.
- operator: the same clusters after true &&, true ;, false || and inside ( ) x positions x div.
- plain: each cluster with no f x positions x div and main: its verdict at the head equals main's (read as before).
- value: f as -o's value (-of, -4of, -o f, -o -f): git does not force; the head may refuse it (over-refusal, counted).
A hole: the head's guard passes and git rewrote main or div (a forced update, as each is diverged) or deleted main; deleting
div is ordinary work the door passes. A misread: a ref rewritten and the head's refusal is not the force refusal. Each command is read by the guard of both trees, with the origin read as o/r, default branch main.

Usage: python3 -I probe.py <main tree> <head tree> <empty folder>
Prints per class: generated, ran (the stub logged a git push), holes and misreads at head and main, newly refused,
newly passed; then each hole."""
import importlib
import json
import os
import shutil
import subprocess
import sys
from itertools import product
from pathlib import Path

MAIN_T, HEAD_T, BASE = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]).resolve()
if BASE.exists():
    shutil.rmtree(BASE)
GH, C, HOME, ROOT, BIN = (BASE / n for n in ('gh.git', 'c', 'home', 'root', 'bin'))
for d in (HOME, ROOT / '.wuwei', BIN):
    d.mkdir(parents=True)
REAL = shutil.which('git')
LOG = BASE / 'stub.log'
(BIN / 'git').write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {LOG}\nexec {REAL} "$@"\n')
(BIN / 'git').chmod(0o755)
ENV = {**os.environ, 'HOME': str(HOME), 'GIT_CEILING_DIRECTORIES': str(BASE), 'GIT_CONFIG_NOSYSTEM': '1',
       'GIT_ALLOW_PROTOCOL': 'file', 'GIT_TERMINAL_PROMPT': '0', 'GIT_SSH_COMMAND': 'false',
       'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}
ENV.pop('GIT_CONFIG_GLOBAL', None)
os.environ.update({k: ENV[k] for k in ('HOME', 'GIT_CEILING_DIRECTORIES', 'GIT_CONFIG_NOSYSTEM', 'GIT_ALLOW_PROTOCOL')})
os.environ.pop('GIT_CONFIG_GLOBAL', None)


def git(*args, at=BASE, check=True):
    return subprocess.run([REAL, *args], cwd=at, env=ENV, check=check, capture_output=True, text=True).stdout.strip()


git('init', '-q', '--bare', str(GH))
git('config', 'receive.advertisePushOptions', 'true', at=GH)
git('init', '-q', '-b', 'main', str(C))
git('commit', '-q', '--allow-empty', '-m', 'base', at=C)
git('remote', 'add', 'origin', str(GH), at=C)
git('commit', '-q', '--allow-empty', '-m', 'remote only', at=C)
git('push', '-q', 'origin', 'main', 'main:div', at=C)
git('reset', '-q', '--hard', 'HEAD~1', at=C)
git('commit', '-q', '--allow-empty', '-m', 'local only', at=C)  # main and div diverged: only a force push moves either
git('branch', 'div', at=C)
CONFIG = (C / '.git' / 'config').read_text()


def snap(at):
    return git('for-each-ref', '--format=%(refname) %(objectname)', at=at).splitlines()


START = {GH: snap(GH), C: snap(C)}
X0 = dict(line.split() for line in START[GH])


def restore():
    for at, start in START.items():
        now = snap(at)
        if now == start:
            continue
        keep = dict(line.split() for line in start)
        script = ''.join(f'delete {r}\n' for r in {x.split()[0] for x in now} - set(keep)) + ''.join(
            f'update {r} {o}\n' for r, o in keep.items())
        subprocess.run([REAL, 'update-ref', '--no-deref', '--stdin'], cwd=at, env=ENV, input=script, text=True, check=True)
    if (C / '.git' / 'config').read_text() != CONFIG:
        (C / '.git' / 'config').write_text(CONFIG)


def load(tree):
    for m in [m for m in sys.modules if m == 'wuwei' or m.startswith('wuwei.')]:
        del sys.modules[m]
    sys.path.insert(0, str(tree / 'cli'))
    gh, guards = importlib.import_module('wuwei.gh'), importlib.import_module('wuwei.guards')
    sys.path.pop(0)
    guards.TEMP = (str(BASE / 'nowhere'),)  # gh.git is no scratch remote: it stands for the code host
    guards.origin = lambda cwd: 'o/r'
    gh.default_branch = lambda repo: 'main'
    return guards


GUARDS = {'main': load(MAIN_T), 'head': load(HEAD_T)}
cmds = []
POSITIONS = ['git push {o} origin {t}', 'git push origin {o} {t}', 'git push origin {t} {o}']
TARGETS = ['div', 'div:div', 'refs/heads/div', 'main']
FLAGS = list('vqndu46')
BEFORE = [''] + FLAGS + [a + b for a, b in product(FLAGS, repeat=2)]
CLUSTERS = ['-' + b + 'f' + a for b, a in product(BEFORE, [''] + FLAGS)] + ['-' + b + 'fo' + v for b, v in
                                                                         product(['', '4', 'q6'], ['x', '=x', '.x', '/x'])]
FIVE = ['-4f', '-f4', '-6f', '-qf6', '-4vf', '-fo=x']
for c, p, t in product(CLUSTERS, POSITIONS, TARGETS):
    cmds.append(('cluster', p.format(o=c, t=t)))
for c, q, p in product(FIVE, ["'{}'", '"{}"', '\\{}'], POSITIONS):
    cmds.append(('spelling', p.format(o=q.format(c), t='div')))
for c, op, p in product(FIVE, ['true && {}', 'true ; {}', 'false || {}', '( {} )'], POSITIONS):
    cmds.append(('operator', op.format(p.format(o=c, t='div'))))
for b, p, t in product(BEFORE[1:], POSITIONS, ('div', 'main')):
    cmds.append(('plain', p.format(o='-' + b, t=t)))
for v, p in product(['-of', '-4of', '-o f', '-o -f'], POSITIONS):
    cmds.append(('value', p.format(o=v, t='div')))
cmds = list(dict.fromkeys(cmds))


def remote_ref(name):
    return git('rev-parse', '-q', '--verify', name, at=GH, check=False)


rows = []
for kind, command in cmds:
    dec = {k: g.bash(str(ROOT), command, str(C), 's1') for k, g in GUARDS.items()}
    LOG.write_text('')
    done = subprocess.run(['bash', '-c', command], cwd=C, env={**ENV, 'PATH': f'{BIN}:{ENV["PATH"]}'},
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    ran = any(line.startswith('push') for line in LOG.read_text().splitlines())
    forced = any((now := remote_ref(r)) and now != X0[r] for r in ('refs/heads/main', 'refs/heads/div'))
    moved = forced or not remote_ref('refs/heads/main')
    rows.append({'kind': kind, 'command': command, 'ran': ran, 'forced': forced, 'moved': moved, 'exit': done.returncode,
                 **{k: (d or {}).get('reason') for k, d in dec.items()}, **{k + '_refused': d is not None for k, d in dec.items()}})
    restore()
(BASE / 'rows.json').write_text(json.dumps(rows, indent=1))
FORCE = 'force push refused'
by = {}
for r in rows:
    k = by.setdefault(r['kind'], dict.fromkeys(('generated', 'ran', 'forced', 'moved', 'holes_head', 'holes_main', 'misread_head',
                                                'misread_main', 'newly_refused', 'newly_passed', 'reason_moved'), 0))
    k['generated'] += 1
    k['ran'] += r['ran']
    k['forced'] += r['forced']
    k['moved'] += r['moved']
    for t in ('head', 'main'):
        k['holes_' + t] += r['moved'] and not r[t + '_refused']
        k['misread_' + t] += r['forced'] and not (r[t] or '').startswith(FORCE)
    k['newly_refused'] += r['head_refused'] and not r['main_refused']
    k['newly_passed'] += r['main_refused'] and not r['head_refused']
    k['reason_moved'] += r['head'] != r['main']
print(json.dumps({'all': {n: sum(v[n] for v in by.values()) for n in next(iter(by.values()))}}))
for kind, v in by.items():
    print(kind, json.dumps(v))
for r in rows:
    if r['moved'] and not r['head_refused']:
        print('HOLE', r['kind'], r['command'])
