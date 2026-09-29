# Implementation Plan: Goals, discovery and rank

## Technical context

Python 3.11 stdlib runtime; pytest for tests. Reuse workspace config, registry ports, plan lint and guard scope helpers.

## Constitution check

Use three-state exits, fail closed on malformed input, test before each change, and keep all external reads behind registry adapters. No new runtime dependency.

## Design

- Parse goal blocks in a small pure module with line-numbered errors.
- Rank a validated candidate list in a pure function; CLI reads JSON and workspace config.
- Extend plan proposal validation to call the shared score validator and goal parser.
- Discovery reads configured adapters and local day state, returns source measurements and deduplicated proposals. Wire it to morning proposal and sweep; expose a queue-threshold hook for seat release.
- Route intraday candidates through a pure autostart decision; #22 consumes the result.
- Protect goals with the existing state guard.

## Verification

Run focused red/green tests for each behavior and the full repository pytest command.
