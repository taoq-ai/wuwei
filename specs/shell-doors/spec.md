# Feature Specification: process substitution, glued separators, $'...' quoting and ledger paths without a trailing slash meet the doors

**Feature branch**: `claude/shell-doors`
**Item**: shell-doors, tier full, goal G-2
**Input**: a stub `git` on PATH shows bash runs `git push origin main` for `cat <(git push origin
main)`, `echo >(git push origin main)`, `true;>x git push origin main`, `true&&(git push origin
main)`, `x=1;(git push origin main)`, `git push origin $'main'` and `git push origin $"main"`.
`guards.bash` on main passed all seven, and passed `rm -rf .wuwei/ledger`, `mv .wuwei/ledger x`,
`cp x .wuwei/ledger` and `rm -rf .wuwei`, because `LEDGER` needed a trailing `/` or `.jsonl`.

## The promise in my words

Allow the plain shapes WUWEI can read; never chase spellings.

1. `shlex` hands back a run of the characters `();<>|&` as one word (`<(`, `;>`, `&&(`, `);`).
   `guards.segments` splits such a word into the operators sh reads, so each part reaches its own
   door: the push after `<(` or `;>` is a segment of its own and meets the push door. `|&` joins
   `CONTROL` as a pipe. A word that could not be split into known operators would be unreadable;
   with every single character an operator, every such word splits. `_unwrap` reads every redirect
   operator the split yields (`<`, `<>`, `>&`, `<&`, `&>>`, `<<<` beside `>`, `>>`, `>|`, `&>`), and
   an fd number glued before a redirect (`2>&1`, `2>/dev/null`) is dropped as sh drops it, so the
   program after a redirect is the command.
2. A command with `$'...'` or `$"..."` quoting outside other quotes is unreadable (`segments` puts
   `UNREAD` first), so the existing rule refuses it when it names a door program and passes it when
   it names none. Its segments are still read, so the leak, infrastructure and ledger checks run.
3. `LEDGER` matches `.wuwei/ledger` and `.wuwei/ledger.jsonl` with or without a trailing slash, and
   `.wuwei` itself, also spelled with `//` or `/./`, at the start of a word or after `/` or `=`, as
   a writer argument, a redirect
   target or an edit path. The ledger entry in `DOOR_WORDS` also matches bare `.wuwei`, so the
   multi-line rule and the hook's fail-closed path cover `rm -rf .wuwei`.

Out of scope, recorded gaps: a ledger write after `cd .wuwei` (cwd is not tracked), a glob such as
`rm -rf .wuwei/*`, a symlink, a quote glued before the path, `install`, `find -delete`, `git clean`,
and wrappers beyond those `guards.py` lists.

The acceptance scenarios, restated:

1. For each of the seven shapes, bash with a stub `git` on PATH logs `push origin main`, and
   `guards.bash` refuses the command: the first five by the push door, the `$'` and `$"` ones as
   unreadable.
2. `diff <(sort a) <(sort b)` and `echo $'a\tb'` pass: no door program is named.
3. `rm -rf .wuwei/ledger`, `mv .wuwei/ledger x`, `cp x .wuwei/ledger`, `rm -rf .wuwei` and
   `rm -rf /abs/path/.wuwei/ledger` are refused as ledger writes; `cat .wuwei/ledger/x.jsonl` and
   `ls .wuwei` pass.
4. Every pre-existing row of `tests/fixtures/routes.json` keeps its verdict.

## Clarifications

### Session 2026-10-17

- Q: Refuse a punctuation-only word as unreadable, as the promise words it, or split it? A: Split
  it. The allowlist spike showed refusing falsely refuses `x=$(gh pr view 5 --json state); echo
  $x` and `r=$(wuwei evidence o/r#5); [ "$r" = ok ] && gh pr merge 5 --squash`, which breaks the
  #1038 test `test_a_pr_reference_does_not_hide_the_rest_of_the_command`. Splitting sends each part
  to its real door, which refuses every acceptance shape too.
- Q: Does `$'` inside other quotes count? A: No. `"it's $'x'"` and `grep '$"'` hold a literal
  `$'` or `$"`; bash does no ANSI-C or locale quoting there. The check scans quote spans left to
  right the way sh does and counts only a `$'` or `$"` that opens a span. A main-style check on the
  raw text falsely refused one traced seat command (`grep -rln '\$"' ...` with a door word).
- Q: Does `|&` count as a separator? A: Yes. On main `true |& git push origin main` was one
  command; bash reads `|&` as a pipe of stdout and stderr, so the push is its own command.
- Q: Should the ledger rule read `of=.wuwei/ledger.jsonl`? A: Yes. The promise names `dd`, whose
  target comes after `of=`; the rule now accepts `=` before `.wuwei` as well as `/` and the word
  start, at no extra line.
- Q: (gates at 67b367a) Does an unreadable `$'` command skip the other doors? A: It did: `segments`
  returned None, so `curl -H $'Authorization: token ghp_...'` passed the leak check and `terraform
  apply $'x'` skipped the infrastructure ask. Now `segments` keeps the segments and puts `UNREAD`
  first, so the door-word refusal and every per-segment check both apply.
- Q: (security gate at 67b367a) Do the split redirects reach `_unwrap`? A: They did not: `<x git push
  origin main`, `>&2 git push origin main` and `&>>x git push origin main` passed while bash pushed.
  The redirect tuple now holds every operator the split yields, and the fd number of `2>&1` is
  dropped before the lexer, at no extra line.
- Q: Is bare `.wuwei` a door word? A: Yes, as the lead asked: `.wuwei` not followed by another path
  character (`.wuwei`, `.wuwei/`), so `.wuwei/plan.json` and `.wuwei.bak` stay ordinary.

## How this fails

1. A seat runs a multi-line command that names `.wuwei` (`cd /repo/.wuwei && python3 -c "...` over
   several lines) and is refused by the multi-line rule. Two of 2,435 traced Bash commands in
   `.wuwei/traces.jsonl` move this way. The refusal names the fix: one line, or a script file.
2. A seat copies workspace files into a dry-run tree (`cp plan.json dry/.wuwei/`) or passes the
   `.wuwei` directory to a Python script, and is refused as a ledger write. One traced command
   (`python3 -I rows.py /home/user/wuwei/.wuwei`) moves. The fix is to name the file
   (`dry/.wuwei/plan.json`).
3. A redirect operator `_unwrap` does not know hides the program after it: the word after the
   operator becomes the command and the door program becomes an argument. The security gate at
   67b367a showed this for `<x git push origin main` and `>&2 git push origin main`; bash pushed
   while the guard passed. The redirect tuple now lists every operator in `OPS` that takes a word,
   and the redirect tests pin each one. A new operator added to `OPS` without the tuple would
   reopen it.

## User scenarios

### US1: a push behind punctuation or `|&` meets the push door (P1)

Acceptance 1. Tests in `tests/test_guards.py`: `test_a_push_glued_to_punctuation_meets_the_push_door`,
`test_a_door_command_glued_to_punctuation_or_quoting_a_dollar_reaches_its_door`.

### US2: `$'` and `$"` quoting naming a door is unreadable (P1)

Acceptance 1, 2. Tests: `test_dollar_quoting_in_a_command_naming_a_door_is_unreadable`,
`test_everyday_shell_shapes_pass`.

### US3: every ledger spelling is a ledger write (P1)

Acceptance 3. Tests: `test_a_ledger_path_without_a_trailing_slash_is_a_ledger_write`,
`test_an_edit_of_a_ledger_path_without_a_file_name_is_refused`, and in `tests/test_hook.py` the
fail-closed cases `rm -rf .wuwei` and `rm -rf .wuwei/`, with `cat .wuwei/plan.json` and
`ls .wuwei.bak` failing open.

### US4: the route corpus holds (P1)

Acceptance 4. `test_every_route_reads_as_recorded` with 27 new rows.

## Requirements

- FR-001: `segments` splits a word made only of `();<>|&` into the operators sh reads (`OPS`);
  `|&` is in `CONTROL`; `_unwrap` reads every redirect operator, and a glued fd number is dropped.
- FR-002: `segments` puts `UNREAD` first when `$'` or `$"` opens a quote span outside other
  quotes, and still returns every segment.
- FR-003: `LEDGER` matches `.wuwei`, `.wuwei/ledger` and `.wuwei/ledger.jsonl`, each with an
  optional trailing `/`, and any path under `.wuwei/ledger/`, after the word start, `/` or `=`;
  `//` and `/./` count as `/`.
- FR-004: the ledger entry of `DOOR_WORDS` matches `.wuwei/ledger` and bare `.wuwei`.
- FR-005: routes.json gains a row per new shape naming its source; docs, SECURITY.md and
  `.claude/` follow.

## Breaking

Commands that passed on main and are now refused:

- A door command behind process substitution or a glued separator (`cat <(git push origin main)`,
  `true;>x git push origin main`, `true |& git push origin main`): each now meets its door, which
  refuses or passes it on its own terms.
- Any command naming a door program that uses `$'...'` or `$"..."` quoting outside other quotes.
- A writer (`rm`, `mv`, `cp`, `tee`, `dd`, `chmod`, `ln`, `shred`, `truncate`, `sed -i`, python)
  or redirect naming `.wuwei`, `.wuwei/`, `.wuwei/ledger`, `.wuwei/ledger.jsonl` (with or without a
  trailing slash, with `//` or `/./`), also after `=`; an edit of such a path. This includes
  read-only shapes: `cp file dir/.wuwei/`, `cp -r .wuwei /tmp/bk`, `python3 script.py
  <path>/.wuwei` and `python3 -m pytest .wuwei`.
- A door command after a redirect: `<x git push origin main`, `2>&1 git push origin main`, `git
  2>/dev/null push origin main` now meet the push door.
- A multi-line command naming bare `.wuwei` or `.wuwei/`.

Migration: run a door command in its own plain one-line call, with plain quotes (`'main'`, not
`$'main'`). Name the file when copying into a `.wuwei/` tree (`cp plan.json dry/.wuwei/plan.json`)
or pass a script the file it reads. To copy the workspace out, name the files or use `tar` or
`rsync` (`tar -cf /tmp/bk.tar .wuwei`); run tests on a path inside it (`pytest .wuwei/tests`) or from
inside the directory. Put a multi-line script that reads `.wuwei` in a file written
with Write. No pre-existing row in `tests/fixtures/routes.json` changes its verdict.

## Assumptions

- No seat route puts a door program inside process substitution or `$'...'` (none in routes.json
  or the 2,435 traced Bash commands). Overturned if the corpus moves a recorded route.
- The change is breaking by the rule "commands that passed on main now refused", though every
  moved shape is a door bypass or a ledger write spelling. Overturned if the owner reads the
  guards' refusals as outside the outward contract.
- Splitting a punctuation run into sh's operators (maximal munch over `OPS`) reads it as sh does,
  so no punctuation word is refused as unreadable, unlike the promise's wording. Every character of
  `();<>|&` is an sh operator, so the split only adds segments. Overturned if a probe shows sh
  reading a run as one word, or the planner keeps the promise's refusal.
- The `$'` check leaves a backslash-escaped `\$'` to sh's reading (an escaped `$`, then a quote).
  Overturned if a probe shows sh reading it as ANSI-C quoting.

Rollback: revert the commit; no data, config or schema changes.
