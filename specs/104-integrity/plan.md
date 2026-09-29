# Implementation plan: 104 integrity

## Technical Context
Python 3.11 stdlib runtime, pytest development tests. Reuse registry.Result,
workspace scope and atomic writer, state allowlists, protect_state, promotion,
SessionStart lifecycle, watch and obligations sweeps, and the git adapter.

## Constitution Check
Test before implementation. No subprocess imports in core. All measurements use
0/1/2 results. SessionStart is the documented exit-0 exception. No dependencies,
network tests, commits to this checkout, or speculative configuration.

## Design
- Add a fixed SSH signature adapter for sign and verify. No shell commands or
  caller-selected namespace/principal. Register the port and unavailable adapter.
- Add integrity core for canonical inventory creation, strict relative-path
  validation, pinned-key verification, content hashing and protected cached verdict.
  A host-terminal confirmation records the exact measured inventory fingerprint.
- Add integrity CLI check/reconfirm and SessionStart/PreToolUse integration.
  A dedicated guard covers every PreToolUse invocation using one cached read.
- Extend the vcs port with workspace initialization, selected-path promotion commit,
  and history evidence. Track charters, memory, goals and voice only. Never commit
  an unrelated staged change. Git commands disable hooks and ambient signing.
- CI stages shipped directories, builds inventory, signs via adapter and uploads a
  signed archive. Documentation names the owner placeholder and secret.

## Validation
Fake adapters and subprocess stubs cover errors and command allowlists. One real
SSH smoke test generates temporary keys and rejects a different signer. One real
git boundary smoke verifies init, promotion and trailer-less detection. Remaining
workspace/hook tests use fakes. Run the specified interpreter's full pytest suite.

## Risks
A same-uid process can forge local evidence or modify the verifier. Missing signing
setup intentionally leaves source checkouts untrusted. Cache freshness is bounded
by SessionStart and sweeps, not each tool call. History scanning grows with history;
optimize only if measured session latency requires it.
