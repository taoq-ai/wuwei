# Feature Specification: the Bash doors read a multi-line command, a heredoc and an unbalanced quote

**Feature Branch**: `claude/1068-guards-multiline`
**Created**: 2026-10-16
**Status**: Ready
**Input**: WUWEI plan item 1068 (issue taoq-ai/wuwei#1068), tier full.

## The promise in my words

Today `guards.segments()` treats a newline as plain whitespace and gives up on any command shlex
cannot tokenize. A second-line `git push --force` or `gh pr create` then reaches no door. After this
change sh's own line rules decide: a newline outside quotes ends a command, a backslash-newline joins
two lines before anything is split, and a heredoc body is data. A heredoc fed to sh, bash, zsh or
dash is read as commands. A command that still cannot be tokenized is refused when its raw text names
a door program (git push, gh pr, gh api, gh repo, wuwei hook, the ledger path), and the refusal names
the unreadable command as the reason. Anything else that cannot be read passes, as before.

The runtime stays at 3,000 lines: the lines come out of guards.py and hook.py.

## User scenarios and testing

### User story 1: a door program on a later line meets its door (P1)

**Acceptance scenarios**:

1. **Given** `true\ngit push --force origin x`, **when** the Bash door reads it, **then** the force-push door refuses.
2. **Given** `cat > b.md <<'EOF'\nit's done\nEOF\ngh pr create -F b.md` and the gates missing at the branch head, **when** the Bash door reads it, **then** the create door reads the create and refuses.
3. **Given** `git push \\\n  --force origin x`, **when** the Bash door reads it, **then** the force-push door refuses.
4. **Given** `bash <<'EOF'\ngit push --force origin x\nEOF`, **when** the Bash door reads it, **then** the force-push door refuses.

### User story 2: an unreadable command naming a door stays shut (P1)

1. **Given** an unclosed quote in a command that also runs `gh pr merge 5`, **when** the Bash door reads it, **then** it refuses and names the unreadable command as the reason.

### User story 3: ordinary work still passes (P1)

1. **Given** `git commit -m "a\nb" && git push origin feature`, **when** the Bash door reads it, **then** the quoted newline stays in the message and nothing is refused.
2. **Given** an ordinary multi-line command with no door program, including one with an unbalanced apostrophe, **when** the Bash door reads it, **then** nothing is refused.
3. **Given** the change, **when** the suite runs, **then** the runtime size test still passes at 3,000 lines or fewer.

### Edge cases

- A heredoc that never ends is read as commands, not dropped (an arithmetic `$((1<<2))` or a `<<` in
  text must not hide the lines after it).
- An unquoted heredoc whose body runs `$(...)` or backticks, or holds a backslash-newline, is read as
  commands: sh expands it, and joins the continuation before it compares a line with the delimiter.
- Once a body cannot be dropped (its terminator is missing, or it is unquoted and expands), no later
  heredoc starts, so each command is scanned in linear time.
- Several heredocs on one line are read in order, each body starting where the last ended. Once one
  body cannot be dropped, it and every later body on that line are read as commands.
- From the first unquoted opener, no heredoc body is dropped for the rest of the command. The
  openers are `((` (which covers `$((`), `${`, `[` joined to the character before it (`$[`, `a[`,
  `([`), `=(` and `+=(` (a compound array, where `[k<<EOF ]` is a subscript) and the extglob groups
  `?(`, `*(`, `+(`, `@(`, `!(`. They are read from the text sh reads, so a backslash-newline
  between their two characters does not hide them. bash 5.2 reads the `<<`
  in `$((1<<EOF))`, `$[1<<EOF]`, `${x:1<<EOF }` and `a[1<<EOF ]=x` as a shift and runs the next
  line. The flag is one-way, so no paren shape can turn body dropping back on.
- Accepted cost, pinned by a test: a heredoc whose body names a door, after a closed `$((..))` or a
  `${..}`, is refused. The lead's spike found 1 such command in 506 real commands.
- A quoted heredoc keeps a trailing backslash in its body literal, so its delimiter still ends it.
- A `#` that starts a word begins a comment to the end of the line; `owner/repo#42` stays a word (#1038).
  After an opener no comment is skipped, since `${x:- #}` holds a `#` that is not a comment.
- A token made only of `();|&` and backticks separates commands, so `` x=`date`; git push `` and
  `true;(git push ...)` meet their doors.
- Nested shell heredocs too deep to read raise `RecursionError`, which is refused like an unreadable
  command when it names a door.

## Requirements

- **FR-001**: `segments()` ends a command at a newline outside quotes and heredoc bodies.
- **FR-002**: a backslash-newline outside single quotes is removed before tokenizing.
- **FR-003**: a heredoc body is one data word; it is read as commands when the heredoc feeds sh, bash, zsh or dash.
- **FR-004**: `segments()` raises `ValueError` on a command shlex cannot tokenize; `bash()` refuses it when the raw text names a door program and passes it otherwise. The refusal names the way out for a PR body (`gh --body-file`) and a commit message (`git commit -F`).
- **FR-005**: the module docstring no longer says an unreadable command passes.
- **FR-006**: the runtime stays at most 3,000 lines.

Out of scope: python -c and other interpreter bodies, here-strings, any new door, a heredoc piped
into a shell (`cat <<EOF | sh`).

## Clarifications

### Session 2026-10-16

- Q: The PostToolUse hook also called `segments()`. Once it raises, must the hook change? A: Yes. It
  now finds `gh pr create` with a regular expression on the raw command, so an unreadable command
  that ran records no hook error.
- Q: How is the raw-text door match scoped? A: Only commands shlex cannot tokenize meet it, so a
  broad pattern (`git ... push`, `gh ... pr|api|repo`, `wuwei ... hook`, `.wuwei/ledger`) fails
  closed without touching readable commands.
- Q: Backticks? A: Outside quotes a backtick now separates commands, so a backtick substitution in a
  command or an unquoted heredoc body meets its door. Zero added lines; fail closed.

- Q (fix round 1): the quality and security gates showed two bypasses at ee252d7. A quoted second
  heredoc on a line covered an unquoted first one, and an arithmetic `<<` started a heredoc. How are
  they closed? A: bodies are read in order and the scan stops dropping at the first body it cannot
  drop. A `<<` counts as a heredoc only when the `((` before it are all closed.

- Q (fix round 2): the gates showed the round 1 check counted `((` and `))` in raw text, so a `))`
  in quotes or a comment cancelled a real `((`. A: the depth lives in the `_lines` loop, which knows
  the quote state and skips comments; the four gate inputs are tests.
- Q (redesign after fix round 2, approved by the owner): the depth counter mis-paired `))` that
  closed single parens or nested `$( )` (`$(((1)) <<EOF )`, `$(( $(echo $(echo 1))<<EOF ))`), and
  `$[`, `${` and `a[` were not tracked at all. A: a one-way flag replaces the counter; a paren stack
  was rejected because a mis-pop reopens body dropping, the failure class of both fix rounds.
- Q (redesign fix round 1): the gates showed a compound-array subscript, an extglob group, an opener
  split by a backslash-newline, a backtick merged with `;` by shlex, an unquoted body joined by a
  backslash-newline, a `#` inside `${...}`, deep nesting and a quadratic rescan. A: openers are read
  as two characters from the text sh reads, with `=(` and the extglob groups added; a separator is
  any token of `();|&` and backticks; an unquoted body with a backslash-newline is not dropped;
  comments are skipped only before an opener; `RecursionError` is refused; a missing body sets the
  flag. Real bash 5.2.21 with logging stand-ins for git, gh, wuwei and rm ran the door line in each
  refusing input.

## Assumptions

- A quoted heredoc body line is read literally when matching its delimiter. An unquoted body that
  holds a backslash-newline is not dropped at all, so the join sh makes there cannot end it early.
- The expansion flag is set only outside quotes and comments. A `[` after whitespace (`[ -f x ]`)
  does not set it. `[[` does: its second `[` is joined to the first, so a heredoc after `[[ ... ]]`
  is read as commands. A joined `[` in a glob or a format string (`foo[1]`, `--format=[%h]`) sets it
  too. Each of these can only add refusals.
- `=(` sets the flag, so an ordinary array assignment (`a=(1 2)`) stops later body dropping. That is
  the accepted cost of reading `a=( [1<<EOF ]=x )`, where bash runs the next line. Overturned by
  measured refusals on real commands outweighing the bypass.
- The refusal cannot tell whether the flag made the command unreadable, so it always names the third
  way out: give a heredoc that follows an expansion, an array or `((` its own Bash call.
- `gh pr create` text inside a heredoc body now triggers the PostToolUse PR note when the output
  also holds a PR URL. That note is advice only.
