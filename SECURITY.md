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
- A function body (`f() { ...; }`), a shell option that takes an argument before `-c`
  (`bash -o pipefail -c ...`), and a wrapper not in the guards' list (`setsid`, `flock`, `ionice`).

A multi-line command, or one the reader cannot parse, that names a door program is refused
whatever its shape.

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
