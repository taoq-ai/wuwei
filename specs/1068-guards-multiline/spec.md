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
- An unquoted heredoc whose body runs `$(...)` or backticks is read as commands: sh runs them.
- Several heredocs on one line are read in order, each body starting where the last ended. Once one
  body cannot be dropped, it and every later body on that line are read as commands.
- No heredoc starts inside an arithmetic `((` or `$((`: `echo $((1<<EOF))` is a shift, and the next
  line is a command.
- A quoted heredoc keeps a trailing backslash in its body literal, so its delimiter still ends it.
- A `#` that starts a word begins a comment to the end of the line; `owner/repo#42` stays a word (#1038).

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

## Assumptions

- A heredoc body line is read literally when matching its delimiter, even for an unquoted delimiter
  where sh would join a trailing backslash. Overturned by a case where that ends a body early and
  hides a command; ending early only reads more lines as commands, so it fails closed.
- Arithmetic depth is tracked in the scan itself, outside quotes and comments: `((` opens and `))`
  closes, never below zero. A `))` that closes a nested `$(...)` (`$(a $(b))`) does not count against
  a later heredoc. A mispaired `)))` still nets to zero.
- `gh pr create` text inside a heredoc body now triggers the PostToolUse PR note when the output
  also holds a PR URL. That note is advice only.
