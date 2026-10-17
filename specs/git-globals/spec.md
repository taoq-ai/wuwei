# Feature Specification: git options before the subcommand are read by allowlist

**Feature branch**: `claude/git-globals`
**Item**: git-globals, tier full, goal G-2
**Input**: the records builder found that `guards.bash` skips git global options one word at a time
except `-C`, `-c`, `--git-dir` and `--work-tree`, so an option that takes its value as the next word
hides the subcommand. Real git 2.43 pushed `git --config-env core.abc=Y push origin main` to main of
a local bare remote and the guard on main passed it.

## The promise in my words

1. In the git branch of `guards.bash`, the options git 2.43 reads with a separate value (`-C`, `-c`,
   `--git-dir`, `--work-tree`, `--namespace`, `--config-env`, `--attr-source`, `--shallow-file`)
   take the next word. The options with no value, and the `--opt=value` forms, take one word. So the
   word after them is the subcommand git runs, and a push to the default branch meets the push door.
2. A word before the subcommand that is not an option git 2.43 takes is unknown. When any later word
   is `push`, the command is refused, and the text names the option and the route (run git push
   without it).
3. The records rule for `git clean` keeps its own allowlist: any option before `clean` other than
   `-C <dir>` still refuses it.

Addition to the promise (named in the PR): a `-c` or `--config-env` before the subcommand that sets
`alias.*`, `remote.*`, `branch.*`, `url.*`, `include*` or `push.default` (section names in any case)
is refused whatever the subcommand. The item's aim is that a push to the default branch meets the
push door whatever global options come first. Under real git 2.43, `git -c alias.p=push p origin main`,
`git -c remote.origin.push=HEAD:main push origin`, `git -c remote.origin.mirror=true push origin`,
`git -c include.path=<file> push origin` and `git -c push.default=upstream -c branch.feature.merge=refs/heads/main
-c branch.feature.remote=origin push origin feature` each moved main, and the guard on main passed
each. An alias runs a command the guard never reads (a `!` body can spell push any way), so every
command-line alias refuses, not only one whose value names push. This is the shortest closed rule.

The acceptance scenarios, restated:

1. Real git against a local bare remote records whether `git --config-env core.abc=Y push origin
   main`, `git --namespace x push origin main` and `git --attr-source HEAD push origin main` push to
   main; `guards.bash` refuses each.
2. A generated probe of every git 2.43 global option (separate and `=` values, alone and in pairs,
   plus the `-c` steering forms) x push targets (main, a feature branch, no refspec, an alias) runs
   under real git; at the head every command that moved main is refused (0 holes), and every feature
   push with known options only passes.
3. `git -C sub push origin feature`, `git -c user.name=x push origin feature`, `git --no-pager log`
   and `git --version` pass.

Outside (the item's Outside): wrappers that change directory or environment (`env -C`, `sudo -D`),
the cd stand-in class, git config written before the call, and `GIT_CONFIG_*` environment variables.

## Clarifications

- Q: Which options does git 2.43 take, and with which value forms? A: read from real git 2.43 (each
  option before `status`): separate value only `-C`, `-c`, `--shallow-file`; separate or `=`
  `--git-dir`, `--work-tree`, `--namespace`, `--config-env`, `--attr-source`; `=` only
  `--exec-path=`, `--list-cmds=`; no value `-p`, `-P`, `--paginate`, `--no-pager`, `--bare`,
  `--no-replace-objects`, `--literal-pathspecs`, `--no-literal-pathspecs`, `--glob-pathspecs`,
  `--noglob-pathspecs`, `--icase-pathspecs`, `--no-optional-locks`, `--exec-path`, `--html-path`,
  `--man-path`, `--info-path`, `-h`, `--help`, `-v`, `--version`. git 2.43 answers
  `unknown option` to `--super-prefix`, `--shallow-file=x`, `-cfoo=bar`, `-c=a.b=c`, `-Csub`,
  `--list-cmds`, `--no-advice` and `--no-lazy-fetch`.
- Q: The promise lists `--super-prefix` as a valued option. A: git 2.43 removed it, so it is
  unknown: refused before a push. That covers older git, where it took a value and pushed, and
  costs nothing on 2.43, where it errors.
- Q: Why `push.default` and not every `push.*` key? A: of the push keys, only `push.default` decides
  which remote branch a push without a refspec writes (with `upstream` it pushes to the branch's
  upstream, which `git checkout -b x origin/main` sets to main). `push.autoSetupRemote`,
  `push.followTags` and the rest change nothing about the target, and seats may use them.
- Q: Does an unknown option refuse without a push? A: no (the promise). `git --frobnicate status`
  passes; git itself fails on it.

## How this fails

1. A seat route sets a steering key on the command line (`git -c push.default=current push`,
   `git -c remote.origin.url=... fetch`) and is now refused. Guarded by the route corpus: no
   recorded route moves, and the refusal names the option and says to run without it.
2. A seat on a newer git uses an option git 2.43 does not have (`--no-advice`, `--no-lazy-fetch`)
   before a push and is refused. The failure is over-refusal, never a hole; the text names the
   option.
3. A valued option read as one word would hide the subcommand again. Guarded by reading git 2.43
   for each option and by the probe: 0 holes over 6,478 commands, and a future valued option
   is unknown, so it is refused before a push. Holes that stay: git config written before the
   call, and `GIT_CONFIG_*` in the environment (listed in SECURITY.md).

## Requirements

- FR-001: `GIT_OPTS` holds git 2.43's options; the git branch takes two words for a valued option.
- FR-002: an unknown option before a push is refused, naming it and the route.
- FR-003: a steering `-c` or `--config-env` is refused whatever the subcommand.
- FR-004: the `git clean` allowlist keeps its verdicts (its tests and corpus rows hold).
- FR-005: routes.json gets the acceptance rows; every older row keeps its verdict.
- FR-006: runtime within +2 lines; measured 2,996 (net 0) by tightening existing lines.
- FR-007: the option loop stays linear: 125 KB of options reads in under 0.2 s.

## Breaking

Commands that passed on main are now refused:

- a push after a valued git option (`--config-env`, `--namespace`, `--attr-source`, `--shallow-file`)
  to the default branch (the bypass);
- any git command after a `-c` or `--config-env` that sets `alias.*`, `remote.*`, `branch.*`,
  `url.*`, `include*` or `push.default` (`git -c alias.st=status st`);
- a command naming `push` after an option git 2.43 does not take (`git --no-advice push origin x`,
  `git --super-prefix x push`).

Migration: run git push without the option; set aliases and push configuration in git config
(outside an agent session) rather than on the command line. The PR title carries `!` and the
commit a `BREAKING CHANGE:` line.

## Assumptions

- The valued global options are those git 2.43's git.c reads with a separate word, as read from
  real git 2.43. Overturned if a probe on a newer git shows another option pushing (it would be
  unknown, so refused before a push, unless it appears without `push`).
- The steering key list closes what decides a push target from the command line: `remote.*`
  (push, url, pushurl, mirror, pushDefault), `branch.*` (merge, remote, pushRemote), `url.*`
  (insteadOf), `include*` (a file of any of these), `push.default`, and `alias.*`. Overturned if a
  probe finds another key that moves main.
- No recorded seat route uses a steering `-c` or an unknown option before push: the route corpus
  keeps every verdict. Overturned if a corpus row moves.
- `push.recurseSubmodules` and `submodule.recurse` push submodule commits to the submodules'
  remotes, other repositories; left outside.
- The steering refusal is told apart from the unknown one by its two words (the option and its
  value); an unknown option word holding a space is refused as steering, which only refuses more.

Rollback: revert the commit; no data or config migrates.
