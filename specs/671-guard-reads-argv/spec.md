# Feature Specification: the git and gh guard reads the executed command, not prose

**Feature Branch**: `671-guard-reads-argv`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #671, "fix(guards): the git and gh guard reads the executed command,
not prose: words in a brief body or a heredoc are text, and a split string that runs git is
still caught". Owner, 2026-10-10 (item 36): the guard refused a shepherd brief because its
body said "falls back to gh" in plain prose, and a builder heredoc for the same reason, while
a probe that split a string ran git past it.

## Root cause (read and reproduced on main, 66b3720)

The orchestrator notes named for this issue do not exist, so the failures were reproduced
read-only in throwaway workspaces (the `tests/test_parser_warns.py` and
`tests/test_commit_push.py` fixtures, VCS faked, each posture), calling the guards and
`commands.hook.run` in process:

| Probe | Result on main |
| --- | --- |
| `cat > brief.md <<'EOF'`, body `Raise the PR with gh pr create; then git push.` | strict: exit 2 `unparsed: ...`; observe and guarded: runs with a `guard.would_refuse` warning from `commit_push` |
| `cat > brief.md <<'EOF'`, body `The shepherd falls back to gh pr list.`, repository cwd | `pr.check` returns `(2, 'unparsed: ...')` |
| `echo 'falls back to gh'`, `grep -n 'git push' notes.md` | `normalize` raises `unaccounted git/gh mention` (the guards pass them only because the classifier calls them read-only) |
| `sh -c "gi""t commit --no-verify -m x"`, `eval 'gi''t commit --no-verify -m x'`, `sh -c "gi""t push"` | strict: exit 2 `could not run: unaccounted git/gh mention`; observe and guarded: runs, warning `opaque: unaccounted git/gh mention; ... it ran with this warning` |
| `gi\` newline `t commit --no-verify -m x`, `g\` newline `h pr merge 5 --admin` | exit 0 in every posture, strict included, no warning: no guard looks at it |
| `x=git; $x push` | every guard exit 2 `could not run: unaccounted git/gh mention`; below strict the hook lowers it to the opaque warning |
| `g""it push` | already resolved: `commit_push` refuses it as it refuses `git push` |

1. **Prose is read as a command.** `cli/wuwei/shell.py` `_parse` lines 320-325 reject any
   git or gh word in a here-doc body whose owner is not `git` or `gh`, and `_unwrap` lines
   494-495 reject any git or gh word in the arguments of every program that is not a
   guarded one. `cat`, `echo`, `grep` and the other readers never run their text, yet the
   call raises `ParseError`. `shell.unread` (line 993) then finds the call not read-only (it
   writes `brief.md`) and unparsed, and returns `UNPARSED`: strict refuses it, observe and
   guarded record a warning.
2. **A quote-split name inside `sh -c` or `eval` is refused as unreadable instead of read.**
   The parser already resolves `g""it` to `git` (`_word`, line 202), and the recursive parse
   of a shell script or eval string resolves it the same way, but `_unwrap` raises first:
   lines 453-454 (`eval`) and 482-485 (`sh -c`) reject a split name before the recursion.
   Each guard returns exit 2, and `commands/hook.py` `posture` (line 298) lowers a
   publish-area exit 2 whose call `shell.unreadable` cannot read to the opaque warning below
   strict (design 4.5, #530), so a `--no-verify` commit or an identity override runs.
3. **A line continuation hides the program name from every guard.** `shell.mentions`
   (line 99) removes quotes and backslashes but keeps the newline, so `g\` newline `h` never
   matches `gh`. Every git and gh guard decides relevance with `mentions` first and returns
   0, while the shell joins the continuation into `gh` and the parser resolves it too
   (`[['gh', 'pr', 'merge', '5', '--admin']]`). This passes under strict.
4. **A variable-built name is unreadable and unnamed.** `x=git; $x push` raises at the
   assignment (`_unwrap` line 427) or at the nonliteral command name (line 436); the reason
   says "unaccounted git/gh mention", and below strict the hook lowers it to the opaque
   warning.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Whose text is data? A: A reader's, by the shared `shell.reads(argv)` (the `READ_ONLY`
  words, `sed -n Np`, `find` without an action, read-only `wuwei` calls), the rule #471
  applied to owner-command mentions in `protect_state`. Its arguments and the here-doc body
  it reads are text.
- Q: "Only an argument to a reader or a Write": what is the Write? A: A reader's output
  redirected to a file (`cat > brief.md <<'EOF'`, `echo ... > notes.md`). The Write tool
  never reaches a Bash guard.
- Q: Can a reader's text still reach something that runs it? A: Only through another
  command of the same call: a pipe into `sh`, `xargs -I@ sh -c @`, an interpreter, or a
  script the call writes and then runs. So the rule is per call, as in #471: the text is
  data only when every command the call runs is a reader or a guarded program (`git`, `gh`
  and a guard's extra `protected` names, whose argv the guards judge themselves). With any
  other command in the call, every git or gh word in that text raises exactly as today.
- Q: Which constructed names are resolved? A: Those the text fixes statically: quotes
  (`g""it`, already), a line continuation, the literal string of `eval`, and the literal
  script of `sh -c` (and `bash`, `zsh`, `dash`, `ksh`, `busybox sh`). The recursive parse
  returns the real argv and each guard judges it as if typed plainly: allowed when the plain
  command is allowed, refused with the plain command's reason otherwise.
- Q: And a name built from a variable (`$x` holding git)? A: Named, not resolved. Its value
  at run time depends on shell state the parser cannot evaluate soundly (a skipped or
  conditional assignment, a subshell, an inherited `$SHELL`, `IFS`), and resolving it to
  one value could turn a call strict refuses today into a pass. It stays unparsed and
  refused; when an assignment in the same call gives the variable a value that builds git
  or gh, the refusal names that command and the hook no longer lowers it to the opaque
  warning.
- Q: Where is the resolved command named? A: Once, in the hook, for every Bash refusal: a
  last line `resolved: git push` when the call runs a git or gh command its text does not
  spell plainly. The guards' own reasons stay (a resolved push already says `run git push
  origin HEAD:refs/heads/<branch>`).
- Q: Does `mentions` change role? A: No. It stays the conservative relevance check, also
  for owner words in data (`merge`, `WUWEI_SEAT_ROLE`, the CLI groups). It only joins line
  continuations before matching, as the shell does.

## User Scenarios and Testing

### User Story 1 - Prose about git or gh in a brief or heredoc is written (Priority: P1)

A planner writes a shepherd brief, or a builder writes notes, with a quoted here-doc to a
file. The body says the shepherd "falls back to gh", or mentions `gh pr create` and
`git push` in prose. The call runs in every posture with no refusal and no warning.

**Why this priority**: it is the reported false refusal; under strict it stops the work.

**Independent Test**: the hook in process on the call, in a workspace at each posture.

**Acceptance Scenarios**:

1. **Given** a heredoc whose body says "falls back to gh", **When** `cat > brief.md
   <<'EOF'` runs through the hook under observe, guarded and strict, **Then** exit 0 and no
   `guard.would_refuse` event.
2. **Given** a body that also says `Raise the PR with gh pr create; then git push.`,
   **When** the same call runs, **Then** exit 0 in every posture.
3. **Given** `echo 'falls back to gh' > notes.md`, `grep -rn "gh pr" docs | head -20` or
   `git status; cat <<'EOF'` with a body naming `git push`, **When** `shell.normalize` reads
   it, **Then** it returns the argv and raises nothing.
4. **Given** the same text fed to something that can run it (`| sh`, `| python3`,
   `| xargs -I@ sh -c @`, `awk`, `watch`, a `python3` here-doc), **When** `normalize` reads
   it, **Then** it raises `ParseError` as today, and the hook result is unchanged.

---

### User Story 2 - A split string that runs git is caught as git (Priority: P1)

A probe builds the program name from pieces. The guards judge the command it runs, and the
refusal names it.

**Why this priority**: it is the reported bypass; the continuation form passes under strict.

**Independent Test**: `normalize` and `constructed` on each form; the commit/push and PR
guards on their fixtures; the hook in process for the reason.

**Acceptance Scenarios**:

1. **Given** `g""it push` or `sh -c "gi""t push"`, **When** the guards run, **Then** the call
   is refused as `git push`: `normalize` returns `[['git', 'push']]`, `commit_push` returns
   what it returns for plain `git push` (`(1, 'name the remote and the branch: ...')`), and
   the hook's reason ends with `resolved: git push`.
2. **Given** `eval 'gi''t commit --no-verify -m x'` or `sh -c "gi""t commit --no-verify -m
   x"`, **When** `commit_push` runs, **Then** it returns `(1, 'disabling commit hooks is
   refused; ...')`, as for the plain command.
3. **Given** `g\` newline `h pr merge 5 --admin`, **When** the hook runs it under each
   posture, **Then** it is refused with `admin merge is refused; ...` and the reason ends with
   `resolved: gh pr merge`; and `mentions('gi\\\nt push', {'git'})` is true.
4. **Given** a resolved form the plain command allows (`sh -c "gi""t push origin
   HEAD:refs/heads/feature"` with recorded evidence), **When** `commit_push` runs, **Then**
   it returns `(0, '')`, as for plain `git push origin HEAD:refs/heads/feature`.
5. **Given** `x=git; $x push` or `x=gi; ${x}t commit --no-verify -m x`, **When** the hook
   runs in each posture, **Then** it gets the exit plain `git push` gets in that posture,
   never the opaque warning, and a refusal's reason ends with `resolved: git push` (or
   `resolved: git commit`).

### Edge Cases

- `tee`, `printf` and `cat <<'EOF' | tee f` are not readers; their text keeps today's rule.
  Write files with `cat > file <<'EOF'` or the Write tool.
- A reader in a call that also runs a non-reader (`mkdir -p d && cat > d/x.md <<'EOF'`):
  today's rule for the whole call.
- Comments, redirect targets (`> git.log`), assignment values, wrapper options
  (`sudo -u git`), `find git -exec`, `command -v git` and the extra arguments of `sh -c`
  keep today's rule: none is a reader's text.
- `sh -c 'echo git'hub` and `eval 'echo git'hub` now parse to `echo github`: the source
  mention was data printed by `echo`.
- `$(printf git) push` and a name read from a file stay opaque and keep the opaque warning
  below strict (design 4.5); nothing in the call assigns them.
- `bin/wuwei ... --prompt '... gh ...'` is not a reader (only read-only `wuwei` calls are);
  unchanged.

## Requirements

### Functional Requirements

- **FR-001**: `shell.mentions` MUST remove a backslash-newline before matching, so a name
  split by a line continuation is relevant to every guard.
- **FR-002**: `shell.normalize` MUST NOT raise for a git or gh word in a reader's
  arguments, or in a here-doc body whose owner is not `git` or `gh`, when every command of
  the call is a reader (`shell.reads(argv)`) or a guarded program (`git`, `gh`, the caller's
  `protected` names). In any other call those words MUST raise `ParseError` as today.
- **FR-003**: `shell.normalize` MUST resolve a git or gh name split by quotes in an `eval`
  string or a `sh -c` script and return the resolved argv, instead of raising before the
  recursive parse.
- **FR-004**: `shell.constructed(command)` MUST return the git and gh commands a call runs
  under a name its text does not spell plainly (`git <verb>`, `gh <group> <verb>`, joined by
  `; `), else `''`: from `normalize`'s argv when the call parses, and otherwise from a
  variable-built program word (`$x`, `${x}`, `${x}t`) whose values from assignments in the
  same call build `git` or `gh`.
- **FR-005**: `shell.unreadable` MUST return `''` when `constructed` names a command, so
  `hook.posture` keeps that refusal at its area's level instead of the opaque warning.
- **FR-006**: The hook MUST end a PreToolUse Bash refusal's reason with a line `resolved:
  <constructed>` when `constructed` names a command.
- **FR-007**: Everything else in `normalize` MUST stay: the mention checks on comments,
  redirect targets, assignments, wrapper options, `xargs`, `command -v`, the extra `sh -c`
  arguments, the hidden-mention check of line 337, ANSI-C quoting, nonliteral command names,
  and every guard's own rules.
- **FR-008**: Invariant I41 in design 9.2 and `tests/test_invariants.py`: a Bash call is
  judged by what it runs: prose in a reader's text never refuses an all-reader call, a git
  or gh name built by quotes, a line continuation, `eval` or `sh -c` is judged as the plain
  command, and a variable-built one is refused naming it.
- **FR-009**: `docs/site/security.md` says what is text and what is resolved, beside the
  `unparsed` paragraph.

### Key Entities

- **Reader**: a command `shell.reads(argv)` accepts; it prints or redirects its text and
  runs none of it.
- **Constructed command**: a git or gh command whose program word the text does not spell
  plainly.

## Success Criteria

- **SC-001**: Any prose about git and gh can be written to a file with `cat > file <<'EOF'`
  under strict with no refusal.
- **SC-002**: No quote, continuation, `eval` or `sh -c` form of a refused git or gh command
  runs without the refusal its plain form gets, in any posture.
- **SC-003**: Every refusal of a constructed git or gh command names the command it runs.

## Assumptions

- The orchestrator notes named for this issue do not exist; the root cause was reproduced
  from the issue text in throwaway fixture workspaces, not in a named dry-run workspace.
- "Write" in the issue means a reader's output redirected to a file. The Write tool is not a
  Bash call and no git or gh guard reads it.
- The owner's "probe that split a string" is one of the reproduced forms: the line
  continuation passed under strict, the quote split inside `sh -c` and `eval` passed below
  strict.
- The reader set is `shell.reads` as it is; widening it (`tee`, `printf`) is not asked.
- Naming happens once in the hook for every guard, not in each guard's reason.
- The next free invariant id is I41; if another item lands I41 first, this one takes the
  next free id.
- The owner message relayed with this run (items 29 to 31: merge soak, merge check wording,
  launch registration) does not describe this issue; this spec follows issue #671 (item 36).

## Deferred

- A variable-built name is named and refused, never resolved and judged. A sound resolver
  needs the call's control flow and the inherited environment; file it only if a seat needs
  `x=git; $x status` to pass.
