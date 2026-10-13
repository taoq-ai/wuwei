# Research

## Decision

Change the shared blocked parser and card reason in `dispatch.py`.

## Rationale

`_blocked` selects the latest recorded Blocked field for both build and dispatch. `_blocked_card` creates the owner card used by both paths. The exact answer matcher remains unchanged.

## Alternatives considered

Changing only `build next` would leave dispatch with the same false escalation. Relaxing owner answer matching would accept reworded cards and weaken the established exact-card rule.
