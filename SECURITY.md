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
wrapper's options. Known shapes they do not read on one line, reported and not yet fixed:

- `eval`, input piped or fed to a shell (`| sh`, a here-string), and a variable as the program name.
- `$(...)` inside double quotes, process substitution (`<(...)`), and ANSI-C quoting (`$'...'`).
- A separator glued to a redirect or a pipe (`>;`, `|&`), and quote splicing inside a word.
- A function body (`f() { ...; }`, `function f { ...; }`), `coproc`, `builtin command`, and
  unquoted backticks.
- A shell option before `-c` that takes an argument or is not a single-dash cluster
  (`bash -o pipefail -c`, `+e -c`, `-O extglob -c`, `--rcfile f -c`).
- A wrapper not in the guards' list (`setsid`, `flock`, `ionice`), and a wrapper option whose value
  names a program a door reads (`sudo -u gh gh pr merge 5`, `env -C /x/git git push`).

A multi-line command, or one the reader cannot parse, that names a door program is refused
whatever its shape. The text of an unreadable `sh -c` body inside a readable command meets only
that door-word rule; the leak scan does not read it.

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
a pull request, moves a ref, commits to a branch or changes protection are refused. The GitHub MCP
tools `push_files`, `create_or_update_file` and `delete_file` are refused on the default branch or
with no branch. A draft pull request create passes before its gates (`--draft`, a JSON `draft: true`
from `-F` or from an `--input` file read only when the gh call runs alone); the ready door holds the
flip to ready and reviewer requests on a draft until the gates pass at its head, reading the PR and
`--repo` as gh's flag parser does and the endpoint with repeated slashes collapsed and
percent-escapes decoded. Not read: a `GH_REPO` that fills gh's placeholders with another repository than the
origin remote, `--hostname`, and a gh alias.

The doors and what they leave to the code host are in section 6 of the
[design](docs/design.md); `bin/wuwei doctor` prints how strongly each door holds per repository.

## What a reviewer asks first

- Hooks: SessionStart, PreToolUse, PostToolUse, SubagentStop and Stop run `bin/wuwei hook`.
  PreToolUse answers with the harness's own deny or ask decision. They act only inside a
  `.wuwei/` workspace; elsewhere they return at once. A door that cannot read its evidence stays
  shut; every other hook fails open and records why.
- Runtime: Python 3.11+ standard library only, at most 3,000 lines.
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
