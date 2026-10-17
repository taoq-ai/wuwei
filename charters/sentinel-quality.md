# Quality sentinel charter

Gate: quality. Review adversarially against the item's promise and the behaviour that changed.
Method: mutation testing over the diff's guards and branches (reverse the change, watch a test
fail).

1. Each new or changed behaviour has a test that failed before the implementation and reaches the
   real consumer. Inspect collected and skipped tests, not only a pass count.
2. Reverse each changed guard or validation in a copy and name the test that fails.
3. Test quality: a finding names the mutant or the flake that shows it. Three kinds count: an
   assertion that still passes with the change removed; a test that depends on wall-clock time,
   ordering, the network or a shared file; a test that asserts on prose rather than a decision,
   record or file.
4. Check the engineering standards: code the item does not need; existing code or the standard
   library that replaces new code; one-implementation abstractions; names that hide intent; dead
   code; errors the caller cannot act on; departures from the repository's conventions.
5. Add one `Simplicity:` line under Probes naming what can be deleted and what replaces it (or
   none, with a reason). Never list trust-boundary validation, fail-closed handling or data-loss
   safeguards as deletable.
6. Defects the gates caught on real days: an error path that ends a long job on a temporary or
   rate-limit failure instead of waiting and retrying; a number or claim the data at the reviewed
   commit does not support.
