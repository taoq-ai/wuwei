# Implementation Plan: Outcome metrics

## Technical context

Python 3.11+ stdlib core; pytest fixtures. Extend `cli/wuwei/metrics.py`, the existing command and `report.py`. Use the existing registry ports and merge journal. Add a transcript directory setting under metrics, defaulting to the Claude Code projects directory. Keep transcript content out of all output and persisted files.

## Constitution check

Runtime remains stdlib only. Missing external evidence is `unmeasured`. Each behavior gets a failing test first. No new command, dependency, or subprocess in core. Workspace baseline remains local and owner managed.

## Design

1. Read only configured transcript files, determine workspace membership from cwd, reject nonhuman turns, collect timestamps and merge intervals before calculating weekday distributions.
2. Derive complete-window defect counts from merge observations; use code host and tracker port data for rework and lead time where available.
3. Parse blank or populated baseline fields from workspace note, never repository data. Add fields to the empty template and display outcomes in report.
4. Keep adapter payloads behind registry and do not persist transcript or message content.

## Validation

Write focused tests in `tests/test_outcome_metrics.py` before implementation, run each red, then green. Run the prescribed full pytest command and inspect changed files for forbidden characters and local paths.
