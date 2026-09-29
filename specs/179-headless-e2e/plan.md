# Implementation Plan: Real Claude Code headless day

## Technical Context

Python 3.11 standard library runner under scripts, with subprocesses confined to
its adapter. Existing release builder, CLI producers, hooks and skills remain the
implementation under test. No new runtime dependency or workspace config key.

## Design

1. Copy the release inputs to scratch, replace only the signing public key, and
   invoke scripts/build-release.py with the corresponding throwaway private key.
2. Stage the resulting plugin under a temporary HOME; initialize a workspace and
   clone the local repository as a disposable demo, removing its origin remote.
3. Supply a proposal and explicit fixture owner approval. Drive the plan skill,
   builder step loop and three gate seats through one bounded Claude session.
4. Observe the unmodified plugin executable through a temporary python3 PATH shim.
   It preserves hook stdin, stdout, stderr and exit and appends hook telemetry to
   a separate fixture log. This log is test evidence, never production trust state.
5. Require producer events, completed build state, stopped seats, gate receipts,
   skill traces, a refused launch probe and blocked/allowed Stop hook exits.
6. Skip without a key unless the owner explicitly requests local-login mode.
   Classify expired OAuth, unavailable executables, invalid results and timeouts
   as exit 2 with a reason; measured missing lifecycle evidence is exit 1.

## Constitution Check

Stdlib-only; test-first offline pytest; reuse producer APIs; no core subprocess,
new trusted state, outward sends or production policy changes. Scratch telemetry
is not an authorization proof. No shell command rewrites to bypass guards.

## Files

- scripts/headless_e2e.py: fixture, prompt, evidence validation, CLI.
- scripts/headless_adapter.py: bounded external calls and transparent hook observer.
- tests/test_headless_e2e.py: offline contracts, mutation and boundary checks.
- .github/workflows/tests.yml: gated paid job matching skill-evals.
- docs/headless-e2e.md: local command, bounds, evidence and limitations.

## Validation

Run new tests red before each implementation, then the full requested pytest
suite. Run the no-key command and, where credentials permit, the local-login
command. A failed auth run is explicitly unmeasured, never a claimed live pass.
