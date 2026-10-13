# Data model

Seats retain running/stopped/unmeasured status. A ready/continue build can receive
a new completion from its recorded agent without a synthetic launch transition.
The result and usage remain one atomic write; replayed completion IDs do nothing.

A clean descendant HEAD plus completed-seat evidence can recover a missing result
to check. The result stays absent. Failed result capture appends seat.result_gap.

An approved same-repository rebind atomically replaces the item's worktree,
discards the old build record and returns it to implement. It compares the prior
item, build and seats under the writer lock. Reconcile creates a fresh build for
the selected tree and runs checks; old gates cannot advance it without new evidence.
