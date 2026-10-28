# Security policy

## Supported versions

Only the latest release receives security fixes. Upgrade to it before you report.

## What counts

- A guard bypass reachable through the normal tools, by a cooperating agent or by an
  injected instruction.
- A way to forge a record that a guard, sweep or policy trusts as proof of an owner action.
- A bypass of the signed manifest or the integrity check.
- A credential leaked into a seat environment, an event or a log.

## What does not count

The Bash guards are cooperative mistake prevention. They are never an isolation boundary.
Out of scope is a determined process running as the owner's user with a shell: it can forge
any local file. The hard boundaries sit outside the owner's user account: the code
host's protected refs, required checks and required reviews, and publication credentials
kept out of seat environments.

The Bash guards read a one-line command with `shlex`. They read the body of a loop, an if or a
brace group, a `bash -c` body after combined flags (`-lc`, `-e -c`), and the command after a
wrapper's options. A run of punctuation that `shlex` hands back as one word (`<(`, `;>`, `&&(`,
`);`) is split into the operators sh reads, so process substitution and glued separators reach
their doors; `|&` is a pipe. Every redirect operator, with or without an fd number (`<x`, `>&2`,
`&>>x`, `<>x`, `<<x`, `<&0`, `2>&1`, `10>x`, `2>/dev/null`), or with a named fd glued before it
(`{fd}>x`, `{a_b}<x`), is read as a redirect, so the program
after it is the command. A redirect whose next token is another operator or nothing (`>&>x`,
`git push origin main >`) is a shape they do not read, and so is a command with `$'...'` or
`$"..."` quoting outside other quotes: either is refused when it names a door program, and its
segments still meet the leak, infrastructure and ledger checks. An input redirect (`<`, `<&`,
`<<`, `<<<`) reads its word, so `cat < .wuwei/ledger/a.jsonl` is not a ledger write.

The records rule matches `.wuwei` itself, `.wuwei/ledger`, `.wuwei/ledger.jsonl` and anything under
them in the spellings sh expands (`//`, `/./`, `..`, the globs `*`, `?` and `[...]`, which never
match a leading dot, and brace expansion `{a,b}` and `{a..z}`; a bracket holding a POSIX class,
`[=x=]` or `[.x.]` reads as `*`, and a path whose braces expand to more than 512 words is refused
unexpanded), as a writer argument (`of=` too, and each path inside a `python -c` body), a redirect
target or an edit path. A write to `.wuwei/cache` is refused the same way, because its entries
feed gate inputs; removing a cache file passes. `find` with
`-delete`, `-exec`, `-execdir`, `-fprint`, `-fprintf` or `-fls` and an argument naming the records
is refused. After `cd` or `pushd` into `.wuwei` or below, or in a session whose directory is inside
it, a writer or a redirect to a file is refused. So is any writer or file redirect in a command
where a `-C`, `--chdir` or `-D` value names `.wuwei` (`env -C .wuwei rm -rf ledger`,
`sudo -D .wuwei ...`, `tar -C .wuwei -xf x.tar > log`), or expands past 64 words. `git clean` is read by allowlist. After any git
option other than `-C <dir>`, or with `GIT_` anywhere in the command, it is refused. With `x` or
`X`, or with an exclude (`-e` or any prefix of `--exclude`) whose value is not a plain word, it
passes only when every pathspec and `-C` dir is a plain word (letters, digits, `_ . / -`) and each
pathspec, joined to the `-C` dirs, lies below them and outside `.wuwei`. A dry run gets no
exemption, because a later `--no-dry-run` cancels `-n`.

git's options before the subcommand are read by allowlist, the options git 2.43 takes (git.c): a
valued option (`-C`, `-c`, `--git-dir`, `--work-tree`, `--namespace`, `--config-env`,
`--attr-source`, `--shallow-file`) takes the next word, so `git --config-env core.abc=Y push origin
main` meets the push door. Any other option before a push is refused, naming it. A `-c` or
`--config-env` that sets `remote.*`, `branch.*`, `url.*` or `push.default` is refused before a push,
because it decides where the push goes. One that sets an alias or an include (`include.path`,
`includeIf.*`) is refused whatever the subcommand and whatever option comes first, because an alias
runs a command the guard never reads. Set either with `git config` before the call.

The push door passes any push, force and delete included, to a git directory in a scratch folder,
so real-git evidence needs no route around it. The command must be one plain git call: `git`, its
options, `push`, then the remote as the first word, with every word plain (letters, digits and
`./=@:+-`) and no `--exec` or `--receive-pack` (or a prefix git reads as one). Each URL git
pushes to (`git remote get-url --push --all` for a remote name, so a `pushurl` or `pushInsteadOf`
counts) must be a path or a `file:///` URL. The shell's directory must lie inside the work tree,
where git reads a relative path from the top; from outside it (`--work-tree`, `core.worktree`)
git reads it from the shell's directory, so the rule refuses. git's own options (`-C`,
`--git-dir`, `--work-tree`) are passed to the guard's git calls. The path must be a git directory
(bare, or a `.git` path) with no `.git` entry inside it. Its common directory, symlinks resolved,
must lie below `tempfile.gettempdir()` or `/tmp`. It must not be the common directory of the
repository git runs in, and neither it nor any folder above it may hold `.wuwei`. Config in any
scope that sends the push elsewhere keeps the door: a `url.<base>.insteadOf` or `pushInsteadOf`
whose value starts a push URL, any `remote.<name>.vcs` or `remote.<name>.receivepack`, and a
`remote.<word>.*` key for a typed word that `git remote get-url` does not name (a remote set in
global or system config). So do a `cd`, `pushd`, wrapper, subshell, env assignment, `~`, `$`,
quote or second command, an option before the remote, a `%` escape or a host in a `file://` URL,
a worktree or non-bare path, and a network URL.

Known shapes they do not read on one line, reported and not yet fixed:

- `eval`, `source` or `.` on `/dev/stdin` or `<(...)`, and a variable as the program name.
- A `-c` body that is a variable or a substitution (`bash -c "$C"`, `xargs -I{} bash -c {}`).
- `env -S 'bash -s'` fed on stdin (the quoted string hides the shell), and shells outside the
  guards' list (`ksh`, `busybox sh`).
- `$(...)` inside double quotes, and quote splicing inside a word.
- A function body (`f() { ...; }`, `function f { ...; }`), `coproc`, `builtin command`, and
  unquoted backticks.
- A wrapper not in the guards' list (`setsid`, `flock`, `ionice`), and a wrapper option whose value
  names a program a door reads (`sudo -u gh gh pr merge 5`, `env -C /x/git git push`).
- A records write through a path the guards do not see: a symlink, a path a program builds at
  run time (`python3 -c "open('.wu' + 'wei/ledger/a.jsonl', 'w')"`), a writer not in the guards' list
  (`install`), `cd` to a variable or `cd -`, paths fed by a pipe (`find .wuwei | xargs rm`), and
  globs that reach dot files once `shopt -s dotglob` or `GLOBIGNORE` is set (`rm -rf *`).
- Deleting from an ancestor without naming `.wuwei` (`find . -delete`, `rm -rf ..`): the ledger is
  hash-chained and synced to `wuwei/state`, and the guard is a tripwire, not a sandbox.
- Two steps that un-ignore the ledger: `rm .wuwei/.gitignore` (or `mv`) and then `git clean -fd`.
- A `python -c` body that builds the path (`'.wu' + 'wei'`, `'.wuwei\x2fcache'`), and git config
  set before the call (`git config alias.p push`, `git config remote.origin.push HEAD:main`, then
  `git p` or `git push`), or passed through `GIT_CONFIG_*` environment variables.
- A scratch push that git sends elsewhere through state the guard does not read: a `.git` entry
  another process plants inside the remote between the guard's read and the push (git enters
  `<path>/.git` first), or an exec path or receive hook that runs another push.
- A push whose ref the same command changes first. The push door reads HEAD, and the ref a source
  alone resolves to, when the guard runs: `git checkout main && git push origin HEAD`, or a local
  symbolic ref written and pushed with no colon in one command
  (`git symbolic-ref refs/heads/x refs/heads/main && git push origin x`).
- `git stash --all` (or `-a`, `git stash push --all`) moves the ignored `.wuwei` into a stash and
  removes it from the tree; `git stash pop` brings it back.

An owner answer (a ruling, a plan approval, an exception) and a seat stop (with its attestation)
are recorded only when the harness's session transcript shows them: the AskUserQuestion tool_use
and its answer row, or the seat's meta file and its Agent tool_use. The transcript must resolve to a
regular file under `.claude/projects` or `.codex/sessions` in the account's home, read from the password database, so a
hand-made hook call that sets `HOME` or `CLAUDE_CONFIG_DIR` moves nothing. Anything else is recorded
as `answer.unconfirmed` or `seat.unconfirmed` with the reason. The guards refuse writes under
`.claude/projects` or `.codex/sessions` (and to `.claude` or `.codex` itself) in the spellings the records rule reads, and after `cd`,
`pushd`, `-C`, `--chdir` or `-D` into it; reads pass, except a `python` command that names a
transcript path, which the guards cannot tell from a write (read it with `python3 - < <path>`).
Claude Code's own memory stays writable: a regular file directly in `<project>/memory` under the
account's projects folder takes Write, Edit, a redirect, `tee`, `sed -i`, `truncate` or `rm`, when
its path is literal (`~`, `$HOME` or absolute, no glob, brace or `%` once quotes are removed) and
resolves there with links read. `ln`, `mv`, `cp`, `find` and `python` never get that pass, since
they can stage a link in memory that a later write follows, and a working directory in or below
memory still holds every write. What stays open: a process that writes the transcript itself,
through a script file, a writer the guards do not list (`install`, `perl`, `rsync`), a path built
at run time, a symlink or hard link made outside the guards' sight (a hard link from a memory file
to a transcript included), or a command that sets `HOME` before its `~` expands.
Bash quoting the guards do not read writes there too: ANSI-C or locale quoting
(`$'...'`, `$"..."`) of the `.claude` segment, and `eval` around a refused spelling. That is a forged
transcript line, and only the sandbox item closes it. A replayed real answer records nothing more,
since each answer id is recorded once. A gate's attestation, at its SubagentHandback (PreToolUse) and
at its SubagentStop, reads the report from the seat's own transcript: the one the payload names, or
for PreToolUse the one beside the session transcript, resolved under the projects folder, beside the
meta file that confirms the launch. A report the payload carries that the transcript does not hold
records `seat.unconfirmed` and no attestation, stop or kept report. A replayed real stop or hand-back
still re-reads the verdict file the seat's own report names, and the guards do not hold
`.wuwei/verdicts`, so two rules bind it. Only the seat's last report counts: a payload carrying an
earlier report from its transcript (one naming a path it later replaced) records `seat.unconfirmed`
as a replay. And a later sha for a path the seat already attested records `verdict.rewritten` and no
attestation, so evidence keeps the first. A resumed seat that writes a new verdict file in a new
last report attests it. A rewrite before the seat attests a path is still attested. `wuwei init` imports
0.34 decision files (`.wuwei/days/<date>/decisions/gate-*.md`) only into a workspace with no ledger
yet, so a decision file a seat writes later is never imported. The guards refuse literal spellings
of a hook call: `wuwei hook`, `wuwei -- hook`, and an interpreter's `-m wuwei hook`, `-m
wuwei.__main__ hook`, `-m cli.wuwei hook` or `-m runpy wuwei hook` (`python3`, `py -3`, `uv run
python`, any path). The transcript check, not this guard, is the boundary: a hook call built at run
time still passes (`${IFS}`, a variable, command substitution, a brace, `xargs`, `env -S`), as does a
script or `-c` body that imports the hook. A harness that keeps
transcripts elsewhere (`CLAUDE_CONFIG_DIR` or a moved `CODEX_HOME`), or an account with no password-database entry,
gets unsupported answers and stops recorded as unconfirmed while the guards keep running. An answer the
planner session never confirms (it ends before another hook call) leaves its `answer.pending` row.

Native Codex stops use the same account lookup and protection, including Windows profile lookup;
`HOME`, `USERPROFILE` and `CODEX_HOME` cannot move the accepted default root. The first metadata row
must identify the child, parent, role and canonical path. Its fork boundary excludes inherited rows.
A matching parent collaboration.spawn_agent call and result proves the requested role and task path.
The stop UUID maps to that path only after proof. Persisted identity keeps ordinary task paths unchanged; a credential/canary-bearing path uses a stable SHA256 key at launch and verified stop. Report filenames hash that key, and notification comparison applies the same mapping to the raw canonical author. The last own assistant final_answer supplies the
report; a later available task_complete must agree. The trusted SubagentStop itself supplies
completion when that later row has not been written yet. Child turn_context model/effort is recorded
separately from requested, parent and provider-resolved settings. This does not authenticate ordinary
owner replies or companion jobs. All process, dynamic-path and unseen-link limits above still apply.

A multi-line command, or one the reader cannot parse, that names a door program is refused
whatever its shape. The text of an unreadable `sh -c` body inside a readable command meets only
that door-word rule; the leak scan does not read it. A shell (`sh`, `bash`, `zsh`, `dash`) with no
readable `-c` body reads text the guards never see: input piped or fed to it (`| sh`, a
here-string, `-s`, `< file`), a script path, or a `-c` after an option they do not read
(`bash -o pipefail -c`, `+e -c`, `-O extglob -c`, `--rcfile f -c`, `bash --command`). Such a
command is refused when its text names a door program; the fed text still meets no leak or
infrastructure check.

When a guard raises on a call, the hook refuses the call if it could pass a door: an edit (the tools
in `guards.DOORS`, or a Codex `apply_patch`), any MCP tool, or a Bash command naming a door program
or a network program (`gh`, `curl`, `wget`, `nc`, `ssh`, `scp`, `http`, `https`, the names in
`guards.NETWORK` read as a program, not inside a URL), with its quotes and backslashes removed. Any other call fails open and the error is recorded.

The Bash guards read a `gh api` call the way gh's flag parser does: the method in every spelling
(`-X PUT`, `-XPUT`, `--method=put`, and POST when a field or `--input` is given; an empty attached
value such as `-X=` or `--jq=` is a value, as in gh), the endpoint without a scheme and host in any
case, a leading `/` or a query and with gh's `{owner}/{repo}` filled from the origin remote, and
the fields, reading `-F key=@file` and the `--input` file. A REST pull request create meets the
create door and a REST merge or auto-merge meets the merge door. A REST write to `merges`,
`git/refs/` or `contents/`, a repository delete, and a `gh api graphql` mutation that merges, opens
a pull request, moves a ref, commits to a branch or changes protection are refused. A `gh api graphql`
query WUWEI cannot read is refused: `--input -`, `-F query=@-`, a missing or empty file, or an
`--input` or `-F query=@` file outside one plain `gh` call; an `--input` file WUWEI reads has its
whole text, JSON escapes decoded, checked for those mutations. Any REST write on
`repositories/<id>/...` is refused with the `repos/<owner>/<repo>` spelling to use. `gh pr merge`
reads `--admin` and `--auto` the way pflag does: `--admin` with any true value is refused, the last
`--auto` wins, and `--auto` read as another flag's value (`-t --auto`) does not count. The GitHub MCP
tools `push_files`, `create_or_update_file` and `delete_file` are refused on the default branch or
with no branch. A draft pull request create passes before its gates (`--draft`, a JSON `draft: true`
from `-F`, or from an `--input` file read only when gh is the whole command, with no wrapper and
every word plain: letters, digits and `./=@:-`; the same plain-call rule now covers the graphql
`--input` file and the `-F query=@` file); the ready door holds the flip to ready and reviewer requests on a
draft until the gates pass at its head, reading the PR and `--repo` as gh's flag parser does. An
endpoint is read with percent-escapes decoded, empty and `.` segments dropped and a PR number from its
leading digits (`7abc`, ` 7`, `7.0` are PR 7, as GitHub reads them); a write through a
`..` segment is refused. Not read: a `GH_REPO` that fills gh's placeholders with another repository than the
origin remote, `--hostname`, and a gh alias.

The doors and what they leave to the code host are in section 6 of the
[design](docs/design.md); `bin/wuwei doctor` prints how strongly each door holds per repository.

## What a reviewer asks first

- Hooks: SessionStart, PreToolUse, PostToolUse, SubagentStop and Stop run `bin/wuwei hook`.
  PreToolUse answers with the harness's own deny or ask decision. They act only inside a
  `.wuwei/` workspace; elsewhere they return at once. A door that cannot read its evidence stays
  shut; every other hook fails open and records why.
- Runtime: Python 3.11+ standard library only, at most 3,800 lines.
- Integrity: a release ships `MANIFEST.sha256` signed with the key in `keys/`.
- Network: the plugin reads the code host through `gh` with the owner's credentials and makes no
  other network call. Telemetry is local traces only.
- Credentials: the plugin stores none, and traces redact secret shapes.

## How to report

Use GitHub private vulnerability reporting: open the repository's Security tab and choose
"Report a vulnerability". Do not open a public issue, pull request or discussion.

Include the WUWEI version, your OS and Python version, the guard or command, the exact tool
input, the expected and actual exit code, and whether the bypass needs a cooperating agent,
an injected instruction or neither.

## What to expect

You get an acknowledgement and an assessment against the scope above. A confirmed issue is
fixed in a release with a published advisory, and the advisory credits you if you want it.
The project has one maintainer, so there is no fixed response time.
