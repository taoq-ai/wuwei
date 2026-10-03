# Feature Specification: a command the parser cannot read warns instead of falling to the publish floor, and read-only commands are never opaque

**Feature Branch**: `347-parser-warns`

**Created**: 2026-10-03

**Status**: Draft

**Input**: GitHub issue #347, "fix(guards): a command the parser cannot read warns instead of
falling to the publish floor, and read-only commands are never opaque". Evidence: the
owner's second first-day trial (2026-10-03, development build of 0.12.0, posture observe):
the planner's reads were refused eleven times before its first decision; the day logged
`hook.refusal` x27 and `guard.would_refuse` x15. Main is ed28ab4 (v0.12.0).

## Root cause (read and reproduced on main)

Reproduction (read-only, in a throwaway workspace under the session scratchpad; the notes
name no dry-run workspace): a workspace with seeded integrity evidence and
`[security]\nposture = "observe"\n`, each shape piped through `wuwei hook PreToolUse` in
process, plus the decision lint through PostToolUse. Neutral forms of the five trial shapes
(Assumption A7):

| Shape | Exit under observe | Refused by (reason, posture line) |
|---|---|---|
| S1 `cd .wuwei/ziran && for r in a b c; do cat $r/report.json; done` | 2 | state guard: "dynamic command or shell control flow is unsupported", records floor |
| S2 `ls; ls days/x; cat days/x/decisions/D-1.md; grep -n rm config.toml` | 0 under observe, 2 under guarded | commit/push guard: "opaque interpreter command: ls" |
| S3 `W=$(cat .wuwei/executable); $W plan session abc --take-over; $W mcp check` | 2 | deploy and PR guard: "command substitution is unsupported", owner-only floor; state guard: same text, records floor; commit/push guard recorded as would-refuse |
| S4 `python3 -P -c 'import subprocess;r=subprocess.run(["git","log","-1"]);print(open("config.toml").read())'` | 2 | deploy and PR guard: "unaccounted git/gh mention", owner-only floor; with a `D-` path in the snippet the decision lint (PostToolUse) adds "could not inspect decision record", records floor |
| S5 `mkdir -p ../scratch && cd ../scratch && ls` | 2 | state guard: "Keep the workspace root", records floor |

Five code facts produce this:

1. Every Bash guard fails closed on `shell.ParseError` once it finds a call relevant:
   `cli/wuwei/guards/commit_push.py:282-298` (inside a workspace session it re-raises),
   `cli/wuwei/guards/deploy.py:269-272`, `cli/wuwei/guards/pr.py:357-364`,
   `cli/wuwei/guards/protect_state.py:414-431` and `cli/wuwei/guards/decision.py:56-68`.
   The parser rejects `for`, `$(...)`, nonliteral command names and quoted git or gh
   mentions (`cli/wuwei/shell.py:246-260`, `:433-438`, `:82-84`), so any loop or
   substitution that a guard considers relevant becomes exit 2.
2. Relevance is wide on exactly these texts: `shell.mentions` (`cli/wuwei/shell.py:125-127`)
   calls a text with a nonliteral command word (`$W`) relevant for every name, and a text
   with a git mention and any nonliteral word relevant for every name (`:117-123`). S3 and
   S4 are therefore relevant to the deploy and PR guards although nothing in them publishes.
3. The hook (`cli/wuwei/commands/hook.py:188-218`) sets the level from the guard's area
   alone (`cli/wuwei/guards/__init__.py:47-60`): `deploy` and `pr` are owner-only and
   `protect_state` and `decision` are records, so their "could not run" lands on a floor no
   posture lowers, even when the call cannot publish or write a record.
4. The state guard treats any mention of `.wuwei` or a state file in an unparsable command
   as a write (`protect_state.py:421-426`), so reading `.wuwei/ziran/...` in a loop (S1) or
   `cat .wuwei/executable` in a substitution (S3) hits the records floor.
5. Read-only commands are judged opaque in parsed lists: the commit/push guard refuses
   every non-git command in a multi-command call it finds relevant
   (`commit_push.py:357-362`; S2 is relevant because of the words `rm` and `config`), and
   the decision lint refuses every interpreter snippet (`decision.py:86-87`). The cd rule
   blocks on the records floor (`protect_state.py:427-430`, `:468`, `:471-476`).

Spec 4.5 and 9.1 (#237): the Bash guards are cooperative mistake prevention; the publishing
guarantee comes from protected refs and credentials kept out of seats. The floors stay
right for a call that names a publishing tool or writes a record; they are wrong for a call
that can do neither.

## User Scenarios & Testing

### User Story 1 - A seat can read reports, decisions and config under observe (Priority: P1)

A planner or seat reads the day with loops, lists, a launcher held in a variable, an inline
interpreter, or a scratch directory. None of these can publish or write a record, so under
`observe` none is refused; the ones the parser could not read are recorded for the owner.

**Why this priority**: it is the reported defect; the trial day could not start.

**Independent Test**: `python -m pytest -q tests/test_parser_warns.py -k shapes`.

**Acceptance Scenarios**:

1. Given a workspace under `observe`, when each of S1 to S5 goes through PreToolUse, then
   the hook exits 0; S3 and S4 record exactly one `guard.would_refuse` whose `reason`
   begins with `unparsed`; S1 and S5 record exactly one `guard.would_refuse` whose reason is
   the cd rule's line (it names the subshell form); S2 records no event.
2. Given the same shapes under `guarded`, then the exits and events are the same as under
   `observe`.
3. Given the same shapes under `strict`, then S1, S2 and S5 exit 0 as above, and S3 and S4
   exit 2 with a deny reason that is exactly the one line
   `unparsed: write the commands to a file with the Write tool and run bash <file>; a plain git or gh command stays plain`,
   and no event.
4. Given a heartbeat session (`wuwei-heartbeat`, no posture applied) in a workspace under
   any posture, when `for r in a b; do cat .wuwei/$r/report.json; done` goes through
   PreToolUse from `.wuwei`, then the hook exits 0 with no output.
5. Given the decision lint (PostToolUse, Bash) under `observe`, when S4 with a
   `days/x/decisions/D-1.md` read in its snippet runs, then the hook exits 0 and records one
   `unparsed` would-refuse.

---

### User Story 2 - Publishing and record writes still refuse in every posture (Priority: P1)

The relief in US1 must not open a path around the deployment ban, the merge policy, the
commit and push rules or the records floor.

**Why this priority**: constitution VII and spec 4.6, 4.7 and 9.1 floors.

**Independent Test**: `python -m pytest -q tests/test_parser_warns.py -k still_refuse`.

**Acceptance Scenarios**:

1. Given `git push origin main` wrapped as `for r in a b; do git -C $r push origin main; done`,
   `x=$(git push origin main)` or `G=git; $G push origin main`, then the hook exits 2 under
   `observe`, `guarded` and `strict`, and the deny reason names the deploy guard.
2. Given `echo x > .wuwei/days/<date>/state.json` written plainly, inside a `for` loop,
   behind `$(date)`, through `tee` of a path from `$(ls ...)`, from a variable holding
   `tee <state path>`, or from `python3 -c` opening the path for writing, then the hook
   exits 2 under `observe`, `guarded` and `strict`.
3. Given `echo "gh pr merge 17"` under any profile, then the hook still exits 2 with
   "plain command" in the reason (the existing hard-guard row).

---

### User Story 3 - Read-only commands are never opaque (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_shell.py -k classify` and the guard
rows named in tasks.md.

**Acceptance Scenarios**:

1. Given `shell.classify`, then each command in the plan's classification table yields the
   listed `readonly`, `publishes`, `inline` and protected-write answers.
2. Given the commit/push guard and S2, then it returns `(0, '')`.
3. Given the deploy guard, the PR guard and the commit/push guard, when a relevant call the
   parser cannot read has no publisher word, then each returns `(2, UNPARSED)`; when every
   word is read-only, each returns `(0, '')`; when a publisher word appears, each returns
   today's refusal.
4. Given every existing row of the bypass tables (`tests/test_shell.py`,
   `tests/test_deploy.py`, `tests/test_commit_push.py`, `tests/test_pr_guards.py`,
   `tests/test_protect_state.py`, `tests/test_owner_actions.py`,
   `tests/test_seat_command_forms.py`, `tests/test_profiles.py`) and the #18 mutation tests,
   then all pass with the exceptions listed in Assumption A6.

### Edge Cases

- A loop the walk reads fully with only read-only words (`for f in *.py; do wc -l $f; done`)
  passes every Bash guard with no event, in every posture.
- A call no guard finds relevant (`python3 -m pytest -q`, `export X=1`, a loop over
  `echo`) is not classified at all: exit 0, no event, in every posture including strict
  (design 9.1, relevance before parsing).
- Unbalanced quotes or an unterminated here-doc cannot be walked: the classifier answers
  "publishes", so the guard refuses as today (`echo "unterminated state.json` stays 2).
- Code fed to an interpreter from a pipe or a file redirect (`git show HEAD:d.py | python3`)
  is never in the text: it counts as a publisher, so today's refusal stands.
- Outside a workspace nothing changes: the hook returns before any guard (spec 9.1, #323).
- A heartbeat session skips the posture (`hook.py:96-98`), so its probe proves the
  read-only class, not a warn.

## Requirements

### Functional Requirements

- **FR-001**: `cli/wuwei/shell.py` gains one classification, `classify(command,
  publishers=())`, returning `Shape(parsed, readonly, inline, publishes, written)`. It
  splits on `;`, `&&`, `||`, `|`, `&` and newlines, walks `for`, `while`, `until`, `if`,
  `case` and their keywords, `$(...)`, backticks, here-docs and `sh -c` scripts, and
  collects every command word. It never executes or expands anything.
- **FR-002**: `shell.unread(command, publishers=())` is the decision table for a relevant
  call: `(0, '')` when `readonly`; `(2, UNPARSED)` when no publisher word appears and the
  call was not parsed or runs inline code; `None` otherwise (the guard decides as before).
- **FR-003**: The commit/push, deploy and PR guards call `shell.unread` at every point
  where today they fail closed on a parse error (re-raising when it returns `None`) and once
  on the parsed path before their opaque-command checks. Their relevance and scope checks
  run first, unchanged (#323, #330).
- **FR-004**: The state guard, on a parse error, keeps the records floor when the owner
  action rule applies to a word the walk cannot pin or to literal owner words, or when
  `Shape.written` mentions a protected path, or when the cwd is protected and the write is
  dynamic (all as today but on `written` instead of the whole text). Otherwise it returns
  the cd rule when a top-level cd, pushd or popd may leave the workspace, `(0, '')` when
  `readonly`, `(2, UNPARSED)` when the text mentions a protected path, and `(0, '')`
  otherwise.
- **FR-005**: The decision lint, on a parse error, returns `(0, '')` when `readonly`,
  `(2, UNPARSED)` when the call runs inline code or `written` names no `D-` record, and
  today's refusal otherwise; its interpreter-snippet result becomes `(2, UNPARSED)` and the
  day's records are still linted.
- **FR-006**: Every cd, pushd and popd refusal of the state guard uses one reason,
  `shell.WORKSPACE_ROOT`, that names the subshell form. Guard exit codes are unchanged.
- **FR-007**: `hook.posture` decides two reasons by the reason, not the area: `UNPARSED`
  blocks under `strict` and warns otherwise; `WORKSPACE_ROOT` warns in every posture. Both
  carry no posture line, and a call records at most one event per reason.
- **FR-008**: The heartbeat gains a `read_loop` probe and doctor shows its row.
- **FR-009**: `docs/site/security.md` and `docs/site/reference.md` describe the unparsed
  class, the cd rule and the probe.
- **FR-010**: `guards.AREAS`, `OWNER_ONLY`, `level`, `workspace.POSTURES`, `FLOORS`,
  `shell.normalize`, `shell.mentions` and `shell.is_opaque` are unchanged. Every hook stays
  within its `WUWEI_BENCH=1` budget.

### Key Entities

- `Shape` (NamedTuple in `wuwei.shell`): `parsed`, `readonly`, `inline`, `publishes`,
  `written`. Never persisted.
- `UNPARSED` and `WORKSPACE_ROOT` (str constants in `wuwei.shell`): refusal reasons the
  hook levels by text. The `guard.would_refuse` event (#308, #331) is reused as is.

## Success Criteria

- **SC-001**: The issue's four acceptance criteria pass as tests (US1-1, US2-1, US2-2,
  US1-3).
- **SC-002**: The full suite passes: `python -m pytest -q`.

## Assumptions

- A1. The decision table applies only where a guard, after its own relevance and scope
  checks, would fail closed today (its parse-failure branch and its opaque or
  inline-interpreter checks). A call no guard finds relevant is never classified, so it
  never warns or blocks, also under strict. The issue's "a command the parser could not
  fully read ... blocks only under strict" is read with this scope (pre-flight rule:
  `python3 -m pytest -q`, a `for` loop and `export X=1` are never blocked).
- A2. Read-only words are exactly the issue's list (`ls`, `cat`, `grep`, `head`, `tail`,
  `sed`, `wc`, `jq`, `diff`, `find`) plus `cd`, `pushd` and `popd`. `sed` is read-only only
  as `sed -n <lines>p` without `-i` (`sed` scripts can write with `w` or run with `e`);
  `find` only without `-exec`, `-execdir`, `-ok`, `-okdir`, `-delete`, `-fprint`,
  `-fprint0`, `-fprintf` or `-fls`. `echo` and `printf` are not read-only: their output can
  feed a shell.
- A3. Publisher words: `gh`, `glab`, `hub`; the deploy guard adds its programs and the
  `[deploy].deny` programs; `git` unless its verb is a known read (`status`, `diff`, `log`,
  `show`, `rev-parse`, `ls-files`, `ls-remote`, `remote`, `symbolic-ref`, `describe`,
  `show-ref`, `blame`, `grep`, `cat-file`, `rev-list`, `for-each-ref`, `shortlog`, `fetch`,
  `help`, `version`). This allowlist is stricter than the issue's verb list on purpose: an
  alias or `git config core.hooksPath` cannot be pinned to a safe form. In inline code and
  in the arguments of a command that is not read-only, a publisher is a mention of a
  publisher program, or of `git` together with one of the issue's verbs (`push`, `commit`,
  `tag`, `merge`, `rebase`, `reset`, `checkout`, `switch`, `branch`). A nonliteral command
  word is a publisher unless its variable is assigned in the same call to text that names
  no publisher and all its arguments are literal non-publisher words. `xargs`, `eval`,
  `source`, `.`, a shell without `-c`, and an interpreter reading code from a pipe or a
  file redirect cannot be pinned and count as publishers.
- A4. A write aimed at a protected path is judged on `Shape.written`: the text of every
  command that is not read-only (redirect targets and substitution bodies included) plus
  assignment values (substitutions whose command is read-only dropped), or the whole
  command when such a command has a nonliteral argument or redirect target. The state
  guard keeps its patterns (`_STATE_MENTION`, `_STATE_GLOB`); the decision lint looks for
  `D-`. Inline code is written text for the state guard (so `python3 -c` opening a state
  file still refuses) but not for the decision lint (inline code is a file it cannot read;
  the day's decision records are still linted when the call parses).
- A5. The `guard.would_refuse` payload for an unparsed call keeps today's fields; its
  `reason` is the `UNPARSED` line, which begins with `unparsed`. The issue's
  "`reason: unparsed`" is read as that prefix, so `wuwei why` and the shadow report show
  the accepted form too.
- A6. Existing tests that change, all required by the issue: hook-level rows
  `tests/test_protect_state.py::test_discovered_guards_through_hook` (`cd ..`, 2 to 0) and
  `tests/test_seat_command_forms.py::test_seat_command_forms`
  (`cd $(git rev-parse --show-toplevel) && ls`, 2 to 0) follow the cd rule (warn, never
  block); `tests/test_heartbeat.py` and `tests/test_doctor.py` fixtures gain the new probe.
  Guard-level rows keep their exit codes. The design was checked on a scratch copy of main
  (not the worktree): with exactly the plan's changes and these four test edits the full
  suite passed (7407 passed, 10 skipped).
- A7. The trial shapes are reproduced with neutral names. S2's trial text held a word the
  commit/push guard looks for; `rm` and `config.toml` give the same refusal ("opaque
  interpreter command: ls"). S4's trial snippet is unknown; a snippet naming `git log` and
  `config.toml` gives the trial's refusals. No client, repository or local path from the
  trial appears anywhere.
- A8. S1 and S5 warn (the cd rule) in every posture, including strict; this is the issue's
  cd rule ("warn, never block, in every posture"). S1's cd stays inside the workspace, but
  the parser cannot read the call, so the guard cannot prove it; the warn is cheap and the
  call goes through.
- A9. The probe is `for r in a b; do cat .wuwei/$r/report.json; done` from `.wuwei`: it
  names `.wuwei`, so it fails on main (records floor) and passes only through the read-only
  class. Heartbeat sessions skip the posture, so a warn would not help it.
- A10. The relayed owner question ("the default security posture is better to be observe
  rather than guard if we are running --shadow"): it already is. `wuwei init --shadow`
  writes `security.posture = "observe"` (`cli/wuwei/commands/init.py:41`), `wuwei setup
  --shadow` sets it (`cli/wuwei/commands/setup.py:217-219`), and the deprecated
  `guards.mode = "shadow"` resolves to observe (`cli/wuwei/workspace.py:538`). Without
  `--shadow` the default stays `guarded` (spec 9.1). No change here; this issue makes
  observe let unparsed reads through, which the trial showed it did not.
- A11. Known residuals, same anchors as spec 4.5 (pre-push hook, protected refs,
  credentials kept out of seats), each with a `ponytail:` comment: a variable assigned
  from a read-only command's output (`W=$(cat file)`) is not followed into the file; a
  command name built at run time from words the walk sees as literal is not evaluated.
- A12. Under `guarded` an unparsed warn produces the existing `guard.would_refuse` status
  nudge (one per guard per day). Making it silent is out of scope.

- A13. Changes made during implementation, all stricter than A3 and A4: `commit_push` treats `rm` as a publisher word for the decision table, because it guards hook pointers. `git -c` and `--config-env` count as publishers. A variable used as a command word publishes when any value assigned to it mentions `git`. A `for` or `select` header counts as an assignment. An unquoted here-doc that holds a substitution counts as a publisher. plan.md lists these under "Changes made during implementation".
