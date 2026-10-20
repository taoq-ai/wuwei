"""Generated combinatorial probe for item push-refspecs, run under real bash with a stub git on PATH that logs each call and
then execs real git 2.43. The layout is WUWEI's: the main clone c on main (tracking origin/main, one commit ahead), a linked
worktree w on feature (one commit ahead of the remote's feature, so feature onto main is a fast-forward), a diverged branch div
for the force class, and the bare remote gh.git (push options advertised) that stands for the code host.

Classes (each from c and from w):
- refspec-quoted: sources x destination spellings, deletes, :, + refspecs, source-only words, glob pairs, x quoting (plain,
  single, double, backslash, $'..'); refspec-after-branch: the same words after a branch, plain and single-quoted.
- options: --all, --branches, --mirror, --tags, --prune, --delete and prefixes x before the remote, after it, last x tails.
- wrapped: cd, env -C, sudo -D and git -C into either clone (out of scope for a moved HEAD; kept as main's probe had them).
- valued: each option that takes the next word (-o, -vo, -qo, -uo, -4o, --push-option and prefixes, --repo and prefixes,
  --receive-pack, --exec, --recurse-submodules) x the word it takes (--tags, --no-tags, --all, --mirror, --branches, --, a
  remote, a branch) x tails x three positions; with -ox, --repo=x and -o=x as controls whose next word is not taken.
- option and no-option: every prefix of every push long option, and its --no- form, x tails x position.
- tags: pairs of --tags, --ta, --no-tags, --no-ta in each order x tails x position (the last one wins).
- refspec: worktree pseudo refs, remote-tracking, path classes (//, /../, /./, %xx, .lock, trailing /), negative refspecs, the
  tag keyword, +:, : x alone, after a branch, after --, with --prune, with -d.
- end-of-options: -- and --end-of-options before the remote, after it, after a refspec, last, with operands that start with a
  dash (refs/heads/-x at feature, -y a symbolic ref to main, -z at local main) and option-like operands.
- resolve: a source alone whose ref resolves to main, written before the call (a symbolic ref in refs/heads, refs/, refs/tags,
  a chain of two), another worktree's HEAD (main-worktree/HEAD, worktrees/w/HEAD), and controls that resolve to feature.
- valued-accepted (round 2): each valued option with a value git accepts (-o ci.skip, --repo origin or the remote's path,
  --receive-pack and --exec git-receive-pack, --recurse-submodules no, check, on-demand, only) x tails x three positions.
- rootref (round 2): a source alone that only the ref read finds, written before the call: root refs (ORIG_HEAD, FOO_HEAD, a
  .git/zz file), refs/remotes/<w> and refs/remotes/<w>/HEAD, the ambiguous origin (refs/heads/origin beside
  refs/remotes/origin/HEAD), refs/heads/HEAD, a name with @, a worktree whose id is not its folder's name; controls to feature.
- end-marker (round 2): two end markers in each order (only the first ends the options; a later one is a refspec, here a
  symbolic ref to main) x operands x positions, with -o and --repo taking the first marker.
- rootfile (round 3, the security gate's classes at aa63d3b): a root ref to main written as a file in each spelling git reads
  (ref: and a space, no space, a tab, 300 spaces, a symlink) x eight places (ZZ, zz, a/zz, x/y/ZZ, refs/bisect/x in the common
  folder; ZZ, refs/bisect/x and refs/worktree/x in w's folder) x three names (the name, main-worktree/, worktrees/w/).
- stopper (round 3): words git push may take that rev-parse cannot resolve, before a root ref to main (git push origin -- <word>
  ZZ), each with and without a branch of its name; a root ref named -- or -x; negative refspecs; a root ref beside a ref of its
  name; a lowercase name over a root ref.
- force: force spellings on the diverged branch (digit clusters are a known gap outside the item).
A hole: the guard passes and the remote's main moved, appeared or vanished (force class: div moved). Each command is read by
the guard of both trees, with guards.TEMP moved off the probe folder (gh.git is not a scratch remote) and the origin read as
o/r, default branch main.

Usage: python3 -I probe.py <main tree> <head tree> <empty folder> [class,...]
Prints per class: generated, ran (the stub logged a git push), holes at head and at main, regressions; then each hole."""
import importlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from itertools import product
from pathlib import Path

MAIN_T, HEAD_T, BASE = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]).resolve()
if BASE.exists():
    shutil.rmtree(BASE)
GH, C, W, HOME, ROOT, BIN = (BASE / n for n in ('gh.git', 'c', 'w', 'home', 'root', 'bin'))
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
git('push', '-q', 'origin', 'main', 'main:feature', 'main:f/x', at=C)
git('switch', '-q', '-c', 'div', at=C)
git('commit', '-q', '--allow-empty', '-m', 'remote div', at=C)
git('push', '-q', 'origin', 'div', at=C)
git('reset', '-q', '--hard', 'main', at=C)
git('commit', '-q', '--allow-empty', '-m', 'local div', at=C)  # div diverged: only a force push moves the remote's div
git('switch', '-q', 'main', at=C)
git('fetch', '-q', 'origin', at=C)
git('branch', '-q', '--set-upstream-to=origin/main', 'main', at=C)
git('commit', '-q', '--allow-empty', '-m', 'ahead on main', at=C)  # every push that names main moves it
git('branch', 'f/main', at=C)  # refs/heads/f/* onto refs/heads/* reaches main
git('branch', 'f/x', 'origin/f/x', at=C)
git('tag', 'v1', at=C)
git('worktree', 'add', '-q', '-b', 'feature', str(W), 'origin/feature', at=C)
git('branch', '-q', '--unset-upstream', 'feature', at=W)
git('commit', '-q', '--allow-empty', '-m', 'ahead on feature', at=W)  # feature onto main is a fast-forward
CONFIG = (C / '.git' / 'config').read_text()


def snap(at):
    return git('for-each-ref', '--format=%(refname) %(objectname)', at=at).splitlines()


START = {GH: snap(GH), C: snap(C)}
X0 = dict(line.split() for line in START[GH])


PLANTED = ('ORIG_HEAD', 'FOO_HEAD', 'zz', 'ZZ', '--', '-x', 'foo', 'a', 'x', 'refs/bisect', 'refs/worktree', 'worktrees/w/ZZ',
           'worktrees/w/zz', 'worktrees/w/refs/bisect', 'worktrees/w/refs/worktree')


def restore():
    for name in PLANTED:  # root refs and folders a rootref, rootfile or stopper setup wrote
        p = C / '.git' / name
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink(missing_ok=True)
    if (BASE / 'w3').exists():
        git('worktree', 'remove', '-f', '-f', str(BASE / 'w3'), at=C)
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
cmds = []  # (class, setup run before the guard reads, command)


def add(kind, command, setup=''):
    cmds.append((kind, setup, ' '.join(command.split())))


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
for w in WORDS:
    for q in QUOTES.values():
        add('refspec-quoted', f'git push origin {q(w)}')
    for q in ('plain', 'single'):
        add('refspec-after-branch', f'git push origin feature {QUOTES[q](w)}')
OPTS = ['--all', '--al', '--a', '--branches', '--bra', '--b', '--mirror', '--mirr', '--m', '--tags', '--follow-tags', '--prune',
        '--delete', '-d', '--atomic', '--no-verify', '-o x', '--push-option=x', '-q', '--no-all']
TAILS = ['', 'feature', 'main', 'heads/main', "'refs/heads/*:refs/heads/*'", 'refs/heads/f/*:refs/heads/f/*', ':', 'feature:feature',
         'feature:heads/main', 'f/x']
for o, t in product(OPTS, TAILS):
    for form in ('git push {o} origin {t}', 'git push origin {o} {t}', 'git push origin {t} {o}'):
        add('options', form.format(o=o, t=t))
for f, d, w in product(['cd {D} && git push origin {W}', 'env -C {D} git push origin {W}', 'sudo -D {D} git push origin {W}',
                        'git -C {D} push origin {W}'], (C, W),
                       ('heads/main', 'feature:refs/heads/main', 'refs/heads/./main', 'refs/heads//main', ':', "'refs/heads/*'", '--all')):
    add('wrapped', f.replace('{D}', str(d)).replace('{W}', w))
VALUED = ['-o', '--push-option', '--push', '--pu', '--repo', '--rep', '--receive-pack', '--rece', '--exec', '--e', '-vo', '-qo', '-uo',
          '-4o', '--recurse-submodules', '--recurse', '-ox', '--repo=x', '-o=x']
TAKEN = ['--tags', '--ta', '--tag', '--no-tags', 'x', 'origin', '--all', '--mirror', '--branches', '--', '--end-of-options',
         'feature', 'main', 'HEAD']
for v, s, t in product(VALUED, TAKEN, ['', 'feature', 'main', 'HEAD', 'feature:feature']):
    for form in ('git push {v} {s} origin {t}', 'git push origin {v} {s} {t}', 'git push origin {t} {v} {s}'):
        add('valued', form.format(v=v, s=s, t=t))
NAMES = ['verbose', 'quiet', 'repo', 'all', 'branches', 'mirror', 'delete', 'tags', 'dry-run', 'porcelain', 'force',
         'force-with-lease', 'force-if-includes', 'recurse-submodules', 'thin', 'receive-pack', 'exec', 'set-upstream', 'progress',
         'prune', 'verify', 'follow-tags', 'signed', 'atomic', 'push-option', 'ipv4', 'ipv6']
for p in sorted({n[:i] for n in NAMES for i in range(1, len(n) + 1)}):
    for t in ('', 'feature', 'main', ':'):
        add('option', f'git push --{p} origin {t}')
        add('option', f'git push origin {t} --{p}')
    for t in ('', 'feature'):
        add('no-option', f'git push --no-{p} origin {t}')
for a, b in product(['--tags', '--ta', '--no-tags', '--no-ta'], repeat=2):
    for t in ('', 'feature', 'main', 'HEAD'):
        for form in ('git push {a} {b} origin {t}', 'git push {a} origin {t} {b}', 'git push origin {t} {a} {b}'):
            add('tags', form.format(a=a, b=b, t=t))
SRCS2 = ['feature', 'HEAD', '@', 'main', 'main-worktree/HEAD', 'worktrees/w/HEAD', 'refs/remotes/origin/main', 'origin/main',
         'remotes/origin/main', 'v1', 'main-worktree/refs/heads/main', 'worktrees/w/refs/heads/main']
DSTS2 = ['main', 'heads/main', 'refs/heads/main', 'HEAD', '@', 'refs/remotes/origin/main', 'remotes/origin/main', 'origin/main',
         'main-worktree/HEAD', 'worktrees/w/HEAD', 'refs/heads//main', 'refs/heads/x/../main', 'refs/heads/%6dain',
         'refs/heads/main.lock', 'refs/heads/main/', 'refs/heads/./main', 'main-worktree/refs/heads/main']
WORDS2 = list(dict.fromkeys(SRCS2 + [s + ':' + d for s in SRCS2 for d in DSTS2] + [':' + d for d in DSTS2] + ['+' + s for s in SRCS2]
                            + ['+feature:' + d for d in DSTS2]
                            + ["'refs/heads/*'", "'refs/heads/*:refs/heads/*' '^refs/heads/main'", "'^refs/heads/main' :",
                               "'refs/heads/f/*:refs/heads/*' '^refs/heads/f/main'", "'^main'", "'^refs/heads/main'", '+:', ':',
                               'tag v1', 'tag main', 'tag feature:main', 'tag :main', 'tag v1:main', 'tag @:main',
                               "'refs/*:refs/*'", "'refs/remotes/origin/*:refs/heads/*'", "'refs/remotes/*:refs/remotes/*'"]))
for w in WORDS2:
    for form in ('git push origin {w}', 'git push origin feature {w}', 'git push origin -- {w}', 'git push --prune origin {w}',
                 'git push -d origin {w}'):
        add('refspec', form.format(w=w))
DASH = 'git update-ref refs/heads/-x refs/heads/feature && git symbolic-ref refs/heads/-y refs/heads/main && git update-ref refs/heads/-z main'
for m, w in product(['--', '--end-of-options'], ['-x:main', '-x:heads/main', '-x:refs/heads/main', '-x', '-y', '-z', '-x:feature',
                                                  '-z:main', '-y:-y', '--all', '--tags', '--mirror', '-f', 'main', ':']):
    for form in ('git push origin {m} {w}', 'git push {m} origin {w}', 'git push origin feature {m} {w}', 'git push origin {m} feature {w}',
                 'git push origin {w} {m}', 'git push {m} origin'):
        add('end-of-options', form.format(m=m, w=w), DASH)
SYMREFS = {'git symbolic-ref refs/heads/x refs/heads/main': ['x', 'heads/x', 'refs/heads/x', 'x:x', 'x:refs/heads/x', 'x:main'],
           'git symbolic-ref refs/x refs/heads/main': ['refs/x', 'refs/x:refs/x'],
           'git symbolic-ref refs/tags/t refs/heads/main': ['t', 'tags/t', 'refs/tags/t'],
           'git symbolic-ref refs/heads/y refs/heads/main && git symbolic-ref refs/heads/z refs/heads/y': ['z', 'heads/z'],
           'git symbolic-ref refs/heads/f2 refs/heads/feature': ['f2', 'heads/f2', 'f2:f2'],
           '': ['main-worktree/HEAD', 'worktrees/w/HEAD', 'main-worktree/HEAD:feature', 'worktrees/w/HEAD:feature', 'HEAD', '@']}
for setup, names in SYMREFS.items():
    for n in names:
        add('resolve', f'git push origin {n}', setup)
        add('resolve', f'git push origin feature {n}', setup)
ACCEPTED = {('-o', '--push-option', '--pu', '-vo', '-qo'): ['ci.skip'], ('--repo', '--rep'): ['origin', str(GH)],
            ('--receive-pack', '--rece', '--exec', '--e'): ['git-receive-pack'],
            ('--recurse-submodules', '--recu'): ['no', 'check', 'on-demand', 'only']}
for spellings, values in ACCEPTED.items():
    for v, s, t in product(spellings, values, ['', 'feature', 'main', 'HEAD', 'feature:feature']):
        for form in ('git push {v} {s} origin {t}', 'git push origin {v} {s} {t}', 'git push origin {t} {v} {s}'):
            add('valued-accepted', form.format(v=v, s=s, t=t))
WT2 = f'git worktree add -q -f {BASE / "w2"} main && mv {BASE / "w2"} {BASE / "w3"} && git worktree repair {BASE / "w3"}'
ROOTREFS = {'git symbolic-ref ORIG_HEAD refs/heads/main': ['ORIG_HEAD'], 'git symbolic-ref FOO_HEAD refs/heads/main': ['FOO_HEAD'],
            "printf 'ref: refs/heads/main\\n' > .git/zz": ['zz'], 'git symbolic-ref refs/remotes/zr refs/heads/main': ['zr', 'remotes/zr'],
            'git symbolic-ref refs/remotes/zq/HEAD refs/heads/main': ['zq', 'remotes/zq/HEAD'],
            'git symbolic-ref refs/heads/origin refs/heads/main && git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main':
                ['origin', 'heads/origin'],
            'git symbolic-ref refs/tags/main refs/heads/feature': ['main', 'tags/main'], WT2: ['worktrees/w2/HEAD', 'worktrees/w3/HEAD'],
            'git symbolic-ref refs/heads/a@b refs/heads/main': ['a@b'], 'git symbolic-ref refs/heads/HEAD refs/heads/main': ['HEAD']}
for setup, names in ROOTREFS.items():
    for n, form in product(names, ('git push origin {n}', 'git push origin feature {n}', 'git push origin -- {n}', 'git push -u origin {n}',
                                   'git push origin {n} --dry-run', 'git push --tags origin {n}', 'git push origin {n}:')):
        add('rootref', form.format(n=n), setup)
ENDS = 'git symbolic-ref refs/heads/--end-of-options refs/heads/main && git symbolic-ref refs/heads/-- refs/heads/main && ' + DASH
for a, b, w in product(['--', '--end-of-options'], ['--', '--end-of-options'], ['', '-x:main', '-y', 'feature']):
    for form in ('git push origin {a} {b} {w}', 'git push {a} origin {b} {w}', 'git push origin feature {a} {b} {w}', 'git push -o {a} {b} origin {w}',
                 'git push --repo {a} {b} origin {w}', 'git push origin {a} {w} {b}'):
        add('end-marker', form.format(a=a, b=b, w=w), ENDS)
SPELLINGS = ["printf 'ref: refs/heads/main\\n' > {f}", "printf 'ref:refs/heads/main' > {f}", "printf 'ref:\\trefs/heads/main\\n' > {f}",
             "printf 'ref:%300srefs/heads/main\\n' > {f}", 'ln -s refs/heads/main {f}']
PLACES = ['ZZ', 'zz', 'a/zz', 'x/y/ZZ', 'refs/bisect/x', 'worktrees/w/ZZ', 'worktrees/w/refs/bisect/x', 'worktrees/w/refs/worktree/x']
for spelling, place in product(SPELLINGS, PLACES):
    name = place.removeprefix('worktrees/w/')
    setup = f'mkdir -p {os.path.dirname(".git/" + place)} && ' + spelling.format(f='.git/' + place)
    for form in ('{}', 'main-worktree/{}', 'worktrees/w/{}'):
        add('rootfile', f'git push origin {form.format(name)}', setup)
ZZ = "printf 'ref:refs/heads/main' > .git/ZZ && git tag t1"
STOP = ['--', '--end-of-options', '-', '-x', '--git-dir', '--all', '-n', 'tag', '@', 'HEAD', 'ORIG_HEAD', 'FETCH_HEAD', '@{-1}', '@{0}',
        '.', '..', 'refs/heads/f/*', '*', 'main~0', 'main^0', 'feature@{0}', 't1', 'nope', git('rev-parse', 'feature', at=C), 'a..b',
        'x/', '/x', 'a b', '', 'refs/heads/feature', 'heads/feature', 'feature', '^feature', '^nope', 'feature^!', 'HEAD:', ':/a',
        '@@', 'x.lock', 'main-worktree/HEAD', 'FOO_HEAD']
for word, planted in product(STOP, (False, True)):
    plant = f' && (git update-ref refs/heads/{shlex.quote(word)} refs/heads/feature || true)' if planted and word else ''
    add('stopper', f'git push origin -- {"tag t1" if word == "tag" else shlex.quote(word)} ZZ', ZZ + plant)
ROOT = "printf 'ref: refs/heads/main\\n' > .git/"
for setup, command in [(ROOT + '--', 'git push origin -- --'), (ROOT + '-- && git update-ref refs/heads/x refs/heads/feature', 'git push origin -- x --'),
                       (ROOT + '--', 'git push origin -- feature --'), (ROOT + '-x', 'git push origin -- -x'),
                       (ZZ + ' && git update-ref refs/heads/-- refs/heads/feature', 'git push origin -- -- ZZ'),
                       (ZZ, "git push origin '^refs/heads/nope' ZZ"), (ZZ, "git push origin '^refs/heads/f/*' ZZ"),
                       (ZZ, 'git push origin ^feature ZZ'), (ZZ, 'git push origin tag v1 ZZ'), (ZZ, "git push origin 'refs/heads/f/*' ZZ"),
                       (ROOT + 'foo && git update-ref refs/foo refs/heads/main', 'git push origin foo'),
                       (ROOT + 'FOO_HEAD && git update-ref refs/heads/FOO_HEAD refs/heads/feature', 'git push origin FOO_HEAD'),
                       ("printf 'ref: refs/heads/feature\\n' > .git/ZZ && git symbolic-ref refs/heads/ZZ refs/heads/main", 'git push origin ZZ'),
                       (ROOT + 'ZZ && git update-ref refs/heads/ZZ refs/heads/feature', 'git push origin ZZ'),
                       (ZZ, 'git push origin zz'), (ROOT + "zz && printf 'ref: refs/heads/feature\\n' > .git/worktrees/w/zz", 'git push origin zz')]:
    add('stopper', command, setup)
FORCE = ['-f', '-4f', '-f4', '-6f', '-vf', '-uf', '-qf6', '-4vf', '-nf', '--force', '--forc', '--force-w', '--force-with-lease',
         '--force-i', '--fo', '--f', '-o f', '--no-force', '--mirror', '--mirr', '-df', '--force-with-lease=div',
         '--force-with-lease=div:', '--force-if-includes']
for f, t in product(FORCE, ('div', 'div:div', 'div:refs/heads/div', 'refs/heads/div')):
    add('force', f'git push {f} origin {t}')
    add('force', f'git push origin {t} {f}')
for t in ('+div', '+div:div', "'+refs/heads/d*:refs/heads/d*'"):
    add('force', f'git push origin {t}')
cmds = [c for c in dict.fromkeys(cmds) if len(sys.argv) < 5 or c[0] in sys.argv[4].split(",")]


def remote_ref(name):
    return git('rev-parse', '-q', '--verify', name, at=GH, check=False)


rows = []
for where, cwd in (('c on main', C), ('w on feature', W)):
    for kind, setup, command in cmds:
        if setup:
            subprocess.run(['bash', '-c', setup], cwd=C, env=ENV, check=True, capture_output=True)
        dec = {k: (g.bash(str(ROOT), command, str(cwd), 's1') or {}).get('decision') for k, g in GUARDS.items()}
        LOG.write_text('')
        done = subprocess.run(['bash', '-c', command], cwd=cwd, env={**ENV, 'PATH': f'{BIN}:{ENV["PATH"]}'},
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        ran = any(' push ' in f' {line} ' or line.startswith('push') for line in LOG.read_text().splitlines())
        main_moved = remote_ref('refs/heads/main') != X0['refs/heads/main']
        div_moved = remote_ref('refs/heads/div') != X0['refs/heads/div']
        bad = main_moved or (kind == 'force' and div_moved)
        rows.append({'kind': kind, 'cwd': where, 'setup': setup, 'command': command, 'main': dec['main'], 'head': dec['head'],
                     'ran': ran, 'bad': bad, 'exit': done.returncode})
        restore()
(BASE / 'rows.json').write_text(json.dumps(rows, indent=1))
by = {}
for r in rows:
    k = by.setdefault(r['kind'], dict.fromkeys(('generated', 'ran', 'holes_head', 'holes_main', 'regressions', 'fixed'), 0))
    k['generated'] += 1
    k['ran'] += r['ran']
    k['holes_head'] += r['bad'] and r['head'] is None
    k['holes_main'] += r['bad'] and r['main'] is None
    k['regressions'] += r['bad'] and r['head'] is None and r['main'] is not None
    k['fixed'] += r['bad'] and r['main'] is None and r['head'] is not None
print(json.dumps({'all': {n: sum(v[n] for v in by.values()) for n in next(iter(by.values()))},
                  'head_refused_main_unmoved_exit_0': sum(r['head'] is not None and not r['bad'] and r['exit'] == 0 for r in rows),
                  'newly_refused_unmoved_exit_0': sum(r['head'] is not None and r['main'] is None and not r['bad'] and r['exit'] == 0
                                                      for r in rows),
                  'newly_passed': sum(r['head'] is None and r['main'] is not None for r in rows)}))
for kind, v in by.items():
    print(kind, json.dumps(v))
for r in rows:
    if r['bad'] and r['head'] is None:
        print('HOLE', 'regression' if r['main'] is not None else 'existing', r['kind'], r['cwd'], r['setup'] and f'[{r["setup"]}]', r['command'])
