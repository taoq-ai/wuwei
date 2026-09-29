# Implementation Plan: Shepherd PR Actions

## Technical context

Python 3.11 standard library at runtime; pytest with fake code host, VCS and checks ports. Extend `pr_actions`, `build`, and the existing ports and guards. No new configuration.

## Constitution check

Test first. All external commands remain in adapters. Producer-owned action state is reserved. Exit 2 carries reasons. Keep the worktree diff small.

## Design

`pr act` reads the current PR episode and its item. It emits one structured next action. Conflict steps use the VCS and checks adapters; completion verifies the new head and records the producer-owned action outcome. CI and review fixes supply measured feedback to `build next`. Replies use the outward tier; unsafe text becomes a draft. Scope changes use the decision writer.

## Verification

Run focused tests after each red-green change, then the full pytest suite.
