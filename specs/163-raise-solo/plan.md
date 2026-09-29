# Implementation Plan: Solo PR raise

## Technical Context

Python 3.11+ stdlib runtime, pytest tests, existing VCS and code host ports.

## Constitution Check

Use existing state, brief, gate, and adapter helpers. Test each behavior before code. No new runtime dependency or adapter layer.

## Design

Brief creation records the resolved worktree in item state. Raise reads that path and uses it for all local VCS evidence and gate matching. The shared reviewer ranker uses `shepherd.min_reviewers` for its acceptance threshold, including the lead. Raise checks the configured code host before touching VCS to give a clear exit 2. Add shepherd settings to the template and documentation.

## Verification

Run targeted tests after each red and green step, then the full pytest suite.
