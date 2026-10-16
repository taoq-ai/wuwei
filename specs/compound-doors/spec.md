# Feature Specification: the doors read a command inside a loop or if body, after shell flags, and after a wrapper's options

**Feature branch**: `claude/compound-doors`
**Item**: compound-doors, tier full, goal G-2
**Input**: main's Bash guards split a command at `;`, `&&`, `|` and the like, then read the first
word of each piece as the program. A piece that starts with a shell reserved word (`do`, `then`,
`{`) names that word as the program, so `for pr in 1 2; do gh pr merge $pr; done` never meets the
merge door. `bash -lc '...'` is not unwrapped because only a bare `-c` is. After a wrapper, the
guards skip words that start with `-`, so the option argument in `nice -n 10 git push --force`
(`10`) becomes the program.

## The promise in my words

Three readings change in `guards._unwrap`, and nothing else in the doors:

1. Leading shell reserved words that open a body (`do`, `then`, `else`, `elif`, `if`, `while`,
   `until`, `!`, `{`) are dropped like a leading `VAR=value`, so the command after them is the one
   the doors read.
2. A shell (`sh`, `bash`, `zsh`, `dash`) whose options before the first plain word hold a
   single-dash cluster with `c` (`-c`, `-lc`, `-ec`, or `-e -c`) has that plain word read as its
   `-c` body.
3. After a wrapper (env, nice, timeout, stdbuf, sudo, xargs, nohup, command, exec, time) the
   command starts at the first word that names a program a door reads (git, gh, wuwei, a shell, an
   infrastructure tool, a network tool, a file writer, sed or python). The wrapper's own option
   arguments no longer stand in for the program.

The diff to `cli/wuwei/` is net zero lines or fewer.

The acceptance scenarios, restated:

1. `for pr in 1 2; do gh pr merge $pr; done`: the merge door reads `gh pr merge` and refuses, since
   it has no PR evidence.
2. `if true; then git push --force origin x; fi`, the same in a `while` loop, a brace group
   `{ ...; }` and after `!`: the force-push door refuses each.
3. `bash -lc 'git push --force origin x'` and `sh -ec 'gh pr merge 5'`: the matching door refuses.
4. `timeout 60 gh pr merge 5`, `nice -n 10 git push --force origin x` and
   `env -u GH_TOKEN gh pr merge 5`: the matching door reads the wrapped command.
5. `for f in *.md; do wc -l $f; done` and `if [ -f x ]; then echo ok; fi`: nothing refused.
6. The runtime size test still passes at 3,000 lines or fewer.

## Clarifications

### Session 2026-10-16

- Q: Which program names count for the first-program rule? A: Every program a door in `bash`
  reads: git, gh, wuwei, the shells, the infrastructure tools, the network tools, the file writers,
  sed and any name starting with `python`. The promise lists git, gh, wuwei, shells and
  infrastructure tools; the other names keep the ledger and leak doors reading what main read after
  a wrapper (`env FOO=1 rm .wuwei/ledger/x`, `nice -n 5 python3 x .wuwei/ledger.jsonl`).
- Q: What if no such program follows the wrapper? A: The command stays as written with the wrapper
  as its program. No door reads that program, so it passes, as a command naming no door does today.
- Q: Does the first-program rule apply after a reserved word or a `VAR=value`? A: No. Those are
  dropped one word at a time, so `do echo "git push --force"` stays an `echo`. Only a wrapper jumps
  ahead, because only a wrapper takes option arguments.
- Q: Does an unreadable `sh -c` body now reach the raw-text rule of #1077? A: Yes, as the arch gate
  on item 1068 recommended. When the nested `segments` returns `None`, `_unwrap` returns the
  marker segment `UNREAD` (no argv, one placeholder target) in its place. `bash` applies the
  raw-text rule when it sees the marker, so `bash -c "echo it's; gh pr merge 5 --admin"` is refused
  with the one-line hint. The readable outer segments still reach the leak, infra and other doors
  (coordinator, before gates: an earlier head returned `None` for the whole text, and
  `curl -d <canary> x && bash -c "echo it's"` passed where main refused it). An unreadable body
  naming no door program still passes.
- Q: Are `fi`, `done`, `}` and `esac` dropped too? A: Not needed. They close a body and stand alone
  after a separator, so they read as a program no door reads.
- Q: Which words does the first-program search after a wrapper skip? A: Every word that starts
  with `-` or holds `=` (fix round 1, arch and security gates). Without this, `env
  GIT_SSH=/usr/bin/ssh git push --force` stopped at the assignment, whose base name is `ssh`, and
  lost the push door that main applied. The gates' main-vs-head script now reports 0 regressions
  in 130 commands.
- Q: Is this a breaking change? A: Yes, to the Bash door's outward behavior. Newly refused: a door
  command inside a loop, an if, a brace group, after `!`, in a `bash -lc` body, or after a
  wrapper's options; an over-read such as `nohup echo git push origin main`; and an unreadable
  `sh -c` body inside a command whose text names a door program. The migration is the one the
  refusal already gives: run the door command in its own one-line Bash call, without a wrapper.

## User Scenarios & Testing

### User Story 1: a door inside a loop, an if or a brace group meets its door (Priority: P1)

**Independent test**: acceptance 1 and 2, plus `elif`, `else`, `until` and `if git push ...` forms,
are refused with the matching door's reason.

### User Story 2: a shell with combined flags is unwrapped (Priority: P1)

**Independent test**: `bash -lc`, `sh -ec`, `bash -e -c` and a loop inside a `bash -c` body are
refused by the matching door; an unreadable `bash -c` body naming `gh pr` is refused with the hint.

### User Story 3: a wrapper's options hide nothing (Priority: P1)

**Independent test**: `timeout 60`, `nice -n 10`, `env -u GH_TOKEN`, `stdbuf -oL`, a chain
`sudo -u ci env A=1 timeout 5` and `xargs -n 1 sh -c` reach the wrapped door.

### User Story 4: ordinary loops, ifs and wrapped commands pass (Priority: P1)

**Independent test**: acceptance 5, a `while read` loop, a brace group with a redirect, `! grep`,
`bash -lc 'make test'`, `timeout 60 git push origin feature` and `env -u GH_TOKEN gh pr view 5`
pass.

### Edge Cases

- `if ! git push --force ...`: both `if` and `!` are dropped.
- `bash -c` with no body word: not unwrapped, as on main.
- `bash --login -c '...'`: `--login` is skipped, `-c` matches.
- A redirect in the middle of a command still gives its target and keeps the words after it.

## Requirements

### Functional Requirements

- **FR-001**: `_unwrap` drops leading `VAR=value` words and the reserved words `do`, `then`,
  `else`, `elif`, `if`, `while`, `until`, `!`, `{`.
- **FR-002**: after a leading wrapper, `_unwrap` starts the command at the first word whose base
  name is in `READ` or starts with `python`, skipping words that start with `-` or hold `=`; with
  none, the command is unchanged.
- **FR-003**: a shell whose dash options before the first plain word include a single-dash cluster
  with `c` has that word read as its body.
- **FR-004**: an unreadable `sh -c` body leaves the `UNREAD` marker segment; `bash` applies the
  raw-text rule to a command holding it and reads every other segment as before.
- **FR-005**: `WRAPPERS` adds `timeout` and `stdbuf`.
- **FR-006**: `cli/wuwei/` changes by net zero lines or fewer.

## Success Criteria

- **SC-001**: every acceptance scenario has a passing test in tests/test_guards.py.
- **SC-002**: the suite passes with the runtime at 3,000 lines, as on main since #1081.

## Assumptions

- A wrapper followed by a program no door reads, whose arguments name one (`nohup echo git push
  origin main`), is read as that named program and may be refused. Assumed rare and cheap: the
  session drops the wrapper. Overturned if the audit shows such refusals in real sessions.
- The redirect loop in `_unwrap` is rewritten in three lines with the same behavior to keep the
  diff net zero. A test pins a mid-command redirect.

## Residual (recorded in SECURITY.md)

Not read on one line: `eval`, input piped or fed to a shell (`| sh`, here-strings), a variable as
the program name, `$(...)` inside double quotes, process substitution, ANSI-C quoting, a separator
glued to a redirect or pipe (`>;`, `|&`), quote splicing inside a word, a function body
(`f() { ...; }`, `function f { ...; }`), `coproc`, `builtin command`, unquoted backticks, a shell
option before `-c` that takes an argument or is not a single-dash cluster (`bash -o pipefail -c`,
`+e -c`, `-O extglob -c`, `--rcfile f -c`), wrappers outside the list (`setsid`, `flock`,
`ionice`), and a wrapper option whose value names a read program (`sudo -u gh gh pr merge 5`,
`env -C /x/git git push`). The text of an unreadable `sh -c` body inside a readable command meets
only the door-word rule, not the leak scan.

## How this fails

1. The first-program rule reads too far: `time echo gh pr merge 5` or `xargs printf git push origin
   main` is refused, and a session that prints commands through a wrapper is blocked until it drops
   the wrapper.
2. A wrapper not in the list (`setsid git push --force`) or a shell option with an argument
   (`bash -o pipefail -c 'git push --force'`) still hides the door: the gate probes find it and it
   stays residual.
3. A caller of `segments` other than `bash` (the PostToolUse `gh pr create` check) ignores the
   marker: it has no argv, so it reads as no command. A future caller that indexes targets could
   mistake the placeholder for a file; the marker's text names what it is. An earlier head of this
   branch raised instead and hid the outer segments from the leak door; tests now pin a canary and
   `terraform apply` beside an unreadable body.
4. Breaking: sessions that wrote door commands inside loops, ifs or `bash -lc`, or through a
   wrapper with options, are now refused where main let them pass, including over-reads such as
   `nohup echo git push origin main`. A session that relied on those shapes must split the door
   command into its own call.
