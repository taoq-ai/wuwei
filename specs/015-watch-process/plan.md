# Implementation plan

## Technical context
Python 3.11 stdlib runtime, pytest tests, synchronous JSON state and JSONL events.
Use `watch.py` for one-cycle operations and the loop, a thin CLI command and one
lifecycle guard module. Poll the raised and claimed day PRs through existing
code_host reads. Reuse obligations evaluation via a result-returning helper so the
watch emits one combined summary. Use existing state locking and atomic writes.

## Constitution check
Ports only; no subprocess in core. Dedicated reserved namespace and events.
All behavior has tests first. No extra dependencies or shell parsing. No commits.

## Implementation sequence
1. Day PR selection and isolated snapshot failures using fake ports.
2. Split obligations calculation from recording with unchanged standalone behavior.
3. Watch health, clocks, worktree activity, staleness, scanner and sweep aggregation.
4. Persist PR snapshots and accumulated wake marker with reserved Stop acknowledgement; continuous scheduler, retries,
   singleton lock, graceful shutdown and date rollover.
5. Scoped session and compaction checks; templates and operating contract.

## Validation
Use in-process fake ports and controllable time. Test exits, exact event counts,
read-failure preservation, restart, ownership changes and field edits. Run the
requested Python interpreter against the complete suite and inspect diff hygiene.
