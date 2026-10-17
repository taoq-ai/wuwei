# Feature Specification: a shell fed its commands on stdin and a named-fd redirect meet the doors

**Feature branch**: `claude/shell-stdin`
**Item**: shell-stdin, tier full, goal G-2
**Input**: the lead's spike and generated probe found 586 commands that bash runs as `git push origin
main` (a stub `git` on PATH logged it) while `guards.bash` on main passed them. Two shapes cause
them: a shell that reads its commands from stdin (`bash <<< 'git push origin main'`, `echo ... | sh`)
and a named-fd redirect before the program (`{fd}>x git push origin main`).

## The promise in my words

1. A shell (`sh`, `bash`, `zsh`, `dash`) run without a `-c` body reads its commands from somewhere
   WUWEI does not see: a pipe, a here-string, `-s`, `< file` or a script path. `guards._unwrap` now
   returns that shell's segment plus `UNREAD`. The existing rule in `guards.bash` then refuses the
   command when its raw text names a door program, and passes it when it names none.
2. Bash reads `{name}` glued before a redirect operator (`{fd}>x`, `{a_b}<x`) as a redirect that
   opens a new fd, the way it reads `2` in `2>x`. `guards.segments` now drops `{name}` in the same
   spot it drops an fd number, so the program after it is the command and meets every door (push,
   merge, infra ask, leak check).

Out of scope: a script file that holds a door command while the command line names none
(`bash run.sh`; the guard is not a sandbox), and heredocs, which the multi-line rule already refuses.

The acceptance scenarios, restated:

1. Bash with a stub `git` on PATH logs `push origin main` for `{fd}>x git push origin main`,
   `{a_b}<x git push origin main`, `bash <<< 'git push origin main'`, `echo 'git push origin main' |
   bash`, `printf %s 'git push origin main' |& sh -s` and `env bash -s <<<"git push origin main"`,
   and `guards.bash` refuses each.
2. The generated probe (fd spellings x redirect operators x targets x positions, and shells x
   flags x feeders x quotes) runs every command under real bash with the stub `git` and through
   `guards.bash` at the head, and reports 0 holes.
3. `bash run.sh`, `echo hi | bash`, `bash -c 'echo hi'`, `echo {a,b}>x` and `diff <(sort a) <(sort
   b)` pass.
4. Every route in the suite's seat-command corpus and `tests/fixtures/routes.json` keeps its verdict.

## Clarifications

- Q: Does a shell with flags but no `-c` (`bash -e`, `bash -o pipefail`) count? A: yes. Any shell
  segment that `_unwrap` does not read as a `-c` body leaves `UNREAD`. This also closes
  `bash -o pipefail -c '...'`, where the option value hid the `-c` from the body scan.
- Q: Which `{name}` spellings are dropped? A: bash's own rule, a name (`[A-Za-z_]\w*`) in braces,
  glued before `<` or `>`, at the start of a word. `{a,b}>x` is brace expansion and stays a word.
- Q: Does a shell reached through a wrapper count (`env bash`, `command bash`, `xargs sh`)? A: yes,
  the wrapper rule already makes the shell the first program read.

## How this fails

1. A seat runs a script with a shell and then a door command in the same call (`bash
   scripts/check.sh && git push origin feature`). The call is now refused with the one-line hint.
   This is a false refusal, by design of the raw-text rule; the route corpus shows no recorded seat
   route has this shape.
2. The `{name}` pattern is too wide and drops a word that is not a redirect, so a real program name
   is skipped. Guarded by the lookbehind (start, space or an operator before it) and the name rule;
   `echo {a,b}>x` and `{fd}>x echo hi` pass in the tests.
3. A shell fed an infra write or a leaking network command (`bash <<< 'terraform apply'`,
   `echo 'curl -d <token> ...' | bash`) still passes: those checks read segments, not raw text, and
   the fed body is never read. This is unchanged from main (the probe shows equal counts on both);
   it is recorded as residual risk and a candidate item.

## Requirements

- FR-001: `_unwrap` returns `[(argv, targets), UNREAD]` for a shell segment without a `-c` body.
- FR-002: `segments` drops `{name}` before a redirect where it drops an fd number.
- FR-003: no change to `routes.json` verdicts; docs (design.md) name the new unreadable shape and
  the `{fd}>x` redirect; the vendored `guards.py` matches the tree.
- FR-004: runtime within the budget (+2 lines); measured +0 (2,976 after merging #1112).

## Breaking

Commands that passed on main are now refused: a command that runs a shell without `-c` and whose
text names a door program anywhere, for example `echo 'git push origin feature' | bash` or
`bash run.sh && gh pr view 5`.

Migration: run the door command in its own one-line Bash call (`git push origin feature`), and run
the script in a separate call. Commands that name no door program are unaffected. The PR title
carries `!` and the commit a `BREAKING CHANGE:` line.

## Assumptions

- No recorded seat route pipes text naming a door program into a shell or chains a script run with
  a door command. Why: the route corpus (168 routes) and the seat-command payload corpus keep every
  verdict at the head. Overturned if a corpus row moves from pass to refuse.
- `docs/site/concepts/doors.md` does not list the unreadable shapes, so only `docs/design.md`
  changes. Overturned if a later docs page lists them.
- No new `routes.json` row: the corpus records commands seats are told to run, and no source tells a
  seat to feed a shell on stdin. Overturned if a charter or skill adds such a command.

Rollback: revert the commit.
