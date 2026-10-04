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

The full threat model is in [docs/site/security.md](docs/site/security.md) and in section
9.1 of the [design spec](docs/specs/2026-09-24-wuwei-design.md).

## What a reviewer asks first

- Hooks: PreToolUse, PostToolUse, SessionStart, Stop, SubagentStop and PreCompact run
  `bin/wuwei hook`. They read the tool call, exit 0 to allow, 1 to refuse with a reason, 2
  when they could not measure. They act only inside a `.wuwei/` workspace; elsewhere they
  exit 0 at once.
- Runtime: Python 3.11+ standard library only. No package install, no third-party code at
  run time. pytest is a development dependency.
- Integrity: every release ships `MANIFEST.sha256` signed with an ED25519 key; the key
  fingerprint is pinned in [docs/site/integrity.md](docs/site/integrity.md) and `wuwei
  integrity` verifies the installed tree against it.
- Network: the plugin makes no network call of its own. Adapters call the services the
  owner configures (code host, tracker, docs, chat) with the owner's own tools and
  credentials; telemetry is off unless the owner turns it on and then sends an aggregate the
  owner has read, to an endpoint named in the config.
- Credentials: the plugin stores none. It reads tokens from the environment the owner
  provides to a command and never writes them to records, events, traces or logs; the trace
  redactor is tested against a corpus of secret shapes.

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
