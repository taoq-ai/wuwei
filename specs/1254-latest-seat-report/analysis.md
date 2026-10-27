# Approved report selection reconsideration

The owner approved revised report selection after the first delta found invalid archived entries
could suppress a genuine pending final. The additional design round is explicitly authorized.

The selector now uses one reader for retention, delivery, and moved copies. A file must have the
writer's session/agent/known-role/positive-integer-version name, be a regular file, decode as UTF-8,
and contain nonblank text before establishing a watermark. Symlinks and other nonregular entries
provide no evidence of delivery. This adds no persistent store or new authentication protocol.

| Finding | Resolution |
| --- | --- |
| Archived directory, dangling link, or binary suppresses a real final | Shared validated reader runs before the watermark. |
| Pending invalid entries or blank reports | The same reader rejects them in both consumers. |
| Moved copy changes type or becomes unreadable | The fallback invokes the same validation. |
| Claim races | Pending-first enumeration and validated archive fallback remain; all six race regressions pass. |
| Legacy positive integer versions | Both consumers compare the validated suffix numerically. |

Forty-four invalid-entry cases initially produced 40 failures and 4 passes. FIFO reads use a
deterministic open guard so the regression fails without hanging. All 44 cases now pass, together
with the six closed race cases. The legacy numeric-ordering case failed before its fix and passes.
No open CRITICAL or HIGH finding remains in this analysis. Independent review is still required.
