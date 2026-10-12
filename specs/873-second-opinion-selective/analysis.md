# Analysis: 873-second-opinion-selective

CRITICAL 0, HIGH 0 open.

| ID | Severity | Summary | Resolution |
|---|---|---|---|
| A1 | HIGH | Computing the second opinion live inside `gate_set` would need the config at ten call sites (merge, derive, report, shepherd, rotate) and could let merge and dispatch disagree. | Resolved. One function decides; `dispatch next` and `dispatch opinion` write the release into the tier record, so every reader keeps one source and sees it. `next` reaches it because it resolves every gate offer through `dispatch next` (test through `launch_set`). |
| A2 | HIGH | Releasing could leave a running second-opinion seat or its recorded verdict inconsistent. | Resolved. The gate leaves the gate set only; a recorded passing verdict stays in `gate_verdicts` (the retro lists it) and a running seat finishes. `dispatch opinion` refuses after the release. |
| A3 | MEDIUM | Turning the second opinion on mid-round does not add it to tiered items. | Accepted and recorded: a gate added at delta would need an initial verdict that cannot exist; it applies at the next tiering. |
| A4 | HIGH | Review F1: release dropped a second opinion that had already returned FIX, so the item raised unfixed (also in fix and delta). | Resolved in fix round 1: a second opinion whose latest verdict blocks keeps its gate; T007 covers off and a narrowed selector. |
| A5 | LOW | The per-item `plan set <item> second_opinion=on|off` card is not built. | Deferred; the issue asks for the selector or the card. |
| A6 | LOW | The new event kind needs an attention tier. | `gate.released` is silent, like `gate.tiered`; `test_emitted_kinds_have_intended_tiers` lists it. |

Coverage: FR-001 and FR-002 T001-T002, FR-003 T003-T004, 100 percent.
