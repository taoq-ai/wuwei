# Feature Specification: every read-only git subcommand is known, unknown git subcommands warn under observe and guarded, and a read in a loop never hits the records floor

**Feature Branch**: `470-git-reads`

**Created**: 2026-10-04

**Status**: Draft

**Input**: GitHub issue #470, "fix(guards): every read-only git subcommand is known, unknown
git subcommands warn under observe and guarded, and a read with a variable or loop target
never hits the records floor". Owner report 2026-10-04, confirmed on the 0.15.0 asset.
Follows #347 (classifier and the unparsed rule) and #349 (reads never refused).

## Root cause (read and reproduced on main, 963a839)

Reproduced read-only with a scratch script outside the repository: a copy of the v0.15.0
smoke workspace, each guard called in process and the full `hook PreToolUse` run with the
worktree code under `observe`, `guarded` and `strict`. Every row of the issue's table
behaves as the owner reported, in all three postures.

**Gap 1, git reads refused as unknown.** The deploy guard keeps its own list of known git
subcommands, `cli/wuwei/guards/deploy.py:132-136` (`status`, `diff`, `log`, `show`,
`rev-parse`, `branch`, `tag`, `fetch`, ...). Anything else raises `unknown git command or
alias`, which `check` turns into `2, 'deploy: could not inspect: ...'`
(`deploy.py:316-317`). `deploy` is in `OWNER_ONLY` (`cli/wuwei/guards/__init__.py:46`), so
`hook.posture` (`cli/wuwei/commands/hook.py:247`) blocks it in every posture with
`posture: publish = block (owner-only action; ...)`. `git grep`, `git blame` and
`git shortlog` hit this in observe, guarded and strict. The shared classifier already has a
longer read list, `_GIT_READS` in `cli/wuwei/shell.py:606-609`, which includes `grep`,
`blame`, `shortlog` and `cat-file`; the two lists drifted apart. The commit guard keeps no
subcommand list (`COMMIT_VERBS` in `commit_push.py:47` is only its relevance set) and is
not involved.

**Gap 2, a read loop on the records floor.** The owner's loop is
`cd .wuwei; for f in days/<date>/decisions/D-*.md; do echo "### $f"; cat $f; done; cat days/<date>/state.json`.
`normalize` rejects the `for`, so `protect_state.check_bash` falls back to
`shell.classify` (`protect_state.py:526`). `cat $f` is already a read there (`cat` is in
`READ_ONLY` and `reads` ignores its operands). The word that breaks it is `echo`:
`READ_ONLY` (`shell.py:602-603`) does not contain it, so `_classify` (`shell.py:909-914`)
counts `echo "### $f"` as a possible write, and because its argument is not literal it sets
`whole`, which makes `written` the entire command text. That text mentions `.wuwei` and
`state.json`, so `protect_state.py:531` returns `2` with the parser's "dynamic command or
shell control flow is unsupported" text, and the `records` floor blocks it in every
posture. Checked: with `echo` added to `READ_ONLY` the classifier returns `readonly=True`
for this command, `for f in a; do cat $f; done`, `for f in a; do cat "$f"/x; done` and
`head $(ls .wuwei/days)`, while `for f in a b; do echo x > .wuwei/days/x/state.json; done`
still has `written` naming the state file and `for f in a b; do git push origin $f; done`
still `publishes`. The issue's wording ("a read with an unresolvable target is treated as a
write") names the symptom; the cause is the missing `echo`.

**What `echo` was silently holding up.** Because `echo` was a non-read, its arguments always
landed in `written`. Three things leaned on that. `tests/test_protect_state.py`
(`echo .wuwei/config.toml | sh`, expected 2) fails with `echo` as a read word: the shell
fed by the pipe has no `-c`, so `written` becomes just `sh`, no state path matches, and
the call drops from the records floor to an `UNPARSED` warning. The same applies to
`echo '<write to state.json>' | sh`, `| bash -s` and `| source /dev/stdin` inside a loop:
the piped text is code, and it would escape the floor. Prototyped on a scratch copy: when a
non-read command reads from a pipe, `written` must be the whole command text, the way a
here-doc already is (`shell.py:913`, `whole |= ... fed == 'heredoc'`). With that one
change all those shapes refuse in every posture, and read pipelines (`... | wc -l`,
`... | grep x`) stay `readonly`. Two test rows encode the old `echo` and change on purpose:
`tests/test_shell.py` `CLASSIFY` row `echo "gh pr merge 17"` (now readonly, no publish:
printing a word publishes nothing) and `tests/test_decision.py`
`test_relevant_opaque_or_unparseable_bash` row `for x in D-3; do echo x; done` (now a read,
so 0; the row becomes a non-read loop such as `for x in D-3; do touch x; done` to keep
the test's intent).

Shapes that already behave as the issue wants (locked by tests, not changed): `git log`,
`show`, `diff`, `ls-files`, `rev-parse` and `fetch` exit 0; the `cat ...; echo; echo
'====='; ...` row exits 0; `for f in a b; do git push origin $f; done` exits 2 in every
posture (deploy, owner-only); `for f in a b; do echo x > <state.json>; done` exits 2 in
every posture (records floor).

## User Scenarios & Testing

### User Story 1 - Read-only git subcommands pass every guard (Priority: P1)

A seat reads a repository with `git grep`, `git blame` or any other read-only subcommand,
plain or with `-C <repo>`, and the hook lets it through in every posture with no event.

**Why this priority**: the owner hits it daily; a read refused as an owner-only action
stops a seat for nothing.

**Independent Test**: `python -m pytest -q tests/test_shell.py tests/test_deploy.py tests/test_parser_warns.py -k git`.

**Acceptance Scenarios**:

1. **Given** a guarded workspace, **When** the hook receives
   `git -C <repo> grep -n -E '<pattern>' origin/main -- a.py b.py`, **Then** it exits 0 and
   records no `guard.would_refuse` (also under observe and strict).
2. **Given** the same, **When** it receives `git -C <repo> blame -L 1,5 a.py`, **Then** it
   exits 0 with no event, in every posture.
3. **Given** the same, **When** it receives `git -C <repo> log`, `show`, `diff`,
   `ls-files`, `rev-parse` or `fetch`, **Then** each exits 0, as today.
4. **Given** any subcommand in the read table, **Then** `shell.git_kind` returns `read`;
   for each subcommand in the write table, `write`; for `branch`, `tag`, `remote`, `stash`,
   `worktree`, `config` and `bisect`, `read` only in their read forms (`branch`, `tag` and
   `remote` bare, `branch --list`, `tag -l`, `remote -v`, `remote get-url origin`,
   `stash list`, `worktree list`, `config --get x`, `bisect log`) and `write` otherwise
   (`branch -D x`, `tag v1`, `remote add x u`, `stash`, `stash pop`, `config x y`).
5. **Given** every subcommand the deploy guard knew on main, **Then** each is still read or
   write, never unknown.

### User Story 2 - An unknown git subcommand warns, and refuses only under strict (Priority: P1)

**Why this priority**: it is the issue's acceptance line; an alias or a newer subcommand
should not stop a seat outright when the code host and the pre-push hook are the publish
anchors (design 4.5).

**Independent Test**: `python -m pytest -q tests/test_parser_warns.py -k unknown_git`.

**Acceptance Scenarios**:

1. **Given** an observe or guarded workspace, **When** the hook receives
   `git -C <repo> frobnicate`, **Then** it exits 0 and records exactly one
   `guard.would_refuse` from `deploy` whose reason is `unknown git subcommand frobnicate; if
   it publishes, run it as a plain literal command from a host terminal`.
2. **Given** a strict workspace, **When** it receives the same, **Then** it exits 2 with
   that reason and no posture line, and records no `guard.would_refuse`.
3. **Given** `git -c alias.x=log x` (or `GIT_DIR=elsewhere git x`, `git --git-dir d x`),
   **Then** the deploy guard keeps today's `2, deploy: could not inspect: unknown git
   command or alias; ...`, refused in every posture: the override can define the alias.
4. **Given** a read subcommand with an option that runs a program (`git grep -Ocmd x`,
   `git grep --open-files-in-pager=cmd x`, `git fetch --upload-pack=cmd origin`), **Then**
   `git_kind` returns `unknown` and the hook warns or refuses as in scenarios 1 and 2.

### User Story 3 - A loop of read words never hits the records floor (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_parser_warns.py -k owner_rows`.

**Acceptance Scenarios**:

1. **Given** a workspace in any posture, **When** the hook receives
   `cd .wuwei; for f in days/<date>/decisions/D-*.md; do echo "### $f"; cat $f; done; cat days/<date>/state.json`
   from the workspace root, **Then** it exits 0 and records exactly one
   `guard.would_refuse`, the workspace guard's top-level `cd` warning (`WORKSPACE_ROOT`).
2. **Given** the same, **When** it receives
   `cd .wuwei; cat days/<date>/lead.json; echo; echo '====='; cat config.toml; ls days/<date>`,
   **Then** it exits 0, as today.
3. **Given** `shell.classify`, **Then** `echo` without a redirection is a read word: a
   command made of `echo`, `cat`, `ls`, `head` and the other read words, inside `for`,
   `while`, `if` or `$(...)` or with variables, is `readonly`.

### User Story 4 - Publishing and record writes inside loops still refuse (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_parser_warns.py -k still_refuse`.

**Acceptance Scenarios**:

1. **Given** `for f in a b; do git push origin $f; done`, **Then** the hook refuses it in
   every posture.
2. **Given** `for f in a b; do git commit -m $f; done`, **Then** refused in every posture.
3. **Given** `x=$(git commit -m y)`, **Then** refused under guarded and strict; under
   observe it keeps observe's publish rule (warn), as today (see Assumptions).
4. **Given** `echo x > .wuwei/days/<date>/state.json` inside a `for` loop, **Then** refused
   in every posture (existing test, kept).
5. **Given** `echo .wuwei/config.toml | sh` (existing test, kept),
   `echo 'echo x > <state.json>' | bash -s`, or
   `for i in 1; do echo 'echo x > <state.json>'; done | sh`, **Then** refused in every
   posture: text piped into a non-read command counts as written.

### User Story 5 - The heartbeat and doctor probe both shapes (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_heartbeat.py tests/test_doctor.py tests/test_parser_warns.py -k heartbeat`.

**Acceptance Scenarios**:

1. **Given** the heartbeat, **Then** a new `git_read` probe sends `git grep -n probe`
   through `hook PreToolUse` and is ok on exit 0, and the `read_loop` probe's command is
   the owner's shape with `echo`:
   `for r in a b; do echo "### $r"; cat .wuwei/$r/report.json; done`.
2. **Given** doctor, **Then** its guards section lists `git_read` next to `read_loop`.
3. **Given** a workspace in any posture, **Then** both probe commands exit 0 through the
   hook as the heartbeat session.

### Edge Cases

- `git` with no subcommand, or only global options, is `read` (deploy already returns 0).
- A subcommand word containing `$` is `unknown` (the classifier already treats it as a
  publish).
- A read form followed by a flag outside its read words (`git branch -a -D x`,
  `git stash show -p`) is `write`: conservative and still known, so the deploy guard passes
  it and the classifier treats it as a publish inside a loop.
- `echo ... > file` keeps its write target: the redirection is collected apart from the
  word, so `echo` becoming a read word changes nothing for writes.
- `echo $(git push origin main)`: the substitution body is classified on its own and still
  publishes.
- `for f in a; do cat $f; done | wc -l` and `... | grep x` stay `readonly`: the pipe rule
  only touches a non-read fed by a pipe.
- `for f in a; do cat <state.json> | python3 -m json.tool; done` stays `readonly`
  (`json.tool` on standard input is a read).
- Two unknown subcommands in one call (`git a; git b`): the deploy guard stops at the first
  and returns one reason, so one event.

## Requirements

### Functional Requirements

- **FR-001**: `cli/wuwei/shell.py` holds the git tables as data: a read set, a read-forms
  map (subcommand to the words that keep it read-only), a write set, and the
  program-running option prefixes. The read set is the issue's list plus the reads already
  in `_GIT_READS`; the write set is the issue's publishing list plus `add`, `restore`,
  `init` and the form subcommands.
- **FR-002**: `shell.git_kind(args)` returns `read`, `write` or `unknown` for git's argv
  after `git`, skipping global options; a `-c` or `--config-env` override, a `$` in the
  subcommand or a program-running option is `unknown`.
- **FR-003**: The classifier's `_git_publishes` uses `git_kind`: anything not `read`
  publishes, as today.
- **FR-004**: `deploy.git` replaces its own tuple with `git_kind`: `read` and `write` pass
  (push and merge keep their existing handling first); `unknown` returns
  `2, f'{UNKNOWN_GIT}{verb}; if it publishes, run it as a plain literal command from a host terminal'`,
  except with a config, git-dir, work-tree or `GIT_*` override, where it keeps today's
  `unknown('unknown git command or alias')`.
- **FR-005**: `hook.posture` levels a reason starting with `shell.UNKNOWN_GIT` like
  `UNPARSED`: block under strict, warn otherwise, no posture line, one event per reason.
- **FR-006**: `echo` joins `shell.READ_ONLY`. In `_classify`, a non-read command fed by a
  pipe makes `written` the whole command, as a here-doc does, so text echoed into a shell or
  interpreter stays on the records floor. `python3 -m json.tool` reading standard input (no
  file operand) becomes a read in `shell.reads`, so the common
  `cat <state.json> | python3 -m json.tool` read inside a loop stays `readonly` under the
  pipe rule; with two operands (an outfile) it is still not a read.
- **FR-007**: The heartbeat gains the `git_read` probe (untimed) and the `read_loop`
  command gains `echo "### $r";`; doctor lists `git_read`; `docs/site/reference.md` lists
  both probe rows; `docs/site/security.md` names `echo` as a read word and the unknown git
  subcommand rule.
- **FR-008**: No new import on the hook path: `hook.posture` already imports from
  `wuwei.shell`, and `deploy` already imports from `wuwei.shell`. The #346 import-graph
  tests in `tests/test_hooks.py` pass unchanged.

- **FR-009** (review F1, F3): `deploy.git` refuses a program-running option
  (`shell.git_runs`: `-O`, `--open-files-in-pager`, `--upload-pack`, and `-u` on
  `ls-remote`) with `unknown('git option runs a program')` before the `git_kind` check, so
  the publish floor holds in every posture.
- **FR-010** (owner's sixth row): `normalize` accepts nonliteral arguments on git or gh when
  the subcommand is a literal read (`git_kind` is `read`, or gh's second word is `list`,
  `view`, `status`, `checks` or `diff`) and every nonliteral word is a plain variable
  (`$R`, `${R}`, `"$R"`) that the same command assigns only to single safe words (a word
  character first, then word characters or `./:@+-`). A publishing subcommand
  (`git -C $R push origin main`) keeps needing literal arguments and still refuses.

### Key Entities

- **Git kind**: `read`, `write` or `unknown`, the outcome of one git argv against the
  tables.
- **Unknown git reason**: the text starting with `UNKNOWN_GIT`; the hook levels it by its
  text, like `UNPARSED` and `WORKSPACE_ROOT`.

## Success Criteria

- **SC-001**: The five owner rows exit 0 under observe, guarded and strict; the loop row
  records exactly one `guard.would_refuse` (the top-level `cd` warning).
- **SC-002**: `git -C <repo> frobnicate` warns with the subcommand named under observe and
  guarded and refuses under strict.
- **SC-003**: Push and commit in a loop, and a state write in a loop, still refuse as in
  User Story 4.
- **SC-004**: The full suite passes, with exactly three existing test rows changed on
  purpose (the `echo "gh pr merge 17"` classify row, the `D-3` echo loop row in
  `tests/test_decision.py`, and the `echo "gh pr merge 17"` row in `tests/test_profiles.py`,
  which becomes `printf "gh pr merge 17"`; the third was found while building).

## Assumptions

- The root cause of row 4 is `echo` missing from `READ_ONLY`, not the unresolvable `cat`
  target: `cat $f` was already a read (reproduced above). The fix is one word in the shared
  set, which both the classifier and the state guard read through `shell.reads`.
- A command of read words only keeps passing in every posture, strict included. The issue's
  second gap says such a command "refuses only under strict", but its own table expects 0
  with no posture named, #349 says reads are never refused, `docs/site/security.md` says a
  command whose words are all read-only passes, and `tests/test_parser_warns.py` S1 already
  expects 0 in every posture for the same shape. The one would-refuse event on row 4 is the
  workspace guard's warning for the top-level `cd .wuwei` (`WORKSPACE_ROOT`), which warns
  in every posture.
- "`git commit` inside `$(...)` still refuses in every posture": under observe the commit
  guard's refusal is a `publish` area warning by the posture contract ("records and
  owner-only actions still refuse"), and that is today's behaviour. This issue keeps it:
  `x=$(git commit -m y)` refuses under guarded and strict and warns under observe. The loop
  form refuses in every posture today through the deploy guard (a non-literal word next to
  `git` makes it relevant) and keeps doing so. `git push` in a loop or `$(...)` refuses in
  every posture through the deploy guard.
- An unknown subcommand with `-c`, `--config-env`, `--git-dir`, `--work-tree` or a `GIT_*`
  environment override keeps today's refusal in every posture: the override can define the
  alias (`-c alias.x='!git push ...'`), so the call is not a plain literal command.
- A read subcommand with an option that runs a program (`-O`/`--open-files-in-pager` on
  grep, `--upload-pack` on fetch and ls-remote, `-u` on ls-remote) is `unknown`, and the
  deploy guard refuses it in every posture (FR-009): admitting these as reads, or only
  warning, would let a command ride inside a read. `log -O<orderfile>` also matches the
  `-O` prefix and refuses; accepted, it is rare.
- The sixth row's variable is accepted only when the same command assigns it a single safe
  word, because an unquoted `$R` word-splits: `R='x push origin main'; git -C $R log` runs
  a push. A variable set nowhere in the command, or joined to other text
  (`$S..origin/main`), keeps the literal rule. Under strict the owner's full row still
  refuses for its `python3 -c` part (unparsed), not for the git or gh parts.
- Some subcommands in the issue's read list edit local refs with extra arguments
  (`reflog expire`, `symbolic-ref HEAD <ref>`). They stay in the read set as listed: a
  local ref edit is not a publish, and the pre-push hook and protected refs anchor pushes.
  Marked with a `ponytail:` comment.
- The write table is the issue's publishing list plus `add`, `restore` and `init`, which
  the deploy guard knew on main (`init` aside, added because it only creates a local
  repository); leaving them out would turn every `git add` into an unknown warning.
- `_GIT_PUBLISH` (the mention words `_names_publisher` matches anywhere in a non-read
  command's text) is unchanged. Widening it with `rm`, `mv`, `add` or `apply` would turn
  unrelated unparsed commands into publishes. The new write set is a separate table for the
  argv outcome.
- `commit_push.py` needs no change: it keeps no subcommand list. `protect_state.py` needs no
  change: it reads `READ_ONLY` through `shell.reads` and `classify`.
- The `git_read` probe is not timed: telemetry's hook latency set (`telemetry.PROBES`) and
  design 5.13's four timed probes stay as they are. Its command names no path, because a
  git operand naming a protected file keeps the records floor (see Deferred).
- Reproduction ran on a scratch copy of the v0.15.0 smoke workspace named in the
  orchestrator notes, with the worktree code (main at 963a839), so the original stayed
  untouched.

## Deferred

- A git read naming a protected path (`git grep x -- .wuwei/config.toml`,
  `git log -- .wuwei/config.toml`) still meets the records floor: `protect_state` treats
  every git operand as a possible write target, and read subcommands accept writing options
  (`git diff --output=<file>`, `git log --output`), so dropping their operands would open a
  write. A follow-up issue can teach `_write_targets` the read forms with their writing
  options; no owner row needs it.
- `echo '<python that writes state.json>' | python3`, written plainly with no loop, passes
  on main today and after this change: `normalize` parses it, and the parsed path of
  `protect_state` checks the interpreter's arguments, not its piped input. The loop form is
  refused (FR-006). A follow-up issue can treat a stdin-fed interpreter or shell as opaque
  in the parsed path too.
- The pipe rule refuses a loop that pipes a state file into a command that is not a read
  word (for example `| jq` is a read, `| awk '{print}'` is not). Accepted: the floor wins,
  and the plain command form is parsed and passes.
- Inside an unparsed command, a git read is still not a read word (`for ...; done; git log`
  stays `unparsed`, as `tests/test_deploy.py` pins); unchanged here.
