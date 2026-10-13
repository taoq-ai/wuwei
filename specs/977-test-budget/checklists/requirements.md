# Requirements quality checklist

- [x] The CI regex threshold is measurable and stricter than the existing gate.
- [x] Distinct collected cases retain their exact inputs and assertions.
- [x] Per-file baseline comparisons expose accidental case loss.
- [x] Exact duplicate deletion requires a reviewable list.
- [x] Runtime edits, skips, and network access are excluded.
- [x] Verification names the required interpreter and explicit test files.
