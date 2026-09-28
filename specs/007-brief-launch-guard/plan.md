# Implementation plan

Python 3.11 stdlib core, existing pytest suite and in-process port fakes. Reuse the
workspace clock, atomic writer, locked state writer, registry and Guard discovery.
No new dependencies, no external commands in core, no changes outside this feature.

## Design

A brief module owns evidence gathering and the ordered source refusals. The command
only parses arguments and stdin. The Agent guard resolves the logged brief from the
prompt, verifies its digest and role, then checks phase, live builders, tree, CAP and
free memory. Gate checks are shared with brief creation. No shell matching is needed.
Workspace scope and role relevance precede parsing. Capacity and reuse checks share
one locked state update with the running reservation. Stop hooks correlate runtime ids
through the brief marker and its day in the agent transcript. Missing or unmatched
transcripts log an event without blocking the stop. Reserve seats using state.RESERVED;
launch and stop use the dedicated writer path. Owner stand-down is a follow-up.

Add vcs branches and host free_memory operations. Reservations provide liveness.
Stale reservations still count toward capacity and are named in refusals, but do not
independently block other items. Default stale timeout is four hours.
Host reads MemAvailable on Linux and free, inactive and speculative vm_stat pages on macOS.
Tests use fakes and recorded output. Config carries protected path regexes and branch
patterns; repo default branch determines merge-base with a configurable remote.

## Constitution check

Pass: stdlib, three-state exits, shared writer, tests before implementation, port-only
external access, smallest extensions, no engagement-specific defaults. Test first in
three increments: source brief refusals/header, adapter extensions, launch checks.

## Validation

Run each new test group red, implement, run green. Run the full suite with the supplied
interpreter. Inspect changed files for machine paths, forbidden punctuation and scope.
