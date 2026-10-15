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

The doors and what they leave to the code host are in section 6 of the
[design](docs/design.md); `scripts/wuwei doctor` prints how strongly each door holds per repository.

## What a reviewer asks first

- Hooks: SessionStart, PreToolUse, PostToolUse, SubagentStop and Stop run `scripts/wuwei hook`.
  `scripts/wuwei` is a six-line POSIX shell launcher that runs the stdlib Python CLI in `cli/wuwei/`
  in isolated mode; the plugin ships no compiled code and downloads nothing at install.
  PreToolUse answers with the harness's own deny or ask decision. They act only inside a
  `.wuwei/` workspace; elsewhere SessionStart names the CLI for `init` and the others return at once. A door that cannot read its evidence stays
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
